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
