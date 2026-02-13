"""Application configuration"""
from pydantic_settings import BaseSettings
from typing import Optional
import os
from cryptography.fernet import Fernet


def get_app_version():
    """Get application version from database or fallback to default"""
    try:
        import sqlite3
        db_path = os.getenv("DATABASE_URL", "sqlite:////var/lib/depl0y/db/depl0y.db")
        # Extract path from sqlite URL
        if db_path.startswith("sqlite:///"):
            db_path = db_path.replace("sqlite:///", "")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_settings WHERE key = 'app_version'")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
    except Exception as e:
        # Fallback to hardcoded version if database query fails
        pass

    return "1.3.11"  # Fix update process with dedicated upgrade script


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "Depl0y"
    APP_VERSION: str = get_app_version()
    DEBUG: bool = False

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Security
    # SECURITY: Generate strong random SECRET_KEY if not set via environment
    SECRET_KEY: str = os.getenv("SECRET_KEY") or __import__('secrets').token_urlsafe(64)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Password hashing
    PASSWORD_BCRYPT_ROUNDS: int = 12

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:////var/lib/depl0y/db/depl0y.db"
    )

    # CORS
    BACKEND_CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ]

    # ISO Storage
    ISO_STORAGE_PATH: str = os.getenv("ISO_STORAGE_PATH", "/var/lib/depl0y/isos")
    MAX_ISO_SIZE: int = 10 * 1024 * 1024 * 1024  # 10GB

    # Upload directory for cloud images and other files
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/var/lib/depl0y")

    # Proxmox polling
    PROXMOX_POLL_INTERVAL: int = 60  # seconds

    # Encryption key for sensitive data
    # SECURITY: Auto-generate strong encryption key if not set via environment
    # This prevents application crashes when encrypting/decrypting credentials
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY") or Fernet.generate_key().decode()

    # Cloud-init
    CLOUDINIT_TEMPLATE_PATH: str = os.getenv(
        "CLOUDINIT_TEMPLATE_PATH",
        "/var/lib/depl0y/cloud-init"
    )

    # SSH
    SSH_TIMEOUT: int = 30
    SSH_KEY_PATH: str = os.getenv("SSH_KEY_PATH", "/var/lib/depl0y/ssh_keys")

    # Default VM settings
    DEFAULT_QEMU_AGENT_INSTALL: bool = True
    DEFAULT_LINUX_PARTITION_SCHEME: str = "single"  # single or custom

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "/var/log/depl0y/app.log")

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
