"""Users API routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional
from datetime import datetime
import secrets
import string
import re

from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.models import User, UserRole
from app.api.auth import get_current_user, require_admin

router = APIRouter()


_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_-]+$')


# Pydantic models
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.VIEWER

    @validator('username')
    def username_valid(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('Username cannot be empty')
        if not _USERNAME_RE.match(v):
            raise ValueError(
                'Username may only contain letters, numbers, underscores, and hyphens'
            )
        return v

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    is_active: bool
    totp_enabled: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all users (admin only)"""
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new user (admin only)"""
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")

    # Enforce password policy from system settings
    try:
        from app.api.auth import _validate_password_policy
        policy_error = _validate_password_policy(db, user_data.password)
        if policy_error:
            raise HTTPException(status_code=400, detail=policy_error)
    except ImportError:
        pass

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Audit log: user created
    try:
        from app.api.audit import log_audit_event
        log_audit_event(
            db,
            action="user_created",
            user_id=current_user.id,
            resource_type="user",
            resource_id=new_user.id,
            details={"username": new_user.username, "role": str(new_user.role), "created_by": current_user.username},
            success=True,
        )
    except Exception:
        pass

    return new_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get user by ID (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update user (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from disabling themselves
    if user.id == current_user.id and user_data.is_active is False:
        raise HTTPException(
            status_code=400, detail="Cannot deactivate your own account"
        )

    # Update fields
    if user_data.email is not None:
        # Check if email already exists
        existing_email = (
            db.query(User)
            .filter(User.email == user_data.email, User.id != user_id)
            .first()
        )
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already exists")
        user.email = user_data.email

    old_role = str(user.role) if user_data.role is not None else None
    if user_data.role is not None:
        user.role = user_data.role

    if user_data.is_active is not None:
        user.is_active = user_data.is_active

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    # Audit log: user updated
    try:
        from app.api.audit import log_audit_event
        changes = {}
        if user_data.email is not None:
            changes["email"] = user_data.email
        if user_data.role is not None:
            changes["role"] = {"from": old_role, "to": str(user_data.role)}
        if user_data.is_active is not None:
            changes["is_active"] = user_data.is_active
        action = "user_role_changed" if user_data.role is not None else "user_updated"
        log_audit_event(
            db,
            action=action,
            user_id=current_user.id,
            resource_type="user",
            resource_id=user.id,
            details={"username": user.username, "changes": changes, "updated_by": current_user.username},
            success=True,
        )
    except Exception:
        pass

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete user (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    username_deleted = user.username
    db.delete(user)
    db.commit()

    # Audit log: user deleted
    try:
        from app.api.audit import log_audit_event
        log_audit_event(
            db,
            action="user_deleted",
            user_id=current_user.id,
            resource_type="user",
            resource_id=user_id,
            details={"username": username_deleted, "deleted_by": current_user.username},
            success=True,
        )
    except Exception:
        pass

    return None


@router.patch("/{user_id}", response_model=UserResponse)
async def patch_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Patch user fields (admin only) — same as PUT but partial."""
    return await update_user(user_id, user_data, current_user, db)


class UserStatusUpdate(BaseModel):
    is_active: bool


@router.patch("/{user_id}/status", response_model=UserResponse)
async def toggle_user_status(
    user_id: int,
    data: UserStatusUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Enable or disable a user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id and not data.is_active:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    user.is_active = data.is_active
    user.updated_at = datetime.utcnow()
    # Bump token_version to invalidate existing sessions when disabling
    if not data.is_active:
        user.token_version = (getattr(user, "token_version", 0) or 0) + 1
    db.commit()
    db.refresh(user)
    return user


class ResetPasswordResponse(BaseModel):
    temporary_password: str
    message: str


def _generate_temp_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        # Ensure complexity
        if (any(c.isupper() for c in pwd) and any(c.islower() for c in pwd)
                and any(c.isdigit() for c in pwd) and any(c in "!@#$%^&*" for c in pwd)):
            return pwd


@router.post("/{user_id}/reset-password", response_model=ResetPasswordResponse)
async def admin_reset_password(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin resets a user's password, returning a one-time temporary password."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    temp_password = _generate_temp_password()
    user.hashed_password = get_password_hash(temp_password)
    user.updated_at = datetime.utcnow()
    # Bump token_version to invalidate all active sessions
    user.token_version = (getattr(user, "token_version", 0) or 0) + 1
    db.commit()

    return {
        "temporary_password": temp_password,
        "message": f"Password reset for {user.username}. Share this temporary password securely — it will not be shown again.",
    }


class DisableTotpRequest(BaseModel):
    pass  # No body needed; admin action


@router.post("/{user_id}/disable-totp")
async def admin_disable_totp(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin force-disables 2FA for a user (account recovery)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled for this user")
    user.totp_enabled = False
    user.totp_secret = None
    user.updated_at = datetime.utcnow()
    db.commit()
    return {"message": f"2FA disabled for {user.username}"}


@router.post("/invalidate-sessions/{user_id}")
async def invalidate_user_sessions(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Invalidate all active sessions for a specific user by bumping token_version."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.token_version = (getattr(user, "token_version", 0) or 0) + 1
    user.updated_at = datetime.utcnow()
    db.commit()
    return {"message": f"All sessions invalidated for {user.username}"}


@router.post("/invalidate-sessions-all")
async def invalidate_all_sessions(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Invalidate all active sessions for ALL users by bumping token_version."""
    users = db.query(User).all()
    for u in users:
        u.token_version = (getattr(u, "token_version", 0) or 0) + 1
    db.commit()
    return {"message": f"All sessions invalidated for {len(users)} users"}


@router.post("/change-password")
async def change_password(
    password_data: UserPasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change current user's password"""
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    # Update password
    current_user.hashed_password = get_password_hash(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Password changed successfully"}


# ── Host Permissions ──────────────────────────────────────────────────────────

class HostPermissionCreate(BaseModel):
    host_id: int
    can_view: bool = True
    can_manage: bool = False
    can_admin: bool = False


class HostPermissionResponse(BaseModel):
    id: int
    user_id: int
    host_id: int
    can_view: bool
    can_manage: bool
    can_admin: bool
    host_name: Optional[str] = None
    host_hostname: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/{user_id}/host-permissions", response_model=List[HostPermissionResponse])
async def list_user_host_permissions(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List which Proxmox hosts a user can access (admin only)."""
    from app.models.database import UserHostPermission, ProxmoxHost
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    perms = db.query(UserHostPermission).filter(UserHostPermission.user_id == user_id).all()
    result = []
    for p in perms:
        host = db.query(ProxmoxHost).filter(ProxmoxHost.id == p.host_id).first()
        result.append(HostPermissionResponse(
            id=p.id,
            user_id=p.user_id,
            host_id=p.host_id,
            can_view=p.can_view,
            can_manage=p.can_manage,
            can_admin=p.can_admin,
            host_name=host.name if host else None,
            host_hostname=host.hostname if host else None,
        ))
    return result


@router.post("/{user_id}/host-permissions", response_model=HostPermissionResponse)
async def grant_user_host_permission(
    user_id: int,
    data: HostPermissionCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Grant a user access to a Proxmox host (admin only)."""
    from app.models.database import UserHostPermission, ProxmoxHost
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == data.host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")

    existing = db.query(UserHostPermission).filter(
        UserHostPermission.user_id == user_id,
        UserHostPermission.host_id == data.host_id,
    ).first()

    if existing:
        # Update existing permission
        existing.can_view = data.can_view
        existing.can_manage = data.can_manage
        existing.can_admin = data.can_admin
        db.commit()
        db.refresh(existing)
        return HostPermissionResponse(
            id=existing.id,
            user_id=existing.user_id,
            host_id=existing.host_id,
            can_view=existing.can_view,
            can_manage=existing.can_manage,
            can_admin=existing.can_admin,
            host_name=host.name,
            host_hostname=host.hostname,
        )

    perm = UserHostPermission(
        user_id=user_id,
        host_id=data.host_id,
        can_view=data.can_view,
        can_manage=data.can_manage,
        can_admin=data.can_admin,
    )
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return HostPermissionResponse(
        id=perm.id,
        user_id=perm.user_id,
        host_id=perm.host_id,
        can_view=perm.can_view,
        can_manage=perm.can_manage,
        can_admin=perm.can_admin,
        host_name=host.name,
        host_hostname=host.hostname,
    )


@router.delete("/{user_id}/host-permissions/{host_id}")
async def revoke_user_host_permission(
    user_id: int,
    host_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Revoke a user's access to a Proxmox host (admin only)."""
    from app.models.database import UserHostPermission
    perm = db.query(UserHostPermission).filter(
        UserHostPermission.user_id == user_id,
        UserHostPermission.host_id == host_id,
    ).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    db.delete(perm)
    db.commit()
    return {"message": "Permission revoked"}
