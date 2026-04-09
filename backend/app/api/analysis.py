"""Analysis & recommendations API"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from app.core.database import get_db
from app.api.auth import get_current_user

router = APIRouter()


def _rec_to_dict(rec) -> dict:
    return {
        "id": rec.id,
        "host_id": rec.host_id,
        "node": rec.node,
        "vmid": rec.vmid,
        "vm_name": rec.vm_name,
        "resource_label": rec.resource_label,
        "category": rec.category,
        "rule_type": rec.rule_type,
        "severity": rec.severity,
        "title": rec.title,
        "detail": rec.detail,
        "suggestion": rec.suggestion,
        "metric_value": rec.metric_value,
        "metric_unit": rec.metric_unit,
        "threshold": rec.threshold,
        "dismissed": rec.dismissed,
        "dismissed_at": rec.dismissed_at.isoformat() if rec.dismissed_at else None,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }


@router.get("/recommendations")
def get_recommendations(
    category: Optional[str] = None,
    severity: Optional[str] = None,
    include_dismissed: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return all active (non-dismissed) recommendations, optionally filtered."""
    from app.models.analysis_models import Recommendation
    q = db.query(Recommendation)
    if not include_dismissed:
        q = q.filter(Recommendation.dismissed == False)
    if category:
        q = q.filter(Recommendation.category == category)
    if severity:
        q = q.filter(Recommendation.severity == severity)
    q = q.order_by(
        Recommendation.severity.desc(),  # critical first
        Recommendation.created_at.desc()
    )
    return [_rec_to_dict(r) for r in q.all()]


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return counts by category and severity for dashboard widgets."""
    from app.models.analysis_models import Recommendation
    from sqlalchemy import func

    rows = (
        db.query(Recommendation.category, Recommendation.severity, func.count())
        .filter(Recommendation.dismissed == False)
        .group_by(Recommendation.category, Recommendation.severity)
        .all()
    )
    summary: dict = {}
    total = 0
    for cat, sev, cnt in rows:
        summary.setdefault(cat, {})[sev] = cnt
        total += cnt

    return {"total": total, "by_category": summary}


@router.post("/recommendations/{rec_id}/dismiss")
def dismiss_recommendation(
    rec_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Dismiss a single recommendation so it won't appear again until re-triggered."""
    from app.models.analysis_models import Recommendation
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    rec.dismissed = True
    rec.dismissed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/recommendations/dismiss-all")
def dismiss_all(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Dismiss all (or all in a category) active recommendations."""
    from app.models.analysis_models import Recommendation
    q = db.query(Recommendation).filter(Recommendation.dismissed == False)
    if category:
        q = q.filter(Recommendation.category == category)
    now = datetime.utcnow()
    for rec in q.all():
        rec.dismissed = True
        rec.dismissed_at = now
    db.commit()
    return {"ok": True}


@router.post("/run")
def trigger_analysis(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Manually trigger an analysis cycle (runs in background)."""
    from app.services.analysis_engine import analysis_engine
    background_tasks.add_task(analysis_engine.run_now)
    return {"ok": True, "message": "Analysis started"}
