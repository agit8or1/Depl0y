"""System logs API routes"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
import subprocess
import logging
from app.api.auth import get_current_user, require_admin
from app.models import User

router = APIRouter()
logger = logging.getLogger(__name__)

# sudoers allows journalctl only with these exact arguments, so we always fetch
# JOURNAL_LINES lines and trim to what the caller asked for here.
JOURNAL_LINES = 1000


def _journal(*extra: str) -> str:
    result = subprocess.run(
        ["/usr/bin/sudo", "-n", "/usr/bin/journalctl", "-u", "depl0y-backend", "-n", str(JOURNAL_LINES), "--no-pager", *extra],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise Exception(f"Failed to retrieve logs: {result.stderr}")
    return result.stdout


def _last(text: str, lines: Optional[int]) -> list:
    n = max(1, min(int(lines or 1), JOURNAL_LINES))
    return text.splitlines()[-n:]


@router.get("/backend")
async def get_backend_logs(
    lines: Optional[int] = 100,
    current_user: User = Depends(require_admin),
):
    """Get backend service logs (admin only)"""
    try:
        # Get logs from systemd journal (requires sudo)
        return {
            "logs": "\n".join(_last(_journal(), lines)) + "\n",
            "lines": lines
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout while retrieving logs")
    except Exception as e:
        logger.error(f"Failed to get backend logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backend/tail")
async def tail_backend_logs(
    lines: Optional[int] = 50,
    current_user: User = Depends(require_admin),
):
    """Get most recent backend logs (admin only)"""
    try:
        # Return as array of lines for easier frontend processing
        log_lines = _last(_journal("-o", "cat").strip(), lines)

        return {
            "logs": log_lines,
            "count": len(log_lines)
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout while retrieving logs")
    except Exception as e:
        logger.error(f"Failed to tail backend logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
