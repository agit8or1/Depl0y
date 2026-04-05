"""Authentication API routes"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
import qrcode
import io
import base64
import secrets
import string
import hashlib
import time
from collections import defaultdict

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
from app.models.database import ApiKey, TotpBackupCode, RefreshToken

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

# In-memory rate limiting for API keys: {key_id: [timestamp, ...]}
_api_key_rate: dict = defaultdict(list)
_API_KEY_RPM = 60  # requests per minute per API key

# Temp token store for 2FA login challenge: {temp_token: {username, expires_at}}
_temp_tokens: dict = {}
_TEMP_TOKEN_TTL = 300  # 5 minutes


def _cleanup_temp_tokens():
    """Remove expired temp tokens from in-memory store."""
    now = datetime.utcnow()
    expired = [k for k, v in _temp_tokens.items() if v["expires_at"] < now]
    for k in expired:
        del _temp_tokens[k]


def _hash_token(token: str) -> str:
    """SHA-256 hash a token for DB storage (not bcrypt — speed matters here)."""
    return hashlib.sha256(token.encode()).hexdigest()


def _store_refresh_token(
    db: Session,
    user_id: int,
    token: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
    expires_delta_days: int = 30,
) -> RefreshToken:
    """Persist a refresh token hash to the database."""
    from app.core.config import settings
    expires_at = datetime.utcnow() + timedelta(days=expires_delta_days)
    rt = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(token),
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
        created_at=datetime.utcnow(),
        expires_at=expires_at,
        revoked=False,
    )
    db.add(rt)
    db.commit()
    db.refresh(rt)
    return rt


def _revoke_refresh_token(db: Session, token: str) -> bool:
    """Mark a refresh token as revoked. Returns True if found."""
    token_hash = _hash_token(token)
    rt = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked == False,
    ).first()
    if rt:
        rt.revoked = True
        rt.revoked_at = datetime.utcnow()
        db.commit()
        return True
    return False


def _validate_refresh_token(db: Session, token: str) -> Optional[RefreshToken]:
    """Return the RefreshToken row if valid (exists, not revoked, not expired)."""
    token_hash = _hash_token(token)
    rt = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked == False,
    ).first()
    if rt is None:
        return None
    if rt.expires_at < datetime.utcnow():
        # Expired — revoke it to keep the table clean
        rt.revoked = True
        rt.revoked_at = datetime.utcnow()
        db.commit()
        return None
    return rt


# Pydantic models
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TwoFactorLoginRequest(BaseModel):
    temp_token: str
    totp_code: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TOTPSetupResponse(BaseModel):
    secret: str
    qr_code: str
    uri: str


class TOTPVerifyRequest(BaseModel):
    code: str


class TOTPDisableRequest(BaseModel):
    code: str


class BackupCodesResponse(BaseModel):
    codes: List[str]
    remaining: int


class SessionResponse(BaseModel):
    id: int
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


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
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # --- Try X-API-Key header first ---
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header and api_key_header.startswith("dk_"):
        # Look up all active keys for this user prefix (first 8 chars)
        prefix = api_key_header[:8]
        candidate_keys = (
            db.query(ApiKey)
            .filter(
                ApiKey.key_prefix == prefix,
                ApiKey.is_active == True,
            )
            .all()
        )
        matched_key = None
        for candidate in candidate_keys:
            if verify_password(api_key_header, candidate.key_hash):
                matched_key = candidate
                break

        if matched_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check expiry
        if matched_key.expires_at and matched_key.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired",
            )

        # Rate limit per API key
        now = time.time()
        cutoff = now - 60
        _api_key_rate[matched_key.id] = [t for t in _api_key_rate[matched_key.id] if t > cutoff]
        if len(_api_key_rate[matched_key.id]) >= _API_KEY_RPM:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="API key rate limit exceeded (60 req/min)",
            )
        _api_key_rate[matched_key.id].append(now)

        # Update last_used
        try:
            matched_key.last_used = datetime.utcnow()
            db.commit()
        except Exception:
            db.rollback()

        # Load the associated user
        user = db.query(User).filter(User.id == matched_key.user_id).first()
        if user is None or not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        return user

    # --- Fall back to JWT Bearer token ---
    if not token:
        raise credentials_exception

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


def _generate_backup_codes() -> List[str]:
    """Generate 8 random 8-character alphanumeric backup codes."""
    alphabet = string.ascii_uppercase + string.digits
    codes = []
    for _ in range(8):
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        codes.append(code)
    return codes


def _count_remaining_backup_codes(db: Session, user_id: int) -> int:
    """Count unused backup codes for a user."""
    return (
        db.query(TotpBackupCode)
        .filter(TotpBackupCode.user_id == user_id, TotpBackupCode.used == False)
        .count()
    )


def _finalize_login(
    db: Session,
    user: User,
    ip_address: str,
    user_agent: str,
) -> dict:
    """Complete a successful login: update last_login, create tokens, store refresh token."""
    import random

    is_first_login = user.last_login is None
    user.last_login = datetime.utcnow()
    db.commit()

    # Welcome notification on first login
    if is_first_login:
        try:
            from app.models.database import Notification
            welcome = Notification(
                user_id=user.id,
                title=f"Welcome to Depl0y, {user.username}!",
                message="Your account is ready. Explore the dashboard to manage your Proxmox infrastructure.",
                type="success",
                action_url="/dashboard",
            )
            db.add(welcome)
            db.commit()
        except Exception:
            pass

    token_version = getattr(user, "token_version", 0) or 0
    access_token = create_access_token(data={"sub": user.username, "tv": token_version})
    refresh_token_value = create_refresh_token(data={"sub": user.username, "tv": token_version})

    # Store refresh token in DB for rotation/revocation
    from app.core.config import settings
    _store_refresh_token(
        db,
        user_id=user.id,
        token=refresh_token_value,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_delta_days=getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 30),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_value,
        "token_type": "bearer",
    }


@router.post("/login")
async def login(credentials: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Login endpoint — step 1 of 2.

    If the user has 2FA enabled, returns:
        {requires_2fa: true, temp_token: "..."}

    Otherwise returns the standard Token response.
    """
    import random

    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    # Brute-force: check if account is locked
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
        # Audit log: failed login
        try:
            from app.api.audit import log_audit_event
            log_audit_event(
                db,
                action="login_failed",
                user_id=user.id if user else None,
                resource_type="user",
                details={"username": credentials.username, "reason": "bad_password"},
                ip_address=client_ip,
                user_agent=user_agent,
                success=False,
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        _record_login_attempt(db, user.id, credentials.username, client_ip, user_agent, False, "account_disabled")
        raise HTTPException(status_code=400, detail="Inactive user")

    # If 2FA is enabled, issue a short-lived temp token and require second step
    if user.totp_enabled:
        _cleanup_temp_tokens()
        temp_token = secrets.token_urlsafe(32)
        _temp_tokens[temp_token] = {
            "username": user.username,
            "ip_address": client_ip,
            "user_agent": user_agent,
            "expires_at": datetime.utcnow() + timedelta(seconds=_TEMP_TOKEN_TTL),
        }
        return {"requires_2fa": True, "temp_token": temp_token}

    # No 2FA — complete login immediately
    _clear_failed_attempts(db, credentials.username)
    _record_login_attempt(db, user.id, credentials.username, client_ip, user_agent, True, None)

    # Audit log: successful login
    try:
        from app.api.audit import log_audit_event
        log_audit_event(
            db,
            action="login",
            user_id=user.id,
            resource_type="user",
            details={"username": user.username},
            ip_address=client_ip,
            user_agent=user_agent,
            success=True,
        )
    except Exception:
        pass

    return _finalize_login(db, user, client_ip, user_agent)


@router.post("/2fa/login", response_model=Token)
async def login_2fa(data: TwoFactorLoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Login step 2: verify TOTP or backup code against temp_token from step 1.
    Returns full JWT tokens on success.
    """
    _cleanup_temp_tokens()

    entry = _temp_tokens.get(data.temp_token)
    if not entry or entry["expires_at"] < datetime.utcnow():
        # Remove stale token if present
        _temp_tokens.pop(data.temp_token, None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired 2FA session. Please log in again.",
        )

    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    username = entry["username"]

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        _temp_tokens.pop(data.temp_token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Check lockout again (in case they were locked during the 2FA window)
    lockout_msg = _check_account_lockout(db, username)
    if lockout_msg:
        _temp_tokens.pop(data.temp_token, None)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=lockout_msg)

    code = data.totp_code.strip().upper()

    # Try TOTP first
    totp_valid = user.totp_secret and verify_totp_code(user.totp_secret, code)

    # If TOTP fails, try backup codes
    if not totp_valid:
        backup_valid = False
        if len(code) == 8:
            # Check unused backup codes
            backup_codes = (
                db.query(TotpBackupCode)
                .filter(TotpBackupCode.user_id == user.id, TotpBackupCode.used == False)
                .all()
            )
            for bc in backup_codes:
                if verify_password(code, bc.code_hash):
                    # Mark as used
                    bc.used = True
                    bc.used_at = datetime.utcnow()
                    db.commit()
                    backup_valid = True
                    break

        if not backup_valid:
            _record_failed_login(db, username, client_ip, user_agent)
            _record_login_attempt(db, user.id, username, client_ip, user_agent, False, "2fa_failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code",
            )

    # Successful 2FA — consume temp token
    del _temp_tokens[data.temp_token]
    _clear_failed_attempts(db, username)
    _record_login_attempt(db, user.id, username, client_ip, user_agent, True, None)

    # Audit log: successful 2FA login
    try:
        from app.api.audit import log_audit_event
        log_audit_event(
            db,
            action="login",
            user_id=user.id,
            resource_type="user",
            details={"username": user.username, "method": "2fa"},
            ip_address=client_ip,
            user_agent=user_agent,
            success=True,
        )
    except Exception:
        pass

    return _finalize_login(db, user, client_ip, user_agent)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    db: Session = Depends(get_db),
):
    """
    Refresh token rotation:
    - Validates old refresh token against DB (must exist, not revoked, not expired)
    - Revokes old token
    - Issues new access + refresh token pair
    """
    token_value = body.refresh_token
    payload = decode_token(token_value)

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

    # Validate against DB store (rotation check)
    rt = _validate_refresh_token(db, token_value)
    if rt is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or expired",
        )

    # Revoke the old token (rotation)
    _revoke_refresh_token(db, token_value)

    # Issue new pair
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    tv = user_token_version

    access_token = create_access_token(data={"sub": user.username, "tv": tv})
    new_refresh_token_value = create_refresh_token(data={"sub": user.username, "tv": tv})

    from app.core.config import settings
    _store_refresh_token(
        db,
        user_id=user.id,
        token=new_refresh_token_value,
        ip_address=client_ip,
        user_agent=user_agent,
        expires_delta_days=getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 30),
    )

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token_value,
        "token_type": "bearer",
    }


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


@router.post("/logout")
async def logout(
    data: LogoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the current refresh token, invalidating this session."""
    if data.refresh_token:
        _revoke_refresh_token(db, data.refresh_token)
    return {"message": "Logged out successfully"}


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List active (non-revoked, non-expired) refresh tokens for the current user."""
    now = datetime.utcnow()
    sessions = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > now,
        )
        .order_by(RefreshToken.created_at.desc())
        .all()
    )
    return sessions


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke a specific session by ID (must belong to current user)."""
    rt = db.query(RefreshToken).filter(
        RefreshToken.id == session_id,
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked == False,
    ).first()
    if not rt:
        raise HTTPException(status_code=404, detail="Session not found")
    rt.revoked = True
    rt.revoked_at = datetime.utcnow()
    db.commit()
    return {"message": "Session revoked"}


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

    # Audit log: password change
    try:
        from app.api.audit import log_audit_event
        log_audit_event(
            db,
            action="password_change",
            user_id=current_user.id,
            resource_type="user",
            details={"username": current_user.username},
            success=True,
        )
    except Exception:
        pass

    return {"message": "Password changed"}


# ── TOTP 2FA ──────────────────────────────────────────────────────────────────

@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def setup_totp(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Generate a new TOTP secret and return it with a QR code URI.
    The secret is stored temporarily (totp_enabled remains False until /totp/verify succeeds).
    """
    secret = generate_totp_secret()
    uri = generate_totp_uri(secret, current_user.username)

    # Generate QR code as base64 PNG
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

    # Store secret (not yet enabled) — frontend must call /totp/verify to activate
    current_user.totp_secret = secret
    current_user.totp_enabled = False
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
    """
    Verify the TOTP code against the pending secret and enable 2FA.
    Returns backup codes on first enable (one-time display).
    """
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="TOTP not set up. Call /totp/setup first.")

    if not verify_totp_code(current_user.totp_secret, request.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    # Enable 2FA
    current_user.totp_enabled = True
    db.commit()

    # Generate and return backup codes
    codes = _generate_backup_codes()
    # Delete any existing backup codes for this user
    db.query(TotpBackupCode).filter(TotpBackupCode.user_id == current_user.id).delete()
    for code in codes:
        bc = TotpBackupCode(
            user_id=current_user.id,
            code_hash=get_password_hash(code),
            used=False,
        )
        db.add(bc)
    db.commit()

    # Audit log: 2FA enabled
    try:
        from app.api.audit import log_audit_event
        log_audit_event(
            db,
            action="2fa_enabled",
            user_id=current_user.id,
            resource_type="user",
            details={"username": current_user.username},
            success=True,
        )
    except Exception:
        pass

    return {
        "message": "2FA enabled successfully",
        "backup_codes": codes,
        "backup_codes_remaining": len(codes),
    }


@router.post("/totp/disable")
async def disable_totp(
    request: TOTPDisableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Disable TOTP 2FA. Requires current TOTP code or a valid backup code.
    """
    if not current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA not enabled")

    code = request.code.strip().upper()
    totp_valid = current_user.totp_secret and verify_totp_code(current_user.totp_secret, code)

    if not totp_valid:
        # Try backup code
        if len(code) == 8:
            backup_codes = (
                db.query(TotpBackupCode)
                .filter(TotpBackupCode.user_id == current_user.id, TotpBackupCode.used == False)
                .all()
            )
            for bc in backup_codes:
                if verify_password(code, bc.code_hash):
                    totp_valid = True
                    break

    if not totp_valid:
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    # Disable TOTP and clean up
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.query(TotpBackupCode).filter(TotpBackupCode.user_id == current_user.id).delete()
    db.commit()

    # Audit log: 2FA disabled
    try:
        from app.api.audit import log_audit_event
        log_audit_event(
            db,
            action="2fa_disabled",
            user_id=current_user.id,
            resource_type="user",
            details={"username": current_user.username},
            success=True,
        )
    except Exception:
        pass

    return {"message": "2FA disabled successfully"}


@router.post("/totp/backup-codes", response_model=BackupCodesResponse)
async def regenerate_backup_codes(
    request: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Regenerate backup codes. Requires current TOTP code to confirm identity.
    Returns new plaintext codes once — old codes are immediately invalidated.
    """
    if not current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA not enabled")

    if not verify_totp_code(current_user.totp_secret, request.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    # Delete existing backup codes and generate new ones
    db.query(TotpBackupCode).filter(TotpBackupCode.user_id == current_user.id).delete()
    codes = _generate_backup_codes()
    for code in codes:
        bc = TotpBackupCode(
            user_id=current_user.id,
            code_hash=get_password_hash(code),
            used=False,
        )
        db.add(bc)
    db.commit()

    return {"codes": codes, "remaining": len(codes)}


@router.get("/totp/backup-codes/count")
async def get_backup_code_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the number of unused backup codes remaining for the current user."""
    remaining = _count_remaining_backup_codes(db, current_user.id)
    return {"remaining": remaining}


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

    # Audit log: API key created
    try:
        from app.api.audit import log_audit_event
        log_audit_event(
            db,
            action="api_key_created",
            user_id=current_user.id,
            resource_type="api_key",
            resource_id=api_key.id,
            details={"name": api_key.name, "key_prefix": api_key.key_prefix},
            success=True,
        )
    except Exception:
        pass

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

    # Audit log: API key revoked
    try:
        from app.api.audit import log_audit_event
        log_audit_event(
            db,
            action="api_key_revoked",
            user_id=current_user.id,
            resource_type="api_key",
            resource_id=api_key.id,
            details={"name": api_key.name, "key_prefix": api_key.key_prefix},
            success=True,
        )
    except Exception:
        pass

    return {"message": "API key revoked"}
