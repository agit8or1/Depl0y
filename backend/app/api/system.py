"""System information API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.database import SystemSettings
from app.api.auth import get_current_user, require_admin
from app.models import User
from typing import Dict, Any, Optional
import logging
import smtplib
import ssl
import os
import time
import sqlite3
import ipaddress
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Settings cache (5-minute TTL) ────────────────────────────────────────────
_settings_cache: Dict[str, str] = {}
_settings_last_fetch: float = 0


def get_cached_setting(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a system setting with 5-minute in-process cache."""
    global _settings_cache, _settings_last_fetch
    if time.time() - _settings_last_fetch > 300:
        try:
            rows = db.query(SystemSettings).all()
            _settings_cache = {r.key: r.value for r in rows}
            _settings_last_fetch = time.time()
        except Exception:
            pass
    return _settings_cache.get(key, default)


def invalidate_settings_cache():
    """Force cache refresh on next call (call after settings are updated)."""
    global _settings_last_fetch
    _settings_last_fetch = 0


from app.api.auth import get_current_user as _sysinfo_auth


@router.get("/info")
def get_system_info(db: Session = Depends(get_db), current_user=Depends(_sysinfo_auth)) -> Dict[str, str]:
    """Get system information including version"""
    try:
        # Get version from database
        version_setting = db.query(SystemSettings).filter(SystemSettings.key == "app_version").first()
        app_name_setting = db.query(SystemSettings).filter(SystemSettings.key == "app_name").first()
        
        version = version_setting.value if version_setting else "1.9.0"
        app_name = app_name_setting.value if app_name_setting else "Depl0y"
        
        return {
            "version": version,
            "app_name": app_name,
            "status": "running"
        }
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        # Fallback to hardcoded version if database query fails
        return {
            "version": "1.9.0",
            "app_name": "Depl0y",
            "status": "running"
        }


def _get_setting(db: Session, key: str, default: str = "") -> str:
    """Helper to read a system setting value."""
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    return row.value if row else default


@router.post("/test-email")
def send_test_email(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Dict[str, str]:
    """Send a test email using the configured SMTP settings"""
    smtp_host = _get_setting(db, "smtp_host")
    smtp_port_str = _get_setting(db, "smtp_port", "587")
    smtp_username = _get_setting(db, "smtp_username")
    smtp_password = _get_setting(db, "smtp_password")
    smtp_from = _get_setting(db, "smtp_from") or smtp_username
    smtp_to = _get_setting(db, "smtp_to") or smtp_from
    smtp_tls = _get_setting(db, "smtp_tls", "true").lower() in ("true", "1", "yes")

    if not smtp_host:
        raise HTTPException(
            status_code=400,
            detail="SMTP host is not configured. Please set smtp_host in System Settings."
        )

    try:
        smtp_port = int(smtp_port_str)
    except (ValueError, TypeError):
        smtp_port = 587

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Depl0y Test Email"
    msg["From"] = smtp_from
    msg["To"] = smtp_to

    html_body = """\
<html><body>
<h2>Depl0y Test Email</h2>
<p>This is a test email sent from your Depl0y instance to verify that email configuration is working correctly.</p>
<p>If you received this, your SMTP settings are configured properly.</p>
</body></html>"""
    text_body = "Depl0y Test Email\n\nThis is a test email sent from your Depl0y instance to verify SMTP configuration."

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if smtp_tls and smtp_port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
                if smtp_username and smtp_password:
                    server.login(smtp_username, smtp_password)
                server.sendmail(smtp_from, smtp_to, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                if smtp_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                if smtp_username and smtp_password:
                    server.login(smtp_username, smtp_password)
                server.sendmail(smtp_from, smtp_to, msg.as_string())

        logger.info(f"Test email sent successfully to {smtp_to}")
        return {"success": "true", "message": f"Test email sent to {smtp_to}"}

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        raise HTTPException(status_code=400, detail=f"SMTP authentication failed: {e.smtp_error.decode() if hasattr(e, 'smtp_error') else str(e)}")
    except smtplib.SMTPConnectError as e:
        logger.error(f"SMTP connection failed: {e}")
        raise HTTPException(status_code=400, detail=f"Could not connect to SMTP server {smtp_host}:{smtp_port}")
    except Exception as e:
        logger.error(f"Failed to send test email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send test email: {str(e)}")


@router.get("/diagnostics")
def get_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Return a diagnostic bundle: version, db stats, log tail, uptime (admin only)"""
    from app.core.config import settings

    # Version info
    version_setting = db.query(SystemSettings).filter(SystemSettings.key == "app_version").first()
    version = version_setting.value if version_setting else settings.APP_VERSION

    # DB stats
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    db_size_bytes = 0
    try:
        db_size_bytes = os.path.getsize(db_path)
    except Exception:
        pass

    user_count = 0
    host_count = 0
    vm_count = 0
    try:
        from app.models.database import User as UserModel, ProxmoxHost, VirtualMachine
        user_count = db.query(UserModel).count()
        host_count = db.query(ProxmoxHost).count()
        vm_count = db.query(VirtualMachine).count()
    except Exception:
        pass

    # Last 100 log lines
    last_log_lines = []
    log_file = settings.LOG_FILE
    try:
        if os.path.exists(log_file):
            with open(log_file, "r", errors="replace") as f:
                all_lines = f.readlines()
                last_log_lines = [l.rstrip() for l in all_lines[-100:]]
    except Exception as e:
        last_log_lines = [f"Could not read log file: {e}"]

    # System uptime
    uptime_seconds = None
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.read().split()[0])
    except Exception:
        pass

    return {
        "version": version,
        "app_name": settings.APP_NAME,
        "db_path": db_path,
        "db_size_bytes": db_size_bytes,
        "user_count": user_count,
        "host_count": host_count,
        "vm_count": vm_count,
        "last_100_log_lines": last_log_lines,
        "uptime_seconds": uptime_seconds,
        "generated_at": time.time(),
    }


@router.post("/db-check")
def db_integrity_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Run SQLite PRAGMA integrity_check (admin only)"""
    from app.core.config import settings

    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        rows = cursor.fetchall()
        conn.close()
        results = [r[0] for r in rows]
        ok = len(results) == 1 and results[0] == "ok"
        return {
            "ok": ok,
            "results": results,
            "db_path": db_path,
        }
    except Exception as e:
        logger.error(f"DB integrity check failed: {e}")
        raise HTTPException(status_code=500, detail=f"DB integrity check failed: {e}")


@router.get("/health")
def system_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Enhanced health check: db, SMTP config, Proxmox hosts, encryption, disk space."""
    from app.core.config import settings as app_settings

    checks: Dict[str, Any] = {}

    # 1. Database connectivity
    db_ok = False
    try:
        db.execute(__import__('sqlalchemy').text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    checks["db"] = "ok" if db_ok else "fail"

    # 2. SMTP configured
    smtp_host = _get_setting(db, "smtp_host")
    checks["smtp"] = "configured" if smtp_host else "not_configured"

    # 3. Proxmox hosts
    host_count = 0
    try:
        from app.models.database import ProxmoxHost
        host_count = db.query(ProxmoxHost).count()
    except Exception:
        pass
    checks["hosts"] = host_count

    # 4. Encryption key
    enc_key = getattr(app_settings, "ENCRYPTION_KEY", None)
    checks["encryption"] = "ok" if enc_key else "missing"

    # 5. Disk space for DB file
    disk_free_gb = None
    try:
        db_path = app_settings.DATABASE_URL.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path) or "/"
        stat = os.statvfs(db_dir)
        disk_free_gb = round(stat.f_frsize * stat.f_bavail / (1024 ** 3), 2)
    except Exception:
        pass
    checks["disk_free_gb"] = disk_free_gb

    overall = "healthy" if db_ok else "degraded"

    return {
        "status": overall,
        "checks": checks,
    }


@router.get("/metrics")
def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Return Prometheus-compatible metrics as JSON (admin only)"""
    from app.main import _request_counter, _app_start_time
    from app.models.database import User as UserModel, ProxmoxHost, ApiKey

    users_total = 0
    hosts_total = 0
    api_keys_total = 0
    try:
        users_total = db.query(UserModel).count()
        hosts_total = db.query(ProxmoxHost).count()
        api_keys_total = db.query(ApiKey).filter(ApiKey.is_active == True).count()
    except Exception:
        pass

    uptime_seconds = int(time.time() - _app_start_time)

    return {
        "depl0y_users_total": users_total,
        "depl0y_proxmox_hosts_total": hosts_total,
        "depl0y_api_keys_total": api_keys_total,
        "depl0y_requests_total": _request_counter,
        "depl0y_uptime_seconds": uptime_seconds,
    }


@router.get("/settings")
def get_all_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Return all system settings as a key→value dict (admin only)"""
    rows = db.query(SystemSettings).all()
    return {row.key: row.value for row in rows}


@router.patch("/settings")
def update_settings(
    updates: Dict[str, str],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Bulk-upsert system settings (admin only). Accepts a dict of key→value pairs."""
    try:
        for key, value in updates.items():
            row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
            if row:
                row.value = value
            else:
                row = SystemSettings(key=key, value=value)
                db.add(row)
        db.commit()
        invalidate_settings_cache()
        # Live-apply settings that drive scheduled jobs so the user doesn't
        # have to restart the backend to see the new cadence take effect.
        if "bmc_poll_interval_minutes" in updates:
            try:
                from app.services.scheduler import reschedule_bmc_poll, _BMC_POLL_ALLOWED_MIN
                v = int(updates["bmc_poll_interval_minutes"])
                if v in _BMC_POLL_ALLOWED_MIN:
                    reschedule_bmc_poll(v)
            except Exception as exc:
                logger.warning("Could not live-apply bmc_poll_interval_minutes: %s", exc)
        return {"success": True, "updated": list(updates.keys())}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {e}")


@router.post("/settings/validate")
def validate_settings(
    data: Dict[str, str],
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Validate a partial settings dict without saving.
    Returns {valid: true} or {valid: false, errors: {key: "message"}}.
    """
    errors: Dict[str, str] = {}

    for key, value in data.items():
        if key == "smtp_port":
            try:
                port = int(value)
                if not (1 <= port <= 65535):
                    errors[key] = "Port must be between 1 and 65535"
            except (ValueError, TypeError):
                errors[key] = "Port must be a valid integer"

        elif key == "ip_allowlist":
            if value.strip():
                entries = [e.strip() for e in value.split(",") if e.strip()]
                bad = []
                for entry in entries:
                    try:
                        ipaddress.ip_network(entry, strict=False)
                    except ValueError:
                        bad.append(entry)
                if bad:
                    errors[key] = f"Invalid CIDR notation: {', '.join(bad)}"

        elif key == "session_timeout":
            try:
                minutes = int(value)
                if not (5 <= minutes <= 10080):
                    errors[key] = "Session timeout must be between 5 and 10080 minutes (7 days)"
            except (ValueError, TypeError):
                errors[key] = "Session timeout must be a valid integer"

        elif key == "session_timeout_minutes":
            try:
                minutes = int(value)
                if not (5 <= minutes <= 10080):
                    errors[key] = "Session timeout must be between 5 and 10080 minutes (7 days)"
            except (ValueError, TypeError):
                errors[key] = "Session timeout must be a valid integer"

        elif key == "max_login_attempts":
            try:
                attempts = int(value)
                if not (1 <= attempts <= 100):
                    errors[key] = "Max login attempts must be between 1 and 100"
            except (ValueError, TypeError):
                errors[key] = "Max login attempts must be a valid integer"

    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True}


@router.get("/cache/stats")
def cache_stats(
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Return PVE TTL cache statistics (admin only)"""
    from app.core.cache import pve_cache
    return pve_cache.stats()


@router.post("/cache/clear")
def clear_cache(
    current_user: User = Depends(require_admin),
) -> Dict[str, str]:
    """Clear the entire PVE TTL cache (admin only)"""
    from app.core.cache import pve_cache
    pve_cache.clear()
    logger.info(f"PVE cache cleared by {current_user.username}")
    return {"success": "true", "message": "Cache cleared successfully"}


@router.post("/db-vacuum")
def db_vacuum(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Run SQLite VACUUM to reclaim disk space (admin only)"""
    from app.core.config import settings as app_settings

    db_path = app_settings.DATABASE_URL.replace("sqlite:///", "")
    try:
        # Get size before vacuum
        size_before = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        conn = sqlite3.connect(db_path)
        conn.execute("VACUUM")
        conn.close()
        size_after = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        freed = max(0, size_before - size_after)
        logger.info(f"DB VACUUM completed by {current_user.username}. Freed: {freed} bytes")
        return {
            "success": True,
            "size_before_bytes": size_before,
            "size_after_bytes": size_after,
            "freed_bytes": freed,
        }
    except Exception as e:
        logger.error(f"DB VACUUM failed: {e}")
        raise HTTPException(status_code=500, detail=f"VACUUM failed: {e}")


@router.post("/restart")
def restart_backend(
    current_user: User = Depends(require_admin),
) -> Dict[str, str]:
    """Schedule a backend service restart (admin only). Returns immediately; restart happens after 3s."""
    import subprocess
    import threading

    logger.warning(f"Backend restart requested by {current_user.username}")

    def _do_restart():
        import time as _time
        _time.sleep(3)
        try:
            subprocess.run(["systemctl", "restart", "depl0y-backend"], check=False)
        except Exception as exc:
            logger.error(f"Restart subprocess failed: {exc}")

    t = threading.Thread(target=_do_restart, daemon=True)
    t.start()
    return {"success": "true", "message": "Backend restart scheduled in 3 seconds"}


@router.put("/version")
def update_version(new_version: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Update system version (admin only)"""
    try:
        version_setting = db.query(SystemSettings).filter(SystemSettings.key == "app_version").first()
        
        if version_setting:
            version_setting.value = new_version
        else:
            version_setting = SystemSettings(
                key="app_version",
                value=new_version,
                description="Current application version"
            )
            db.add(version_setting)
        
        db.commit()
        
        return {
            "success": True,
            "version": new_version,
            "message": "Version updated successfully"
        }
    except Exception as e:
        logger.error(f"Failed to update version: {e}")
        db.rollback()
        return {
            "success": False,
            "message": str(e)
        }
