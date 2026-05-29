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

# Interactive console / shell sessions that surface in PVE's task list but
# don't represent meaningful "background work". They linger until the user
# (or PVE's idle timeout) ends them, cluttering the floating task bar.
_INTERACTIVE_TASK_TYPES = frozenset({
    "vncshell", "vncproxy", "spiceshell", "spiceproxy", "termproxy",
})

# Circuit breaker: maps PBS server id → time.monotonic() expiry. While the
# value is in the future we skip polling that server (it failed recently).
# This stops a single unreachable PBS host from blocking the 5s task-bar
# poll on every page in the app.
_PBS_UNHEALTHY: dict[int, float] = {}


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
    """List all currently-running tasks: Depl0y-tracked + live poll from Proxmox.

    Performance notes (this endpoint is hit every 5s by the floating task bar
    on every page, so it has to stay fast even when some nodes/PBS servers are
    unreachable):
      • Skip nodes whose DB status isn't 'online' — querying an offline node
        blocks ~30s on a TCP connect and brings the whole call past the 60s
        axios timeout.
      • Run per-node `tasks.get(source="active")` calls in a ThreadPoolExecutor
        with a short wall-clock budget; any node that exceeds it is dropped
        from this tick (it'll be retried in 5s).
      • Same circuit-breaker logic for PBS servers via `_PBS_UNHEALTHY`.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.models.database import ProxmoxNode

    # Start with Depl0y in-memory tracked tasks
    tracked = task_tracker.get_running()
    tracked_upids = {t["upid"] for t in tracked}

    # ── PVE: parallel per-node tasks.get, skipping offline nodes ──────────────
    node_targets: list[tuple[int, str]] = []  # (host_id, node_name)
    host_index: dict[int, ProxmoxHost] = {}
    try:
        hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()
        for host in hosts:
            host_index[host.id] = host
            db_nodes = (
                db.query(ProxmoxNode)
                .filter(
                    ProxmoxNode.host_id == host.id,
                    ProxmoxNode.status == "online",
                )
                .all()
            )
            if db_nodes:
                for n in db_nodes:
                    node_targets.append((host.id, n.node_name))
            else:
                # First-run / no poll yet — fall back to a single live nodes.get
                # so the UI still shows tasks before the poller has run.
                try:
                    live = ProxmoxService(host).proxmox.nodes.get()
                    for n in live:
                        if n.get("status") == "online" and n.get("node"):
                            node_targets.append((host.id, n["node"]))
                except Exception:
                    pass
    except Exception as exc:
        logger.debug("get_running_tasks host enumeration error: %s", exc)

    def _fetch_node_tasks(host_id: int, node_name: str):
        host = host_index.get(host_id)
        if not host:
            return host_id, node_name, []
        try:
            pve = ProxmoxService(host).proxmox
            return host_id, node_name, pve.nodes(node_name).tasks.get(source="active") or []
        except Exception as e:
            logger.debug("tasks.get failed for %s/%s: %s", host_id, node_name, e)
            return host_id, node_name, []

    pve_running = []
    if node_targets:
        # Wall-clock budget: must finish well under the frontend's 60s timeout
        # so the rest of the response (PBS + progress) still has time. 12s
        # leaves plenty of headroom for the 5s poll cadence.
        deadline = time.monotonic() + 12.0
        with ThreadPoolExecutor(max_workers=min(len(node_targets), 16)) as pool:
            futures = {
                pool.submit(_fetch_node_tasks, hid, nn): (hid, nn)
                for hid, nn in node_targets
            }
            for fut in as_completed(futures):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.warning("get_running_tasks: PVE budget exceeded, dropping unfinished nodes")
                    break
                try:
                    host_id, node_name, node_tasks = fut.result(timeout=remaining)
                except Exception:
                    continue
                for t in node_tasks:
                    upid = t.get("upid")
                    if not upid or upid in tracked_upids:
                        continue
                    if t.get("type") in _INTERACTIVE_TASK_TYPES:
                        continue
                    pve_running.append({
                        "upid": upid,
                        "host_id": host_id,
                        "node": node_name,
                        "task_type": t.get("type", "unknown"),
                        "description": f"{t.get('type', 'Task')} on {node_name}"
                                       + (f" (VM {t['id']})" if t.get("id") else ""),
                        "status": "running",
                        "vmid": t.get("id"),
                        "started_at": t.get("starttime"),
                        "source": "proxmox",
                    })
                    tracked_upids.add(upid)

    # ── PBS: parallel poll with circuit breaker for unreachable servers ───────
    pbs_running = []
    try:
        from app.models.database import PBSServer
        from app.services.pbs import PBSService

        active_pbs = db.query(PBSServer).filter(PBSServer.is_active == True).all()
        # Skip servers that failed recently (set by previous tick)
        now = time.monotonic()
        targets = [p for p in active_pbs if _PBS_UNHEALTHY.get(p.id, 0) < now]

        def _fetch_pbs_tasks(pbs):
            try:
                svc = PBSService(pbs)
                return pbs, svc._get("/nodes/localhost/tasks?running=1&limit=100") or []
            except Exception as e:
                logger.debug("pbs tasks poll failed for %s: %s", pbs.name, e)
                # Skip this server for the next 60s so the dashboard isn't
                # blocked by an unreachable PBS host on every 5s poll.
                _PBS_UNHEALTHY[pbs.id] = time.monotonic() + 60
                return pbs, None

        if targets:
            deadline = time.monotonic() + 8.0
            with ThreadPoolExecutor(max_workers=min(len(targets), 8)) as pool:
                futures = {pool.submit(_fetch_pbs_tasks, p): p for p in targets}
                for fut in as_completed(futures):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        logger.warning("get_running_tasks: PBS budget exceeded")
                        break
                    try:
                        pbs, tasks = fut.result(timeout=remaining)
                    except Exception:
                        continue
                    if tasks is None:
                        continue
                    for t in tasks:
                        upid = t.get("upid")
                        if not upid or upid in tracked_upids:
                            continue
                        ttype = t.get("worker_type") or t.get("type") or "unknown"
                        worker_id = t.get("worker_id") or ""
                        desc = f"{ttype} on {pbs.name}" + (f" ({worker_id})" if worker_id else "")
                        pbs_running.append({
                            "upid": upid,
                            "host_id": None,
                            "server_id": pbs.id,
                            "pbs_name": pbs.name,
                            "node": "localhost",
                            "task_type": ttype,
                            "description": desc,
                            "status": "running",
                            "started_at": t.get("starttime"),
                            "source": "pbs",
                        })
                        tracked_upids.add(upid)
    except Exception as exc:
        logger.debug("get_running_tasks pbs poll outer error: %s", exc)

    result = tracked + pve_running + pbs_running
    for t in result:
        if t.get("source") == "proxmox":
            # External PVE task — fetch+parse log with short TTL cache
            t["progress"] = task_tracker.progress_for_external(
                upid=t.get("upid"),
                host_id=t.get("host_id"),
                node=t.get("node"),
                started_at_ts=t.get("started_at"),
                task_type=t.get("task_type") or "",
            )
        elif t.get("source") == "pbs":
            # PBS tasks — use a time-based estimate for now (no log-parse yet).
            # sync / verify / gc can run for hours; cap at 50% so the bar doesn't lie.
            import time as _t
            started = t.get("started_at")
            if started:
                elapsed = _t.time() - float(started)
                t["progress"] = round(min(elapsed / 1800 * 100, 50.0), 1)  # 30-min reference
            else:
                t["progress"] = 0.0
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
