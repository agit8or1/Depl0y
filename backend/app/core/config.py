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

    return "2.2.112"


def _persistent_secret(env_name: str, filename: str, generate) -> str:
    """Return a secret from the environment, or from a key file that persists.

    Installer deploys set these in /etc/depl0y/config.env. For any other deploy
    we generate the secret once and keep it in DEPL0Y_KEY_DIR (default
    /var/lib/depl0y) with mode 0600, so encrypted DB fields stay readable and
    sessions survive a restart. If the directory can't be written we fall back
    to a per-process value and log loudly.
    """
    value = os.getenv(env_name)
    if value:
        return value
    import logging
    log = logging.getLogger("depl0y.config")
    key_dir = os.getenv("DEPL0Y_KEY_DIR", "/var/lib/depl0y")
    path = os.path.join(key_dir, filename)
    try:
        with open(path, "r") as fh:
            stored = fh.read().strip()
        if stored:
            return stored
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.error("Cannot read %s (%s)", path, exc)
    new_value = generate()
    try:
        os.makedirs(key_dir, mode=0o700, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(new_value + "\n")
        log.warning("%s not set; generated one and saved it to %s. Back this file up.", env_name, path)
        return new_value
    except FileExistsError:
        # Another worker created it first; use theirs.
        with open(path, "r") as fh:
            return fh.read().strip()
    except OSError as exc:
        log.critical(
            "%s not set and %s is not writable (%s). Using a temporary value: "
            "data encrypted with it will be unreadable after a restart. "
            "Set %s in the environment.", env_name, path, exc, env_name,
        )
        return new_value


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
    SECRET_KEY: str = _persistent_secret(
        "SECRET_KEY", "secret_key", lambda: __import__("secrets").token_urlsafe(64)
    )
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

    # CORS — set CORS_ORIGINS in /etc/depl0y/config.env to a comma-separated list of
    # allowed browser origins (protocol + host + optional :port), e.g.
    #   CORS_ORIGINS=https://deploy.example.com,https://panel.example.com
    # When unset we fall back to the local-dev defaults. The localhost entries are
    # kept in both cases so `npm run dev` against a production backend still works.
    BACKEND_CORS_ORIGINS: list = sorted({
        *(o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()),
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    })

    # ISO Storage
    ISO_STORAGE_PATH: str = os.getenv("ISO_STORAGE_PATH", "/var/lib/depl0y/isos")
    MAX_ISO_SIZE: int = 10 * 1024 * 1024 * 1024  # 10GB

    # Upload directory for cloud images and other files
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/var/lib/depl0y")

    # Proxmox polling
    PROXMOX_POLL_INTERVAL: int = 60  # seconds

    # Encryption key for sensitive data
    # SECURITY: never a fresh key per start — that would make every stored
    # secret unreadable after a restart. See _persistent_secret.
    ENCRYPTION_KEY: str = _persistent_secret(
        "ENCRYPTION_KEY", "encryption.key", lambda: Fernet.generate_key().decode()
    )

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

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: int = 600  # requests per minute per IP (general)
    RATE_LIMIT_AUTH: int = 10      # requests per minute per IP (auth endpoints)

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "/var/log/depl0y/app.log")

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
