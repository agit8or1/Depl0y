"""VM configuration, lifecycle, snapshots, clone, migrate — Proxmox-native control plane"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from app.core.database import get_db
from app.models import ProxmoxHost
from app.api.auth import get_current_user, require_operator
from app.services.proxmox import ProxmoxService
from app.core.cache import pve_cache
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_host(host_id: int, db: Session) -> ProxmoxHost:
    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id, ProxmoxHost.is_active == True).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")
    return host


def _svc(host: ProxmoxHost) -> ProxmoxService:
    return ProxmoxService(host)


def _pve(svc: ProxmoxService):
    return svc.proxmox


# ── Pydantic models ───────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    cores: Optional[int] = None
    sockets: Optional[int] = None
    memory: Optional[int] = None
    balloon: Optional[int] = None
    onboot: Optional[bool] = None
    protection: Optional[bool] = None
    boot: Optional[str] = None
    cpu: Optional[str] = None
    agent: Optional[str] = None

class SnapshotCreate(BaseModel):
    snapname: str
    description: Optional[str] = ""
    vmstate: bool = False

class CloneRequest(BaseModel):
    newid: int
    name: str
    full: bool = True
    storage: Optional[str] = None
    target: Optional[str] = None  # target node

class MigrateRequest(BaseModel):
    target: str  # target node name
    online: bool = True
    with_local_disks: bool = False

class DiskAdd(BaseModel):
    storage: str
    size: int  # GB
    bus: str = "scsi"  # scsi, virtio, ide, sata
    format: str = "qcow2"
    ssd: bool = False

class DiskResize(BaseModel):
    size: str  # e.g. "+10G" or "50G"

class NICAdd(BaseModel):
    bridge: str
    model: str = "virtio"
    vlan: Optional[int] = None
    mac: Optional[str] = None
    firewall: bool = False

class FirewallRule(BaseModel):
    type: str  # in / out
    action: str  # ACCEPT / DROP / REJECT
    proto: Optional[str] = None
    source: Optional[str] = None
    dest: Optional[str] = None
    dport: Optional[str] = None
    sport: Optional[str] = None
    comment: Optional[str] = None
    enable: int = 1


# ── VM config read/write ──────────────────────────────────────────────────────

@router.get("/{host_id}/{node}/{vmid}/config")
def get_vm_config(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                  current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:{node}/{vmid}/config"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        cfg = _pve(_svc(host)).nodes(node).qemu(vmid).config.get()
        pve_cache.set(cache_key, cfg, ttl=30)
        return cfg
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/{node}/{vmid}/config")
def update_vm_config(host_id: int, node: str, vmid: int, update: ConfigUpdate,
                     db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    payload = {k: v for k, v in update.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(status_code=400, detail="Nothing to update")
    try:
        _pve(_svc(host)).nodes(node).qemu(vmid).config.put(**payload)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/{node}/{vmid}/status")
def get_vm_status(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                  current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:{node}/{vmid}/status"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        st = _pve(_svc(host)).nodes(node).qemu(vmid).status.current.get()
        pve_cache.set(cache_key, st, ttl=10)
        return st
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Lifecycle actions ─────────────────────────────────────────────────────────

@router.post("/{host_id}/{node}/{vmid}/start")
def start_vm(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
             current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).status.start.post()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/{node}/{vmid}/stop")
def stop_vm(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
            current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).status.stop.post()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/{node}/{vmid}/shutdown")
def shutdown_vm(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).status.shutdown.post()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/{node}/{vmid}/reboot")
def reboot_vm(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
              current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).status.reboot.post()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/{node}/{vmid}/reset")
def reset_vm(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
             current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).status.reset.post()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/{node}/{vmid}/suspend")
def suspend_vm(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
               current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).status.suspend.post()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/{node}/{vmid}/resume")
def resume_vm(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
              current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).status.resume.post()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Snapshots ─────────────────────────────────────────────────────────────────

@router.get("/{host_id}/{node}/{vmid}/snapshots")
def list_snapshots(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                   current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:{node}/{vmid}/snapshots"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        snaps = _pve(_svc(host)).nodes(node).qemu(vmid).snapshot.get()
        pve_cache.set(cache_key, snaps, ttl=30)
        return snaps
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/{node}/{vmid}/snapshots")
def create_snapshot(host_id: int, node: str, vmid: int, snap: SnapshotCreate,
                    db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).snapshot.post(
            snapname=snap.snapname,
            description=snap.description,
            vmstate=int(snap.vmstate),
        )
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/{node}/{vmid}/snapshots/{snapname}")
def delete_snapshot(host_id: int, node: str, vmid: int, snapname: str,
                    db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).snapshot(snapname).delete()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/{node}/{vmid}/snapshots/{snapname}/rollback")
def rollback_snapshot(host_id: int, node: str, vmid: int, snapname: str,
                      db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).snapshot(snapname).rollback.post()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Clone ─────────────────────────────────────────────────────────────────────

@router.post("/{host_id}/{node}/{vmid}/clone")
def clone_vm(host_id: int, node: str, vmid: int, req: CloneRequest,
             db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    params: Dict[str, Any] = {"newid": req.newid, "name": req.name, "full": int(req.full)}
    if req.storage:
        params["storage"] = req.storage
    if req.target:
        params["target"] = req.target
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).clone.post(**params)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Migrate ───────────────────────────────────────────────────────────────────

@router.post("/{host_id}/{node}/{vmid}/migrate")
def migrate_vm(host_id: int, node: str, vmid: int, req: MigrateRequest,
               db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).migrate.post(
            target=req.target,
            online=int(req.online),
            with_local_disks=int(req.with_local_disks),
        )
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Convert to template ───────────────────────────────────────────────────────

@router.post("/{host_id}/{node}/{vmid}/template")
def convert_to_template(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                        current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        _pve(_svc(host)).nodes(node).qemu(vmid).template.post()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Delete VM ─────────────────────────────────────────────────────────────────

@router.delete("/{host_id}/{node}/{vmid}")
def delete_vm(host_id: int, node: str, vmid: int,
              purge: bool = True, destroy_unreferenced_disks: bool = True,
              db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        params: Dict[str, Any] = {}
        if purge:
            params["purge"] = 1
        if destroy_unreferenced_disks:
            params["destroy-unreferenced-disks"] = 1
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).delete(**params)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Disk management ───────────────────────────────────────────────────────────

@router.post("/{host_id}/{node}/{vmid}/disk")
def add_disk(host_id: int, node: str, vmid: int, req: DiskAdd,
             db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Add a new disk to a VM."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        cfg = pve.nodes(node).qemu(vmid).config.get()
        # Find next free bus slot
        bus = req.bus
        idx = 0
        while f"{bus}{idx}" in cfg:
            idx += 1
        disk_key = f"{bus}{idx}"
        disk_val = f"{req.storage}:{req.size},format={req.format}"
        if req.ssd:
            disk_val += ",ssd=1"
        pve.nodes(node).qemu(vmid).config.post(**{disk_key: disk_val})
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True, "disk": disk_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/{node}/{vmid}/disk/{disk_key}/resize")
def resize_disk(host_id: int, node: str, vmid: int, disk_key: str, req: DiskResize,
                db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        _pve(_svc(host)).nodes(node).qemu(vmid).resize.put(disk=disk_key, size=req.size)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/{node}/{vmid}/disk/{disk_key}")
def detach_disk(host_id: int, node: str, vmid: int, disk_key: str,
                delete: bool = False,
                db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Detach a disk from a VM config. Optionally delete the volume."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        # Get current disk volid before detaching
        cfg = pve.nodes(node).qemu(vmid).config.get()
        disk_str = cfg.get(disk_key, "")
        # Detach: set disk key to empty (removes from config)
        pve.nodes(node).qemu(vmid).config.put(**{disk_key: None})
        if delete and disk_str:
            # Extract volid from disk string (format: storage:volname,...)
            volid = disk_str.split(",")[0].strip()
            try:
                pve.nodes(node).qemu(vmid).unlink.put(idlist=volid, force=1)
            except Exception:
                pass
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── NIC management ────────────────────────────────────────────────────────────

@router.post("/{host_id}/{node}/{vmid}/network")
def add_nic(host_id: int, node: str, vmid: int, req: NICAdd,
            db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        cfg = pve.nodes(node).qemu(vmid).config.get()
        idx = 0
        while f"net{idx}" in cfg:
            idx += 1
        net_key = f"net{idx}"
        net_val = f"{req.model},bridge={req.bridge}"
        if req.vlan is not None:
            net_val += f",tag={req.vlan}"
        if req.mac:
            net_val += f"={req.mac}"
        if req.firewall:
            net_val += ",firewall=1"
        pve.nodes(node).qemu(vmid).config.put(**{net_key: net_val})
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True, "interface": net_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/{node}/{vmid}/network/{net_key}")
def remove_nic(host_id: int, node: str, vmid: int, net_key: str,
               db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        _pve(_svc(host)).nodes(node).qemu(vmid).config.put(**{net_key: None})
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Per-VM Firewall ───────────────────────────────────────────────────────────

@router.get("/{host_id}/{node}/{vmid}/firewall/rules")
def get_vm_firewall_rules(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                          current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:{node}/{vmid}/firewall/rules"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(_svc(host)).nodes(node).qemu(vmid).firewall.rules.get()
        pve_cache.set(cache_key, result, ttl=30)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/{node}/{vmid}/firewall/rules")
def add_vm_firewall_rule(host_id: int, node: str, vmid: int, rule: FirewallRule,
                         db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    params = {k: v for k, v in rule.model_dump().items() if v is not None}
    try:
        _pve(_svc(host)).nodes(node).qemu(vmid).firewall.rules.post(**params)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/{node}/{vmid}/firewall/rules/{pos}")
def update_vm_firewall_rule(host_id: int, node: str, vmid: int, pos: int, rule: FirewallRule,
                            db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    params = {k: v for k, v in rule.model_dump().items() if v is not None}
    try:
        _pve(_svc(host)).nodes(node).qemu(vmid).firewall.rules(pos).put(**params)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/{node}/{vmid}/firewall/rules/{pos}")
def delete_vm_firewall_rule(host_id: int, node: str, vmid: int, pos: int,
                            db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        _pve(_svc(host)).nodes(node).qemu(vmid).firewall.rules(pos).delete()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/{node}/{vmid}/firewall/options")
def get_vm_firewall_options(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                            current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(_svc(host)).nodes(node).qemu(vmid).firewall.options.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/{node}/{vmid}/firewall/options")
def set_vm_firewall_options(host_id: int, node: str, vmid: int, options: dict,
                            db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        _pve(_svc(host)).nodes(node).qemu(vmid).firewall.options.put(**options)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── VNC console ticket ────────────────────────────────────────────────────────

@router.post("/{host_id}/{node}/{vmid}/vncticket")
def get_vnc_ticket(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                   current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        result = _pve(_svc(host)).nodes(node).qemu(vmid).vncproxy.post(websocket=1)
        return {
            "ticket": result.get("ticket"),
            "port": result.get("port"),
            "host": host.hostname,
            "pve_port": host.port,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── RRD data for VM charts ────────────────────────────────────────────────────

@router.get("/{host_id}/{node}/{vmid}/rrddata")
def get_vm_rrddata(host_id: int, node: str, vmid: int,
                   timeframe: str = "hour", cf: str = "AVERAGE",
                   db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:{node}/{vmid}/rrddata:{timeframe}:{cf}"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        data = _pve(_svc(host)).nodes(node).qemu(vmid).rrddata.get(timeframe=timeframe, cf=cf)
        pve_cache.set(cache_key, data, ttl=60)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
