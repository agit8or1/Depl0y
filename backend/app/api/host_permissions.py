"""Authorization for host-scoped infrastructure routes."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.core.database import get_db
from app.models import User, UserRole
from app.models.database import UserHostPermission


def require_host_access(db: Session, user: User, host_id: int, action: str = "view") -> None:
    if action not in {"view", "manage", "admin"}:
        raise ValueError("Unknown host action")
    if user.role == UserRole.ADMIN:
        return
    if action != "view" and user.role != UserRole.OPERATOR:
        raise HTTPException(status_code=403, detail="Operator privileges required")
    permission = db.query(UserHostPermission).filter(
        UserHostPermission.user_id == user.id,
        UserHostPermission.host_id == host_id,
    ).first()
    allowed = permission is not None and permission.can_view
    if allowed and action == "manage":
        allowed = permission.can_manage or permission.can_admin
    elif allowed and action == "admin":
        allowed = permission.can_admin
    if not allowed:
        raise HTTPException(status_code=403, detail="Access to this host is not permitted")


async def authorize_host_request(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Protect direct host-id routes independently of filtered list screens."""
    raw_id = request.path_params.get("host_id")
    if raw_id is None:
        return  # Collection and non-host routes retain their own authorization.
    try:
        host_id = int(raw_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Invalid host ID")
    action = "view" if request.method in {"GET", "HEAD", "OPTIONS"} else "manage"
    require_host_access(db, current_user, host_id, action)
