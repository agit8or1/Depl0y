"""Task queue management API — tracks all async Proxmox operations initiated through Depl0y."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.models import ProxmoxHost
from app.api.auth import get_current_user, require_operator
from app.services.proxmox import ProxmoxService
from app.services.task_tracker import task_tracker
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_host(host_id: int, db: Session) -> ProxmoxHost:
    host = db.query(ProxmoxHost).filter(
        ProxmoxHost.id == host_id,
        ProxmoxHost.is_active == True,
    ).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")
    return host


def _pve(host: ProxmoxHost):
    return ProxmoxService(host).proxmox


# ── Running tasks ─────────────────────────────────────────────────────────────

@router.get("/running")
def get_running_tasks(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """List all currently-running tasks: Depl0y-tracked + live poll from Proxmox."""
    # Start with Depl0y in-memory tracked tasks
    tracked = task_tracker.get_running()
    tracked_upids = {t["upid"] for t in tracked}

    # Also query Proxmox directly for any running tasks across all active hosts/nodes
    pve_running = []
    try:
        hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()
        from app.models.database import ProxmoxNode
        for host in hosts:
            try:
                pve = _pve(host)
                db_nodes = db.query(ProxmoxNode).filter(ProxmoxNode.host_id == host.id).all()
                # Fall back to live Proxmox node query if DB has no records yet
                if db_nodes:
                    node_names = [n.node_name for n in db_nodes]
                else:
                    live = pve.nodes.get()
                    node_names = [n.get("node") for n in live if n.get("node")]
                for node_name in node_names:
                    try:
                        # source=active returns currently-running tasks only.
                        # Without it, Proxmox returns historical (finished) tasks.
                        node_tasks = pve.nodes(node_name).tasks.get(source="active")
                        for t in node_tasks:
                            if t.get("upid") in tracked_upids:
                                continue
                            pve_running.append({
                                "upid": t.get("upid"),
                                "host_id": host.id,
                                "node": node_name,
                                "task_type": t.get("type", "unknown"),
                                "description": f"{t.get('type', 'Task')} on {node_name}"
                                               + (f" (VM {t['id']})" if t.get("id") else ""),
                                "status": "running",
                                "vmid": t.get("id"),
                                "started_at": t.get("starttime"),
                                "source": "proxmox",
                            })
                            tracked_upids.add(t.get("upid"))
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception as exc:
        logger.debug("get_running_tasks pve poll error: %s", exc)

    result = tracked + pve_running
    for t in result:
        if t.get("source") == "proxmox":
            # External task — fetch+parse log with short TTL cache
            t["progress"] = task_tracker.progress_for_external(
                upid=t.get("upid"),
                host_id=t.get("host_id"),
                node=t.get("node"),
                started_at_ts=t.get("started_at"),
                task_type=t.get("task_type") or "",
            )
        else:
            t["progress"] = task_tracker.estimate_progress(t)
    # Drop cache entries for tasks that are no longer running
    task_tracker.prune_ext_progress({t.get("upid") for t in result if t.get("upid")})
    return result


# ── Task history ──────────────────────────────────────────────────────────────

@router.get("/history")
def get_task_history(
    limit: int = 50,
    user_id: Optional[int] = None,
    current_user=Depends(get_current_user),
):
    """List recent completed tasks from the in-memory tracker."""
    # Non-admins only see their own tasks
    from app.models import UserRole
    effective_user_id = user_id
    if current_user.role != UserRole.ADMIN:
        effective_user_id = current_user.id
    return task_tracker.get_history(limit=limit, user_id=effective_user_id)


# ── Single task status ────────────────────────────────────────────────────────

@router.get("/{host_id}/{node}/{upid}/status")
def get_task_status(
    host_id: int,
    node: str,
    upid: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get the live status of a specific task directly from Proxmox."""
    host = _get_host(host_id, db)
    try:
        result = _pve(host).nodes(node).tasks(upid).status.get()
        # Also attach tracker metadata if available
        tracked = task_tracker.get_task(upid)
        if tracked:
            result["description"] = tracked.get("description")
            result["progress"] = task_tracker.estimate_progress(tracked)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Task log ──────────────────────────────────────────────────────────────────

@router.get("/{host_id}/{node}/{upid}/log")
def get_task_log(
    host_id: int,
    node: str,
    upid: str,
    start: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Fetch task log lines from Proxmox. Returns a JSON array of log lines."""
    host = _get_host(host_id, db)
    try:
        lines = _pve(host).nodes(node).tasks(upid).log.get(start=start, limit=limit)
        return {"lines": [ln.get("t", "") for ln in lines]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Stop / cancel task ────────────────────────────────────────────────────────

@router.delete("/{host_id}/{node}/{upid}")
def stop_task(
    host_id: int,
    node: str,
    upid: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_operator),
):
    """Stop / cancel a running Proxmox task."""
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).tasks(upid).delete()
        # Update tracker immediately
        task_tracker.update_status(upid, "stopped", "stopped")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
