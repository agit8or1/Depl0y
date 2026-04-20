"""AI Reports API router."""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_admin, require_operator
from app.core.database import get_db
from app.core.security import encrypt_data
from app.models.database import (
    AIProviderSettings,
    AuditLog,
    NodePowerProfile,
    PowerCostSettings,
    ProxmoxNode,
    ReportRun,
    ReportSchedule,
    User,
)
from app.services.ai_reports import ai_provider, report_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Rate limiting for report generation (5/min per user) ─────────────────────
_RATE: Dict[int, List[float]] = defaultdict(list)
_RATE_WINDOW = 60.0
_RATE_MAX = 5


def _rate_ok(user_id: int) -> bool:
    now = time.time()
    q = _RATE[user_id]
    # prune
    while q and now - q[0] > _RATE_WINDOW:
        q.pop(0)
    if len(q) >= _RATE_MAX:
        return False
    q.append(now)
    return True


def _audit(db: Session, user_id: Optional[int], action: str, resource_id: Optional[int], details: Dict[str, Any]):
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type="ai_report",
            resource_id=resource_id,
            details=details,
            success=True,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()


# ── Schemas ─────────────────────────────────────────────────────────────────

class SettingsResponse(BaseModel):
    provider: str
    model: str
    enabled: bool
    has_key: bool
    last_test_at: Optional[datetime] = None
    last_test_ok: Optional[bool] = None


class SettingsUpdate(BaseModel):
    provider: Optional[str] = Field(default="openai")
    api_key: Optional[str] = None
    model: Optional[str] = None
    enabled: Optional[bool] = None


class PowerSettingsResponse(BaseModel):
    electricity_rate_per_kwh: float
    currency: str
    node_profiles: List[Dict[str, Any]]


class PowerSettingsUpdate(BaseModel):
    electricity_rate_per_kwh: Optional[float] = None
    currency: Optional[str] = None
    node_profiles: Optional[List[Dict[str, Any]]] = None  # [{node_id: int|null, idle_watts, load_watts}]


class ReportCreateRequest(BaseModel):
    report_type: str
    scope_type: str = "global"
    scope_ref: Optional[str] = None
    custom_prompt: Optional[str] = None
    title: Optional[str] = None


class ReportSummary(BaseModel):
    id: int
    title: str
    report_type: str
    scope_type: str
    scope_ref: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    model_used: Optional[str]

    class Config:
        from_attributes = True


class ReportDetail(ReportSummary):
    findings: Optional[List[Dict[str, Any]]] = None
    ai_narrative: Optional[Dict[str, Any]] = None
    rendered_markdown: Optional[str] = None
    rendered_html: Optional[str] = None
    assumptions: Optional[List[str]] = None
    data_freshness_seconds: Optional[int] = None
    error_message: Optional[str] = None
    manual_notes: Optional[str] = None
    token_usage: Optional[Dict[str, Any]] = None


class NotesUpdate(BaseModel):
    manual_notes: str


class ScheduleCreate(BaseModel):
    name: str
    report_type: str
    scope_type: str = "global"
    scope_ref: Optional[str] = None
    cadence: str = "weekly"
    cron_expr: Optional[str] = None
    enabled: bool = True
    include_executive_summary: bool = True
    include_raw_appendix: bool = True


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    report_type: Optional[str] = None
    scope_type: Optional[str] = None
    scope_ref: Optional[str] = None
    cadence: Optional[str] = None
    cron_expr: Optional[str] = None
    enabled: Optional[bool] = None
    include_executive_summary: Optional[bool] = None
    include_raw_appendix: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: int
    name: str
    report_type: str
    scope_type: str
    scope_ref: Optional[str]
    cadence: str
    cron_expr: Optional[str]
    enabled: bool
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    include_executive_summary: bool
    include_raw_appendix: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_or_create_openai_settings(db: Session) -> AIProviderSettings:
    row = db.query(AIProviderSettings).filter(AIProviderSettings.provider == "openai").first()
    if row:
        return row
    row = AIProviderSettings(provider="openai", model="gpt-4o-mini", enabled=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _run_to_detail(run: ReportRun) -> ReportDetail:
    return ReportDetail(
        id=run.id,
        title=run.title,
        report_type=run.report_type,
        scope_type=run.scope_type,
        scope_ref=run.scope_ref,
        status=run.status,
        created_at=run.created_at,
        completed_at=run.completed_at,
        model_used=run.model_used,
        findings=json.loads(run.findings_json) if run.findings_json else None,
        ai_narrative=json.loads(run.ai_narrative_json) if run.ai_narrative_json else None,
        rendered_markdown=run.rendered_markdown,
        rendered_html=run.rendered_html,
        assumptions=json.loads(run.assumptions_json) if run.assumptions_json else None,
        data_freshness_seconds=run.data_freshness_seconds,
        error_message=run.error_message,
        manual_notes=run.manual_notes,
        token_usage=json.loads(run.token_usage_json) if run.token_usage_json else None,
    )


# ── AI provider settings ────────────────────────────────────────────────────

@router.get("/settings", response_model=SettingsResponse)
def get_ai_settings(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    row = _get_or_create_openai_settings(db)
    return SettingsResponse(
        provider=row.provider,
        model=row.model,
        enabled=row.enabled,
        has_key=bool(row.api_key),
        last_test_at=row.last_test_at,
        last_test_ok=row.last_test_ok,
    )


@router.put("/settings", response_model=SettingsResponse)
def update_ai_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = _get_or_create_openai_settings(db)
    if payload.provider and payload.provider not in ("openai",):
        raise HTTPException(400, detail="Only 'openai' is supported in Phase 1")
    if payload.model is not None:
        if payload.model not in ai_provider.OpenAIProvider.ALLOWED_MODELS:
            raise HTTPException(400, detail=f"Unsupported model. Allowed: {sorted(ai_provider.OpenAIProvider.ALLOWED_MODELS)}")
        row.model = payload.model
    if payload.api_key is not None:
        key = payload.api_key.strip()
        if key:
            try:
                row.api_key = encrypt_data(key)
            except Exception:
                raise HTTPException(500, detail="Failed to encrypt API key")
        else:
            row.api_key = None
    if payload.enabled is not None:
        row.enabled = bool(payload.enabled)
    row.created_by_user_id = row.created_by_user_id or admin.id
    db.commit()
    db.refresh(row)

    _audit(db, admin.id, "ai_report_settings_update", row.id,
           {"model": row.model, "enabled": row.enabled, "provider": row.provider, "key_changed": payload.api_key is not None})

    return SettingsResponse(
        provider=row.provider,
        model=row.model,
        enabled=row.enabled,
        has_key=bool(row.api_key),
        last_test_at=row.last_test_at,
        last_test_ok=row.last_test_ok,
    )


@router.post("/settings/test")
def test_ai_settings(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = _get_or_create_openai_settings(db)
    if not row.api_key:
        raise HTTPException(400, detail="No API key stored yet")
    provider = ai_provider.get_active_provider(db)
    if provider is None:
        # Force instantiation even if disabled — admin might be testing before enabling
        from app.core.security import decrypt_data
        try:
            key = decrypt_data(row.api_key)
        except Exception:
            raise HTTPException(500, detail="Could not decrypt stored key")
        try:
            provider = ai_provider.OpenAIProvider(key)
        except ai_provider.AIProviderError as exc:
            raise HTTPException(500, detail=str(exc))
    ok = provider.test_connection(row.model)
    row.last_test_at = datetime.utcnow()
    row.last_test_ok = ok
    db.commit()
    _audit(db, admin.id, "ai_report_settings_test", row.id, {"ok": ok})
    return {"ok": ok, "tested_at": row.last_test_at.isoformat()}


# ── Power settings ──────────────────────────────────────────────────────────

def _get_or_create_cost(db: Session) -> PowerCostSettings:
    row = db.query(PowerCostSettings).filter(PowerCostSettings.id == 1).first()
    if row:
        return row
    row = PowerCostSettings(id=1, electricity_rate_per_kwh=0.12, currency="USD")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/power-settings", response_model=PowerSettingsResponse)
def get_power_settings(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    cost = _get_or_create_cost(db)
    profiles = []
    for p in db.query(NodePowerProfile).all():
        profiles.append({
            "node_id": p.node_id,
            "idle_watts": p.idle_watts,
            "load_watts": p.load_watts,
            "is_default": p.node_id is None,
        })
    return PowerSettingsResponse(
        electricity_rate_per_kwh=cost.electricity_rate_per_kwh,
        currency=cost.currency,
        node_profiles=profiles,
    )


@router.put("/power-settings", response_model=PowerSettingsResponse)
def update_power_settings(
    payload: PowerSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    cost = _get_or_create_cost(db)
    if payload.electricity_rate_per_kwh is not None:
        if payload.electricity_rate_per_kwh < 0 or payload.electricity_rate_per_kwh > 5:
            raise HTTPException(400, detail="electricity_rate_per_kwh out of range (0..5)")
        cost.electricity_rate_per_kwh = float(payload.electricity_rate_per_kwh)
    if payload.currency is not None:
        cost.currency = payload.currency[:10]

    if payload.node_profiles is not None:
        for pf in payload.node_profiles:
            node_id = pf.get("node_id")
            idle = int(pf.get("idle_watts", 120))
            load = int(pf.get("load_watts", 350))
            if idle < 30 or idle > 2000 or load < idle or load > 3000:
                raise HTTPException(400, detail=f"Bad watt values for node_id={node_id}")
            if node_id is not None:
                node = db.query(ProxmoxNode).filter(ProxmoxNode.id == node_id).first()
                if not node:
                    raise HTTPException(404, detail=f"Node {node_id} not found")
            existing = db.query(NodePowerProfile).filter(NodePowerProfile.node_id == node_id).first()
            if existing:
                existing.idle_watts = idle
                existing.load_watts = load
            else:
                db.add(NodePowerProfile(node_id=node_id, idle_watts=idle, load_watts=load))
    db.commit()
    _audit(db, admin.id, "ai_report_power_settings_update", None,
           {"rate": cost.electricity_rate_per_kwh, "currency": cost.currency})
    return get_power_settings(db=db, _user=admin)  # type: ignore[arg-type]


# ── Reports ─────────────────────────────────────────────────────────────────

@router.post("/reports", response_model=ReportSummary, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    if not _rate_ok(user.id):
        raise HTTPException(429, detail=f"Rate limit: max {_RATE_MAX} reports per minute per user")
    try:
        run = report_service.generate_report(
            db,
            user=user,
            report_type=payload.report_type,
            scope_type=payload.scope_type,
            scope_ref=payload.scope_ref,
            title=payload.title,
            user_goal=payload.custom_prompt,
            run_async=True,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))
    return ReportSummary.model_validate(run)


@router.get("/reports", response_model=List[ReportSummary])
def list_reports(
    report_type: Optional[str] = Query(default=None),
    scope_type: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = db.query(ReportRun)
    if report_type:
        q = q.filter(ReportRun.report_type == report_type)
    if scope_type:
        q = q.filter(ReportRun.scope_type == scope_type)
    if status_filter:
        q = q.filter(ReportRun.status == status_filter)
    rows = q.order_by(ReportRun.created_at.desc()).offset(offset).limit(limit).all()
    return [ReportSummary.model_validate(r) for r in rows]


@router.get("/reports/{report_id}", response_model=ReportDetail)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    row = db.query(ReportRun).filter(ReportRun.id == report_id).first()
    if not row:
        raise HTTPException(404, detail="Report not found")
    return _run_to_detail(row)


@router.post("/reports/{report_id}/regenerate", response_model=ReportSummary)
def regenerate_report(
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    if not _rate_ok(user.id):
        raise HTTPException(429, detail=f"Rate limit: max {_RATE_MAX} reports per minute per user")
    new_run = report_service.regenerate(db, report_id, user, run_async=True)
    if new_run is None:
        raise HTTPException(404, detail="Source report not found")
    return ReportSummary.model_validate(new_run)


@router.get("/reports/{report_id}/export/markdown", response_class=PlainTextResponse)
def export_markdown(
    report_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    row = db.query(ReportRun).filter(ReportRun.id == report_id).first()
    if not row or not row.rendered_markdown:
        raise HTTPException(404, detail="Report not available")
    return PlainTextResponse(
        content=row.rendered_markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="report-{row.id}.md"'},
    )


@router.get("/reports/{report_id}/export/html", response_class=HTMLResponse)
def export_html(
    report_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    row = db.query(ReportRun).filter(ReportRun.id == report_id).first()
    if not row or not row.rendered_html:
        raise HTTPException(404, detail="Report not available")
    return HTMLResponse(
        content=row.rendered_html,
        headers={"Content-Disposition": f'attachment; filename="report-{row.id}.html"'},
    )


@router.patch("/reports/{report_id}/notes", response_model=ReportDetail)
def update_notes(
    report_id: int,
    payload: NotesUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    row = db.query(ReportRun).filter(ReportRun.id == report_id).first()
    if not row:
        raise HTTPException(404, detail="Report not found")
    row.manual_notes = payload.manual_notes
    db.commit()
    db.refresh(row)
    _audit(db, user.id, "ai_report_notes_update", row.id, {})
    return _run_to_detail(row)


# ── Schedules ───────────────────────────────────────────────────────────────

def _compute_next_run(cadence: str, cron_expr: Optional[str], base: Optional[datetime] = None) -> Optional[datetime]:
    """Compute next_run_at for a schedule. Returns None if cron is required but missing."""
    from datetime import timedelta
    now = base or datetime.utcnow()
    if cadence == "daily":
        return now + timedelta(days=1)
    if cadence == "weekly":
        return now + timedelta(days=7)
    if cadence == "monthly":
        return now + timedelta(days=30)
    if cadence == "cron":
        # Cron parsing is deferred — apscheduler handles it at run time.
        return now + timedelta(hours=1)  # check hourly
    return None


@router.get("/schedules", response_model=List[ScheduleResponse])
def list_schedules(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    rows = db.query(ReportSchedule).order_by(ReportSchedule.created_at.desc()).all()
    return [ScheduleResponse.model_validate(r) for r in rows]


@router.post("/schedules", response_model=ScheduleResponse, status_code=201)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    next_run = _compute_next_run(payload.cadence, payload.cron_expr)
    row = ReportSchedule(
        name=payload.name,
        report_type=payload.report_type,
        scope_type=payload.scope_type,
        scope_ref=payload.scope_ref,
        cadence=payload.cadence,
        cron_expr=payload.cron_expr,
        enabled=payload.enabled,
        include_executive_summary=payload.include_executive_summary,
        include_raw_appendix=payload.include_raw_appendix,
        next_run_at=next_run,
        created_by_user_id=admin.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _audit(db, admin.id, "ai_report_schedule_create", row.id, {"name": row.name, "cadence": row.cadence})
    return ScheduleResponse.model_validate(row)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
    if not row:
        raise HTTPException(404, detail="Schedule not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    if payload.cadence is not None or payload.cron_expr is not None:
        row.next_run_at = _compute_next_run(row.cadence, row.cron_expr)
    db.commit()
    db.refresh(row)
    _audit(db, admin.id, "ai_report_schedule_update", row.id, payload.model_dump(exclude_unset=True))
    return ScheduleResponse.model_validate(row)


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
    if not row:
        raise HTTPException(404, detail="Schedule not found")
    db.delete(row)
    db.commit()
    _audit(db, admin.id, "ai_report_schedule_delete", schedule_id, {})
    return None
