"""High Availability summary across every registered Proxmox endpoint.

HA management itself is per cluster and lives under /pve-node/{host_id}/cluster/ha/*
(resources, groups, status, services) and /ha-wizard. This router only answers the
Settings page's "is HA in use anywhere?" question.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models import ProxmoxHost
from app.services.proxmox import ProxmoxService

logger = logging.getLogger(__name__)

router = APIRouter()


def _host_status(host: ProxmoxHost) -> dict:
    entry = {"host_id": host.id, "name": host.name, "error": None}
    try:
        px = ProxmoxService(host).proxmox
        wrapper = px.cluster.ha.status.manager_status.get() or {}
        inner = wrapper.get("manager_status") or {}
        quorum_info = wrapper.get("quorum") or {}
        node_status = inner.get("node_status") or {}
        online = sum(1 for s in node_status.values() if s == "online")
        master_node = inner.get("master_node")
        try:
            resources = px.cluster.ha.resources.get() or []
            protected_vms = len(resources) if isinstance(resources, list) else 0
        except Exception:
            protected_vms = 0
        if master_node and online > 0:
            manager_state = "active"
        elif online > 0:
            manager_state = "no-master"
        else:
            manager_state = "inactive"
        entry.update(
            enabled=bool(node_status) or protected_vms > 0,
            protected_vms=protected_vms,
            manager_status=manager_state,
            quorum=str(quorum_info.get("quorate", "")) == "1",
            master_node=master_node,
            nodes_online=online,
            nodes_total=len(node_status),
        )
    except Exception as e:
        logger.warning("HA status for host %s failed: %s", host.id, e)
        entry.update(enabled=False, protected_vms=0, manager_status="unknown", quorum=False,
                     master_node=None, nodes_online=0, nodes_total=0, error=str(e))
    return entry


@router.get("/status")
def check_ha_status(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """HA state of every active Proxmox endpoint, plus totals (read through the API)."""
    hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).order_by(ProxmoxHost.id).all()
    per_host = [_host_status(h) for h in hosts]
    enabled = any(h["enabled"] for h in per_host)
    protected = sum(h["protected_vms"] for h in per_host)
    if not hosts:
        message = "No Proxmox hosts configured"
    elif enabled:
        message = f"HA protects {protected} guest(s) across {sum(1 for h in per_host if h['protected_vms'])} endpoint(s)"
    else:
        message = "High Availability not configured"
    return {"enabled": enabled, "protected_vms": protected, "hosts": per_host, "message": message}
