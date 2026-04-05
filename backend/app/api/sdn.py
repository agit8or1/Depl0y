"""Proxmox SDN (Software-Defined Networking) API routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Any, Dict
from pydantic import BaseModel

from app.core.database import get_db
from app.models import ProxmoxHost
from app.api.auth import get_current_user, require_admin
from app.services.proxmox import ProxmoxService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sdn", tags=["SDN"])


# ── Pydantic models ────────────────────────────────────────────────────────────

class VNetCreate(BaseModel):
    vnet: str
    zone: str
    alias: Optional[str] = None
    tag: Optional[int] = None
    type: Optional[str] = None

class VNetUpdate(BaseModel):
    alias: Optional[str] = None
    tag: Optional[int] = None
    zone: Optional[str] = None

class ZoneCreate(BaseModel):
    zone: str
    type: str  # simple, vlan, qinq, vxlan, evpn
    # common
    mtu: Optional[int] = None
    nodes: Optional[str] = None
    # simple/vlan
    bridge: Optional[str] = None
    bridge_disable_mac_learning: Optional[int] = None
    # vlan
    vlan_protocol: Optional[str] = None
    # vxlan
    peers: Optional[str] = None
    # evpn
    vrf_vxlan: Optional[int] = None
    controller: Optional[str] = None
    rt_import: Optional[str] = None
    rt_export: Optional[str] = None
    exitnodes: Optional[str] = None

class ZoneUpdate(BaseModel):
    mtu: Optional[int] = None
    nodes: Optional[str] = None
    bridge: Optional[str] = None
    peers: Optional[str] = None
    vrf_vxlan: Optional[int] = None
    controller: Optional[str] = None
    rt_import: Optional[str] = None
    rt_export: Optional[str] = None
    exitnodes: Optional[str] = None

class SubnetCreate(BaseModel):
    subnet: str  # CIDR, e.g. "10.0.0.0/24"
    vnet: str
    gateway: Optional[str] = None
    snat: Optional[int] = None
    dhcp_range: Optional[str] = None
    dns_nameservers: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_host(host_id: int, db: Session) -> ProxmoxHost:
    host = db.query(ProxmoxHost).filter(
        ProxmoxHost.id == host_id, ProxmoxHost.is_active == True
    ).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found or inactive")
    return host


def _pve(host: ProxmoxHost):
    return ProxmoxService(host).proxmox


def _sdn_error(action: str, e: Exception) -> HTTPException:
    msg = str(e)
    status = 500
    if hasattr(e, 'status_code'):
        status = e.status_code
    logger.error(f"SDN {action} failed: {msg}")
    return HTTPException(status_code=status, detail=f"SDN {action} failed: {msg}")


# ── VNet endpoints ─────────────────────────────────────────────────────────────

@router.get("/{host_id}/vnets")
def list_vnets(
    host_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all SDN VNets for a Proxmox cluster"""
    host = _get_host(host_id, db)
    pve = _pve(host)
    try:
        result = pve.cluster.sdn.vnets.get()
        return result or []
    except Exception as e:
        raise _sdn_error("list vnets", e)


@router.post("/{host_id}/vnets", status_code=201)
def create_vnet(
    host_id: int,
    data: VNetCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Create a new SDN VNet"""
    host = _get_host(host_id, db)
    pve = _pve(host)
    payload = data.dict(exclude_none=True)
    try:
        pve.cluster.sdn.vnets.post(**payload)
        return {"status": "created", "vnet": data.vnet}
    except Exception as e:
        raise _sdn_error("create vnet", e)


@router.put("/{host_id}/vnets/{vnet}")
def update_vnet(
    host_id: int,
    vnet: str,
    data: VNetUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Update an SDN VNet"""
    host = _get_host(host_id, db)
    pve = _pve(host)
    payload = data.dict(exclude_none=True)
    try:
        pve.cluster.sdn.vnets(vnet).put(**payload)
        return {"status": "updated", "vnet": vnet}
    except Exception as e:
        raise _sdn_error("update vnet", e)


@router.delete("/{host_id}/vnets/{vnet}", status_code=204)
def delete_vnet(
    host_id: int,
    vnet: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Delete an SDN VNet"""
    host = _get_host(host_id, db)
    pve = _pve(host)
    try:
        pve.cluster.sdn.vnets(vnet).delete()
        return None
    except Exception as e:
        raise _sdn_error("delete vnet", e)


# ── Zone endpoints ─────────────────────────────────────────────────────────────

@router.get("/{host_id}/zones")
def list_zones(
    host_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all SDN zones for a Proxmox cluster"""
    host = _get_host(host_id, db)
    pve = _pve(host)
    try:
        result = pve.cluster.sdn.zones.get()
        return result or []
    except Exception as e:
        raise _sdn_error("list zones", e)


@router.post("/{host_id}/zones", status_code=201)
def create_zone(
    host_id: int,
    data: ZoneCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Create a new SDN zone"""
    host = _get_host(host_id, db)
    pve = _pve(host)
    payload = data.dict(exclude_none=True)
    try:
        pve.cluster.sdn.zones.post(**payload)
        return {"status": "created", "zone": data.zone}
    except Exception as e:
        raise _sdn_error("create zone", e)


@router.put("/{host_id}/zones/{zone}")
def update_zone(
    host_id: int,
    zone: str,
    data: ZoneUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Update an SDN zone"""
    host = _get_host(host_id, db)
    pve = _pve(host)
    payload = data.dict(exclude_none=True)
    try:
        pve.cluster.sdn.zones(zone).put(**payload)
        return {"status": "updated", "zone": zone}
    except Exception as e:
        raise _sdn_error("update zone", e)


@router.delete("/{host_id}/zones/{zone}", status_code=204)
def delete_zone(
    host_id: int,
    zone: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Delete an SDN zone"""
    host = _get_host(host_id, db)
    pve = _pve(host)
    try:
        pve.cluster.sdn.zones(zone).delete()
        return None
    except Exception as e:
        raise _sdn_error("delete zone", e)


# ── Subnet endpoints ───────────────────────────────────────────────────────────

@router.get("/{host_id}/subnets")
def list_subnets(
    host_id: int,
    vnet: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List SDN subnets; optionally filter by VNet"""
    host = _get_host(host_id, db)
    pve = _pve(host)
    try:
        if vnet:
            result = pve.cluster.sdn.vnets(vnet).subnets.get()
        else:
            # Fetch subnets across all vnets
            vnets = pve.cluster.sdn.vnets.get() or []
            result = []
            for v in vnets:
                vnet_id = v.get("vnet")
                if vnet_id:
                    try:
                        subs = pve.cluster.sdn.vnets(vnet_id).subnets.get() or []
                        for s in subs:
                            s["vnet"] = vnet_id
                        result.extend(subs)
                    except Exception:
                        pass
        return result or []
    except Exception as e:
        raise _sdn_error("list subnets", e)


@router.post("/{host_id}/subnets", status_code=201)
def create_subnet(
    host_id: int,
    data: SubnetCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Create a new subnet under a VNet"""
    host = _get_host(host_id, db)
    pve = _pve(host)
    vnet = data.vnet
    payload = data.dict(exclude_none=True, exclude={"vnet"})
    try:
        pve.cluster.sdn.vnets(vnet).subnets.post(**payload)
        return {"status": "created", "subnet": data.subnet, "vnet": vnet}
    except Exception as e:
        raise _sdn_error("create subnet", e)


@router.delete("/{host_id}/subnets/{subnet:path}", status_code=204)
def delete_subnet(
    host_id: int,
    subnet: str,
    vnet: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Delete a subnet from a VNet (pass vnet as query param)"""
    host = _get_host(host_id, db)
    pve = _pve(host)
    try:
        pve.cluster.sdn.vnets(vnet).subnets(subnet).delete()
        return None
    except Exception as e:
        raise _sdn_error("delete subnet", e)


# ── Apply endpoint ─────────────────────────────────────────────────────────────

@router.post("/{host_id}/apply")
def apply_sdn(
    host_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Apply all pending SDN configuration changes to the cluster"""
    host = _get_host(host_id, db)
    pve = _pve(host)
    try:
        result = pve.cluster.sdn.put()
        return {"status": "applied", "result": result}
    except Exception as e:
        raise _sdn_error("apply SDN", e)
