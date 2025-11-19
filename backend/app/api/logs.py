"""System logs API routes"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
import subprocess
import logging
from app.api.auth import get_current_user, require_admin
from app.models import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/backend")
async def get_backend_logs(
    lines: Optional[int] = 100,
    current_user: User = Depends(require_admin),
):
    """Get backend service logs (admin only)"""
    try:
        # Get logs from systemd journal (requires sudo)
        result = subprocess.run(
            ["sudo", "journalctl", "-u", "depl0y-backend", "-n", str(lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            raise Exception(f"Failed to retrieve logs: {result.stderr}")

        return {
            "logs": result.stdout,
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
        # Get most recent logs (requires sudo)
        result = subprocess.run(
            ["sudo", "journalctl", "-u", "depl0y-backend", "-n", str(lines), "--no-pager", "-o", "cat"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            raise Exception(f"Failed to retrieve logs: {result.stderr}")

        # Return as array of lines for easier frontend processing
        log_lines = result.stdout.strip().split('\n') if result.stdout else []

        return {
            "logs": log_lines,
            "count": len(log_lines)
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout while retrieving logs")
    except Exception as e:
        logger.error(f"Failed to tail backend logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
