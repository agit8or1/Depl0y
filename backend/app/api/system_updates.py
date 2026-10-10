"""System update API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, List
from app.api.auth import get_current_user, require_admin
from app.core.config import settings
from app.services.github_updates import GitHubUpdateService
import logging
import subprocess
import os
import requests

logger = logging.getLogger(__name__)

router = APIRouter()

# Legacy update server configuration (fallback)
UPDATE_SERVER = "https://deploy.agit8or.net"
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


# Installers predating 2.2.90 download their package from this endpoint on
# deploy.agit8or.net. Send them to the latest GitHub release asset instead of a
# tarball kept on this server.
LATEST_RELEASE_ASSET = "https://github.com/agit8or1/Depl0y/releases/latest/download/depl0y.tar.gz"


@router.get("/download")
def download_update():
    """Redirect to the latest release package on GitHub (public, used by old installers)."""
    return RedirectResponse(LATEST_RELEASE_ASSET, status_code=302)


# Written by /usr/local/sbin/depl0y-update (root:depl0y 0640).
UPDATE_LOG = "/var/log/depl0y-update/update.log"
UPDATER = "/usr/local/sbin/depl0y-update"


@router.get("/log")
def get_update_log(current_user=Depends(get_current_user)):
    """Return the current contents of the update log for real-time progress display."""
    try:
        with open(UPDATE_LOG) as f:
            content = f.read()
    except OSError:
        return {"lines": [], "done": False, "failed": False}
    lines = content.splitlines()
    done = any("Upgrade complete" in l for l in lines)
    failed = any("❌" in l for l in lines)
    return {"lines": lines[-300:], "done": done, "failed": failed}


@router.post("/apply")
def apply_update(current_user=Depends(require_admin)):
    """Start the root-owned updater, which installs the latest verified GitHub release."""
    update_info = GitHubUpdateService().check_for_updates()
    if not update_info.get("update_available"):
        raise HTTPException(status_code=400, detail="No update available")
    latest = update_info.get("latest_version", "")

    if not os.path.exists(UPDATER):
        raise HTTPException(
            status_code=500,
            detail=(
                "The updater is not installed. On the Depl0y server run "
                "'sudo bash /opt/depl0y/scripts/install-updater.sh' once, then try again."
            ),
        )

    # The updater detaches into its own systemd unit and returns at once.
    try:
        result = subprocess.run(
            ["/usr/bin/sudo", "-n", UPDATER, "apply"],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="The updater did not start in time")
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip() or f"exit code {result.returncode}"
        logger.error(f"Failed to start updater: {detail}")
        raise HTTPException(status_code=500, detail=f"Failed to start update: {detail}")

    return {
        "success": True,
        "message": f"Update to v{latest} is running. Watch the progress log below.",
        "version": latest,
    }
