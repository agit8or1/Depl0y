"""
PBS management API endpoints.

Provides read-only access to Proxmox Backup Server datastores, snapshot
groups, and individual snapshots, as well as a connection-test endpoint.

Router prefix is expected to be mounted at something like /api/v1/pbs-mgmt
in the main application.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_admin, require_operator
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
    """Instantiate a PBSService — supports either API token or password (ticket) auth."""
    has_token = bool(server.api_token_id and server.api_token_secret)
    has_password = bool(server.username and server.password)
    if not has_token and not has_password:
        raise HTTPException(
            status_code=400,
            detail="PBS server has no credentials configured (set a password or API token)",
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
            "cpu": None,
            "memory": None,
            "uptime": None,
        }

        # Version
        try:
            ver = svc._get("/version")
            if ver:
                result["version"] = ver.get("version")
        except Exception:
            pass

        # Node status (CPU / memory / uptime / fingerprint)
        try:
            status = svc._get("/nodes/localhost/status")
            if status:
                result["cpu"] = status.get("cpu")
                # PBS 4.x exposes uptime inside 'info' or at top level depending on version
                result["uptime"] = status.get("uptime") or status.get("info", {}).get("uptime")
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


@router.get("/{server_id}/tapes")
def get_tapes(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return tape drive, changer, and media inventory for the PBS server."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        return svc.get_tapes()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get tape info for PBS server %s: %s", server_id, exc)
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


@router.get("/{server_id}/remotes")
def list_remotes(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return PBS remotes (destination definitions, not sync jobs)."""
    server = _get_pbs_server(db, server_id)
    try:
        return _make_service(server).get_remotes()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")


@router.get("/{server_id}/remotes/{remote}/scan")
def scan_remote_datastores(
    server_id: int,
    remote: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Enumerate datastores on a configured remote PBS."""
    server = _get_pbs_server(db, server_id)
    try:
        return _make_service(server).get_remote_datastores(remote)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")


@router.post("/{server_id}/sync-jobs")
def create_sync_job(
    server_id: int,
    payload: Dict[str, Any],
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> Any:
    """Create a new PBS sync job (operator+).
    Required keys in payload: id, store, remote, remote-store. Optional: schedule, remove-vanished, comment.
    """
    missing = [k for k in ("id", "store", "remote", "remote-store") if not payload.get(k)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")
    server = _get_pbs_server(db, server_id)
    try:
        return _make_service(server).create_sync_job(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")


@router.delete("/{server_id}/sync-jobs/{job_id}")
def delete_sync_job(
    server_id: int,
    job_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Any:
    server = _get_pbs_server(db, server_id)
    try:
        return _make_service(server).delete_sync_job(job_id)
    except HTTPException:
        raise
    except Exception as exc:
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
    job_type: str = "sync",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Trigger a PBS job to run immediately. Supports sync, verify, and prune jobs."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        run_paths = {
            "sync": f"/config/sync/{job_id}/run",
            "pull": f"/config/pull/{job_id}/run",
            "verify": f"/config/verify/{job_id}/run",
            "prune": f"/config/prune/{job_id}/run",
        }
        path = run_paths.get(job_type, f"/config/sync/{job_id}/run")
        upid = svc._post(path)
        return {"upid": upid, "job_id": job_id, "job_type": job_type}
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


# ---------------------------------------------------------------------------
# Summary endpoint — dashboard card for a PBS server
# ---------------------------------------------------------------------------

@router.get("/{server_id}/summary")
def get_server_summary(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return aggregated summary info for a PBS server.

    Combines datastore totals, sync-job status, and recent backup counts
    into a single response for the PBSManagement dashboard card.

    Each sub-request is executed in parallel and failures downgrade to
    partial data + an 'error' field rather than an HTTP error.
    """
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
    except HTTPException as exc:
        # Missing token / inactive — return partial
        return {
            "server_id": server_id,
            "datastore_totals": {"total_bytes": 0, "used_bytes": 0, "available_bytes": 0,
                                 "usage_pct": 0, "datastores": []},
            "sync_jobs": [],
            "remotes": [],
            "recent_backups_24h": {"ok": 0, "failed": 0, "total": 0},
            "error": exc.detail,
        }

    errors: List[str] = []

    def _safe(fn):
        try:
            return fn()
        except Exception as exc:
            errors.append(str(exc))
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        f_ds = pool.submit(_safe, svc.get_datastores)
        f_jobs = pool.submit(_safe, svc.get_sync_jobs)
        f_remotes = pool.submit(_safe, svc.get_remotes)
        since_epoch = int(time.time()) - 86400
        f_tasks = pool.submit(
            _safe,
            lambda: svc.list_recent_tasks(
                since_epoch=since_epoch,
                types=["backup", "verificationjob", "sync", "prune", "garbage_collection"],
                limit=500,
            ),
        )
        datastores = f_ds.result() or []
        jobs = f_jobs.result() or []
        remotes = f_remotes.result() or []
        recent_tasks = f_tasks.result() or []

    # PBS /admin/datastore returns a bare list without usage figures —
    # fan out to per-store /status endpoints in parallel to collect totals.
    store_names = [
        d.get("store") or d.get("name") for d in datastores
        if d.get("store") or d.get("name")
    ]
    usage_by_store: Dict[str, Dict[str, Any]] = {}
    if store_names:
        def _store_status(name: str):
            try:
                return name, svc.get_datastore_usage(name)
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                return name, {}
        with ThreadPoolExecutor(max_workers=min(6, len(store_names))) as pool:
            for name, status in pool.map(_store_status, store_names):
                usage_by_store[name] = status or {}

    # Datastore totals
    ds_list: List[Dict[str, Any]] = []
    total = 0
    used = 0
    for d in datastores:
        name = d.get("store") or d.get("name") or ""
        status = usage_by_store.get(name, {})
        t = int(status.get("total") or d.get("total") or 0)
        u = int(status.get("used") or d.get("used") or 0)
        a = int(status.get("avail") or d.get("avail") or max(t - u, 0))
        total += t
        used += u
        ds_list.append({
            "store": name,
            "total": t, "used": u, "avail": a,
            "error": d.get("error"),
        })
    avail = max(total - used, 0)
    usage_pct = (used / total * 100.0) if total > 0 else 0.0

    # Sync jobs — filter to sync/pull only for the replication card, include status
    sync_jobs: List[Dict[str, Any]] = []
    for j in jobs:
        jt = (j.get("job-type") or "").lower()
        if jt not in ("sync", "pull"):
            continue
        sync_jobs.append({
            "id": j.get("id") or j.get("job-id"),
            "store": j.get("store") or j.get("datastore"),
            "remote": j.get("remote") or j.get("remote-store") or j.get("source"),
            "schedule": j.get("schedule"),
            "last_run_state": j.get("last-run-state"),
            "last_run_endtime": j.get("last-run-endtime"),
            "next_run": j.get("next-run"),
        })

    # Recent backups in last 24h — ok/failed counts
    ok = 0
    failed = 0
    for t in recent_tasks:
        worker = (t.get("worker_type") or t.get("type") or "").lower()
        if "backup" not in worker:
            continue
        status = (t.get("status") or "").upper()
        if status.startswith("OK"):
            ok += 1
        elif status and status != "RUNNING":
            failed += 1
    total_recent = ok + failed

    result: Dict[str, Any] = {
        "server_id": server_id,
        "datastore_totals": {
            "total_bytes": total,
            "used_bytes": used,
            "available_bytes": avail,
            "usage_pct": round(usage_pct, 2),
            "datastores": ds_list,
        },
        "sync_jobs": sync_jobs,
        "remotes": remotes,
        "recent_backups_24h": {"ok": ok, "failed": failed, "total": total_recent},
    }
    if errors:
        result["error"] = "; ".join(errors[:3])
    return result


# ---------------------------------------------------------------------------
# APT / package update endpoints — per PBS server
# ---------------------------------------------------------------------------

@router.get("/{server_id}/updates")
def pbs_list_updates(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List available package updates for a PBS server's host OS."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        updates = svc.apt_list_updates()
        return {
            "server_id": server_id,
            "count": len(updates),
            "updates": updates,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to list PBS updates for server %s: %s", server_id, exc)
        return {
            "server_id": server_id,
            "count": 0,
            "updates": [],
            "error": str(exc),
        }


@router.post("/{server_id}/updates/refresh")
def pbs_refresh_updates(
    server_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Refresh the package index on a PBS server (apt-get update)."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        upid = svc.apt_refresh_updates()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to refresh PBS updates for server %s: %s", server_id, exc)
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")

    # Register the UPID in the task tracker so it shows in the running-tasks bar
    try:
        from app.services.task_tracker import task_tracker
        task_tracker.register(
            upid,
            host_id=-server_id,  # negative sentinel to avoid collision with PVE host IDs
            node=f"pbs:{server.name}",
            description=f"PBS apt update on {server.name}",
            user_id=getattr(current_user, "id", None),
            task_type="aptupdate",
        )
    except Exception as exc:
        logger.debug("task_tracker.register for PBS UPID failed (non-fatal): %s", exc)

    return {"upid": upid, "server_id": server_id}


@router.post("/{server_id}/updates/apply")
def pbs_apply_updates(
    server_id: int,
    payload: Optional[Dict[str, Any]] = Body(default=None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Apply pending package updates on a PBS server (apt-get dist-upgrade).

    Body: {"packages": ["pkg1", "pkg2"]} or null for all packages.
    Admin-only, rate-limited, and audited.
    """
    server = _get_pbs_server(db, server_id)

    # Rate-limit: 1 apply per 5 min per server
    if not _rate_limit_ok(f"pbs-apply:{server_id}", seconds=300):
        raise HTTPException(
            status_code=429,
            detail="An apply for this PBS server ran recently — wait a few minutes before retrying.",
        )

    packages: Optional[List[str]] = None
    if payload and isinstance(payload, dict):
        raw = payload.get("packages")
        if isinstance(raw, list) and raw:
            packages = [str(p) for p in raw]

    try:
        svc = _make_service(server)
        upid = svc.apt_upgrade(packages=packages)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to apply PBS updates for server %s: %s", server_id, exc)
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")

    # Audit the action (separate from the global audit middleware so we can
    # include the exact package count even if middleware skips it).
    try:
        from app.models.database import AuditLog
        entry = AuditLog(
            user_id=getattr(current_user, "id", None),
            action="apt_upgrade",
            resource_type="pbs",
            resource_id=server_id,
            details={
                "server_name": server.name,
                "packages": packages or "all",
                "upid": upid,
            },
            http_method="POST",
            request_path=f"/api/v1/pbs-mgmt/{server_id}/updates/apply",
            response_status=200,
            success=True,
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        logger.debug("Audit log for PBS apply failed (non-fatal): %s", exc)
        db.rollback()

    # Register in task tracker — don't let tracker errors swallow the success.
    try:
        from app.services.task_tracker import task_tracker
        desc = (
            f"PBS apt upgrade {len(packages)} package(s) on {server.name}"
            if packages else f"PBS apt upgrade all packages on {server.name}"
        )
        task_tracker.register(
            upid,
            host_id=-server_id,
            node=f"pbs:{server.name}",
            description=desc,
            user_id=getattr(current_user, "id", None),
            task_type="aptupgrade",
        )
    except Exception as exc:
        logger.debug("task_tracker.register for PBS apply UPID failed (non-fatal): %s", exc)

    return {"upid": upid, "server_id": server_id, "packages": packages}


@router.get("/{server_id}/updates/task/{upid}")
def pbs_update_task_status(
    server_id: int,
    upid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Poll a PBS apt task status (used by the Updates page to wait for refresh)."""
    server = _get_pbs_server(db, server_id)
    try:
        svc = _make_service(server)
        return svc.get_task_status(upid)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PBS API error: {exc}")


# ---------------------------------------------------------------------------
# Simple in-process rate limiter for destructive apply actions
# ---------------------------------------------------------------------------

_rate_limit_state: Dict[str, float] = {}


def _rate_limit_ok(key: str, seconds: int) -> bool:
    """Return True if enough time has passed since the last call; otherwise False."""
    now = time.time()
    last = _rate_limit_state.get(key, 0.0)
    if now - last < seconds:
        return False
    _rate_limit_state[key] = now
    return True
