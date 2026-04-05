"""Authentication API routes"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
import qrcode
import io
import base64

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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code",
            )

    # Successful login — clear lockout state
    _clear_failed_attempts(db, credentials.username)

    user.last_login = datetime.utcnow()
    db.commit()

    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

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

    # Create new tokens
    access_token = create_access_token(data={"sub": user.username})
    new_refresh_token = create_refresh_token(data={"sub": user.username})

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


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
