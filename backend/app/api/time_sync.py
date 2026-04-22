"""Time Sync API — audit clock + NTP state across infrastructure.

Endpoints:
  GET  /api/v1/time-sync/status       — operator+  summary + per-target detail
  POST /api/v1/time-sync/fix          — admin     fix specific targets
  POST /api/v1/time-sync/fix-all      — admin     fix every drifting/off target
  GET  /api/v1/time-sync/settings     — admin     read NTP server + threshold
  PUT  /api/v1/time-sync/settings     — admin     write NTP server + threshold
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_admin, require_operator
from app.core.database import get_db
from app.models import User
from app.services import time_sync as time_sync_service
from app.services.time_sync import (
    DEFAULT_DRIFT_THRESHOLD_SECONDS,
    DEFAULT_NTP_SERVER,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── simple in-memory 30-second cache keyed by request ───────────────────────

_CACHE_TTL_SECONDS = 30
_cache_lock = threading.Lock()
_cache_payload: Optional[Dict[str, Any]] = None
_cache_expires_at: float = 0.0


def _cached_status(db: Session, force: bool = False) -> Dict[str, Any]:
    global _cache_payload, _cache_expires_at
    now = time.time()
    with _cache_lock:
        if not force and _cache_payload is not None and now < _cache_expires_at:
            return _cache_payload

    # Build outside the lock (slow probe) then swap in
    targets = time_sync_service.collect_all(db)
    target_dicts = [t.to_dict() for t in targets]

    # Drift threshold from settings
    try:
        threshold = int(time_sync_service.get_setting(
            db, "time_sync.drift_threshold_seconds",
            str(DEFAULT_DRIFT_THRESHOLD_SECONDS),
        ))
    except (TypeError, ValueError):
        threshold = DEFAULT_DRIFT_THRESHOLD_SECONDS

    summary = {
        "total": len(target_dicts),
        "ok": 0,
        "drifting": 0,
        "unreachable": 0,
        "ntp_enabled_count": 0,
        "ntp_disabled_count": 0,
        "ntp_unknown_count": 0,
    }
    for t in target_dicts:
        if t.get("error") and t.get("reported_time_utc") is None:
            summary["unreachable"] += 1
            continue
        drift = t.get("drift_seconds")
        if drift is not None and abs(drift) > threshold:
            summary["drifting"] += 1
        elif drift is not None:
            summary["ok"] += 1
        ntp = t.get("ntp_enabled")
        if ntp is True:
            summary["ntp_enabled_count"] += 1
        elif ntp is False:
            summary["ntp_disabled_count"] += 1
        else:
            summary["ntp_unknown_count"] += 1

    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "drift_threshold_seconds": threshold,
        "targets": target_dicts,
        "summary": summary,
    }
    with _cache_lock:
        _cache_payload = payload
        _cache_expires_at = time.time() + _CACHE_TTL_SECONDS
    return payload


def _invalidate_cache() -> None:
    global _cache_payload, _cache_expires_at
    with _cache_lock:
        _cache_payload = None
        _cache_expires_at = 0.0


# ── pydantic models ─────────────────────────────────────────────────────────

class TargetRef(BaseModel):
    kind: str
    id: int


class FixRequest(BaseModel):
    targets: List[TargetRef] = Field(default_factory=list)
    ntp_server: Optional[str] = None


class FixAllRequest(BaseModel):
    ntp_server: Optional[str] = None
    max_drift_seconds: Optional[int] = None


class SettingsResponse(BaseModel):
    ntp_server: str
    drift_threshold_seconds: int


class SettingsUpdate(BaseModel):
    ntp_server: Optional[str] = None
    drift_threshold_seconds: Optional[int] = None


# ── endpoints ────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status(
    refresh: bool = False,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Probe every configured target for clock + NTP state. Cached 30s."""
    try:
        return _cached_status(db, force=refresh)
    except Exception as e:
        logger.exception("time-sync status failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Probe error: {e}")


@router.post("/fix")
async def fix_targets(
    req: FixRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Apply NTP remediation to each requested target."""
    if not req.targets:
        raise HTTPException(status_code=400, detail="No targets specified")

    ntp = (req.ntp_server or time_sync_service.get_setting(
        db, "time_sync.ntp_server", DEFAULT_NTP_SERVER,
    )).strip() or DEFAULT_NTP_SERVER

    results = []
    for t in req.targets:
        res = time_sync_service.fix_target(db, t.kind, t.id, ntp_server=ntp)
        results.append(res)

    _invalidate_cache()
    ok_count = sum(1 for r in results if r.get("status") == "ok")
    return {
        "status": "ok" if ok_count == len(results) else "partial" if ok_count else "error",
        "ntp_server": ntp,
        "results": results,
    }


@router.post("/fix-all")
async def fix_all(
    req: FixAllRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Fix every target whose drift exceeds threshold or whose NTP is disabled."""
    ntp = (req.ntp_server or time_sync_service.get_setting(
        db, "time_sync.ntp_server", DEFAULT_NTP_SERVER,
    )).strip() or DEFAULT_NTP_SERVER

    threshold = req.max_drift_seconds
    if threshold is None:
        try:
            threshold = int(time_sync_service.get_setting(
                db, "time_sync.drift_threshold_seconds",
                str(DEFAULT_DRIFT_THRESHOLD_SECONDS),
            ))
        except (TypeError, ValueError):
            threshold = DEFAULT_DRIFT_THRESHOLD_SECONDS

    status = _cached_status(db, force=True)
    to_fix: List[Dict[str, Any]] = []
    for t in status["targets"]:
        drift = t.get("drift_seconds")
        needs = False
        if drift is not None and abs(drift) > threshold:
            needs = True
        if t.get("ntp_enabled") is False:
            needs = True
        if needs:
            to_fix.append({"kind": t["kind"], "id": t["id"], "label": t["label"]})

    results = []
    for tgt in to_fix:
        res = time_sync_service.fix_target(db, tgt["kind"], tgt["id"], ntp_server=ntp)
        res["label"] = tgt["label"]
        results.append(res)

    _invalidate_cache()
    ok_count = sum(1 for r in results if r.get("status") == "ok")
    return {
        "status": "ok" if ok_count == len(results) and results else "partial" if ok_count else ("noop" if not results else "error"),
        "ntp_server": ntp,
        "drift_threshold_seconds": threshold,
        "considered": len(status["targets"]),
        "attempted": len(results),
        "succeeded": ok_count,
        "results": results,
    }


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Read default NTP server + drift threshold."""
    ntp = time_sync_service.get_setting(db, "time_sync.ntp_server", DEFAULT_NTP_SERVER)
    try:
        thresh = int(time_sync_service.get_setting(
            db, "time_sync.drift_threshold_seconds",
            str(DEFAULT_DRIFT_THRESHOLD_SECONDS),
        ))
    except (TypeError, ValueError):
        thresh = DEFAULT_DRIFT_THRESHOLD_SECONDS
    return SettingsResponse(ntp_server=ntp, drift_threshold_seconds=thresh)


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    data: SettingsUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update default NTP server + drift threshold."""
    if data.ntp_server is not None:
        val = (data.ntp_server or "").strip()
        if not val:
            raise HTTPException(status_code=400, detail="ntp_server cannot be empty")
        time_sync_service.set_setting(
            db, "time_sync.ntp_server", val,
            "Default NTP server used by the Time Sync fix actions",
        )
    if data.drift_threshold_seconds is not None:
        if data.drift_threshold_seconds < 1:
            raise HTTPException(status_code=400, detail="drift_threshold_seconds must be >= 1")
        time_sync_service.set_setting(
            db, "time_sync.drift_threshold_seconds", str(int(data.drift_threshold_seconds)),
            "Drift (seconds) above which a target is considered out-of-sync",
        )
    _invalidate_cache()
    return await get_settings(current_user, db)  # type: ignore
