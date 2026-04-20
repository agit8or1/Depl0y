"""Consolidated system-updates API.

Exposes a single Updates dashboard view covering both PVE nodes and PBS
servers. Most heavy lifting (PVE apt endpoints, PBS apt endpoints) lives
in the existing node.py and pbs_mgmt.py routers — this module adds:

  * /api/v1/updates-mgmt/overview            — combined list of all PVE
    nodes + PBS servers with pending-update counts.

  * /api/v1/updates-mgmt/pve/{host_id}/{node}/...  — spec-path wrappers
    that proxy to the underlying pve.nodes(node).apt.* endpoints and add
    auditing + a basic per-node rate limit on apply.

  * /api/v1/updates-mgmt/pbs/{server_id}/...       — spec-path wrappers
    that proxy to the PBS apt endpoints for the consolidated view.

All destructive applies are admin-only, rate-limited, and audited.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_admin, require_operator
from app.core.database import get_db
from app.models import ProxmoxHost, PBSServer, User
from app.models.database import AuditLog
from app.services.proxmox import ProxmoxService
from app.services.pbs import PBSService
from app.services.task_tracker import task_tracker

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_host(db: Session, host_id: int) -> ProxmoxHost:
    host = db.query(ProxmoxHost).filter(
        ProxmoxHost.id == host_id, ProxmoxHost.is_active == True
    ).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")
    return host


def _get_pbs_server(db: Session, server_id: int) -> PBSServer:
    s = db.query(PBSServer).filter(PBSServer.id == server_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="PBS server not found")
    if not s.is_active:
        raise HTTPException(status_code=400, detail="PBS server is not active")
    return s


def _pve(host: ProxmoxHost):
    return ProxmoxService(host).proxmox


def _pbs_service(server: PBSServer) -> PBSService:
    if not server.api_token_id or not server.api_token_secret:
        raise HTTPException(status_code=400, detail="PBS server has no API token configured")
    return PBSService(server)


# In-process rate limiter — {key: last_epoch}
_rate_limit_state: Dict[str, float] = {}


def _rate_limit_ok(key: str, seconds: int = 300) -> bool:
    now = time.time()
    last = _rate_limit_state.get(key, 0.0)
    if now - last < seconds:
        return False
    _rate_limit_state[key] = now
    return True


def _audit(db: Session, user: Optional[User], action: str, resource_type: str,
           resource_id: Optional[int], path: str, details: Dict[str, Any],
           status_code: int = 200, success: bool = True) -> None:
    try:
        entry = AuditLog(
            user_id=getattr(user, "id", None) if user else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            http_method="POST",
            request_path=path,
            response_status=status_code,
            success=success,
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        logger.debug("audit log insert failed (non-fatal): %s", exc)
        db.rollback()


# ---------------------------------------------------------------------------
# Combined overview — all PVE nodes + all PBS servers
# ---------------------------------------------------------------------------

@router.get("/overview")
def updates_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return a combined list of PVE nodes and PBS servers with pending-update counts.

    Sub-requests run in parallel. If any single host/server fails, it is
    reported with an 'error' field but the response still returns 200.
    """
    hosts: List[ProxmoxHost] = (
        db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).order_by(ProxmoxHost.name).all()
    )
    pbs_servers: List[PBSServer] = (
        db.query(PBSServer).filter(PBSServer.is_active == True).order_by(PBSServer.name).all()
    )

    # ── PVE: enumerate nodes for each host ──────────────────────────────────
    # Build a list of (host, node_name) pairs.
    pve_targets: List[Dict[str, Any]] = []
    for h in hosts:
        try:
            node_list = _pve(h).nodes.get() or []
            for n in node_list:
                pve_targets.append({
                    "host_id": h.id,
                    "host_name": h.name,
                    "node": n.get("node") or n.get("name") or "",
                })
        except Exception as exc:
            pve_targets.append({
                "host_id": h.id,
                "host_name": h.name,
                "node": "",
                "error": str(exc),
            })

    def _pve_one(target):
        if target.get("error"):
            return {
                "role": "PVE",
                "host_id": target["host_id"],
                "host_name": target["host_name"],
                "node": target["node"],
                "count": 0,
                "updates": [],
                "last_checked": None,
                "error": target["error"],
            }
        h = next((x for x in hosts if x.id == target["host_id"]), None)
        if h is None:
            return None
        try:
            updates = _pve(h).nodes(target["node"]).apt.update.get() or []
            return {
                "role": "PVE",
                "host_id": h.id,
                "host_name": h.name,
                "node": target["node"],
                "count": len(updates),
                "updates": updates,
                "last_checked": int(time.time()),
            }
        except Exception as exc:
            return {
                "role": "PVE",
                "host_id": h.id,
                "host_name": h.name,
                "node": target["node"],
                "count": 0,
                "updates": [],
                "last_checked": None,
                "error": str(exc),
            }

    def _pbs_one(s: PBSServer):
        try:
            svc = _pbs_service(s)
            updates = svc.apt_list_updates()
            return {
                "role": "PBS",
                "server_id": s.id,
                "host_name": s.name,
                "node": s.hostname,
                "count": len(updates),
                "updates": updates,
                "last_checked": int(time.time()),
            }
        except HTTPException as exc:
            return {
                "role": "PBS",
                "server_id": s.id,
                "host_name": s.name,
                "node": s.hostname,
                "count": 0,
                "updates": [],
                "last_checked": None,
                "error": exc.detail,
            }
        except Exception as exc:
            return {
                "role": "PBS",
                "server_id": s.id,
                "host_name": s.name,
                "node": s.hostname,
                "count": 0,
                "updates": [],
                "last_checked": None,
                "error": str(exc),
            }

    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for r in pool.map(_pve_one, pve_targets):
            if r is not None:
                results.append(r)
        for r in pool.map(_pbs_one, pbs_servers):
            if r is not None:
                results.append(r)

    return {"items": results, "fetched_at": int(time.time())}


# ---------------------------------------------------------------------------
# PVE per-node update endpoints (spec paths)
# ---------------------------------------------------------------------------

@router.get("/pve/{host_id}/{node}")
def pve_list_updates(
    host_id: int,
    node: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List pending updates for a PVE node."""
    host = _get_host(db, host_id)
    try:
        updates = _pve(host).nodes(node).apt.update.get() or []
        return {
            "host_id": host_id,
            "node": node,
            "count": len(updates),
            "updates": updates,
            "last_checked": int(time.time()),
        }
    except Exception as exc:
        logger.error("pve_list_updates(%s, %s) failed: %s", host_id, node, exc)
        return {
            "host_id": host_id,
            "node": node,
            "count": 0,
            "updates": [],
            "error": str(exc),
        }


@router.post("/pve/{host_id}/{node}/refresh")
def pve_refresh_updates(
    host_id: int,
    node: str,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Refresh package index on a PVE node (apt-get update). Returns UPID."""
    host = _get_host(db, host_id)
    try:
        upid = _pve(host).nodes(node).apt.update.post()
    except Exception as exc:
        logger.error("pve_refresh_updates(%s, %s) failed: %s", host_id, node, exc)
        raise HTTPException(status_code=502, detail=str(exc))
    try:
        task_tracker.register(
            upid, host_id, node,
            f"APT refresh packages on {node}",
            user_id=getattr(current_user, "id", None),
            task_type="aptupdate",
        )
    except Exception as exc:
        logger.debug("task_tracker register failed (non-fatal): %s", exc)
    return {"upid": upid, "host_id": host_id, "node": node}


@router.post("/pve/{host_id}/{node}/apply")
def pve_apply_updates(
    host_id: int,
    node: str,
    payload: Optional[Dict[str, Any]] = Body(default=None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Apply pending updates on a PVE node (apt-get dist-upgrade). Admin-only."""
    host = _get_host(db, host_id)
    if not _rate_limit_ok(f"pve-apply:{host_id}:{node}", seconds=300):
        raise HTTPException(
            status_code=429,
            detail="An apply for this node ran recently — wait a few minutes before retrying.",
        )

    packages: Optional[List[str]] = None
    if payload and isinstance(payload, dict):
        raw = payload.get("packages")
        if isinstance(raw, list) and raw:
            packages = [str(p) for p in raw]

    try:
        kwargs: Dict[str, Any] = {}
        if packages:
            kwargs["packages"] = " ".join(packages)
        upid = _pve(host).nodes(node).apt.upgrade.post(**kwargs)
    except Exception as exc:
        logger.error("pve_apply_updates(%s, %s) failed: %s", host_id, node, exc)
        raise HTTPException(status_code=502, detail=str(exc))

    _audit(
        db, current_user, "apt_upgrade", "node", host_id,
        f"/api/v1/updates-mgmt/pve/{host_id}/{node}/apply",
        {
            "host_name": host.name,
            "node": node,
            "packages": packages or "all",
            "upid": upid,
        },
    )
    try:
        desc = (
            f"APT upgrade {len(packages)} package(s) on {node}"
            if packages else f"APT upgrade all packages on {node}"
        )
        task_tracker.register(
            upid, host_id, node, desc,
            user_id=getattr(current_user, "id", None),
            task_type="aptupgrade",
        )
    except Exception as exc:
        logger.debug("task_tracker register failed for pve apply (non-fatal): %s", exc)

    return {"upid": upid, "host_id": host_id, "node": node, "packages": packages}


# ---------------------------------------------------------------------------
# PBS per-server update endpoints (spec paths — thin wrappers around
# /pbs-mgmt/{server_id}/updates/*)
# ---------------------------------------------------------------------------

@router.get("/pbs/{server_id}")
def pbs_list_updates(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List pending updates for a PBS server's host."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _pbs_service(server)
        updates = svc.apt_list_updates()
        return {
            "server_id": server_id,
            "name": server.name,
            "count": len(updates),
            "updates": updates,
            "last_checked": int(time.time()),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("pbs_list_updates(%s) failed: %s", server_id, exc)
        return {
            "server_id": server_id,
            "name": server.name,
            "count": 0,
            "updates": [],
            "error": str(exc),
        }


@router.post("/pbs/{server_id}/refresh")
def pbs_refresh_updates(
    server_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Refresh package index on a PBS server. Returns UPID."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _pbs_service(server)
        upid = svc.apt_refresh_updates()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("pbs_refresh_updates(%s) failed: %s", server_id, exc)
        raise HTTPException(status_code=502, detail=str(exc))

    try:
        task_tracker.register(
            upid,
            host_id=-server_id,
            node=f"pbs:{server.name}",
            description=f"PBS apt update on {server.name}",
            user_id=getattr(current_user, "id", None),
            task_type="aptupdate",
        )
    except Exception as exc:
        logger.debug("task_tracker register failed (non-fatal): %s", exc)

    return {"upid": upid, "server_id": server_id}


@router.post("/pbs/{server_id}/apply")
def pbs_apply_updates(
    server_id: int,
    payload: Optional[Dict[str, Any]] = Body(default=None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Apply pending package updates on a PBS server. Admin-only."""
    server = _get_pbs_server(db, server_id)
    if not _rate_limit_ok(f"pbs-apply:{server_id}", seconds=300):
        raise HTTPException(
            status_code=429,
            detail="An apply for this PBS server ran recently — wait a few minutes before retrying.",
        )
    packages: Optional[List[str]] = None
    if payload and isinstance(payload, dict):
        raw = payload.get("packages")
        if isinstance(raw, list) and raw:
            packages = [str(p) for p in raw]

    try:
        svc = _pbs_service(server)
        upid = svc.apt_upgrade(packages=packages)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("pbs_apply_updates(%s) failed: %s", server_id, exc)
        raise HTTPException(status_code=502, detail=str(exc))

    _audit(
        db, current_user, "apt_upgrade", "pbs", server_id,
        f"/api/v1/updates-mgmt/pbs/{server_id}/apply",
        {
            "server_name": server.name,
            "packages": packages or "all",
            "upid": upid,
        },
    )
    try:
        desc = (
            f"PBS apt upgrade {len(packages)} package(s) on {server.name}"
            if packages else f"PBS apt upgrade all packages on {server.name}"
        )
        task_tracker.register(
            upid, host_id=-server_id, node=f"pbs:{server.name}",
            description=desc,
            user_id=getattr(current_user, "id", None),
            task_type="aptupgrade",
        )
    except Exception as exc:
        logger.debug("task_tracker register failed (non-fatal): %s", exc)

    return {"upid": upid, "server_id": server_id, "packages": packages}


@router.get("/pbs/{server_id}/task/{upid}")
def pbs_task_status(
    server_id: int,
    upid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Poll a PBS task status (used to wait for a refresh to finish)."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _pbs_service(server)
        return svc.get_task_status(upid)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")


@router.get("/pve/{host_id}/{node}/task/{upid}")
def pve_task_status(
    host_id: int,
    node: str,
    upid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Poll a PVE task status."""
    host = _get_host(db, host_id)
    try:
        result = _pve(host).nodes(node).tasks(upid).status.get()
        return result or {}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
