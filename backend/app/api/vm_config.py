"""VM configuration, lifecycle, snapshots, clone, migrate — Proxmox-native control plane"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from app.core.database import get_db
from app.models import ProxmoxHost
from app.api.auth import get_current_user, require_operator
from app.services.proxmox import ProxmoxService
from app.services.task_tracker import task_tracker
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

class CloudInitConfig(BaseModel):
    ciuser: Optional[str] = None
    cipassword: Optional[str] = None
    sshkeys: Optional[str] = None
    ipconfig0: Optional[str] = None
    ipconfig1: Optional[str] = None
    nameserver: Optional[str] = None
    searchdomain: Optional[str] = None
    cicustom: Optional[str] = None
    ciupgrade: Optional[bool] = None

class DiskAdd(BaseModel):
    storage: str
    size: int  # GB
    bus: str = "scsi"  # scsi, virtio, ide, sata
    format: str = "qcow2"
    ssd: bool = False
    discard: bool = False
    cache: str = ""  # none, writeback, writethrough, directsync, unsafe
    backup: bool = True
    iothread: bool = False
    replicate: bool = True

class DiskMove(BaseModel):
    storage: str
    disk: str
    format: Optional[str] = None
    delete_source: bool = False

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

@router.get("/{host_id}/{node}/{vmid}/pending")
def get_vm_pending(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                   current_user=Depends(get_current_user)):
    """Get pending VM config changes (applied on next reboot)."""
    host = _get_host(host_id, db)
    try:
        return _pve(_svc(host)).nodes(node).qemu(vmid).pending.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

def _register_vm_task(upid, host_id, node, vmid, action, current_user):
    task_tracker.register(
        upid, host_id, node,
        f"VM {vmid} {action}",
        user_id=getattr(current_user, "id", None),
        vmid=vmid,
        task_type=f"qm{action}",
    )


def _fire_vm_webhook(db, event_type, host, node, vmid, current_user, host_id):
    """Fire webhook + Slack for a VM lifecycle event (non-blocking background task)."""
    import asyncio
    from app.services.webhook_dispatcher import dispatcher
    payload = {
        "vm_id": vmid,
        "node": node,
        "host": host.hostname,
        "host_id": host_id,
        "action": event_type.split(".")[-1],
        "user": getattr(current_user, "username", ""),
    }
    emoji_map = {
        "vm.started": ":arrow_forward:",
        "vm.stopped": ":stop_sign:",
        "vm.shutdown": ":zzz:",
    }
    emoji = emoji_map.get(event_type, ":gear:")
    slack_msg = (
        f"{emoji} VM *{vmid}* on `{node}` "
        f"{event_type.split('.')[-1]} by {getattr(current_user, 'username', '')}"
    )
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(
            dispatcher.dispatch_and_slack(db, event_type, payload, slack_msg, host_id=host_id)
        )
    except Exception:
        pass


@router.post("/{host_id}/{node}/{vmid}/start")
def start_vm(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
             current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(_svc(host)).nodes(node).qemu(vmid).status.start.post()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        _register_vm_task(upid, host_id, node, vmid, "start", current_user)
        _fire_vm_webhook(db, "vm.started", host, node, vmid, current_user, host_id)
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
        _register_vm_task(upid, host_id, node, vmid, "stop", current_user)
        _fire_vm_webhook(db, "vm.stopped", host, node, vmid, current_user, host_id)
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
        _register_vm_task(upid, host_id, node, vmid, "shutdown", current_user)
        _fire_vm_webhook(db, "vm.shutdown", host, node, vmid, current_user, host_id)
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
        _register_vm_task(upid, host_id, node, vmid, "reboot", current_user)
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
        _register_vm_task(upid, host_id, node, vmid, "reset", current_user)
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
        _register_vm_task(upid, host_id, node, vmid, "suspend", current_user)
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
        _register_vm_task(upid, host_id, node, vmid, "resume", current_user)
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
        task_tracker.register(
            upid, host_id, node,
            f"Snapshot VM {vmid}: {snap.snapname}",
            user_id=getattr(current_user, "id", None),
            vmid=vmid,
            task_type="qmsnapshot",
        )
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
        task_tracker.register(
            upid, host_id, node,
            f"Delete snapshot {snapname} VM {vmid}",
            user_id=getattr(current_user, "id", None),
            vmid=vmid,
            task_type="qmsnapshot",
        )
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
        task_tracker.register(
            upid, host_id, node,
            f"Rollback VM {vmid} to {snapname}",
            user_id=getattr(current_user, "id", None),
            vmid=vmid,
            task_type="qmrollback",
        )
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/{node}/{vmid}/snapshot/{snapname}/config")
def get_snapshot_config(host_id: int, node: str, vmid: int, snapname: str,
                        db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get the VM config as it was at the time of a specific snapshot."""
    host = _get_host(host_id, db)
    try:
        cfg = _pve(_svc(host)).nodes(node).qemu(vmid).snapshot(snapname).config.get()
        return cfg
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
        task_tracker.register(
            upid, host_id, node,
            f"Clone VM {vmid} → {req.newid}",
            user_id=getattr(current_user, "id", None),
            vmid=vmid,
            task_type="qmclone",
        )
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
        task_tracker.register(
            upid, host_id, node,
            f"Migrate VM {vmid} → {req.target}",
            user_id=getattr(current_user, "id", None),
            vmid=vmid,
            task_type="qmmigrate",
        )
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
        task_tracker.register(
            upid, host_id, node,
            f"Delete VM {vmid}",
            user_id=getattr(current_user, "id", None),
            vmid=vmid,
            task_type="qmdestroy",
        )
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
        if req.discard:
            disk_val += ",discard=on"
        if req.cache:
            disk_val += f",cache={req.cache}"
        if not req.backup:
            disk_val += ",backup=0"
        if req.iothread:
            disk_val += ",iothread=1"
        if not req.replicate:
            disk_val += ",replicate=0"
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


@router.post("/{host_id}/{node}/{vmid}/move-disk")
def move_disk(host_id: int, node: str, vmid: int, req: DiskMove,
              db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Move a disk to a different storage pool."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        params: Dict[str, Any] = {
            "disk": req.disk,
            "storage": req.storage,
            "delete": int(req.delete_source),
        }
        if req.format:
            params["format"] = req.format
        upid = pve.nodes(node).qemu(vmid).move_disk.post(**params)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/{node}/{vmid}/unused-disks")
def list_unused_disks(host_id: int, node: str, vmid: int,
                      db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """List unused disk volumes attached to this VM config (unused0, unused1, ...)."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        cfg = pve.nodes(node).qemu(vmid).config.get()
        unused = []
        for key, val in cfg.items():
            if key.startswith("unused") and key[6:].isdigit():
                unused.append({"key": key, "volid": val})
        return unused
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/{node}/{vmid}/reattach-disk")
def reattach_disk(host_id: int, node: str, vmid: int,
                  unused_key: str,
                  bus: str = "scsi",
                  db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Reattach an unused disk to a bus slot."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        cfg = pve.nodes(node).qemu(vmid).config.get()
        volid = cfg.get(unused_key)
        if not volid:
            raise HTTPException(status_code=404, detail=f"{unused_key} not found in config")
        # Find next free slot for the bus
        idx = 0
        while f"{bus}{idx}" in cfg:
            idx += 1
        disk_key = f"{bus}{idx}"
        # Set the new slot to the volid, clear the unused entry
        pve.nodes(node).qemu(vmid).config.put(**{disk_key: volid, unused_key: None})
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True, "disk": disk_key}
    except HTTPException:
        raise
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

@router.post("/{host_id}/{node}/{vmid}/cloudinit/regenerate")
def regenerate_cloudinit(host_id: int, node: str, vmid: int,
                         db: Session = Depends(get_db),
                         current_user=Depends(require_operator)):
    """Regenerate the cloud-init drive for a VM."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        # Proxmox API: PUT /nodes/{node}/qemu/{vmid}/cloudinit regenerates the drive
        pve.nodes(node).qemu(vmid).cloudinit.put()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True, "message": "Cloud-init drive regenerated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/{node}/{vmid}/cloudinit")
def update_cloudinit_config(host_id: int, node: str, vmid: int,
                            cfg: CloudInitConfig,
                            db: Session = Depends(get_db),
                            current_user=Depends(require_operator)):
    """Apply cloud-init settings to a VM config."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    payload: Dict[str, Any] = {}
    if cfg.ciuser is not None:
        payload["ciuser"] = cfg.ciuser
    if cfg.cipassword is not None:
        payload["cipassword"] = cfg.cipassword
    if cfg.sshkeys is not None:
        # Proxmox expects URL-encoded newlines in sshkeys
        import urllib.parse
        payload["sshkeys"] = urllib.parse.quote(cfg.sshkeys, safe="")
    if cfg.ipconfig0 is not None:
        payload["ipconfig0"] = cfg.ipconfig0
    if cfg.ipconfig1 is not None:
        payload["ipconfig1"] = cfg.ipconfig1
    if cfg.nameserver is not None:
        payload["nameserver"] = cfg.nameserver
    if cfg.searchdomain is not None:
        payload["searchdomain"] = cfg.searchdomain
    if cfg.cicustom is not None:
        payload["cicustom"] = cfg.cicustom
    if cfg.ciupgrade is not None:
        payload["ciupgrade"] = int(cfg.ciupgrade)
    if not payload:
        raise HTTPException(status_code=400, detail="Nothing to update")
    try:
        pve.nodes(node).qemu(vmid).config.put(**payload)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# ── Tag management ────────────────────────────────────────────────────────────

def _parse_tags(tags_str: str) -> List[str]:
    """Parse a semicolon-separated Proxmox tags string into a list."""
    if not tags_str:
        return []
    return [t.strip() for t in tags_str.split(";") if t.strip()]


def _tags_to_str(tags: List[str]) -> str:
    return ";".join(tags)


@router.get("/search")
def search_vms(
    q: Optional[str] = Query(None, description="Text search across name, VMID, node"),
    host_id: Optional[int] = Query(None),
    node: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="running or stopped"),
    tags: Optional[str] = Query(None, description="Comma-separated tag list"),
    min_cpu: Optional[float] = Query(None),
    max_cpu: Optional[float] = Query(None),
    min_ram_gb: Optional[float] = Query(None),
    max_ram_gb: Optional[float] = Query(None),
    os_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Search VMs across all hosts (or a specific host) with filtering and pagination."""
    if host_id is not None:
        hosts = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id, ProxmoxHost.is_active == True).all()
    else:
        hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()

    tag_filter = [t.strip().lower() for t in tags.split(",") if t.strip()] if tags else []
    q_lower = q.strip().lower() if q else None

    matched: List[Dict[str, Any]] = []

    for host in hosts:
        try:
            pve = _pve(_svc(host))
            resources = pve.cluster.resources.get(type="vm")
        except Exception:
            continue

        for item in resources:
            if item.get("type") != "qemu":
                continue

            # Node filter
            if node and item.get("node", "").lower() != node.lower():
                continue

            # Status filter
            if status and item.get("status", "").lower() != status.lower():
                continue

            # CPU usage filter (0.0–1.0 from PVE, compare as percentage)
            cpu_pct = (item.get("cpu") or 0) * 100
            if min_cpu is not None and cpu_pct < min_cpu:
                continue
            if max_cpu is not None and cpu_pct > max_cpu:
                continue

            # RAM filter (maxmem in bytes → GB)
            maxmem_gb = (item.get("maxmem") or 0) / (1024 ** 3)
            if min_ram_gb is not None and maxmem_gb < min_ram_gb:
                continue
            if max_ram_gb is not None and maxmem_gb > max_ram_gb:
                continue

            # Tag filter
            if tag_filter:
                vm_tags = _parse_tags(item.get("tags", "") or "")
                if not all(t in vm_tags for t in tag_filter):
                    continue

            # OS type filter (check config if requested — lightweight: check name heuristic)
            if os_type:
                name_lower = (item.get("name") or "").lower()
                if os_type.lower() not in name_lower:
                    # do a quick config lookup (only if os_type explicitly requested)
                    try:
                        cfg = pve.nodes(item["node"]).qemu(item["vmid"]).config.get()
                        ostype_val = (cfg.get("ostype") or "").lower()
                        if os_type.lower() not in ostype_val:
                            continue
                    except Exception:
                        continue

            # Text search
            if q_lower:
                name = (item.get("name") or "").lower()
                vmid_str = str(item.get("vmid") or "")
                node_str = (item.get("node") or "").lower()
                host_name = (host.name or host.hostname or "").lower()
                tags_str = (item.get("tags") or "").lower()
                if not (
                    q_lower in name
                    or q_lower in vmid_str
                    or q_lower in node_str
                    or q_lower in host_name
                    or q_lower in tags_str
                ):
                    continue

            matched.append({
                "vmid": item.get("vmid"),
                "name": item.get("name") or "",
                "status": item.get("status") or "unknown",
                "node": item.get("node") or "",
                "host_id": host.id,
                "host_name": host.name or host.hostname or f"Host {host.id}",
                "cpu": item.get("cpu"),
                "mem": item.get("mem"),
                "maxmem": item.get("maxmem"),
                "tags": item.get("tags") or "",
                "uptime": item.get("uptime"),
            })

    total = len(matched)
    # Sort by name then vmid
    matched.sort(key=lambda x: (x.get("name") or "", x.get("vmid") or 0))
    paginated = matched[skip: skip + limit]

    return {"total": total, "vms": paginated}


@router.get("/{host_id}/tags")
def list_all_tags(host_id: int, db: Session = Depends(get_db),
                  current_user=Depends(get_current_user)):
    """Return all unique tags used across all VMs in this cluster, with VM counts."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        resources = pve.cluster.resources.get(type="vm")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    tag_counts: Dict[str, int] = {}
    for item in resources:
        raw_tags = item.get("tags", "")
        for tag in _parse_tags(raw_tags):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    return [{"tag": tag, "count": count} for tag, count in sorted(tag_counts.items())]


@router.get("/{host_id}/tags/{tag}/vms")
def list_vms_by_tag(host_id: int, tag: str, db: Session = Depends(get_db),
                    current_user=Depends(get_current_user)):
    """List all VMs that have the given tag."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        resources = pve.cluster.resources.get(type="vm")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    matched = []
    for item in resources:
        if tag in _parse_tags(item.get("tags", "")):
            matched.append(item)
    return matched


class TagBody(BaseModel):
    tag: str


@router.post("/{host_id}/{node}/{vmid}/tags")
def add_vm_tag(host_id: int, node: str, vmid: int, body: TagBody,
               db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Append a tag to a VM (idempotent — won't duplicate)."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    tag = body.tag.strip().lower()
    if not tag:
        raise HTTPException(status_code=400, detail="Tag must not be empty")
    try:
        cfg = pve.nodes(node).qemu(vmid).config.get()
        tags = _parse_tags(cfg.get("tags", ""))
        if tag not in tags:
            tags.append(tag)
            pve.nodes(node).qemu(vmid).config.put(tags=_tags_to_str(tags))
            pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"tags": tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/{node}/{vmid}/tags/{tag}")
def remove_vm_tag(host_id: int, node: str, vmid: int, tag: str,
                  db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Remove a specific tag from a VM."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        cfg = pve.nodes(node).qemu(vmid).config.get()
        tags = _parse_tags(cfg.get("tags", ""))
        tags = [t for t in tags if t != tag]
        pve.nodes(node).qemu(vmid).config.put(tags=_tags_to_str(tags))
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"tags": tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── PCI passthrough management ────────────────────────────────────────────────

class PCIAdd(BaseModel):
    pciid: str                          # e.g. "0000:01:00.0"
    pcie: bool = True
    x_vga: bool = False
    rombar: bool = True
    mdev: Optional[str] = None          # mediated device type (vGPU)


@router.post("/{host_id}/{node}/{vmid}/pci")
def add_pci_device(host_id: int, node: str, vmid: int, req: PCIAdd,
                   db: Session = Depends(get_db),
                   current_user=Depends(require_operator)):
    """Add a PCI passthrough device to a VM (hostpciN=...)."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        cfg = pve.nodes(node).qemu(vmid).config.get()
        # Find next free hostpci slot
        idx = 0
        while f"hostpci{idx}" in cfg:
            idx += 1
        hostpci_key = f"hostpci{idx}"
        val = req.pciid
        if req.mdev:
            val += f",mdev={req.mdev}"
        if req.pcie:
            val += ",pcie=1"
        if req.x_vga:
            val += ",x-vga=1"
        if not req.rombar:
            val += ",rombar=0"
        pve.nodes(node).qemu(vmid).config.put(**{hostpci_key: val})
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True, "key": hostpci_key, "value": val}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/{node}/{vmid}/pci/{index}")
def remove_pci_device(host_id: int, node: str, vmid: int, index: int,
                      db: Session = Depends(get_db),
                      current_user=Depends(require_operator)):
    """Remove a PCI passthrough device from a VM config (hostpciN)."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    hostpci_key = f"hostpci{index}"
    try:
        cfg = pve.nodes(node).qemu(vmid).config.get()
        if hostpci_key not in cfg:
            raise HTTPException(status_code=404, detail=f"{hostpci_key} not found in VM config")
        # Set to None / delete the key — Proxmox API uses delete= parameter
        pve.nodes(node).qemu(vmid).config.put(**{hostpci_key: None})
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── USB passthrough management ────────────────────────────────────────────────

class USBAdd(BaseModel):
    host: str                           # "vendorid:productid" or "spice" or port number
    usb3: bool = False


@router.post("/{host_id}/{node}/{vmid}/usb")
def add_usb_device(host_id: int, node: str, vmid: int, req: USBAdd,
                   db: Session = Depends(get_db),
                   current_user=Depends(require_operator)):
    """Add a USB passthrough device to a VM (usbN=host:{vendor}:{product})."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        cfg = pve.nodes(node).qemu(vmid).config.get()
        idx = 0
        while f"usb{idx}" in cfg:
            idx += 1
        usb_key = f"usb{idx}"
        val = f"host={req.host}"
        if req.usb3:
            val += ",usb3=1"
        pve.nodes(node).qemu(vmid).config.put(**{usb_key: val})
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True, "key": usb_key, "value": val}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/{node}/{vmid}/usb/{index}")
def remove_usb_device(host_id: int, node: str, vmid: int, index: int,
                      db: Session = Depends(get_db),
                      current_user=Depends(require_operator)):
    """Remove a USB passthrough device from a VM config (usbN)."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    usb_key = f"usb{index}"
    try:
        cfg = pve.nodes(node).qemu(vmid).config.get()
        if usb_key not in cfg:
            raise HTTPException(status_code=404, detail=f"{usb_key} not found in VM config")
        pve.nodes(node).qemu(vmid).config.put(**{usb_key: None})
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Serial port management ────────────────────────────────────────────────────

class SerialAdd(BaseModel):
    type: str = "socket"                # "socket" or a host device path e.g. /dev/ttyS0


@router.post("/{host_id}/{node}/{vmid}/serial")
def add_serial_port(host_id: int, node: str, vmid: int, req: SerialAdd,
                    db: Session = Depends(get_db),
                    current_user=Depends(require_operator)):
    """Add a serial port to a VM (serialN=socket|device)."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    try:
        cfg = pve.nodes(node).qemu(vmid).config.get()
        idx = 0
        while f"serial{idx}" in cfg:
            idx += 1
        serial_key = f"serial{idx}"
        pve.nodes(node).qemu(vmid).config.put(**{serial_key: req.type})
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True, "key": serial_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/{node}/{vmid}/serial/{index}")
def remove_serial_port(host_id: int, node: str, vmid: int, index: int,
                       db: Session = Depends(get_db),
                       current_user=Depends(require_operator)):
    """Remove a serial port from a VM config (serialN)."""
    host = _get_host(host_id, db)
    pve = _pve(_svc(host))
    serial_key = f"serial{index}"
    try:
        cfg = pve.nodes(node).qemu(vmid).config.get()
        if serial_key not in cfg:
            raise HTTPException(status_code=404, detail=f"{serial_key} not found in VM config")
        pve.nodes(node).qemu(vmid).config.put(**{serial_key: None})
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
