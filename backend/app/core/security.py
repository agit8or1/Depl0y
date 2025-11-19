"""Security utilities for authentication and encryption"""
from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
import bcrypt
import pyotp
import secrets
from cryptography.fernet import Fernet
from app.core.config import settings

# Encryption for sensitive data
cipher_suite = None
if settings.ENCRYPTION_KEY:
    cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


# TOTP (2FA) functions
def generate_totp_secret() -> str:
    """Generate a new TOTP secret"""
    return pyotp.random_base32()


def generate_totp_uri(secret: str, username: str, issuer: str = "Depl0y") -> str:
    """Generate TOTP provisioning URI for QR code"""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    """Verify TOTP code"""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# Encryption functions for sensitive data
def encrypt_data(data: str) -> str:
    """Encrypt sensitive data"""
    if not cipher_suite:
        raise ValueError("ENCRYPTION_KEY not configured")
    return cipher_suite.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    if not cipher_suite:
        raise ValueError("ENCRYPTION_KEY not configured")
    return cipher_suite.decrypt(encrypted_data.encode()).decode()


def generate_api_key() -> str:
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)
