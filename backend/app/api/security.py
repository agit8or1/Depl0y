"""Security management API — IP lists, GeoIP, brute-force, lockouts, events."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.api.auth import require_admin, get_current_user
from app.models.database import SystemSettings
from app.models.security import (
    FailedLoginAttempt,
    AccountLockout,
    SecurityEvent,
    IPBanList,
    GeoIPRule,
    LoginAttempt,
)
from app.models.database import User
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────

class IPBanListCreate(BaseModel):
    ip_address: str
    list_type: str  # "ban" or "allow"
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None


class IPBanListResponse(BaseModel):
    id: int
    ip_address: str
    list_type: str
    reason: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool

    class Config:
        from_attributes = True


class GeoIPRuleCreate(BaseModel):
    country_code: str
    country_name: str
    action: str  # "block" or "allow"


class GeoIPRuleResponse(BaseModel):
    id: int
    country_code: str
    country_name: str
    action: str
    created_by: Optional[int]
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class SecuritySettingsUpdate(BaseModel):
    brute_force_enabled: Optional[bool] = None
    brute_force_max_attempts: Optional[int] = None
    brute_force_lockout_minutes: Optional[int] = None
    ip_list_mode: Optional[str] = None          # "blacklist" or "whitelist"
    geoip_enabled: Optional[bool] = None
    geoip_mode: Optional[str] = None            # "blacklist" or "whitelist"


class LockoutResponse(BaseModel):
    id: int
    username: str
    locked_at: datetime
    locked_until: datetime
    reason: Optional[str]
    failed_attempts: int

    class Config:
        from_attributes = True


class FailedLoginResponse(BaseModel):
    id: int
    username: str
    ip_address: str
    user_agent: Optional[str]
    attempted_at: datetime
    success: bool

    class Config:
        from_attributes = True


class SecurityEventResponse(BaseModel):
    id: int
    event_type: str
    severity: Optional[str]
    user_id: Optional[int]
    username: Optional[str]
    ip_address: Optional[str]
    details: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────

def _set_setting(db: Session, key: str, value: str, description: str = ""):
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        db.add(SystemSettings(key=key, value=value, description=description))
    db.commit()


def _get_setting(db: Session, key: str, default: str) -> str:
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    return row.value if row else default


# ─────────────────────────────────────────────────────────────
# Security settings
# ─────────────────────────────────────────────────────────────

@router.get("/settings")
async def get_security_settings(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all security settings."""
    return {
        "brute_force_enabled": _get_setting(db, "brute_force_enabled", "1") == "1",
        "brute_force_max_attempts": int(_get_setting(db, "brute_force_max_attempts", "5")),
        "brute_force_lockout_minutes": int(_get_setting(db, "brute_force_lockout_minutes", "15")),
        "ip_list_mode": _get_setting(db, "ip_list_mode", "blacklist"),
        "geoip_enabled": _get_setting(db, "geoip_enabled", "false") == "true",
        "geoip_mode": _get_setting(db, "geoip_mode", "blacklist"),
    }


@router.put("/settings")
async def update_security_settings(
    data: SecuritySettingsUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update security settings."""
    if data.brute_force_enabled is not None:
        _set_setting(db, "brute_force_enabled", "1" if data.brute_force_enabled else "0",
                     "Enable brute force protection")
    if data.brute_force_max_attempts is not None:
        if data.brute_force_max_attempts < 1:
            raise HTTPException(status_code=400, detail="max_attempts must be >= 1")
        _set_setting(db, "brute_force_max_attempts", str(data.brute_force_max_attempts),
                     "Max failed login attempts before lockout")
    if data.brute_force_lockout_minutes is not None:
        if data.brute_force_lockout_minutes < 1:
            raise HTTPException(status_code=400, detail="lockout_minutes must be >= 1")
        _set_setting(db, "brute_force_lockout_minutes", str(data.brute_force_lockout_minutes),
                     "Account lockout duration in minutes")
    if data.ip_list_mode is not None:
        if data.ip_list_mode not in ("blacklist", "whitelist"):
            raise HTTPException(status_code=400, detail="ip_list_mode must be 'blacklist' or 'whitelist'")
        _set_setting(db, "ip_list_mode", data.ip_list_mode, "IP list mode: blacklist or whitelist")
    if data.geoip_enabled is not None:
        _set_setting(db, "geoip_enabled", "true" if data.geoip_enabled else "false",
                     "Enable GeoIP filtering")
    if data.geoip_mode is not None:
        if data.geoip_mode not in ("blacklist", "whitelist"):
            raise HTTPException(status_code=400, detail="geoip_mode must be 'blacklist' or 'whitelist'")
        _set_setting(db, "geoip_mode", data.geoip_mode, "GeoIP mode: blacklist or whitelist")

    return {"message": "Security settings updated"}


@router.get("/lookup-ip/{ip_address}")
async def lookup_ip_country(
    ip_address: str,
    current_user: User = Depends(require_admin),
):
    """Look up the country for an IP address using ip-api.com."""
    import urllib.request, json as _json, ipaddress as _ip
    try:
        _ip.ip_address(ip_address)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid IP address")
    try:
        url = f"http://ip-api.com/json/{ip_address}?fields=status,country,countryCode,city,isp,org"
        req = urllib.request.Request(url, headers={"User-Agent": "depl0y/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read().decode())
            if data.get("status") == "success":
                return {
                    "ip": ip_address,
                    "country": data.get("country"),
                    "country_code": data.get("countryCode"),
                    "city": data.get("city"),
                    "isp": data.get("isp"),
                    "org": data.get("org"),
                }
            return {"ip": ip_address, "country": None, "country_code": None, "error": "Private or reserved IP"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GeoIP lookup failed: {str(e)}")


# ─────────────────────────────────────────────────────────────
# Brute force — lockouts & failed attempts
# ─────────────────────────────────────────────────────────────

@router.get("/lockouts", response_model=List[LockoutResponse])
async def list_lockouts(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all currently locked accounts."""
    now = datetime.utcnow()
    lockouts = (
        db.query(AccountLockout)
        .filter(AccountLockout.locked_until > now)
        .order_by(AccountLockout.locked_at.desc())
        .all()
    )
    return lockouts


@router.delete("/lockouts/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def unlock_account(
    username: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually unlock a locked account and clear its failed attempts."""
    lockout = db.query(AccountLockout).filter(AccountLockout.username == username).first()
    if lockout:
        db.delete(lockout)
    db.query(FailedLoginAttempt).filter(FailedLoginAttempt.username == username).delete()
    db.commit()
    return None


@router.get("/failed-logins", response_model=List[FailedLoginResponse])
async def list_failed_logins(
    limit: int = Query(100, le=500),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List recent failed login attempts."""
    attempts = (
        db.query(FailedLoginAttempt)
        .filter(FailedLoginAttempt.success == False)
        .order_by(FailedLoginAttempt.attempted_at.desc())
        .limit(limit)
        .all()
    )
    return attempts


# ─────────────────────────────────────────────────────────────
# IP Ban / Allow list
# ─────────────────────────────────────────────────────────────

@router.get("/ip-list", response_model=List[IPBanListResponse])
async def list_ip_entries(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all IP ban/allow entries."""
    return db.query(IPBanList).order_by(IPBanList.created_at.desc()).all()


@router.post("/ip-list", response_model=IPBanListResponse, status_code=status.HTTP_201_CREATED)
async def create_ip_entry(
    data: IPBanListCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Add an IP address or CIDR range to the ban or allow list."""
    import ipaddress
    # Validate IP/CIDR
    try:
        ipaddress.ip_network(data.ip_address, strict=False)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid IP address or CIDR range")

    if data.list_type not in ("ban", "allow"):
        raise HTTPException(status_code=400, detail="list_type must be 'ban' or 'allow'")

    entry = IPBanList(
        ip_address=data.ip_address,
        list_type=data.list_type,
        reason=data.reason,
        created_by=current_user.id,
        expires_at=data.expires_at,
        is_active=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    logger.info(f"IP {data.list_type} entry added: {data.ip_address} by {current_user.username}")
    return entry


@router.delete("/ip-list/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ip_entry(
    entry_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Remove an IP entry from the list."""
    entry = db.query(IPBanList).filter(IPBanList.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return None


@router.patch("/ip-list/{entry_id}/toggle")
async def toggle_ip_entry(
    entry_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Toggle an IP entry active/inactive."""
    entry = db.query(IPBanList).filter(IPBanList.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    entry.is_active = not entry.is_active
    db.commit()
    return {"id": entry.id, "is_active": entry.is_active}


# ─────────────────────────────────────────────────────────────
# GeoIP rules
# ─────────────────────────────────────────────────────────────

@router.get("/geoip", response_model=List[GeoIPRuleResponse])
async def list_geoip_rules(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all GeoIP country rules."""
    return db.query(GeoIPRule).order_by(GeoIPRule.country_name).all()


@router.post("/geoip", response_model=GeoIPRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_geoip_rule(
    data: GeoIPRuleCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Add a GeoIP country block/allow rule."""
    if data.action not in ("block", "allow"):
        raise HTTPException(status_code=400, detail="action must be 'block' or 'allow'")
    code = data.country_code.upper()
    if len(code) != 2:
        raise HTTPException(status_code=400, detail="country_code must be ISO 3166-1 alpha-2 (2 chars)")

    existing = db.query(GeoIPRule).filter(GeoIPRule.country_code == code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Rule for {code} already exists")

    rule = GeoIPRule(
        country_code=code,
        country_name=data.country_name,
        action=data.action,
        created_by=current_user.id,
        is_active=True,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    logger.info(f"GeoIP rule added: {code} ({data.action}) by {current_user.username}")
    return rule


@router.delete("/geoip/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_geoip_rule(
    rule_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Remove a GeoIP rule."""
    rule = db.query(GeoIPRule).filter(GeoIPRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return None


@router.patch("/geoip/{rule_id}/toggle")
async def toggle_geoip_rule(
    rule_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Toggle a GeoIP rule active/inactive."""
    rule = db.query(GeoIPRule).filter(GeoIPRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = not rule.is_active
    db.commit()
    return {"id": rule.id, "is_active": rule.is_active}


# ─────────────────────────────────────────────────────────────
# Security events
# ─────────────────────────────────────────────────────────────

@router.get("/events", response_model=List[SecurityEventResponse])
async def list_security_events(
    limit: int = Query(100, le=500),
    event_type: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List recent security events."""
    query = db.query(SecurityEvent)
    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)
    events = query.order_by(SecurityEvent.created_at.desc()).limit(limit).all()
    return events


# ─────────────────────────────────────────────────────────────
# Login history (comprehensive login_attempts table)
# ─────────────────────────────────────────────────────────────

class LoginAttemptResponse(BaseModel):
    id: int
    user_id: Optional[int]
    username_attempted: str
    ip_address: str
    user_agent: Optional[str]
    success: bool
    failure_reason: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


@router.get("/login-history", response_model=List[LoginAttemptResponse])
async def get_login_history(
    limit: int = Query(50, le=500),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List last N login attempts (both successes and failures), admin only."""
    attempts = (
        db.query(LoginAttempt)
        .order_by(LoginAttempt.timestamp.desc())
        .limit(limit)
        .all()
    )
    return attempts


# ─────────────────────────────────────────────────────────────
# Password policy
# ─────────────────────────────────────────────────────────────

class PasswordPolicyResponse(BaseModel):
    min_length: int
    require_uppercase: bool
    require_numbers: bool
    require_symbols: bool


class PasswordPolicyUpdate(BaseModel):
    min_length: Optional[int] = None
    require_uppercase: Optional[bool] = None
    require_numbers: Optional[bool] = None
    require_symbols: Optional[bool] = None


@router.get("/password-policy", response_model=PasswordPolicyResponse)
async def get_password_policy(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get current password policy settings."""
    return {
        "min_length": int(_get_setting(db, "pw_min_length", "8")),
        "require_uppercase": _get_setting(db, "pw_require_uppercase", "false") == "true",
        "require_numbers": _get_setting(db, "pw_require_numbers", "false") == "true",
        "require_symbols": _get_setting(db, "pw_require_symbols", "false") == "true",
    }


@router.patch("/password-policy", response_model=PasswordPolicyResponse)
async def update_password_policy(
    data: PasswordPolicyUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update password policy settings."""
    if data.min_length is not None:
        if data.min_length < 6 or data.min_length > 128:
            raise HTTPException(status_code=400, detail="min_length must be between 6 and 128")
        _set_setting(db, "pw_min_length", str(data.min_length), "Minimum password length")
    if data.require_uppercase is not None:
        _set_setting(db, "pw_require_uppercase", "true" if data.require_uppercase else "false",
                     "Require uppercase letters in password")
    if data.require_numbers is not None:
        _set_setting(db, "pw_require_numbers", "true" if data.require_numbers else "false",
                     "Require numbers in password")
    if data.require_symbols is not None:
        _set_setting(db, "pw_require_symbols", "true" if data.require_symbols else "false",
                     "Require symbols in password")

    return {
        "min_length": int(_get_setting(db, "pw_min_length", "8")),
        "require_uppercase": _get_setting(db, "pw_require_uppercase", "false") == "true",
        "require_numbers": _get_setting(db, "pw_require_numbers", "false") == "true",
        "require_symbols": _get_setting(db, "pw_require_symbols", "false") == "true",
    }


# ─────────────────────────────────────────────────────────────
# 2FA overview
# ─────────────────────────────────────────────────────────────

class UserTotpStatusResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    totp_enabled: bool
    is_active: bool

    class Config:
        from_attributes = True


@router.get("/2fa-overview", response_model=List[UserTotpStatusResponse])
async def get_2fa_overview(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get 2FA status for all users, admin only."""
    users = db.query(User).order_by(User.username).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role.value if hasattr(u.role, "value") else u.role,
            "totp_enabled": u.totp_enabled,
            "is_active": u.is_active,
        }
        for u in users
    ]
