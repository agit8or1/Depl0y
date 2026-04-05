"""Security-related database models"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from app.models.database import Base


class FailedLoginAttempt(Base):
    """Track failed login attempts for account lockout"""
    __tablename__ = "failed_login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), index=True, nullable=False)
    ip_address = Column(String(45), nullable=False)  # IPv6 compatible
    user_agent = Column(String(500))
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())
    success = Column(Boolean, default=False)


class AccountLockout(Base):
    """Track locked accounts"""
    __tablename__ = "account_lockouts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    locked_at = Column(DateTime(timezone=True), server_default=func.now())
    locked_until = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String(200))
    failed_attempts = Column(Integer, default=0)


class TokenBlacklist(Base):
    """Blacklist for revoked JWT tokens"""
    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(100), unique=True, index=True, nullable=False)  # JWT ID
    token_type = Column(String(20))  # access or refresh
    user_id = Column(Integer, nullable=False)
    revoked_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String(200))


class SecurityEvent(Base):
    """Log security-related events"""
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), index=True, nullable=False)  # login_failed, account_locked, token_revoked, etc.
    severity = Column(String(20))  # low, medium, high, critical
    user_id = Column(Integer, nullable=True)
    username = Column(String(100), index=True)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    details = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class IPBanList(Base):
    """IP ban/allow list for access control"""
    __tablename__ = "ip_ban_list"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(50), nullable=False, index=True)  # Single IP or CIDR range
    list_type = Column(String(10), nullable=False)  # "ban" or "allow"
    reason = Column(String(500), nullable=True)
    created_by = Column(Integer, nullable=True)  # user_id
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # NULL = permanent
    is_active = Column(Boolean, default=True, nullable=False)


class GeoIPRule(Base):
    """GeoIP-based access control rules"""
    __tablename__ = "geoip_rules"

    id = Column(Integer, primary_key=True, index=True)
    country_code = Column(String(2), nullable=False, index=True)  # ISO 3166-1 alpha-2
    country_name = Column(String(100), nullable=False)
    action = Column(String(10), nullable=False)  # "block" or "allow"
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True, nullable=False)


class LoginAttempt(Base):
    """Comprehensive login attempt log — both successes and failures."""
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)  # NULL for unknown usernames
    username_attempted = Column(String(100), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(500), nullable=True)
    success = Column(Boolean, nullable=False, default=False)
    failure_reason = Column(String(200), nullable=True)  # "bad_password", "2fa_failed", "account_locked", etc.
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
