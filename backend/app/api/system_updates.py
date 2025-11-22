"""System update API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from app.api.auth import get_current_user
from app.core.config import settings
import logging
import subprocess
import os
import requests

logger = logging.getLogger(__name__)

router = APIRouter()

# Update server configuration
UPDATE_SERVER = "http://deploy.agit8or.net"
UPDATE_ENDPOINT = f"{UPDATE_SERVER}/api/v1/system-updates/version"


class UpdateCheckResponse(BaseModel):
    current_version: str
    latest_version: str
    update_available: bool
    download_url: Optional[str] = None
    release_notes: Optional[str] = None


@router.get("/check")
def check_for_updates(current_user=Depends(get_current_user)):
    """Check if updates are available from the main server"""
    try:
        # Get current version
        current_version = settings.APP_VERSION

        # Query update server for latest version
        try:
            response = requests.get(UPDATE_ENDPOINT, timeout=10)
            if response.status_code == 200:
                update_info = response.json()
                latest_version = update_info.get("version", current_version)

                # Simple version comparison (assumes semantic versioning)
                update_available = latest_version != current_version

                return UpdateCheckResponse(
                    current_version=current_version,
                    latest_version=latest_version,
                    update_available=update_available,
                    download_url=update_info.get("download_url") if update_available else None,
                    release_notes=update_info.get("release_notes")
                )
            else:
                raise Exception(f"Update server returned {response.status_code}")
        except requests.RequestException as e:
            logger.warning(f"Could not reach update server: {e}")
            return UpdateCheckResponse(
                current_version=current_version,
                latest_version=current_version,
                update_available=False,
                release_notes="Could not reach update server"
            )

    except Exception as e:
        logger.error(f"Failed to check for updates: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check for updates: {str(e)}"
        )


@router.get("/version")
def get_version_info():
    """
    Serve version information for update clients
    This endpoint is called BY OTHER INSTANCES to check for updates
    """
    return {
        "version": settings.APP_VERSION,
        "download_url": f"{UPDATE_SERVER}/api/v1/system-updates/download",
        "install_url": f"{UPDATE_SERVER}/install.sh",
        "release_notes": f"""
Depl0y {settings.APP_VERSION} Release Notes:

✨ New in v1.3.6:
- Fixed cloud image enable - sshpass installation now works
- Resolved DEBIAN_FRONTEND sudo environment variable error
- Updated sudoers permissions for proper system functionality

✨ Recent versions:
- Fixed installer tarball structure for clean installs (v1.3.5)
- ISO downloads with real-time status and background processing (v1.3.4)
- Compressed ISO support with automatic decompression (v1.3.2)
- Auto-populate 7 popular cloud images (v1.2.2)
        """.strip()
    }


@router.get("/download")
def download_update():
    """Download the latest update package (public endpoint for automated updates)"""
    try:
        # Use pre-packaged file - check for latest version first
        package_path = "/opt/depl0y/depl0y-latest.tar.gz"
        if not os.path.exists(package_path):
            # Fallback to versioned file
            package_path = "/opt/depl0y/depl0y-v1.3.2.tar.gz"
        
        if not os.path.exists(package_path):
            # Fallback: create package on-the-fly
            temp_package = "/tmp/depl0y-update.tar.gz"
            create_package_cmd = f"""
cd /home/administrator/depl0y && \
tar -czf {temp_package} \
  --exclude='node_modules' \
  --exclude='dist' \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='venv' \
  backend/ frontend/ *.md *.sh nginx-depl0y.conf scripts/ docs/ .github/ 2>/dev/null || true
"""
            subprocess.run(create_package_cmd, shell=True, check=True)
            package_path = temp_package

        if not os.path.exists(package_path):
            raise HTTPException(status_code=500, detail="Failed to find or create update package")

        return FileResponse(
            package_path,
            media_type="application/gzip",
            filename="depl0y-latest.tar.gz",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

    except Exception as e:
        logger.error(f"Failed to serve update package: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to serve update package: {str(e)}"
        )


@router.post("/apply")
def apply_update(current_user=Depends(get_current_user)):
    """Apply update by downloading and running the installer script"""
    try:
        logger.info("Starting update process via installer...")
        
        # Download installer script
        installer_url = f"{UPDATE_SERVER}/downloads/install.sh"
        installer_path = "/tmp/depl0y-update-install.sh"
        
        logger.info(f"Downloading installer from {installer_url}")
        
        response = requests.get(installer_url, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Failed to download installer: HTTP {response.status_code}")
        
        # Save installer
        with open(installer_path, 'wb') as f:
            f.write(response.content)
        
        # Make executable
        os.chmod(installer_path, 0o755)
        
        logger.info("Installer downloaded, starting update in background...")
        
        # Run installer in background (it will detect existing installation and upgrade)
        update_script = f"/usr/bin/sudo /opt/depl0y/scripts/update-wrapper.sh {installer_path}"
        subprocess.Popen(update_script, shell=True)
        
        return {
            "success": True,
            "message": "Update is being applied. The installer will upgrade your installation while preserving your data. The service will restart automatically.",
            "log_file": "/tmp/depl0y-update.log"
        }
        
    except Exception as e:
        logger.error(f"Failed to start update: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start update: {str(e)}"
        )


