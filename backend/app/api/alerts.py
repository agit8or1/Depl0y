"""Alerts API — active alerts, alert events history, and alert rules management"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.api.auth import require_admin, get_current_user
from app.models.database import User
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AlertRuleCreate(BaseModel):
    name: str
    rule_type: str          # storage_usage, node_cpu, node_memory, vm_stopped, backup_failed, login_failures
    threshold: Optional[float] = None
    host_id: Optional[int] = None
    node: Optional[str] = None
    enabled: bool = True
    notify_in_app: bool = True
    notify_webhook: bool = False
    notify_slack: bool = False
    cooldown_minutes: int = 60


class AlertRuleUpdate(AlertRuleCreate):
    pass


class AlertRuleOut(BaseModel):
    id: int
    name: str
    rule_type: str
    threshold: Optional[float]
    host_id: Optional[int]
    node: Optional[str]
    enabled: bool
    notify_in_app: bool
    notify_webhook: bool
    notify_slack: bool
    cooldown_minutes: int
    last_fired_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class AlertEventOut(BaseModel):
    id: int
    rule_id: Optional[int]
    rule_key: Optional[str]
    severity: str
    title: str
    message: str
    fired_at: datetime
    acknowledged: bool
    acknowledged_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Active alerts ─────────────────────────────────────────────────────────────

@router.get("/active", response_model=List[AlertEventOut])
async def get_active_alerts(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return all currently firing, unacknowledged alert events."""
    try:
        from app.models.alert_models import AlertEvent
        events = (
            db.query(AlertEvent)
            .filter(AlertEvent.acknowledged == False)
            .order_by(AlertEvent.fired_at.desc())
            .limit(200)
            .all()
        )
        return events
    except Exception as exc:
        logger.error(f"get_active_alerts error: {exc}")
        return []


@router.post("/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Acknowledge / dismiss an alert event."""
    try:
        from app.models.alert_models import AlertEvent
        event = db.query(AlertEvent).filter(AlertEvent.id == alert_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Alert not found")
        event.acknowledged = True
        event.acknowledged_at = datetime.utcnow()
        event.acknowledged_by = current_user.id
        db.commit()
        return {"status": "dismissed"}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"dismiss_alert error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/dismiss-all")
async def dismiss_all_alerts(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Acknowledge all currently active (unacknowledged) alert events."""
    try:
        from app.models.alert_models import AlertEvent
        db.query(AlertEvent).filter(AlertEvent.acknowledged == False).update(
            {
                "acknowledged": True,
                "acknowledged_at": datetime.utcnow(),
                "acknowledged_by": current_user.id,
            },
            synchronize_session=False,
        )
        db.commit()
        return {"status": "all dismissed"}
    except Exception as exc:
        db.rollback()
        logger.error(f"dismiss_all_alerts error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Alert history ─────────────────────────────────────────────────────────────

@router.get("/history")
async def get_alert_history(
    days: int = Query(7, ge=1, le=90),
    severity: Optional[str] = Query(None),
    rule_key: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return paginated alert event history for the last N days."""
    try:
        from app.models.alert_models import AlertEvent
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = db.query(AlertEvent).filter(AlertEvent.fired_at >= cutoff)
        if severity:
            query = query.filter(AlertEvent.severity == severity)
        if rule_key:
            query = query.filter(AlertEvent.rule_key.contains(rule_key))

        total = query.count()
        events = (
            query.order_by(AlertEvent.fired_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "items": [
                {
                    "id": e.id,
                    "rule_id": e.rule_id,
                    "rule_key": e.rule_key,
                    "severity": e.severity,
                    "title": e.title,
                    "message": e.message,
                    "fired_at": e.fired_at.isoformat() if e.fired_at else None,
                    "acknowledged": e.acknowledged,
                    "acknowledged_at": e.acknowledged_at.isoformat() if e.acknowledged_at else None,
                    "resolution_minutes": (
                        round((e.acknowledged_at - e.fired_at).total_seconds() / 60, 1)
                        if e.acknowledged_at and e.fired_at else None
                    ),
                }
                for e in events
            ],
        }
    except Exception as exc:
        logger.error(f"get_alert_history error: {exc}")
        return {"total": 0, "page": page, "per_page": per_page, "items": []}


@router.get("/history/sparkline")
async def get_alert_sparkline(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return per-day alert count for the last N days (for mini bar charts)."""
    try:
        from app.models.alert_models import AlertEvent
        from sqlalchemy import func
        cutoff = datetime.utcnow() - timedelta(days=days)
        rows = (
            db.query(
                func.date(AlertEvent.fired_at).label("day"),
                func.count(AlertEvent.id).label("cnt"),
            )
            .filter(AlertEvent.fired_at >= cutoff)
            .group_by(func.date(AlertEvent.fired_at))
            .all()
        )
        # Build a full day-indexed dict so we have zeroes for quiet days
        result = {}
        for i in range(days):
            day = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            result[day] = 0
        for row in rows:
            day_str = str(row[0])[:10]
            if day_str in result:
                result[day_str] = row[1]
        return {
            "labels": list(result.keys()),
            "counts": list(result.values()),
        }
    except Exception as exc:
        logger.error(f"get_alert_sparkline error: {exc}")
        return {"labels": [], "counts": []}


# ── Alert rules CRUD ──────────────────────────────────────────────────────────

@router.get("/rules", response_model=List[AlertRuleOut])
async def list_alert_rules(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all user-configured alert rules."""
    try:
        from app.models.alert_models import AlertRule
        rules = db.query(AlertRule).order_by(AlertRule.id.asc()).all()
        return rules
    except Exception as exc:
        logger.error(f"list_alert_rules error: {exc}")
        return []


@router.post("/rules", response_model=AlertRuleOut)
async def create_alert_rule(
    data: AlertRuleCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new alert rule."""
    try:
        from app.models.alert_models import AlertRule
        rule = AlertRule(
            name=data.name,
            rule_type=data.rule_type,
            threshold=data.threshold,
            host_id=data.host_id,
            node=data.node,
            enabled=data.enabled,
            notify_in_app=data.notify_in_app,
            notify_webhook=data.notify_webhook,
            notify_slack=data.notify_slack,
            cooldown_minutes=data.cooldown_minutes,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        logger.info(f"Alert rule created: {rule.name} (id={rule.id}) by {current_user.username}")
        return rule
    except Exception as exc:
        db.rollback()
        logger.error(f"create_alert_rule error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/rules/{rule_id}", response_model=AlertRuleOut)
async def update_alert_rule(
    rule_id: int,
    data: AlertRuleUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update an existing alert rule."""
    try:
        from app.models.alert_models import AlertRule
        rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        for field, value in data.dict().items():
            setattr(rule, field, value)
        db.commit()
        db.refresh(rule)
        logger.info(f"Alert rule updated: {rule.name} (id={rule.id}) by {current_user.username}")
        return rule
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"update_alert_rule error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete an alert rule."""
    try:
        from app.models.alert_models import AlertRule
        rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        db.delete(rule)
        db.commit()
        logger.info(f"Alert rule deleted: {rule_id} by {current_user.username}")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"delete_alert_rule error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/rules/{rule_id}/toggle")
async def toggle_alert_rule(
    rule_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Toggle enabled/disabled state of an alert rule."""
    try:
        from app.models.alert_models import AlertRule
        rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        rule.enabled = not rule.enabled
        db.commit()
        return {"enabled": rule.enabled}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/events/{event_id}/acknowledge")
async def acknowledge_alert_event(
    event_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Acknowledge a specific alert event by its event ID."""
    try:
        from app.models.alert_models import AlertEvent
        event = db.query(AlertEvent).filter(AlertEvent.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Alert event not found")
        event.acknowledged = True
        event.acknowledged_at = datetime.utcnow()
        event.acknowledged_by = current_user.id
        db.commit()
        return {"status": "acknowledged", "event_id": event_id}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"acknowledge_alert_event error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/evaluate")
async def trigger_evaluation(
    current_user: User = Depends(require_admin),
):
    """Manually trigger an immediate alert evaluation cycle."""
    try:
        from app.services.alert_engine import alert_engine
        alert_engine.evaluate_now()
        return {"status": "evaluation triggered"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
