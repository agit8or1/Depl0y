"""Dashboard API routes"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.models import (
    VirtualMachine,
    VMStatus,
    ProxmoxHost,
    ProxmoxNode,
    ISOImage,
    User,
    UpdateLog,
)
from app.api.auth import get_current_user
from app.services.proxmox import is_cloud_template

router = APIRouter()
logger = logging.getLogger(__name__)


# Pydantic models
class DashboardStats(BaseModel):
    total_vms: int
    running_vms: int
    stopped_vms: int
    paused_vms: int
    datacenters: int
    total_nodes: int
    total_isos: int
    total_users: int


class ResourceStats(BaseModel):
    total_cpu_cores: int
    total_memory_gb: float
    total_disk_gb: float
    used_cpu_cores: int
    used_memory_gb: float
    used_disk_gb: float


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get dashboard statistics - queries actual Proxmox data"""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from app.services.proxmox import ProxmoxService

    # Query all active Proxmox hosts
    active_hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()

    def fetch_resources_for_host(host):
        """Use cluster/resources (single call) instead of per-node qemu.get()"""
        try:
            service = ProxmoxService(host)
            # One API call returns all VMs/LXCs across all nodes
            resources = service.proxmox.cluster.resources.get(type='vm')
            return resources
        except Exception as e:
            logger.error(f"Failed to get resources from host {host.name}: {e}")
            return []

    # Fetch all hosts concurrently
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=min(len(active_hosts) or 1, 8)) as pool:
        futures = [loop.run_in_executor(pool, fetch_resources_for_host, h) for h in active_hosts]
        results = await asyncio.gather(*futures, return_exceptions=True)

    total_vms = 0
    running_vms = 0
    stopped_vms = 0
    paused_vms = 0

    for resources in results:
        if isinstance(resources, Exception) or not resources:
            continue
        for vm in resources:
            if is_cloud_template(vm):
                continue
            total_vms += 1
            status = vm.get('status', '').lower()
            if status == 'running':
                running_vms += 1
            elif status == 'stopped':
                stopped_vms += 1
            elif status == 'paused':
                paused_vms += 1

    # Datacenter count (number of Proxmox hosts)
    datacenters = len(active_hosts)

    # Node statistics
    total_nodes = db.query(ProxmoxNode).count()

    # ISO statistics
    total_isos = db.query(ISOImage).filter(ISOImage.is_available == True).count()

    # User statistics (admin only)
    if current_user.role.value == "admin":
        total_users = db.query(User).count()
    else:
        total_users = 0

    return {
        "total_vms": total_vms,
        "running_vms": running_vms,
        "stopped_vms": stopped_vms,
        "paused_vms": paused_vms,
        "datacenters": datacenters,
        "total_nodes": total_nodes,
        "total_isos": total_isos,
        "total_users": total_users,
    }


@router.get("/resources", response_model=ResourceStats)
async def get_resource_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get resource statistics across all nodes"""
    # Query node resources - these are ACTUAL usage from Proxmox
    nodes = db.query(ProxmoxNode).all()

    total_cpu_cores = 0
    total_memory_bytes = 0
    total_disk_bytes = 0
    used_memory_bytes = 0
    used_disk_bytes = 0
    total_cpu_usage_percent = 0
    node_count = 0

    for node in nodes:
        if node.cpu_cores:
            total_cpu_cores += node.cpu_cores
        if node.memory_total:
            total_memory_bytes += node.memory_total
        if node.memory_used:
            used_memory_bytes += node.memory_used
        if node.disk_total:
            total_disk_bytes += node.disk_total
        if node.disk_used:
            used_disk_bytes += node.disk_used
        if node.cpu_usage is not None:
            total_cpu_usage_percent += node.cpu_usage
            node_count += 1

    # Calculate used CPU cores based on average CPU usage across nodes
    # This gives actual CPU usage, not just allocated cores
    if node_count > 0 and total_cpu_cores > 0:
        avg_cpu_usage_percent = total_cpu_usage_percent / node_count
        used_cpu_cores = int((avg_cpu_usage_percent / 100.0) * total_cpu_cores)
    else:
        used_cpu_cores = 0

    return {
        "total_cpu_cores": total_cpu_cores,
        "total_memory_gb": round(total_memory_bytes / (1024**3), 2),
        "total_disk_gb": round(total_disk_bytes / (1024**3), 2),
        "used_cpu_cores": used_cpu_cores,
        "used_memory_gb": round(used_memory_bytes / (1024**3), 2),
        "used_disk_gb": round(used_disk_bytes / (1024**3), 2),
    }


@router.get("/activity")
async def get_recent_activity(
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get recent activity"""
    # Recent VMs
    recent_vms = (
        db.query(VirtualMachine)
        .order_by(VirtualMachine.created_at.desc())
        .limit(limit)
        .all()
    )

    # Recent updates
    recent_updates = (
        db.query(UpdateLog)
        .order_by(UpdateLog.started_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "recent_vms": [
            {
                "id": vm.id,
                "name": vm.name,
                "status": vm.status.value,
                "created_at": vm.created_at.isoformat(),
            }
            for vm in recent_vms
        ],
        "recent_updates": [
            {
                "id": log.id,
                "vm_id": log.vm_id,
                "status": log.status,
                "packages_updated": log.packages_updated,
                "started_at": log.started_at.isoformat(),
            }
            for log in recent_updates
        ],
    }


@router.get("/summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All-in-one summary for the dashboard: vm counts, nodes, storage, failed tasks, active users."""
    from app.services.proxmox import ProxmoxService
    from app.models.database import AuditLog
    from sqlalchemy import desc
    from datetime import datetime, timedelta
    import time

    active_hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()

    def fetch_vm_summary(host):
        try:
            service = ProxmoxService(host)
            resources = service.proxmox.cluster.resources.get(type='vm')
            return resources
        except Exception:
            return []

    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=min(len(active_hosts) or 1, 8)) as pool:
        futures = [loop.run_in_executor(pool, fetch_vm_summary, h) for h in active_hosts]
        results = await asyncio.gather(*futures, return_exceptions=True)

    total_vms = 0
    running_vms = 0
    for resources in results:
        if isinstance(resources, Exception) or not resources:
            continue
        real_vms = [v for v in resources if not is_cloud_template(v)]
        total_vms += len(real_vms)
        running_vms += sum(1 for v in real_vms if v.get("status", "").lower() == "running")

    node_count = db.query(ProxmoxNode).count()

    # Storage used from node data
    nodes = db.query(ProxmoxNode).all()
    total_disk_bytes = sum(n.disk_total or 0 for n in nodes)
    used_disk_bytes = sum(n.disk_used or 0 for n in nodes)
    storage_used_gb = round(used_disk_bytes / (1024 ** 3), 2)
    storage_total_gb = round(total_disk_bytes / (1024 ** 3), 2)

    # Failed tasks in last 24h via audit log
    from sqlalchemy import or_
    cutoff = datetime.utcnow() - timedelta(hours=24)
    failed_tasks_24h = (
        db.query(AuditLog)
        .filter(AuditLog.timestamp >= cutoff)
        .filter(or_(AuditLog.action.ilike("%fail%"), AuditLog.action.ilike("%error%")))
        .count()
    )

    # Active users — users with audit activity in last 24h
    from sqlalchemy import distinct
    active_users = (
        db.query(func.count(distinct(AuditLog.user_id)))
        .filter(AuditLog.timestamp >= cutoff)
        .scalar()
    ) or 0

    return {
        "vm_count": total_vms,
        "running_vms": running_vms,
        "node_count": node_count,
        "storage_used_gb": storage_used_gb,
        "storage_total_gb": storage_total_gb,
        "failed_tasks_24h": failed_tasks_24h,
        "active_users": active_users,
    }


@router.get("/recent-activity")
async def get_recent_activity_alias(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Alias to the audit feed — last N audit entries as a simplified feed."""
    from app.models.database import AuditLog
    from sqlalchemy import desc
    from app.api.audit import _action_icon

    logs = (
        db.query(AuditLog)
        .order_by(desc(AuditLog.timestamp))
        .offset(offset)
        .limit(limit)
        .all()
    )
    feed = []
    for l in logs:
        username = l.user.username if l.user else "system"
        resource = l.resource_type or ""
        if l.resource_id:
            resource = f"{resource} #{l.resource_id}" if resource else f"#{l.resource_id}"
        feed.append({
            "id": l.id,
            "time": l.timestamp.isoformat(),
            "user": username,
            "action": l.action.replace("_", " ").lower(),
            "resource": resource,
            "resource_type": l.resource_type or "",
            "icon": _action_icon(l.action),
        })
    return feed


@router.get("/alerts")
async def get_dashboard_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compute and return dashboard alerts: offline nodes, storage near full, failed backups, etc."""
    from app.services.proxmox import ProxmoxService
    from app.models.database import AuditLog
    from sqlalchemy import desc
    from datetime import datetime, timedelta

    alerts = []
    cutoff_24h = datetime.utcnow() - timedelta(hours=24)

    # 1. Offline nodes (from cached node data — node.is_online or cpu_usage is None)
    all_nodes = db.query(ProxmoxNode).all()
    offline_node_names = set()
    for node in all_nodes:
        # Heuristic: if cpu_usage is None, treat as potentially offline
        if node.cpu_usage is None and node.memory_total is None:
            offline_node_names.add(node.node_name)
            alerts.append({
                "severity": "error",
                "type": "offline_node",
                "title": f"Node may be offline: {node.node_name}",
                "detail": "No telemetry data available for this node.",
            })

    # 2. Storage near full (>85%)
    for node in all_nodes:
        if node.disk_total and node.disk_total > 0 and node.disk_used:
            pct = (node.disk_used / node.disk_total) * 100
            if pct > 85:
                alerts.append({
                    "severity": "warning",
                    "type": "storage_near_full",
                    "title": f"Storage near full on {node.node_name}",
                    "detail": f"{pct:.1f}% used ({round(node.disk_used / (1024**3), 1)} GB / {round(node.disk_total / (1024**3), 1)} GB)",
                })

    # 3. Failed backup jobs in last 24h (via audit log)
    from sqlalchemy import or_
    failed_backups = (
        db.query(AuditLog)
        .filter(AuditLog.timestamp >= cutoff_24h)
        .filter(AuditLog.action.ilike("%backup%"))
        .filter(or_(AuditLog.action.ilike("%fail%"), AuditLog.action.ilike("%error%")))
        .all()
    )
    for log in failed_backups:
        username = log.user.username if log.user else "system"
        alerts.append({
            "severity": "error",
            "type": "failed_backup",
            "title": f"Backup job failed",
            "detail": f"Action: {log.action} — by {username} at {log.timestamp.strftime('%H:%M')}",
        })

    # 4. Unexpectedly stopped VMs (VMs in DB with status stopped that were previously running)
    stopped_vms = (
        db.query(VirtualMachine)
        .filter(VirtualMachine.status == VMStatus.STOPPED)
        .limit(5)
        .all()
    )
    for vm in stopped_vms:
        alerts.append({
            "severity": "info",
            "type": "stopped_vm",
            "title": f"VM stopped: {vm.name}",
            "detail": f"VM ID {vm.id} is currently stopped.",
        })

    return {"alerts": alerts, "count": len(alerts)}
