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

@router.get("/")
def list_pbs_servers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all PBS servers registered in the system."""
    servers = db.query(PBSServer).order_by(PBSServer.name).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "hostname": s.hostname,
            "port": s.port,
            "username": s.username,
            "is_active": s.is_active,
            "verify_ssl": s.verify_ssl,
            "api_token_id": s.api_token_id,
        }
        for s in servers
    ]


@router.get("/{server_id}/overview")
def get_server_overview(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return version, hostname, CPU/memory/uptime and fingerprint for a PBS server."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        result: Dict[str, Any] = {
            "hostname": server.hostname,
            "version": None,
            "fingerprint": None,
            "cpu": None,
            "memory": None,
            "uptime": None,
        }

        # Version
        try:
            ver = svc._get("/version")
            if ver:
                result["version"] = ver.get("version")
                result["fingerprint"] = ver.get("fingerprint")
        except Exception:
            pass

        # Node status (CPU / memory / uptime)
        try:
            status = svc._get("/nodes/localhost/status")
            if status:
                result["cpu"] = status.get("cpu")
                result["uptime"] = status.get("uptime")
                mem_total = status.get("memory", {}).get("total")
                mem_used = status.get("memory", {}).get("used")
                if mem_total is not None:
                    result["memory"] = {"total": mem_total, "used": mem_used or 0}
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get overview for PBS server %s: %s", server_id, exc)
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")


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
    backup_type: Optional[str] = Query(default=None, alias="backup-type"),
    backup_id: Optional[str] = Query(default=None, alias="backup-id"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    List backup snapshots in the specified datastore.

    Optionally filter by vmid, backup-type, or backup-id.
    """
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        return svc.get_snapshots(
            datastore,
            vmid=vmid,
            backup_type=backup_type,
            backup_id=backup_id,
        )
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


@router.post("/{server_id}/datastores/{datastore}/verify")
def verify_snapshot(
    server_id: int,
    datastore: str,
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Start a verify job for a specific snapshot.

    Body must contain backup-type, backup-id, and backup-time.
    Returns the UPID of the started task.
    """
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        return svc.verify_snapshot(
            datastore,
            backup_type=payload["backup-type"],
            backup_id=payload["backup-id"],
            backup_time=int(payload["backup-time"]),
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing field: {exc}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to verify snapshot for PBS server %s datastore %s: %s",
            server_id, datastore, exc,
        )
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")


@router.delete("/{server_id}/datastores/{datastore}/snapshots")
def forget_snapshot(
    server_id: int,
    datastore: str,
    backup_type: str = Query(..., alias="backup-type"),
    backup_id: str = Query(..., alias="backup-id"),
    backup_time: int = Query(..., alias="backup-time"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Permanently delete (forget) a specific snapshot.

    All three of backup-type, backup-id, and backup-time are required.
    """
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        return svc.forget_snapshot(datastore, backup_type, backup_id, backup_time)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to forget snapshot for PBS server %s datastore %s: %s",
            server_id, datastore, exc,
        )
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")


@router.post("/{server_id}/datastores/{datastore}/prune")
def prune_group(
    server_id: int,
    datastore: str,
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Prune old snapshots for a backup group according to keep-* retention rules.

    Body must contain backup-type and backup-id; optional keep-last,
    keep-daily, keep-weekly, keep-monthly, keep-yearly, keep-hourly.
    """
    server = _get_pbs_server(db, server_id)
    try:
        backup_type = payload.pop("backup-type")
        backup_id = payload.pop("backup-id")
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing field: {exc}")
    try:
        svc = _make_service(server)
        return svc.prune(datastore, backup_type, backup_id, prune_options=payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to prune group for PBS server %s datastore %s: %s",
            server_id, datastore, exc,
        )
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")


@router.get("/{server_id}/tasks")
def list_tasks(
    server_id: int,
    datastore: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List tasks on the PBS server, optionally filtered by datastore."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        return svc.list_tasks(datastore=datastore)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to list tasks for PBS server %s: %s", server_id, exc)
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")


@router.get("/{server_id}/jobs")
def list_jobs(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List configured sync/backup jobs on the PBS server."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        return svc.get_sync_jobs()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to list jobs for PBS server %s: %s", server_id, exc)
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")


@router.post("/{server_id}/jobs/{job_id}/run")
def run_job(
    server_id: int,
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Trigger a PBS sync job to run immediately. Returns the task UPID."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        upid = svc.run_sync_job(job_id)
        return {"upid": upid, "job_id": job_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to run job %s for PBS server %s: %s", job_id, server_id, exc
        )
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")


@router.get("/{server_id}/tasks/{upid}/log")
def get_task_log(
    server_id: int,
    upid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[str]:
    """Return the log lines for a PBS task by UPID."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        return svc.get_task_log(upid)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to get task log for PBS server %s task %s: %s",
            server_id, upid, exc,
        )
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")
