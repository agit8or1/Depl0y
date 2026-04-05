"""Node-level Proxmox management: status, RRD charts, tasks, storage content, network"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from app.core.database import get_db
from app.models import ProxmoxHost
from app.api.auth import get_current_user, require_operator, require_admin
from app.services.proxmox import ProxmoxService
from app.core.cache import pve_cache
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_host(host_id: int, db: Session) -> ProxmoxHost:
    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id, ProxmoxHost.is_active == True).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")
    return host


def _pve(host: ProxmoxHost):
    return ProxmoxService(host).proxmox


# ── Cluster-level ─────────────────────────────────────────────────────────────

@router.get("/{host_id}/cluster/status")
def cluster_status(host_id: int, db: Session = Depends(get_db),
                   current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:cluster/status"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(host).cluster.status.get()
        pve_cache.set(cache_key, result, ttl=30)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/cluster/resources")
def cluster_resources(host_id: int, type: Optional[str] = None,
                      db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:cluster/resources:{type or ''}"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        params = {}
        if type:
            params["type"] = type
        result = _pve(host).cluster.resources.get(**params)
        pve_cache.set(cache_key, result, ttl=15)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/cluster/nextid")
def next_vmid(host_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return {"vmid": int(_pve(host).cluster.nextid.get())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/cluster/options")
def cluster_options(host_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.options.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Datacenter firewall ───────────────────────────────────────────────────────

@router.get("/{host_id}/cluster/firewall/rules")
def dc_firewall_rules(host_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.firewall.rules.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/cluster/firewall/rules")
def add_dc_firewall_rule(host_id: int, rule: dict, db: Session = Depends(get_db),
                         current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.rules.post(**rule)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/cluster/firewall/rules/{pos}")
def delete_dc_firewall_rule(host_id: int, pos: int, db: Session = Depends(get_db),
                            current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.firewall.rules(pos).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── HA (native proxmoxer, replaces SSH) ──────────────────────────────────────

@router.get("/{host_id}/cluster/ha/resources")
def ha_resources(host_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.ha.resources.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/cluster/ha/resources")
def add_ha_resource(host_id: int, resource: dict, db: Session = Depends(get_db),
                    current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.ha.resources.post(**resource)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/cluster/ha/resources/{sid}")
def remove_ha_resource(host_id: int, sid: str, db: Session = Depends(get_db),
                       current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.ha.resources(sid).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/cluster/ha/groups")
def ha_groups(host_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.ha.groups.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/cluster/ha/status")
def ha_status(host_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.ha.status.manager_status.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Access management ─────────────────────────────────────────────────────────

@router.get("/{host_id}/access/users")
def list_pve_users(host_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).access.users.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/access/users")
def create_pve_user(host_id: int, user: dict, db: Session = Depends(get_db),
                    current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).access.users.post(**user)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/access/users/{userid}")
def update_pve_user(host_id: int, userid: str, user: dict, db: Session = Depends(get_db),
                    current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).access.users(userid).put(**user)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/access/users/{userid}")
def delete_pve_user(host_id: int, userid: str, db: Session = Depends(get_db),
                    current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).access.users(userid).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/access/users/{userid}/tokens")
def list_user_tokens(host_id: int, userid: str, db: Session = Depends(get_db),
                     current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).access.users(userid).token.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/access/users/{userid}/tokens/{tokenid}")
def create_user_token(host_id: int, userid: str, tokenid: str, token: dict = {},
                      db: Session = Depends(get_db), current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        result = _pve(host).access.users(userid).token(tokenid).post(**token)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/access/users/{userid}/tokens/{tokenid}")
def delete_user_token(host_id: int, userid: str, tokenid: str, db: Session = Depends(get_db),
                      current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).access.users(userid).token(tokenid).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/access/roles")
def list_roles(host_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).access.roles.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/access/acl")
def get_acl(host_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).access.acl.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/access/acl")
def update_acl(host_id: int, acl: dict, db: Session = Depends(get_db),
               current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).access.acl.put(**acl)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Resource pools ────────────────────────────────────────────────────────────

@router.get("/{host_id}/pools")
def list_pools(host_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).pools.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/pools/{poolid}")
def get_pool(host_id: int, poolid: str, db: Session = Depends(get_db),
             current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).pools(poolid).get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/pools")
def create_pool(host_id: int, pool: dict, db: Session = Depends(get_db),
                current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).pools.post(**pool)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/pools/{poolid}")
def update_pool(host_id: int, poolid: str, pool: dict, db: Session = Depends(get_db),
                current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).pools(poolid).put(**pool)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/pools/{poolid}")
def delete_pool(host_id: int, poolid: str, db: Session = Depends(get_db),
                current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).pools(poolid).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Node status & RRD ─────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/status")
def node_status(host_id: int, node: str, db: Session = Depends(get_db),
                current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:nodes/{node}/status"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(host).nodes(node).status.get()
        pve_cache.set(cache_key, result, ttl=20)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/rrddata")
def node_rrddata(host_id: int, node: str, timeframe: str = "hour", cf: str = "AVERAGE",
                 db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:nodes/{node}/rrddata:{timeframe}:{cf}"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(host).nodes(node).rrddata.get(timeframe=timeframe, cf=cf)
        pve_cache.set(cache_key, result, ttl=60)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/vms")
def node_vms(host_id: int, node: str, db: Session = Depends(get_db),
             current_user=Depends(get_current_user)):
    """List all VMs on a specific node."""
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:nodes/{node}/vms"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        vms = _pve(host).nodes(node).qemu.get()
        cts = []
        try:
            cts = _pve(host).nodes(node).lxc.get()
            for c in cts:
                c["type"] = "lxc"
        except Exception:
            pass
        for v in vms:
            v["type"] = "qemu"
        result = {"vms": vms, "containers": cts}
        pve_cache.set(cache_key, result, ttl=15)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Tasks ─────────────────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/tasks")
def node_tasks(host_id: int, node: str, limit: int = 50, start: int = 0,
               vmid: Optional[int] = None, typefilter: Optional[str] = None,
               db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    params: Dict[str, Any] = {"limit": limit, "start": start}
    if vmid:
        params["vmid"] = vmid
    if typefilter:
        params["typefilter"] = typefilter
    try:
        return _pve(host).nodes(node).tasks.get(**params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/tasks/{upid}/status")
def task_status(host_id: int, node: str, upid: str, db: Session = Depends(get_db),
                current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).tasks(upid).status.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/tasks/{upid}/log")
def task_log(host_id: int, node: str, upid: str, start: int = 0, limit: int = 500,
             db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        lines = _pve(host).nodes(node).tasks(upid).log.get(start=start, limit=limit)
        return {"lines": [l.get("t", "") for l in lines]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/nodes/{node}/tasks/{upid}")
def stop_task(host_id: int, node: str, upid: str, db: Session = Depends(get_db),
              current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).tasks(upid).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Storage content ───────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/storage")
def node_storage(host_id: int, node: str, db: Session = Depends(get_db),
                 current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:nodes/{node}/storage"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(host).nodes(node).storage.get()
        pve_cache.set(cache_key, result, ttl=60)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/storage/{storage}/content")
def storage_content(host_id: int, node: str, storage: str, content: Optional[str] = None,
                    db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    params: Dict[str, Any] = {}
    if content:
        params["content"] = content
    try:
        return _pve(host).nodes(node).storage(storage).content.get(**params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/nodes/{node}/storage/{storage}/content/{volid:path}")
def delete_storage_volume(host_id: int, node: str, storage: str, volid: str,
                          db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).storage(storage).content(volid).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Network management ────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/network")
def node_network(host_id: int, node: str, db: Session = Depends(get_db),
                 current_user=Depends(get_current_user)):
    """All network interfaces on a node (all types)."""
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:nodes/{node}/network"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(host).nodes(node).network.get()
        pve_cache.set(cache_key, result, ttl=60)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/network")
def create_network_iface(host_id: int, node: str, iface: dict,
                         db: Session = Depends(get_db), current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).network.post(**iface)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/nodes/{node}/network/{iface}")
def update_network_iface(host_id: int, node: str, iface: str, config: dict,
                         db: Session = Depends(get_db), current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).network(iface).put(**config)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/nodes/{node}/network/{iface}")
def delete_network_iface(host_id: int, node: str, iface: str,
                         db: Session = Depends(get_db), current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).network(iface).delete()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/nodes/{node}/network")
def apply_network_config(host_id: int, node: str, db: Session = Depends(get_db),
                         current_user=Depends(require_admin)):
    """Apply pending network configuration changes."""
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).network.put()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Node shell termproxy ──────────────────────────────────────────────────────

@router.post("/{host_id}/nodes/{node}/termproxy")
def node_termproxy(host_id: int, node: str, db: Session = Depends(get_db),
                   current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        result = _pve(host).nodes(node).termproxy.post()
        return {**result, "host": host.hostname, "pve_port": host.port}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Backup (vzdump) ───────────────────────────────────────────────────────────

@router.post("/{host_id}/nodes/{node}/vzdump")
def run_vzdump(host_id: int, node: str, backup: dict,
               db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).vzdump.post(**backup)
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/cluster/backup")
def list_backup_schedules(host_id: int, db: Session = Depends(get_db),
                          current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).cluster.backup.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/cluster/backup")
def create_backup_schedule(host_id: int, schedule: dict, db: Session = Depends(get_db),
                            current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.backup.post(**schedule)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/cluster/backup/{id}")
def update_backup_schedule(host_id: int, id: str, schedule: dict,
                            db: Session = Depends(get_db), current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.backup(id).put(**schedule)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/cluster/backup/{id}")
def delete_backup_schedule(host_id: int, id: str, db: Session = Depends(get_db),
                            current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.backup(id).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── LXC containers ────────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/lxc")
def list_containers(host_id: int, node: str, db: Session = Depends(get_db),
                    current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:nodes/{node}/lxc"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(host).nodes(node).lxc.get()
        pve_cache.set(cache_key, result, ttl=15)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/lxc/{vmid}/config")
def get_ct_config(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                  current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).lxc(vmid).config.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/nodes/{node}/lxc/{vmid}/config")
def update_ct_config(host_id: int, node: str, vmid: int, config: dict,
                     db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).lxc(vmid).config.put(**config)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/lxc/{vmid}/status")
def get_ct_status(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                  current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).lxc(vmid).status.current.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/lxc/{vmid}/{action}")
def ct_action(host_id: int, node: str, vmid: int, action: str,
              db: Session = Depends(get_db), current_user=Depends(require_operator)):
    allowed = {"start", "stop", "shutdown", "reboot", "suspend", "resume"}
    if action not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid action. Allowed: {allowed}")
    host = _get_host(host_id, db)
    try:
        upid = getattr(_pve(host).nodes(node).lxc(vmid).status, action).post()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/lxc/{vmid}/snapshots")
def list_ct_snapshots(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                      current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).lxc(vmid).snapshot.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/lxc/{vmid}/snapshots")
def create_ct_snapshot(host_id: int, node: str, vmid: int, snap: dict,
                       db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).lxc(vmid).snapshot.post(**snap)
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/lxc/{vmid}/snapshots/{snapname}/rollback")
def rollback_ct_snapshot(host_id: int, node: str, vmid: int, snapname: str,
                         db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).lxc(vmid).snapshot(snapname).rollback.post()
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/lxc/{vmid}/termproxy")
def ct_termproxy(host_id: int, node: str, vmid: int, db: Session = Depends(get_db),
                 current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        result = _pve(host).nodes(node).lxc(vmid).termproxy.post()
        return {**result, "host": host.hostname, "pve_port": host.port}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/nodes/{node}/lxc/{vmid}")
def delete_ct(host_id: int, node: str, vmid: int,
              db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).lxc(vmid).delete()
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── VM restore from backup ────────────────────────────────────────────────────

@router.post("/{host_id}/nodes/{node}/qemu/{vmid}/restore")
def restore_vm_backup(host_id: int, node: str, vmid: int, restore: dict,
                      db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).qemu.post(**{"vmid": vmid, **restore})
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── VM / LXC create ───────────────────────────────────────────────────────────

@router.post("/{host_id}/nodes/{node}/qemu")
def create_vm(host_id: int, node: str, data: dict,
              db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Create a new QEMU VM on a Proxmox node."""
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).qemu.post(**data)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/lxc")
def create_lxc(host_id: int, node: str, data: dict,
               db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Create a new LXC container on a Proxmox node."""
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).lxc.post(**data)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── LXC templates ─────────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/lxc-templates")
def list_lxc_templates(host_id: int, node: str, storage: str,
                       db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """List available LXC templates in a storage."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).storage(storage).content.get(content="vztmpl")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── VM templates ──────────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/templates")
def list_vm_templates(host_id: int, node: str,
                      db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """List QEMU VM templates on a node."""
    host = _get_host(host_id, db)
    try:
        vms = _pve(host).nodes(node).qemu.get()
        return [v for v in vms if v.get("template") == 1]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Storage upload ────────────────────────────────────────────────────────────

@router.post("/{host_id}/nodes/{node}/storage/{storage}/upload")
async def upload_to_storage(host_id: int, node: str, storage: str,
                            file: UploadFile = File(...),
                            db: Session = Depends(get_db),
                            current_user=Depends(require_operator)):
    """Upload an ISO or file to Proxmox storage."""
    host = _get_host(host_id, db)
    try:
        content = await file.read()
        result = _pve(host).nodes(node).storage(storage).upload.post(
            content="iso",
            filename=file.filename,
            file=(file.filename, content, file.content_type or "application/octet-stream"),
        )
        return {"upid": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
