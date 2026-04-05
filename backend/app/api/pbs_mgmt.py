"""
PBS management API endpoints.

Provides read-only access to Proxmox Backup Server datastores, snapshot
groups, and individual snapshots, as well as a connection-test endpoint.

Router prefix is expected to be mounted at something like /api/v1/pbs-mgmt
in the main application.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models import PBSServer, User
from app.services.pbs import PBSService

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_pbs_server(db: Session, server_id: int) -> PBSServer:
    """Fetch a PBSServer by ID or raise 404."""
    server = db.query(PBSServer).filter(PBSServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="PBS server not found")
    if not server.is_active:
        raise HTTPException(status_code=400, detail="PBS server is not active")
    return server


def _make_service(server: PBSServer) -> PBSService:
    """Instantiate a PBSService, raising 502 on configuration problems."""
    if not server.api_token_id or not server.api_token_secret:
        raise HTTPException(
            status_code=400,
            detail="PBS server has no API token configured",
        )
    return PBSService(server)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{server_id}/test")
def test_pbs_connection(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Test connectivity to a PBS server."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        ok = svc.test_connection()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("PBS test_connection error for server %s: %s", server_id, exc)
        return {"status": "error", "message": str(exc)}

    if ok:
        return {
            "status": "success",
            "message": f"Successfully connected to PBS server '{server.name}'",
        }
    return {
        "status": "error",
        "message": f"Could not connect to PBS server '{server.name}'",
    }


@router.get("/{server_id}/datastores")
def list_datastores(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all datastores on the PBS server with usage statistics."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        return svc.get_datastores()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to list datastores for PBS server %s: %s", server_id, exc)
        raise HTTPException(
            status_code=502,
            detail=f"PBS API error: {exc}",
        )


@router.get("/{server_id}/datastores/{datastore}/groups")
def list_backup_groups(
    server_id: int,
    datastore: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all backup groups in the specified datastore."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        return svc.get_groups(datastore)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to list groups for PBS server %s datastore %s: %s",
            server_id, datastore, exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"PBS API error: {exc}",
        )


@router.get("/{server_id}/datastores/{datastore}/snapshots")
def list_snapshots(
    server_id: int,
    datastore: str,
    vmid: Optional[int] = Query(default=None, description="Filter by VM/CT ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    List backup snapshots in the specified datastore.

    Optionally filter by vmid to retrieve only snapshots for a particular
    VM or container.
    """
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        return svc.get_snapshots(datastore, vmid=vmid)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to list snapshots for PBS server %s datastore %s: %s",
            server_id, datastore, exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"PBS API error: {exc}",
        )
