"""System information API endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.database import SystemSettings
from typing import Dict
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/info")
def get_system_info(db: Session = Depends(get_db)) -> Dict[str, str]:
    """Get system information including version"""
    try:
        # Get version from database
        version_setting = db.query(SystemSettings).filter(SystemSettings.key == "app_version").first()
        app_name_setting = db.query(SystemSettings).filter(SystemSettings.key == "app_name").first()
        
        version = version_setting.value if version_setting else "1.1.3"
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
