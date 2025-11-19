"""Dashboard API routes"""
from fastapi import APIRouter, Depends
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
    from app.services.proxmox import ProxmoxService

    # Query all active Proxmox hosts and get VM counts from Proxmox itself
    active_hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()

    total_vms = 0
    running_vms = 0
    stopped_vms = 0
    paused_vms = 0

    for host in active_hosts:
        try:
            service = ProxmoxService(host)
            vms = service.get_all_vms()
            total_vms += len(vms)

            for vm in vms:
                status = vm.get('status', '').lower()
                if status == 'running':
                    running_vms += 1
                elif status == 'stopped':
                    stopped_vms += 1
                elif status == 'paused':
                    paused_vms += 1
        except Exception as e:
            logger.error(f"Failed to get VMs from host {host.name}: {e}")

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
    limit: int = 10,
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
