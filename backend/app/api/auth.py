"""Authentication API routes"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
import qrcode
import io
import base64
import secrets
import string

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    generate_totp_uri,
    verify_totp_code,
)
from app.models import User, UserRole
from app.models.database import ApiKey

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


# Pydantic models
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None


class TOTPSetupResponse(BaseModel):
    secret: str
    qr_code: str
    uri: str


class TOTPVerifyRequest(BaseModel):
    code: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    is_active: bool
    totp_enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Dependency to get current user
async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Check token_version for session invalidation
    token_version = payload.get("tv", 0)
    user_token_version = getattr(user, "token_version", 0) or 0
    if token_version < user_token_version:
        raise credentials_exception

    return user


# Dependency for admin-only access
async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


# Dependency for operator or admin access
async def require_operator(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in [UserRole.ADMIN, UserRole.OPERATOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator privileges required",
        )
    return current_user


def _get_brute_force_setting(db: Session, key: str, default: int) -> int:
    """Helper to read brute force settings from SystemSettings."""
    from app.models.database import SystemSettings
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    try:
        return int(row.value) if row else default
    except (TypeError, ValueError):
        return default


def _record_failed_login(db: Session, username: str, ip_address: str, user_agent: str):
    """Record a failed login attempt and lock the account if threshold exceeded."""
    from app.models.security import FailedLoginAttempt, AccountLockout, SecurityEvent
    from datetime import timedelta

    attempt = FailedLoginAttempt(
        username=username,
        ip_address=ip_address,
        user_agent=user_agent or "",
        success=False,
    )
    db.add(attempt)

    enabled = _get_brute_force_setting(db, "brute_force_enabled", 1)
    if not enabled:
        db.commit()
        return

    max_attempts = _get_brute_force_setting(db, "brute_force_max_attempts", 5)
    lockout_minutes = _get_brute_force_setting(db, "brute_force_lockout_minutes", 15)

    # Count recent failed attempts within the lockout window
    window_start = datetime.utcnow() - timedelta(minutes=lockout_minutes)
    recent_count = (
        db.query(FailedLoginAttempt)
        .filter(
            FailedLoginAttempt.username == username,
            FailedLoginAttempt.success == False,
            FailedLoginAttempt.attempted_at >= window_start,
        )
        .count()
    )
    # +1 for the attempt we just added (not yet flushed)
    recent_count += 1

    if recent_count >= max_attempts:
        locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
        existing = db.query(AccountLockout).filter(AccountLockout.username == username).first()
        if existing:
            existing.locked_at = datetime.utcnow()
            existing.locked_until = locked_until
            existing.failed_attempts = recent_count
            existing.reason = f"Too many failed login attempts ({recent_count})"
        else:
            lockout = AccountLockout(
                username=username,
                locked_until=locked_until,
                reason=f"Too many failed login attempts ({recent_count})",
                failed_attempts=recent_count,
            )
            db.add(lockout)

        event = SecurityEvent(
            event_type="account_locked",
            severity="high",
            username=username,
            ip_address=ip_address,
            user_agent=user_agent or "",
            details=f"Account locked after {recent_count} failed attempts",
        )
        db.add(event)

    db.commit()


def _check_account_lockout(db: Session, username: str) -> Optional[str]:
    """Return a lockout message if the account is currently locked, else None."""
    from app.models.security import AccountLockout
    lockout = db.query(AccountLockout).filter(AccountLockout.username == username).first()
    if lockout is None:
        return None
    if lockout.locked_until > datetime.utcnow():
        remaining = int((lockout.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
        return f"Account locked. Try again in {remaining} minute(s)."
    # Lockout has expired — remove it
    db.delete(lockout)
    db.commit()
    return None


def _clear_failed_attempts(db: Session, username: str):
    """Remove failed login records after a successful login."""
    from app.models.security import FailedLoginAttempt
    db.query(FailedLoginAttempt).filter(FailedLoginAttempt.username == username).delete()
    db.commit()


def _record_login_attempt(
    db: Session,
    user_id: Optional[int],
    username: str,
    ip: str,
    ua: str,
    success: bool,
    reason: Optional[str],
):
    """Record a login attempt in the comprehensive login_attempts table."""
    from app.models.security import LoginAttempt
    try:
        attempt = LoginAttempt(
            user_id=user_id,
            username_attempted=username,
            ip_address=ip,
            user_agent=ua or "",
            success=success,
            failure_reason=reason,
        )
        db.add(attempt)
        db.commit()
    except Exception:
        db.rollback()


@router.post("/login", response_model=Token)
async def login(credentials: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Login endpoint with brute-force protection and timing attack mitigation."""
    import time
    import random

    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    # ── Brute-force: check if account is locked ──────────────────────────
    lockout_msg = _check_account_lockout(db, credentials.username)
    if lockout_msg:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=lockout_msg)

    user = db.query(User).filter(User.username == credentials.username).first()

    # SECURITY: always perform bcrypt verification to prevent timing attacks
    if user:
        password_valid = verify_password(credentials.password, user.hashed_password)
    else:
        dummy_hash = get_password_hash("dummy_password_for_timing_protection")
        verify_password(credentials.password, dummy_hash)
        password_valid = False

    # Small random delay to further mitigate timing attacks (1-50ms)
    time.sleep(random.uniform(0.001, 0.05))

    if not user or not password_valid:
        _record_failed_login(db, credentials.username, client_ip, user_agent)
        _record_login_attempt(
            db,
            user_id=user.id if user else None,
            username=credentials.username,
            ip=client_ip,
            ua=user_agent,
            success=False,
            reason="bad_password",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        _record_login_attempt(db, user.id, credentials.username, client_ip, user_agent, False, "account_disabled")
        raise HTTPException(status_code=400, detail="Inactive user")

    # Check 2FA if enabled
    if user.totp_enabled:
        if not credentials.totp_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="2FA code required",
            )
        if not verify_totp_code(user.totp_secret, credentials.totp_code):
            _record_failed_login(db, credentials.username, client_ip, user_agent)
            _record_login_attempt(db, user.id, credentials.username, client_ip, user_agent, False, "2fa_failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code",
            )

    # Successful login — clear lockout state and record success
    _clear_failed_attempts(db, credentials.username)
    _record_login_attempt(db, user.id, credentials.username, client_ip, user_agent, True, None)

    user.last_login = datetime.utcnow()
    db.commit()

    token_version = getattr(user, "token_version", 0) or 0
    access_token = create_access_token(data={"sub": user.username, "tv": token_version})
    refresh_token = create_refresh_token(data={"sub": user.username, "tv": token_version})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    """Refresh access token"""
    payload = decode_token(refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Check token_version
    token_version = payload.get("tv", 0)
    user_token_version = getattr(user, "token_version", 0) or 0
    if token_version < user_token_version:
        raise HTTPException(status_code=401, detail="Session invalidated")

    # Create new tokens
    tv = user_token_version
    access_token = create_access_token(data={"sub": user.username, "tv": tv})
    new_refresh_token = create_refresh_token(data={"sub": user.username, "tv": tv})

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


@router.patch("/me/password")
async def change_own_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change current user's password"""
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    current_user.hashed_password = get_password_hash(data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Password changed"}


@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def setup_totp(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Setup TOTP 2FA for current user"""
    # Generate new secret
    secret = generate_totp_secret()
    uri = generate_totp_uri(secret, current_user.username)

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

    # Store secret temporarily (not enabled yet)
    current_user.totp_secret = secret
    db.commit()

    return {
        "secret": secret,
        "qr_code": f"data:image/png;base64,{qr_code_base64}",
        "uri": uri,
    }


@router.post("/totp/verify")
async def verify_totp(
    request: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify and enable TOTP 2FA"""
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="TOTP not set up")

    if not verify_totp_code(current_user.totp_secret, request.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    # Enable TOTP
    current_user.totp_enabled = True
    db.commit()

    return {"message": "2FA enabled successfully"}


@router.post("/totp/disable")
async def disable_totp(
    request: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disable TOTP 2FA"""
    if not current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA not enabled")

    if not verify_totp_code(current_user.totp_secret, request.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    # Disable TOTP
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.commit()

    return {"message": "2FA disabled successfully"}


# ── API Key Management ────────────────────────────────────────────────────────

class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    last_used: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class ApiKeyListResponse(BaseModel):
    api_keys: List[ApiKeyResponse]


class ApiKeyCreateRequest(BaseModel):
    name: str
    expires_at: Optional[datetime] = None


class ApiKeyCreateResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    key: str  # Full key returned ONCE only
    created_at: datetime
    expires_at: Optional[datetime]


def _generate_api_key() -> str:
    """Generate a secure random 32-character API key with prefix dk_."""
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(32))
    return f"dk_{random_part}"


@router.get("/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List current user's API keys"""
    keys = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == current_user.id, ApiKey.is_active == True)
        .order_by(ApiKey.created_at.desc())
        .all()
    )
    return {"api_keys": keys}


@router.post("/api-keys", response_model=ApiKeyCreateResponse)
async def create_api_key(
    data: ApiKeyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new API key. The full key is returned only once."""
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="API key name is required")

    raw_key = _generate_api_key()
    key_hash = get_password_hash(raw_key)
    key_prefix = raw_key[:8]

    api_key = ApiKey(
        user_id=current_user.id,
        name=data.name.strip(),
        key_hash=key_hash,
        key_prefix=key_prefix,
        expires_at=data.expires_at,
        is_active=True,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return {
        "id": api_key.id,
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "key": raw_key,
        "created_at": api_key.created_at,
        "expires_at": api_key.expires_at,
    }


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke (deactivate) an API key"""
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
        .first()
    )
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    db.commit()

    return {"message": "API key revoked"}
