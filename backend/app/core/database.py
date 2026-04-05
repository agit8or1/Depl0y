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
    import app.models.security  # ensure security tables are registered  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Add new columns to proxmox_nodes if they don't already exist (migration helper)
    from sqlalchemy import text
    new_columns = [
        ("vm_count", "INTEGER DEFAULT 0"),
        ("lxc_count", "INTEGER DEFAULT 0"),
    ]
    with engine.connect() as conn:
        for col_name, col_def in new_columns:
            try:
                conn.execute(text(f"ALTER TABLE proxmox_nodes ADD COLUMN {col_name} {col_def}"))
                conn.commit()
            except Exception:
                pass  # Column already exists
