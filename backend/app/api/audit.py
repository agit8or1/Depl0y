"""Audit log API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.api.auth import get_current_user, require_admin
from app.models import User

router = APIRouter()


@router.get("/")
async def list_audit_logs(
    skip: int = 0,
    limit: int = 100,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    ip_address: Optional[str] = None,
    resource_type: Optional[str] = None,
    success: Optional[bool] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List audit log entries (admin only) with enhanced filters"""
    from app.models.database import AuditLog
    from sqlalchemy import desc
    query = db.query(AuditLog).order_by(desc(AuditLog.timestamp))
    if action:
        query = query.filter(AuditLog.action.ilike(f'%{action}%'))
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if ip_address:
        query = query.filter(AuditLog.ip_address.ilike(f'%{ip_address}%'))
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if success is not None:
        query = query.filter(AuditLog.success == success)
    if from_date:
        try:
            dt = datetime.fromisoformat(from_date)
            query = query.filter(AuditLog.timestamp >= dt)
        except ValueError:
            pass
    if to_date:
        try:
            dt = datetime.fromisoformat(to_date)
            # If no time component, extend to end of day
            if 'T' not in to_date:
                dt = dt.replace(hour=23, minute=59, second=59)
            query = query.filter(AuditLog.timestamp <= dt)
        except ValueError:
            pass
    total = query.count()
    logs = query.offset(skip).limit(limit).all()
    return {"total": total, "logs": [
        {
            "id": l.id,
            "user_id": l.user_id,
            "username": l.user.username if l.user else "system",
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "details": l.details,
            "ip_address": l.ip_address,
            "user_agent": l.user_agent,
            "request_body": l.request_body,
            "response_status": l.response_status,
            "duration_ms": l.duration_ms,
            "http_method": l.http_method,
            "request_path": l.request_path,
            "success": l.success,
            "created_at": l.timestamp.isoformat(),
        } for l in logs
    ]}


@router.get("/stats")
async def get_audit_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get audit log statistics for the specified period"""
    from app.models.database import AuditLog
    from sqlalchemy import func, desc

    since = datetime.utcnow() - timedelta(days=days)
    base_query = db.query(AuditLog).filter(AuditLog.timestamp >= since)

    total_count = base_query.count()
    failed_count = base_query.filter(AuditLog.success == False).count()

    # Events by day (last N days)
    events_by_day_raw = (
        db.query(
            func.date(AuditLog.timestamp).label("day"),
            func.count(AuditLog.id).label("count"),
        )
        .filter(AuditLog.timestamp >= since)
        .group_by(func.date(AuditLog.timestamp))
        .order_by("day")
        .all()
    )
    events_by_day = [{"date": str(r.day), "count": r.count} for r in events_by_day_raw]

    # Top 5 users
    top_users_raw = (
        db.query(
            AuditLog.user_id,
            func.count(AuditLog.id).label("count"),
        )
        .filter(AuditLog.timestamp >= since, AuditLog.user_id.isnot(None))
        .group_by(AuditLog.user_id)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )
    from app.models.database import User as UserModel
    top_users = []
    for r in top_users_raw:
        u = db.query(UserModel).filter(UserModel.id == r.user_id).first()
        top_users.append({"username": u.username if u else f"user#{r.user_id}", "count": r.count})

    # Top 5 actions
    top_actions_raw = (
        db.query(
            AuditLog.action,
            func.count(AuditLog.id).label("count"),
        )
        .filter(AuditLog.timestamp >= since)
        .group_by(AuditLog.action)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )
    top_actions = [{"action": r.action, "count": r.count} for r in top_actions_raw]

    return {
        "total_count": total_count,
        "failed_count": failed_count,
        "events_by_day": events_by_day,
        "top_users": top_users,
        "top_actions": top_actions,
        "period_days": days,
    }


def _action_icon(action: str) -> str:
    """Map an audit action string to a display icon."""
    a = action.lower()
    if "login" in a or "logout" in a or "auth" in a:
        return "login"
    if "create" in a or "deploy" in a or "add" in a:
        return "create"
    if "delete" in a or "remove" in a or "destroy" in a:
        return "delete"
    if "update" in a or "edit" in a or "patch" in a or "modify" in a or "change" in a:
        return "modify"
    if "start" in a or "stop" in a or "restart" in a or "reboot" in a:
        return "power"
    if "backup" in a or "restore" in a:
        return "backup"
    if "scan" in a or "check" in a:
        return "scan"
    return "info"


@router.get("/feed")
async def get_audit_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get simplified activity feed for the dashboard (all authenticated users)."""
    from app.models.database import AuditLog
    from sqlalchemy import desc

    logs = (
        db.query(AuditLog)
        .order_by(desc(AuditLog.timestamp))
        .offset(offset)
        .limit(limit)
        .all()
    )

    feed = []
    for l in logs:
        username = l.user.username if l.user else "system"
        resource = l.resource_type or ""
        if l.resource_id:
            resource = f"{resource} #{l.resource_id}" if resource else f"#{l.resource_id}"
        action_display = l.action.replace("_", " ").lower()
        feed.append({
            "id": l.id,
            "time": l.timestamp.isoformat(),
            "user": username,
            "action": action_display,
            "resource": resource,
            "resource_type": l.resource_type or "",
            "icon": _action_icon(l.action),
        })
    return feed


def log_audit_event(
    db: Session,
    action: str,
    user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    http_method: Optional[str] = None,
    request_path: Optional[str] = None,
    response_status: Optional[int] = None,
    duration_ms: Optional[int] = None,
    request_body: Optional[str] = None,
):
    """Helper to write an audit log entry from anywhere in the codebase."""
    from app.models.database import AuditLog
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:500] if user_agent else None,
            success=success,
            http_method=http_method,
            request_path=request_path,
            response_status=response_status,
            duration_ms=duration_ms,
            request_body=request_body,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
