"""Audit log API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
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
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List audit log entries (admin only)"""
    from app.models.database import AuditLog
    from sqlalchemy import desc
    query = db.query(AuditLog).order_by(desc(AuditLog.timestamp))
    if action:
        query = query.filter(AuditLog.action.ilike(f'%{action}%'))
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
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
            "created_at": l.timestamp.isoformat(),
        } for l in logs
    ]}


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
        # Build a human-friendly action description
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
