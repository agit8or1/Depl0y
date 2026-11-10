"""Cluster operations API: tasks, replication, evacuation, event log, cluster config/join"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from app.core.database import get_db
from app.models import ProxmoxHost
from app.api.auth import get_current_user, require_operator, require_admin
from app.services.proxmox import ProxmoxService
from app.services import node_evacuation
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_host(host_id: int, db: Session) -> ProxmoxHost:
    host = db.query(ProxmoxHost).filter(
        ProxmoxHost.id == host_id, ProxmoxHost.is_active == True
    ).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")
    return host


def _pve(host: ProxmoxHost):
    return ProxmoxService(host).proxmox


# ── Pydantic models ────────────────────────────────────────────────────────────

class CreateClusterRequest(BaseModel):
    clustername: str


class JoinClusterRequest(BaseModel):
    hostname: str          # master node IP or hostname
    password: str          # root password for the master node
    fingerprint: Optional[str] = None    # TLS fingerprint (optional, auto-detected)
    link0: Optional[str] = None          # corosync link address override


# ── Cluster config / join endpoints ───────────────────────────────────────────

@router.get("/{host_id}/status")
def cluster_status(
    host_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get cluster status: name, nodes, quorum."""
    host = _get_host(host_id, db)
    try:
        raw = _pve(host).cluster.status.get()
        cluster_info = None
        nodes = []
        quorate = None
        for item in raw:
            if item.get("type") == "cluster":
                cluster_info = item
                quorate = bool(item.get("quorate", 0))
            elif item.get("type") == "node":
                nodes.append(item)
        return {
            "cluster": cluster_info,
            "nodes": nodes,
            "quorate": quorate,
            "node_count": len(nodes),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/config")
def cluster_config(
    host_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get cluster configuration (nodes, corosync config)."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.config.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/config/join")
def cluster_config_join(
    host_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Get join information for this cluster (addresses, fingerprint, totem key)."""
    host = _get_host(host_id, db)
    try:
        result = _pve(host).cluster.config.join.get()
        # Extract fingerprint from the preferred node's pve_fp field.
        # Proxmox returns fingerprint per-node in nodelist[].pve_fp, not at top level.
        preferred_node = result.get("preferred_node")
        fingerprint = None
        preferred_addr = None
        for node in result.get("nodelist", []):
            if node.get("name") == preferred_node:
                fingerprint = node.get("pve_fp")
                preferred_addr = node.get("pve_addr") or node.get("ring0_addr")
                break
        if not fingerprint and result.get("nodelist"):
            first = result["nodelist"][0]
            fingerprint = first.get("pve_fp")
            preferred_addr = first.get("pve_addr") or first.get("ring0_addr")
        return {**result, "fingerprint": fingerprint, "preferred_node_addr": preferred_addr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/config/join")
def join_cluster(
    host_id: int,
    body: JoinClusterRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Join this Proxmox node to an existing cluster.
    Proxmox API: POST /cluster/config/join
    Warning: this restarts pve-cluster service (~30s downtime on this node).
    """
    host = _get_host(host_id, db)
    try:
        params = {
            "hostname": body.hostname,
            "password": body.password,
        }
        if body.fingerprint:
            params["fingerprint"] = body.fingerprint
        if body.link0:
            params["link0"] = body.link0
        result = _pve(host).cluster.config.join.post(**params)
        return {"success": True, "join_initiated": True, "result": result}
    except Exception as e:
        err = str(e)
        # pve-cluster restarts on join — the API connection may drop mid-call.
        # A connection reset/timeout here still means the join was initiated.
        if any(s in err.lower() for s in ("connection", "reset", "timeout", "eof", "broken pipe", "remotedisconnected")):
            return {"success": True, "join_initiated": True, "result": "Join initiated (node restarting pve-cluster)"}
        raise HTTPException(status_code=500, detail=err)


@router.delete("/{host_id}/config/nodes/{node}")
def remove_cluster_node(
    host_id: int,
    node: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Remove a node from the cluster (run from an active cluster member, not the node being removed).
    Proxmox API: DELETE /cluster/config/nodes/{node}
    """
    host = _get_host(host_id, db)
    try:
        result = _pve(host).cluster.config.nodes(node).delete()
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/config")
def create_cluster(
    host_id: int,
    body: CreateClusterRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Create a new Proxmox cluster from this standalone node.
    Proxmox API: POST /cluster/config  (clustername=...)
    """
    host = _get_host(host_id, db)
    try:
        result = _pve(host).cluster.config.post(clustername=body.clustername)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Cluster tasks ─────────────────────────────────────────────────────────────

@router.get("/{host_id}/tasks")
def list_cluster_tasks(
    host_id: int,
    limit: int = 100,
    start: int = 0,
    typefilter: Optional[str] = None,
    vmid: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List cluster-wide tasks (across all nodes), merged and sorted by start time."""
    host = _get_host(host_id, db)
    pve = _pve(host)
    try:
        nodes = pve.nodes.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list nodes: {e}")

    all_tasks = []
    params = {"limit": limit, "start": start}
    if typefilter:
        params["typefilter"] = typefilter
    if vmid:
        params["vmid"] = vmid

    for n in nodes:
        node_name = n.get("node")
        if not node_name:
            continue
        try:
            tasks = pve.nodes(node_name).tasks.get(**params)
            for t in tasks:
                t["_node"] = node_name
            all_tasks.extend(tasks)
        except Exception:
            pass

    # Sort by starttime descending, newest first
    all_tasks.sort(key=lambda t: t.get("starttime", 0), reverse=True)
    return all_tasks[:limit]


# ── Replication ───────────────────────────────────────────────────────────────

@router.get("/{host_id}/replication")
def list_replication(
    host_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all replication jobs."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.replication.get()
    except Exception:
        return []


@router.post("/{host_id}/replication")
def create_replication(
    host_id: int,
    job: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_operator),
):
    """Create a replication job. Required fields: id, type ('local'), target, source (vmid)."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.replication.post(**job)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/replication/{job_id}")
def update_replication(
    host_id: int,
    job_id: str,
    job: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_operator),
):
    """Update a replication job."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.replication(job_id).put(**job)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/replication/{job_id}")
def delete_replication(
    host_id: int,
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_operator),
):
    """Delete a replication job."""
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.replication(job_id).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/replication/{job_id}/schedule_now")
def force_replication(
    host_id: int,
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_operator),
):
    """Trigger immediate replication for a job (schedule_now)."""
    host = _get_host(host_id, db)
    try:
        # Proxmox replication schedule_now: POST /replication/{id}/schedule_now
        result = _pve(host).cluster.replication(job_id).schedule_now.post()
        return {"success": True, "upid": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Node maintenance: preview and verified evacuation ────────────────────────
#
# GET  .../nodes/{node}/maintenance/preview  read-only plan for every guest (any user with host access)
# POST .../nodes/{node}/evacuate             carry out a reviewed plan (admin)
# GET  .../evacuations[/{job_id}]            follow a job; POST .../{job_id}/cancel stops after the current move
#
# The decisions live in app.services.node_evacuation. Host power actions are not part of this.

class EvacuateRequest(BaseModel):
    plan_id: str
    guests: Optional[List[str]] = None          # sids to move; default: every "online" guest in the plan
    allow_downtime: List[str] = []              # sids allowed a restart/cold move (an explicit decision each)


def _plan_or_404(plan_id: str, host_id: int, node: str, user):
    plan = node_evacuation.get_plan(plan_id)
    if not plan or plan["host_id"] != host_id or plan["node"] != node:
        raise HTTPException(status_code=404, detail="Plan not found or expired; preview the node again")
    if plan["user_id"] != getattr(user, "id", None):
        raise HTTPException(status_code=403, detail="Only the user who reviewed this plan can carry it out")
    return plan


@router.get("/{host_id}/nodes/{node}/maintenance/preview")
def maintenance_preview(
    host_id: int,
    node: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Where every VM and container on the node would go, and why. Makes no changes in Proxmox."""
    pve = _pve(_get_host(host_id, db))
    try:
        facts = node_evacuation.gather_facts(pve, node)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not read the cluster from Proxmox: {e}")
    if node not in facts["cluster"]["nodes"]:
        raise HTTPException(status_code=404, detail=f"Node {node} is not in this cluster")
    return node_evacuation.store_plan(host_id, node_evacuation.build_preview(facts), current_user.id)


@router.post("/{host_id}/nodes/{node}/evacuate")
def evacuate_node(
    host_id: int,
    node: str,
    body: EvacuateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Carry out a reviewed maintenance plan. Each move is checked again first and verified after.

    Only guests from the plan move, each to its reviewed target. A guest that needs downtime moves
    only if listed in allow_downtime. Returns a job id; follow it at GET /evacuations/{job_id}.
    """
    plan = _plan_or_404(body.plan_id, host_id, node, current_user)
    preview = plan["preview"]
    if not preview.get("executable"):
        raise HTTPException(status_code=409, detail="The reviewed plan failed a cluster check; fix it and preview again")
    by_sid = {e["sid"]: e for e in preview["guests"]}
    wanted = body.guests if body.guests is not None else [
        e["sid"] for e in preview["guests"] if e["class"] == "online"] + [
        s for s in body.allow_downtime if s in by_sid]
    if not wanted:
        raise HTTPException(status_code=400, detail="Nothing to move")
    entries, seen = [], set()
    for sid in wanted:
        e = by_sid.get(sid)
        if e is None:
            raise HTTPException(status_code=400, detail=f"{sid} is not in the reviewed plan")
        if sid in seen:
            continue
        seen.add(sid)
        if e["class"] not in ("online", "downtime"):
            raise HTTPException(status_code=400, detail=f"{sid} is {e['class']} in the plan: {e['reason']}")
        if e["class"] == "downtime" and sid not in body.allow_downtime:
            raise HTTPException(status_code=400,
                                detail=f"{sid} needs downtime ({e['method']} move); list it in allow_downtime to move it")
        entries.append(e)
    pve = _pve(_get_host(host_id, db))
    perms = node_evacuation.check_permissions(_safe_permissions(pve), entries)
    if perms["checked"] and not perms["execute"]["ok"]:
        missing = sorted({f"{m['privilege']} on {m['path']}" for m in perms["execute"]["missing"]})
        raise HTTPException(status_code=403,
                            detail="The Proxmox API token for this host lacks: " + ", ".join(missing))
    try:
        job = node_evacuation.start_job(host_id, node, body.plan_id, current_user.id, entries, pve)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"job_id": job.id, "guests": [e["sid"] for e in entries]}


def _safe_permissions(pve):
    try:
        return pve.access.permissions.get()
    except Exception:
        return None


@router.get("/{host_id}/evacuations")
def list_evacuations(host_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Recent evacuation jobs on this cluster (kept in memory for a day)."""
    _get_host(host_id, db)
    return [j.snapshot() for j in node_evacuation.list_jobs(host_id)]


@router.get("/{host_id}/evacuations/{job_id}")
def evacuation_status(host_id: int, job_id: str, db: Session = Depends(get_db),
                      current_user=Depends(get_current_user)):
    job = node_evacuation.get_job(job_id)
    if not job or job.host_id != host_id:
        raise HTTPException(status_code=404, detail="Evacuation job not found (it may have expired)")
    return job.snapshot()


@router.post("/{host_id}/evacuations/{job_id}/cancel")
def cancel_evacuation(host_id: int, job_id: str, db: Session = Depends(get_db),
                      current_user=Depends(require_admin)):
    """Stop after the move in progress; a running Proxmox migration is not interrupted."""
    job = node_evacuation.get_job(job_id)
    if not job or job.host_id != host_id:
        raise HTTPException(status_code=404, detail="Evacuation job not found (it may have expired)")
    job.cancel.set()
    return {"cancel_requested": True, "status": job.status}


# ── Cluster event log ─────────────────────────────────────────────────────────

@router.get("/{host_id}/log")
def cluster_log(
    host_id: int,
    max: int = 500,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Cluster-wide event log."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.log.get(max=max)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Node replication status ───────────────────────────────────────────────────

@router.get("/{host_id}/replication/{job_id}/log")
def replication_job_log(
    host_id: int,
    job_id: str,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get log output for a specific replication job run."""
    host = _get_host(host_id, db)
    try:
        # job_id format: {vmid}-{target} or numeric id
        # Proxmox: GET /replication/{id}/log is not standard; we pull from task log instead
        # Return job status
        status = _pve(host).cluster.replication(job_id).get()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
