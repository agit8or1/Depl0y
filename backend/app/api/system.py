"""System information API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.database import SystemSettings
from app.api.auth import get_current_user, require_admin
from app.models import User
from typing import Dict
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/info")
def get_system_info(db: Session = Depends(get_db)) -> Dict[str, str]:
    """Get system information including version"""
    try:
        # Get version from database
        version_setting = db.query(SystemSettings).filter(SystemSettings.key == "app_version").first()
        app_name_setting = db.query(SystemSettings).filter(SystemSettings.key == "app_name").first()
        
        version = version_setting.value if version_setting else "1.5.0"
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
            "version": "1.1.3",
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
