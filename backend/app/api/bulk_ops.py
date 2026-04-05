"""Bulk VM operations and automation scripts — operate on many VMs at once."""
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
import time as _time

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_host(host_id: int, db: Session) -> ProxmoxHost:
    host = db.query(ProxmoxHost).filter(
        ProxmoxHost.id == host_id, ProxmoxHost.is_active == True
    ).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"Proxmox host {host_id} not found")
    return host


def _pve(host: ProxmoxHost):
    return ProxmoxService(host).proxmox


# ── Pydantic models ───────────────────────────────────────────────────────────

class VMTarget(BaseModel):
    host_id: int
    node: str
    vmid: int


class BulkPowerRequest(BaseModel):
    vms: List[VMTarget]
    action: str  # start | stop | shutdown | reboot | reset


class BulkSnapshotRequest(BaseModel):
    vms: List[VMTarget]
    snapname_template: str = "bulk-{date}"  # supports {vmid}, {name}, {date}
    description: str = "Bulk snapshot"
    vmstate: bool = False


class BulkDeleteSnapshotsRequest(BaseModel):
    vms: List[VMTarget]
    older_than_days: int  # delete snapshots created more than N days ago


class BulkConfigRequest(BaseModel):
    vms: List[VMTarget]
    cores: Optional[int] = None
    memory: Optional[int] = None
    tags_add: Optional[List[str]] = None      # tags to add
    tags_remove: Optional[List[str]] = None   # tags to remove
    agent: Optional[str] = None               # "1" or "0"
    balloon: Optional[int] = None
    onboot: Optional[bool] = None


class BulkMigrateRequest(BaseModel):
    vms: List[VMTarget]
    target_node: str
    online: bool = True
    with_local_disks: bool = False


# ── Bulk Power ────────────────────────────────────────────────────────────────

@router.post("/bulk/power")
def bulk_power(req: BulkPowerRequest, db: Session = Depends(get_db),
               current_user=Depends(require_operator)):
    """Execute a power action on a list of VMs.
    Returns per-VM result: {host_id, node, vmid, upid, error}.
    """
    VALID_ACTIONS = {"start", "stop", "shutdown", "reboot", "reset"}
    if req.action not in VALID_ACTIONS:
        raise HTTPException(status_code=400,
                            detail=f"Invalid action. Must be one of: {', '.join(VALID_ACTIONS)}")

    results = []
    # Group by host_id so we only look up each host once
    host_cache: Dict[int, ProxmoxHost] = {}

    for vm in req.vms:
        entry: Dict[str, Any] = {
            "host_id": vm.host_id,
            "node": vm.node,
            "vmid": vm.vmid,
            "upid": None,
            "error": None,
        }
        try:
            if vm.host_id not in host_cache:
                host_cache[vm.host_id] = _get_host(vm.host_id, db)
            pve = _pve(host_cache[vm.host_id])
            qemu = pve.nodes(vm.node).qemu(vm.vmid)

            if req.action == "start":
                entry["upid"] = qemu.status.start.post()
            elif req.action == "stop":
                entry["upid"] = qemu.status.stop.post()
            elif req.action == "shutdown":
                entry["upid"] = qemu.status.shutdown.post()
            elif req.action == "reboot":
                entry["upid"] = qemu.status.reboot.post()
            elif req.action == "reset":
                entry["upid"] = qemu.status.reset.post()

            pve_cache.clear_prefix(f"pve:{vm.host_id}:")
        except HTTPException as e:
            entry["error"] = e.detail
        except Exception as e:
            entry["error"] = str(e)

        results.append(entry)

    return {"results": results}


# ── Bulk Snapshot ─────────────────────────────────────────────────────────────

@router.post("/bulk/snapshot")
def bulk_snapshot(req: BulkSnapshotRequest, db: Session = Depends(get_db),
                  current_user=Depends(require_operator)):
    """Create a snapshot on each VM in the list.
    Snapshot name template supports: {vmid}, {name}, {date}.
    """
    from datetime import datetime
    today = datetime.utcnow().strftime("%Y%m%d")

    results = []
    host_cache: Dict[int, ProxmoxHost] = {}

    for vm in req.vms:
        entry: Dict[str, Any] = {
            "host_id": vm.host_id,
            "node": vm.node,
            "vmid": vm.vmid,
            "snapname": None,
            "upid": None,
            "error": None,
        }
        try:
            if vm.host_id not in host_cache:
                host_cache[vm.host_id] = _get_host(vm.host_id, db)
            pve = _pve(host_cache[vm.host_id])

            # Resolve VM name for template
            try:
                cfg = pve.nodes(vm.node).qemu(vm.vmid).config.get()
                vm_name = cfg.get("name", str(vm.vmid))
            except Exception:
                vm_name = str(vm.vmid)

            snapname = (
                req.snapname_template
                .replace("{vmid}", str(vm.vmid))
                .replace("{name}", vm_name)
                .replace("{date}", today)
            )
            # Proxmox snap names: alphanumeric + underscore, max 40 chars
            snapname = snapname[:40]

            entry["snapname"] = snapname
            upid = pve.nodes(vm.node).qemu(vm.vmid).snapshot.post(
                snapname=snapname,
                description=req.description,
                vmstate=int(req.vmstate),
            )
            entry["upid"] = upid
            pve_cache.clear_prefix(f"pve:{vm.host_id}:")
        except HTTPException as e:
            entry["error"] = e.detail
        except Exception as e:
            entry["error"] = str(e)

        results.append(entry)

    return {"results": results}


@router.post("/bulk/delete-snapshots")
def bulk_delete_old_snapshots(req: BulkDeleteSnapshotsRequest,
                               db: Session = Depends(get_db),
                               current_user=Depends(require_operator)):
    """Delete snapshots older than N days across the selected VMs."""
    import time as _time
    cutoff = _time.time() - (req.older_than_days * 86400)

    results = []
    host_cache: Dict[int, ProxmoxHost] = {}

    for vm in req.vms:
        entry: Dict[str, Any] = {
            "host_id": vm.host_id,
            "node": vm.node,
            "vmid": vm.vmid,
            "deleted": [],
            "errors": [],
        }
        try:
            if vm.host_id not in host_cache:
                host_cache[vm.host_id] = _get_host(vm.host_id, db)
            pve = _pve(host_cache[vm.host_id])

            snaps = pve.nodes(vm.node).qemu(vm.vmid).snapshot.get()
            for snap in snaps:
                name = snap.get("name", "")
                if name == "current":
                    continue
                snap_time = snap.get("snaptime", 0)
                if snap_time and snap_time < cutoff:
                    try:
                        pve.nodes(vm.node).qemu(vm.vmid).snapshot(name).delete()
                        entry["deleted"].append(name)
                    except Exception as e:
                        entry["errors"].append({"snap": name, "error": str(e)})

            pve_cache.clear_prefix(f"pve:{vm.host_id}:")
        except HTTPException as e:
            entry["errors"].append({"snap": "*", "error": e.detail})
        except Exception as e:
            entry["errors"].append({"snap": "*", "error": str(e)})

        results.append(entry)

    return {"results": results}


# ── Bulk Config Update ────────────────────────────────────────────────────────

@router.post("/bulk/config")
def bulk_config_update(req: BulkConfigRequest, db: Session = Depends(get_db),
                       current_user=Depends(require_operator)):
    """Update config fields on a list of VMs.
    Returns per-VM result: {vmid, changes_applied, error}.
    """
    results = []
    host_cache: Dict[int, ProxmoxHost] = {}

    for vm in req.vms:
        entry: Dict[str, Any] = {
            "host_id": vm.host_id,
            "node": vm.node,
            "vmid": vm.vmid,
            "changes_applied": {},
            "error": None,
        }
        try:
            if vm.host_id not in host_cache:
                host_cache[vm.host_id] = _get_host(vm.host_id, db)
            pve = _pve(host_cache[vm.host_id])

            payload: Dict[str, Any] = {}
            if req.cores is not None:
                payload["cores"] = req.cores
            if req.memory is not None:
                payload["memory"] = req.memory
            if req.agent is not None:
                payload["agent"] = req.agent
            if req.balloon is not None:
                payload["balloon"] = req.balloon
            if req.onboot is not None:
                payload["onboot"] = int(req.onboot)

            # Handle tag add/remove
            if req.tags_add or req.tags_remove:
                try:
                    cfg = pve.nodes(vm.node).qemu(vm.vmid).config.get()
                    raw = cfg.get("tags", "")
                    tags = [t.strip() for t in raw.split(";") if t.strip()] if raw else []
                    if req.tags_add:
                        for t in req.tags_add:
                            t = t.strip().lower()
                            if t and t not in tags:
                                tags.append(t)
                    if req.tags_remove:
                        remove_set = {t.strip().lower() for t in req.tags_remove}
                        tags = [t for t in tags if t not in remove_set]
                    payload["tags"] = ";".join(tags)
                except Exception as e:
                    entry["error"] = f"Tag fetch failed: {e}"
                    results.append(entry)
                    continue

            if not payload:
                entry["error"] = "Nothing to update"
                results.append(entry)
                continue

            pve.nodes(vm.node).qemu(vm.vmid).config.put(**payload)
            entry["changes_applied"] = payload
            pve_cache.clear_prefix(f"pve:{vm.host_id}:")
        except HTTPException as e:
            entry["error"] = e.detail
        except Exception as e:
            entry["error"] = str(e)

        results.append(entry)

    return {"results": results}


@router.post("/bulk/config/preview")
def bulk_config_preview(req: BulkConfigRequest, db: Session = Depends(get_db),
                        current_user=Depends(require_operator)):
    """Dry-run: return what would change per VM without applying anything."""
    results = []
    host_cache: Dict[int, ProxmoxHost] = {}

    for vm in req.vms:
        entry: Dict[str, Any] = {
            "host_id": vm.host_id,
            "node": vm.node,
            "vmid": vm.vmid,
            "vm_name": None,
            "current": {},
            "proposed": {},
            "diff": {},
            "error": None,
        }
        try:
            if vm.host_id not in host_cache:
                host_cache[vm.host_id] = _get_host(vm.host_id, db)
            pve = _pve(host_cache[vm.host_id])

            cfg = pve.nodes(vm.node).qemu(vm.vmid).config.get()
            entry["vm_name"] = cfg.get("name", str(vm.vmid))

            current: Dict[str, Any] = {}
            proposed: Dict[str, Any] = {}

            if req.cores is not None:
                current["cores"] = cfg.get("cores")
                proposed["cores"] = req.cores
            if req.memory is not None:
                current["memory"] = cfg.get("memory")
                proposed["memory"] = req.memory
            if req.agent is not None:
                current["agent"] = cfg.get("agent")
                proposed["agent"] = req.agent
            if req.balloon is not None:
                current["balloon"] = cfg.get("balloon")
                proposed["balloon"] = req.balloon
            if req.onboot is not None:
                current["onboot"] = cfg.get("onboot")
                proposed["onboot"] = int(req.onboot)
            if req.tags_add or req.tags_remove:
                raw = cfg.get("tags", "")
                tags = [t.strip() for t in raw.split(";") if t.strip()] if raw else []
                current["tags"] = tags[:]
                if req.tags_add:
                    for t in req.tags_add:
                        t = t.strip().lower()
                        if t and t not in tags:
                            tags.append(t)
                if req.tags_remove:
                    remove_set = {t.strip().lower() for t in req.tags_remove}
                    tags = [t for t in tags if t not in remove_set]
                proposed["tags"] = tags

            # Build diff: only keys where value actually changes
            diff = {}
            for key in proposed:
                if proposed[key] != current.get(key):
                    diff[key] = {"from": current.get(key), "to": proposed[key]}

            entry["current"] = current
            entry["proposed"] = proposed
            entry["diff"] = diff
        except HTTPException as e:
            entry["error"] = e.detail
        except Exception as e:
            entry["error"] = str(e)

        results.append(entry)

    return {"results": results}


# ── Bulk Migrate ──────────────────────────────────────────────────────────────

@router.post("/bulk/migrate")
def bulk_migrate(req: BulkMigrateRequest, db: Session = Depends(get_db),
                 current_user=Depends(require_operator)):
    """Migrate a list of VMs to a target node (sequential)."""
    results = []
    host_cache: Dict[int, ProxmoxHost] = {}

    for vm in req.vms:
        entry: Dict[str, Any] = {
            "host_id": vm.host_id,
            "node": vm.node,
            "vmid": vm.vmid,
            "upid": None,
            "error": None,
        }
        try:
            if vm.host_id not in host_cache:
                host_cache[vm.host_id] = _get_host(vm.host_id, db)
            pve = _pve(host_cache[vm.host_id])

            upid = pve.nodes(vm.node).qemu(vm.vmid).migrate.post(
                target=req.target_node,
                online=int(req.online),
                with_local_disks=int(req.with_local_disks),
            )
            entry["upid"] = upid
            pve_cache.clear_prefix(f"pve:{vm.host_id}:")
        except HTTPException as e:
            entry["error"] = e.detail
        except Exception as e:
            entry["error"] = str(e)

        results.append(entry)

    return {"results": results}


# ── Orphaned Disk Finder ──────────────────────────────────────────────────────

@router.get("/orphaned-disks/{host_id}")
def get_orphaned_disks(host_id: int, db: Session = Depends(get_db),
                       current_user=Depends(require_operator)):
    """Find storage volumes not referenced by any VM config on any node.

    Returns list of {storage, volid, format, size, node} for each orphan.
    """
    host = _get_host(host_id, db)
    pve = _pve(host)

    try:
        nodes_list = pve.nodes.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list nodes: {e}")

    # Build the set of all volids referenced by any VM config
    referenced: set = set()

    for node_info in nodes_list:
        node = node_info.get("node", "")
        if not node:
            continue

        # Collect from QEMU VMs
        try:
            vms = pve.nodes(node).qemu.get()
        except Exception:
            vms = []

        for vm in vms:
            vmid = vm.get("vmid")
            if not vmid:
                continue
            try:
                cfg = pve.nodes(node).qemu(vmid).config.get()
                _collect_disk_volids(cfg, referenced)
            except Exception:
                pass

        # Collect from LXC containers
        try:
            ctrs = pve.nodes(node).lxc.get()
        except Exception:
            ctrs = []

        for ct in ctrs:
            vmid = ct.get("vmid")
            if not vmid:
                continue
            try:
                cfg = pve.nodes(node).lxc(vmid).config.get()
                _collect_disk_volids(cfg, referenced)
            except Exception:
                pass

    # Now scan each storage on each node for volumes NOT in referenced
    orphans = []

    for node_info in nodes_list:
        node = node_info.get("node", "")
        if not node:
            continue

        try:
            storages = pve.nodes(node).storage.get()
        except Exception:
            continue

        for st in storages:
            storage_name = st.get("storage", "")
            if not storage_name:
                continue

            try:
                volumes = pve.nodes(node).storage(storage_name).content.get()
            except Exception:
                continue

            for vol in volumes:
                volid = vol.get("volid", "")
                content_type = vol.get("content", "")
                # Only look at disk-type content (images, rootdir, subvol)
                if content_type not in ("images", "rootdir", "subvol"):
                    continue
                if volid and volid not in referenced:
                    orphans.append({
                        "node": node,
                        "storage": storage_name,
                        "volid": volid,
                        "format": vol.get("format", ""),
                        "size": vol.get("size", 0),
                        "content": content_type,
                        "ctime": vol.get("ctime"),
                    })

    return {"host_id": host_id, "orphans": orphans, "count": len(orphans)}


def _collect_disk_volids(cfg: dict, result: set):
    """Extract volids from a Proxmox VM/CT config dict into result set."""
    disk_prefixes = (
        "scsi", "virtio", "ide", "sata",  # QEMU disks
        "rootfs", "mp",                    # LXC disks
        "efidisk", "tpmstate",
    )
    for key, val in cfg.items():
        if not isinstance(val, str):
            continue
        # Check if this key is a disk key
        is_disk = False
        for pfx in disk_prefixes:
            if key.startswith(pfx) and (key[len(pfx):].isdigit() or key == pfx):
                is_disk = True
                break

        if is_disk or key.startswith("unused"):
            # volid is the part before the first comma
            volid = val.split(",")[0].strip()
            if ":" in volid:  # valid volid format: storage:volume
                result.add(volid)


# ── Automation Scripts ────────────────────────────────────────────────────────

class ScriptCleanupSnapsRequest(BaseModel):
    host_id: int
    older_than_days: int = 30
    dry_run: bool = True


class ScriptTagComplianceRequest(BaseModel):
    host_id: int
    required_tags: List[str]
    dry_run: bool = True


class ScriptResourceAuditRequest(BaseModel):
    host_id: int
    cpu_threshold_pct: float = 20.0   # flag VMs using less than N% of allocated
    ram_threshold_pct: float = 20.0


@router.post("/scripts/cleanup-snapshots")
def script_cleanup_snapshots(req: ScriptCleanupSnapsRequest,
                              db: Session = Depends(get_db),
                              current_user=Depends(require_operator)):
    """Find (and optionally delete) all snapshots older than N days across all VMs."""
    import time as _time
    host = _get_host(req.host_id, db)
    pve = _pve(host)
    cutoff = _time.time() - (req.older_than_days * 86400)

    try:
        nodes_list = pve.nodes.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    findings = []

    for node_info in nodes_list:
        node = node_info.get("node", "")
        if not node:
            continue
        try:
            vms = pve.nodes(node).qemu.get()
        except Exception:
            continue
        for vm in vms:
            vmid = vm.get("vmid")
            vm_name = vm.get("name", str(vmid))
            try:
                snaps = pve.nodes(node).qemu(vmid).snapshot.get()
            except Exception:
                continue
            for snap in snaps:
                name = snap.get("name", "")
                if name == "current":
                    continue
                snap_time = snap.get("snaptime", 0)
                if snap_time and snap_time < cutoff:
                    finding = {
                        "node": node,
                        "vmid": vmid,
                        "vm_name": vm_name,
                        "snapname": name,
                        "snaptime": snap_time,
                        "deleted": False,
                        "error": None,
                    }
                    if not req.dry_run:
                        try:
                            pve.nodes(node).qemu(vmid).snapshot(name).delete()
                            finding["deleted"] = True
                            pve_cache.clear_prefix(f"pve:{req.host_id}:")
                        except Exception as e:
                            finding["error"] = str(e)
                    findings.append(finding)

    return {
        "dry_run": req.dry_run,
        "older_than_days": req.older_than_days,
        "total_found": len(findings),
        "findings": findings,
    }


@router.post("/scripts/tag-compliance")
def script_tag_compliance(req: ScriptTagComplianceRequest,
                          db: Session = Depends(get_db),
                          current_user=Depends(require_operator)):
    """Find VMs missing required tags. Optionally add them."""
    host = _get_host(req.host_id, db)
    pve = _pve(host)

    try:
        resources = pve.cluster.resources.get(type="vm")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    required = {t.strip().lower() for t in req.required_tags if t.strip()}
    findings = []

    for item in resources:
        raw_tags = item.get("tags", "")
        current_tags = {t.strip() for t in raw_tags.split(";") if t.strip()} if raw_tags else set()
        missing = required - current_tags
        if not missing:
            continue

        finding = {
            "node": item.get("node", ""),
            "vmid": item.get("vmid"),
            "vm_name": item.get("name", ""),
            "current_tags": list(current_tags),
            "missing_tags": list(missing),
            "fixed": False,
            "error": None,
        }

        if not req.dry_run:
            node = item.get("node", "")
            vmid = item.get("vmid")
            try:
                cfg = pve.nodes(node).qemu(vmid).config.get()
                all_tags = [t.strip() for t in cfg.get("tags", "").split(";") if t.strip()]
                for t in missing:
                    if t not in all_tags:
                        all_tags.append(t)
                pve.nodes(node).qemu(vmid).config.put(tags=";".join(all_tags))
                finding["fixed"] = True
                pve_cache.clear_prefix(f"pve:{req.host_id}:")
            except Exception as e:
                finding["error"] = str(e)

        findings.append(finding)

    return {
        "dry_run": req.dry_run,
        "required_tags": list(required),
        "non_compliant_count": len(findings),
        "findings": findings,
    }


@router.post("/scripts/resource-audit")
def script_resource_audit(req: ScriptResourceAuditRequest,
                          db: Session = Depends(get_db),
                          current_user=Depends(require_operator)):
    """Find over-provisioned VMs by comparing allocation vs recent RRD usage."""
    host = _get_host(req.host_id, db)
    pve = _pve(host)

    try:
        resources = pve.cluster.resources.get(type="vm")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    report = []

    for item in resources:
        if item.get("status") != "running":
            continue
        node = item.get("node", "")
        vmid = item.get("vmid")
        if not node or not vmid:
            continue

        # Get RRD data for the past hour
        cpu_avg = None
        mem_avg_pct = None
        try:
            rrd = pve.nodes(node).qemu(vmid).rrddata.get(timeframe="hour", cf="AVERAGE")
            if rrd:
                cpu_vals = [r.get("cpu", 0) for r in rrd if r.get("cpu") is not None]
                mem_vals = [r.get("mem", 0) for r in rrd if r.get("mem") is not None]
                max_mem_vals = [r.get("maxmem", 0) for r in rrd if r.get("maxmem") is not None]
                if cpu_vals:
                    cpu_avg = (sum(cpu_vals) / len(cpu_vals)) * 100
                if mem_vals and max_mem_vals:
                    avg_mem = sum(mem_vals) / len(mem_vals)
                    avg_max_mem = sum(max_mem_vals) / len(max_mem_vals)
                    if avg_max_mem > 0:
                        mem_avg_pct = (avg_mem / avg_max_mem) * 100
        except Exception:
            pass

        over_provisioned_cpu = (cpu_avg is not None and cpu_avg < req.cpu_threshold_pct)
        over_provisioned_ram = (mem_avg_pct is not None and mem_avg_pct < req.ram_threshold_pct)

        if over_provisioned_cpu or over_provisioned_ram:
            report.append({
                "node": node,
                "vmid": vmid,
                "vm_name": item.get("name", str(vmid)),
                "allocated_cores": item.get("maxcpu", 0),
                "allocated_memory_mb": int(item.get("maxmem", 0) / 1024 / 1024),
                "cpu_avg_pct": round(cpu_avg, 2) if cpu_avg is not None else None,
                "mem_avg_pct": round(mem_avg_pct, 2) if mem_avg_pct is not None else None,
                "over_provisioned_cpu": over_provisioned_cpu,
                "over_provisioned_ram": over_provisioned_ram,
            })

    return {
        "cpu_threshold_pct": req.cpu_threshold_pct,
        "ram_threshold_pct": req.ram_threshold_pct,
        "over_provisioned_count": len(report),
        "report": report,
    }
