"""Authentication API routes"""
from fastapi import APIRouter, Depends, HTTPException, status
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


@router.post("/login", response_model=Token)
async def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """Login endpoint"""
    user = db.query(User).filter(User.username == credentials.username).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code",
            )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create tokens
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
