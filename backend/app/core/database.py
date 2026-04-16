"""Database connection and session management"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Build engine kwargs — SQLite needs check_same_thread=False for background threads
_engine_kwargs: dict = {"pool_pre_ping": True}
if settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

# Create database engine
engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Dependency to get database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database tables
    """
    from app.models.database import Base
    import app.models.security       # ensure security tables are registered   # noqa: F401
    import app.models.alert_models   # ensure alert tables are registered      # noqa: F401
    import app.models.analysis_models  # ensure analysis tables are registered # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Add new columns to proxmox_nodes if they don't already exist (migration helper)
    from sqlalchemy import text
    new_node_columns = [
        ("vm_count", "INTEGER DEFAULT 0"),
        ("lxc_count", "INTEGER DEFAULT 0"),
        ("idrac_hostname", "VARCHAR(255)"),
        ("idrac_port", "INTEGER DEFAULT 443"),
        ("idrac_username", "VARCHAR(100)"),
        ("idrac_password", "VARCHAR(255)"),
        ("idrac_type", "VARCHAR(20)"),
        ("idrac_use_ssh", "BOOLEAN DEFAULT 0"),
        ("notes", "TEXT"),
    ]
    # Add new columns to proxmox_hosts if they don't already exist (migration helper)
    new_host_columns = [
        ("latitude", "REAL"),
        ("longitude", "REAL"),
        ("idrac_hostname", "VARCHAR(255)"),
        ("idrac_port", "INTEGER DEFAULT 443"),
        ("idrac_username", "VARCHAR(100)"),
        ("idrac_password", "VARCHAR(255)"),
        ("idrac_type", "VARCHAR(20)"),
        ("idrac_use_ssh", "BOOLEAN DEFAULT 0"),
        ("notes", "TEXT"),
    ]
    # Use a fresh connection per ALTER TABLE so that a failure (e.g. table didn't
    # exist in an older version) doesn't leave the connection in a dirty transaction
    # state that silently swallows all subsequent column additions.
    for col_name, col_def in new_node_columns:
        try:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE proxmox_nodes ADD COLUMN {col_name} {col_def}"))
                conn.commit()
        except Exception:
            pass  # Column already exists or table doesn't exist yet
    for col_name, col_def in new_host_columns:
        try:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE proxmox_hosts ADD COLUMN {col_name} {col_def}"))
                conn.commit()
        except Exception:
            pass  # Column already exists

    with engine.connect() as conn:
        # Create api_keys table if it doesn't exist yet (for older deployments)
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    name VARCHAR(100) NOT NULL,
                    key_hash VARCHAR(255) NOT NULL UNIQUE,
                    key_prefix VARCHAR(8) NOT NULL,
                    last_used DATETIME,
                    expires_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN NOT NULL DEFAULT 1
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Add token_version to users if missing (session invalidation)
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"))
            conn.commit()
        except Exception:
            pass

        # Create login_attempts table for comprehensive login history
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username_attempted VARCHAR(100) NOT NULL,
                    ip_address VARCHAR(45) NOT NULL,
                    user_agent VARCHAR(500),
                    success BOOLEAN NOT NULL DEFAULT 0,
                    failure_reason VARCHAR(200),
                    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Create notifications table for in-app notification center
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    title VARCHAR(255) NOT NULL,
                    message TEXT NOT NULL,
                    type VARCHAR(20) NOT NULL DEFAULT 'info',
                    read BOOLEAN NOT NULL DEFAULT 0,
                    action_url VARCHAR(500),
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Create webhook_deliveries table for delivery log
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    webhook_id VARCHAR(36) NOT NULL,
                    event VARCHAR(100) NOT NULL,
                    status_code INTEGER,
                    success BOOLEAN NOT NULL DEFAULT 0,
                    response_body TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        except Exception:
            pass

    # TOTP ALTER TABLE loop uses fresh connections (see pattern above)
    for col_name, col_def in [
        ("totp_secret", "VARCHAR(32)"),
        ("totp_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"))
                conn.commit()
        except Exception:
            pass
    with engine.connect() as conn:

        # Create totp_backup_codes table
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS totp_backup_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    code_hash VARCHAR(255) NOT NULL,
                    used BOOLEAN NOT NULL DEFAULT 0,
                    used_at DATETIME
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Create refresh_tokens table for token rotation
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    token_hash VARCHAR(255) NOT NULL UNIQUE,
                    ip_address VARCHAR(50),
                    user_agent VARCHAR(500),
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL,
                    revoked BOOLEAN NOT NULL DEFAULT 0,
                    revoked_at DATETIME
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Create vm_groups table for logical VM groupings
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS vm_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    description VARCHAR(500),
                    color VARCHAR(7) NOT NULL DEFAULT '#3b82f6',
                    host_id INTEGER REFERENCES proxmox_hosts(id),
                    vmids TEXT NOT NULL DEFAULT '[]',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Create alert_rules table for user-configured alert rules
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(200) NOT NULL,
                    rule_type VARCHAR(50) NOT NULL,
                    threshold REAL,
                    host_id INTEGER REFERENCES proxmox_hosts(id),
                    node VARCHAR(100),
                    enabled BOOLEAN NOT NULL DEFAULT 1,
                    notify_in_app BOOLEAN NOT NULL DEFAULT 1,
                    notify_webhook BOOLEAN NOT NULL DEFAULT 0,
                    notify_slack BOOLEAN NOT NULL DEFAULT 0,
                    cooldown_minutes INTEGER NOT NULL DEFAULT 60,
                    last_fired_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Create alert_events table for fired alert history
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS alert_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_id INTEGER REFERENCES alert_rules(id),
                    rule_key VARCHAR(255),
                    severity VARCHAR(20) NOT NULL DEFAULT 'warning',
                    title VARCHAR(255) NOT NULL,
                    message TEXT NOT NULL,
                    fired_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    acknowledged BOOLEAN NOT NULL DEFAULT 0,
                    acknowledged_at DATETIME,
                    acknowledged_by INTEGER REFERENCES users(id)
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Create recommendations table for analysis engine
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host_id INTEGER REFERENCES proxmox_hosts(id),
                    node VARCHAR(100),
                    vmid INTEGER,
                    vm_name VARCHAR(200),
                    resource_label VARCHAR(200),
                    category VARCHAR(50) NOT NULL,
                    rule_type VARCHAR(100) NOT NULL,
                    severity VARCHAR(20) NOT NULL DEFAULT 'info',
                    title VARCHAR(255) NOT NULL,
                    detail TEXT,
                    suggestion TEXT,
                    metric_value REAL,
                    metric_unit VARCHAR(20),
                    threshold REAL,
                    dismissed BOOLEAN NOT NULL DEFAULT 0,
                    dismissed_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        except Exception:
            pass
