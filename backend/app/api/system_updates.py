"""System update API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from app.api.auth import get_current_user
from app.core.config import settings
from app.services.github_updates import GitHubUpdateService
import logging
import subprocess
import os
import requests

logger = logging.getLogger(__name__)

router = APIRouter()

# Legacy update server configuration (fallback)
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
    """Check if updates are available from GitHub releases"""
    try:
        # Use GitHub as primary source
        github_service = GitHubUpdateService()
        update_info = github_service.check_for_updates()

        if update_info.get("error"):
            # Fallback to legacy update server
            logger.info("GitHub check failed, trying legacy update server")
            try:
                response = requests.get(UPDATE_ENDPOINT, timeout=10)
                if response.status_code == 200:
                    legacy_info = response.json()
                    return UpdateCheckResponse(
                        current_version=settings.APP_VERSION,
                        latest_version=legacy_info.get("version", settings.APP_VERSION),
                        update_available=legacy_info.get("version") != settings.APP_VERSION,
                        download_url=legacy_info.get("download_url"),
                        release_notes=legacy_info.get("release_notes")
                    )
            except Exception as e:
                logger.warning(f"Legacy update server also failed: {e}")

        return UpdateCheckResponse(
            current_version=update_info["current_version"],
            latest_version=update_info["latest_version"],
            update_available=update_info["update_available"],
            download_url=update_info.get("package_url") or update_info.get("download_url"),
            release_notes=update_info.get("release_notes")
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
    Now uses GitHub as the source of truth
    """
    from app.services.github_updates import GitHubUpdateService

    github_service = GitHubUpdateService()
    latest_release = github_service.get_latest_release()

    if latest_release:
        return {
            "version": latest_release.get("version", settings.APP_VERSION),
            "download_url": latest_release.get("tarball_url"),
            "install_url": "https://raw.githubusercontent.com/agit8or1/Depl0y/main/install.sh",
            "release_notes": latest_release.get("body", f"Depl0y {settings.APP_VERSION}")
        }

    # Fallback if GitHub is unavailable
    return {
        "version": settings.APP_VERSION,
        "download_url": f"{UPDATE_SERVER}/api/v1/system-updates/download",
        "install_url": f"{UPDATE_SERVER}/install.sh",
        "release_notes": f"""
Depl0y {settings.APP_VERSION} - Security Hardening Release

🔒 Security Fixes:
- Fixed 5 CRITICAL vulnerabilities (command injection, timing attacks, encryption)
- Added security headers (X-Frame-Options, CSP, XSS protection)
- Implemented rate limiting infrastructure
- GitHub update integration
- Auto-generate encryption keys

✨ New Features:
- GitHub integration for updates
- Security database models for account lockout and token revocation
- Enhanced audit logging infrastructure

⚠️ Breaking Changes: None - fully backward compatible

For full details, see SECURITY_AUDIT_REPORT.md
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
            # SECURITY: Use argument list instead of shell=True to prevent command injection
            temp_package = "/tmp/depl0y-update.tar.gz"
            try:
                subprocess.run(
                    [
                        'tar', '-czf', temp_package,
                        '--exclude=node_modules',
                        '--exclude=dist',
                        '--exclude=.git',
                        '--exclude=__pycache__',
                        '--exclude=*.pyc',
                        '--exclude=venv',
                        '-C', '/home/administrator/depl0y',
                        'backend/', 'frontend/', 'install.sh', 'uninstall.sh',
                        'deploy.sh', 'nginx-depl0y.conf', 'scripts/', 'docs/', '.github/'
                    ],
                    check=True,
                    capture_output=True,
                    timeout=60
                )
                package_path = temp_package
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to create package: {e.stderr.decode() if e.stderr else e}")
                raise HTTPException(status_code=500, detail="Failed to create update package")

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
    """Apply update by downloading from GitHub and running the installer"""
    try:
        logger.info("Starting update process from GitHub...")

        # Get latest release from GitHub
        github_service = GitHubUpdateService()
        update_info = github_service.check_for_updates()

        if not update_info.get("update_available"):
            raise HTTPException(status_code=400, detail="No update available")

        download_url = update_info.get("download_url")
        if not download_url:
            raise HTTPException(status_code=500, detail="No download URL found")

        logger.info(f"Downloading update from GitHub: {download_url}")

        # Download tarball from GitHub
        tarball_path = "/tmp/depl0y-update.tar.gz"
        extract_path = "/tmp/depl0y-update"

        # Download the release tarball
        response = requests.get(download_url, timeout=300, stream=True)
        if response.status_code != 200:
            raise Exception(f"Failed to download update: HTTP {response.status_code}")

        # Save tarball
        with open(tarball_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info("Download complete, extracting files...")

        # Clean up old extract directory if it exists
        if os.path.exists(extract_path):
            subprocess.run(['rm', '-rf', extract_path], check=True, timeout=10)

        os.makedirs(extract_path, exist_ok=True)

        # Extract tarball
        subprocess.run(
            ['tar', '-xzf', tarball_path, '-C', extract_path, '--strip-components=1'],
            check=True,
            capture_output=True,
            timeout=60
        )

        # Find the upgrade script
        upgrade_script_path = os.path.join(extract_path, 'scripts', 'upgrade.sh')
        if not os.path.exists(upgrade_script_path):
            raise Exception(f"Upgrade script not found in downloaded package")

        os.chmod(upgrade_script_path, 0o755)

        logger.info("Starting upgrade in background...")

        # Run upgrade script via at daemon to detach from backend process
        update_script = f"""#!/bin/bash
/bin/bash {upgrade_script_path} {extract_path} > /tmp/depl0y-update.log 2>&1
"""
        script_path = "/tmp/depl0y-update-runner.sh"
        with open(script_path, 'w') as f:
            f.write(update_script)
        os.chmod(script_path, 0o755)

        # Schedule via at
        proc = subprocess.Popen(
            ['/usr/bin/at', 'now'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate(input=script_path, timeout=5)
        if proc.returncode != 0:
            raise Exception(f"Failed to schedule update: {stderr}")

        return {
            "success": True,
            "message": "Update is being applied from GitHub. The service will restart automatically when complete.",
            "version": update_info.get("latest_version"),
            "log_file": "/tmp/depl0y-update.log"
        }

    except Exception as e:
        logger.error(f"Failed to apply update: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to apply update: {str(e)}"
        )


