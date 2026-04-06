"""Cluster operations API: tasks, replication, evacuation, event log, cluster config/join"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from app.core.database import get_db
from app.models import ProxmoxHost
from app.api.auth import get_current_user, require_operator, require_admin
from app.services.proxmox import ProxmoxService
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
    current_user=Depends(get_current_user),
):
    """Get join information for this cluster (addresses, fingerprint, totem key)."""
    host = _get_host(host_id, db)
    try:
        result = _pve(host).cluster.config.join.get()
        return result
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


# ── Node evacuation ───────────────────────────────────────────────────────────

@router.post("/{host_id}/nodes/{node}/evacuate")
def evacuate_node(
    host_id: int,
    node: str,
    body: dict = {},
    db: Session = Depends(get_db),
    current_user=Depends(require_operator),
):
    """
    Migrate all VMs off a node to other online nodes.
    Optional body: { target: 'nodename' }  — if not given, picks first available online node.
    Returns list of UPIDs for queued migrations.
    """
    host = _get_host(host_id, db)
    pve = _pve(host)

    # Get all online nodes
    try:
        all_nodes = pve.nodes.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list nodes: {e}")

    online_nodes = [n["node"] for n in all_nodes if n.get("status") == "online" and n["node"] != node]
    if not online_nodes:
        raise HTTPException(status_code=400, detail="No online target nodes available for evacuation")

    # Get VMs on the source node
    try:
        vms = pve.nodes(node).qemu.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list VMs: {e}")

    # Pick target from body or round-robin
    explicit_target = body.get("target")
    upids = []
    errors = []

    for i, vm in enumerate(vms):
        vmid = vm.get("vmid")
        if not vmid:
            continue
        target_node = explicit_target or online_nodes[i % len(online_nodes)]
        try:
            upid = pve.nodes(node).qemu(vmid).migrate.post(
                target=target_node,
                online=1,
            )
            upids.append({"vmid": vmid, "target": target_node, "upid": upid})
        except Exception as e:
            errors.append({"vmid": vmid, "error": str(e)})

    return {"queued": upids, "errors": errors, "total": len(vms)}


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
