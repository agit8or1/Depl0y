"""Node-level Proxmox management: status, RRD charts, tasks, storage content, network"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from app.core.database import get_db
from app.models import ProxmoxHost
from app.api.auth import get_current_user, require_operator, require_admin
from app.services.proxmox import ProxmoxService
from app.services.task_tracker import task_tracker
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


@router.post("/{host_id}/cluster/ha/groups")
def create_ha_group(host_id: int, data: dict = {}, db: Session = Depends(get_db),
                    current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.ha.groups.post(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/cluster/ha/groups/{groupid}")
def delete_ha_group(host_id: int, groupid: str, db: Session = Depends(get_db),
                    current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).cluster.ha.groups(groupid).delete()
        return {"success": True}
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


@router.post("/{host_id}/access/roles")
def create_role(host_id: int, data: dict, db: Session = Depends(get_db),
                current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).access.roles.post(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/access/roles/{roleid}")
def update_role(host_id: int, roleid: str, data: dict, db: Session = Depends(get_db),
                current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).access.roles(roleid).put(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/access/roles/{roleid}")
def delete_role(host_id: int, roleid: str, db: Session = Depends(get_db),
                current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).access.roles(roleid).delete()
        return {"success": True}
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


# ── Access groups ─────────────────────────────────────────────────────────────

@router.get("/{host_id}/access/groups")
def list_groups(host_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).access.groups.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/access/groups")
def create_group(host_id: int, data: dict, db: Session = Depends(get_db),
                 current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).access.groups.post(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/access/groups/{groupid}")
def update_group(host_id: int, groupid: str, data: dict, db: Session = Depends(get_db),
                 current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).access.groups(groupid).put(**data)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/access/groups/{groupid}")
def delete_group(host_id: int, groupid: str, db: Session = Depends(get_db),
                 current_user=Depends(require_admin)):
    host = _get_host(host_id, db)
    try:
        _pve(host).access.groups(groupid).delete()
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


@router.delete("/{host_id}/nodes/{node}/network")
def revert_network_config(host_id: int, node: str, db: Session = Depends(get_db),
                          current_user=Depends(require_admin)):
    """Revert pending network configuration changes."""
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).network.delete()
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
        vmid = backup.get("vmid")
        task_tracker.register(
            upid, host_id, node,
            f"Backup VM {vmid}" if vmid else "Backup",
            user_id=getattr(current_user, "id", None),
            vmid=int(vmid) if vmid else None,
            task_type="vzdump",
        )
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


@router.post("/{host_id}/cluster/backup/{id}/run")
def run_backup_schedule_now(host_id: int, id: str, data: dict = Body(default={}),
                             db: Session = Depends(get_db),
                             current_user=Depends(require_operator)):
    """Run a backup schedule job immediately on the given node (node required in body)."""
    host = _get_host(host_id, db)
    node = data.get("node")
    if not node:
        raise HTTPException(status_code=400, detail="'node' is required")
    try:
        # Fetch schedule to get its parameters
        schedules = _pve(host).cluster.backup.get()
        sched = next((s for s in schedules if str(s.get("id")) == str(id)), None)
        if not sched:
            raise HTTPException(status_code=404, detail=f"Backup schedule '{id}' not found")
        # Build vzdump payload from schedule parameters
        payload: Dict[str, Any] = {}
        for k in ("vmid", "storage", "mode", "compress", "mailnotification", "mailto",
                  "maxfiles", "keep-last", "keep-daily", "keep-weekly", "keep-monthly",
                  "keep-yearly", "protected", "notes-template"):
            if k in sched and sched[k] not in (None, ""):
                payload[k] = sched[k]
        # Merge any overrides from request body (except 'node')
        for k, v in data.items():
            if k != "node":
                payload[k] = v
        upid = _pve(host).nodes(node).vzdump.post(**payload)
        task_tracker.register(
            upid, host_id, node,
            f"Backup schedule {id} on {node}",
            user_id=getattr(current_user, "id", None),
            task_type="vzdump",
        )
        return {"upid": upid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/backup/history")
def backup_task_history(host_id: int, node: Optional[str] = None,
                        limit: int = 200, start: int = 0,
                        db: Session = Depends(get_db),
                        current_user=Depends(get_current_user)):
    """Return completed backup tasks across all (or a specific) node(s)."""
    host = _get_host(host_id, db)
    try:
        if node:
            nodes_to_query = [node]
        else:
            resources = _pve(host).cluster.resources.get(type="node")
            nodes_to_query = [r["node"] for r in resources if "node" in r]

        all_tasks: List[Dict[str, Any]] = []
        for n in nodes_to_query:
            try:
                tasks = _pve(host).nodes(n).tasks.get(
                    limit=limit, start=start, typefilter="vzdump"
                )
                for t in tasks:
                    t["_node"] = n
                all_tasks.extend(tasks)
            except Exception:
                pass

        # Sort by starttime descending
        all_tasks.sort(key=lambda t: t.get("starttime", 0), reverse=True)
        return all_tasks[:limit]
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
        task_tracker.register(
            upid, host_id, node,
            f"LXC {vmid} {action}",
            user_id=getattr(current_user, "id", None),
            vmid=vmid,
            task_type=f"vz{action}",
        )
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
        task_tracker.register(
            upid, host_id, node,
            f"Snapshot LXC {vmid}: {snap.get('snapname', '')}",
            user_id=getattr(current_user, "id", None),
            vmid=vmid,
            task_type="vzsnapshot",
        )
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/lxc/{vmid}/snapshots/{snapname}/rollback")
def rollback_ct_snapshot(host_id: int, node: str, vmid: int, snapname: str,
                         db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).lxc(vmid).snapshot(snapname).rollback.post()
        task_tracker.register(
            upid, host_id, node,
            f"Rollback LXC {vmid} to {snapname}",
            user_id=getattr(current_user, "id", None),
            vmid=vmid,
            task_type="vzrollback",
        )
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
        task_tracker.register(
            upid, host_id, node,
            f"Delete LXC {vmid}",
            user_id=getattr(current_user, "id", None),
            vmid=vmid,
            task_type="vzdestroy",
        )
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/lxc/{vmid}/clone")
def clone_ct(host_id: int, node: str, vmid: int, data: dict,
             db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Clone an LXC container."""
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).lxc(vmid).clone.post(**data)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        new_vmid = data.get("newid")
        task_tracker.register(
            upid, host_id, node,
            f"Clone LXC {vmid} → {new_vmid}",
            user_id=getattr(current_user, "id", None),
            vmid=vmid,
            task_type="vzclone",
        )
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/nodes/{node}/lxc/{vmid}/snapshots/{snapname}")
def delete_ct_snapshot(host_id: int, node: str, vmid: int, snapname: str,
                       db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Delete an LXC snapshot."""
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).lxc(vmid).snapshot(snapname).delete()
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/lxc/{vmid}/resize")
def resize_ct_disk(host_id: int, node: str, vmid: int, data: dict,
                   db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Resize an LXC disk/mount point. Expects disk=rootfs|mpN and size=+XG."""
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).lxc(vmid).resize.put(**data)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── LXC Firewall ──────────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/lxc/{vmid}/firewall/rules")
def list_ct_firewall_rules(host_id: int, node: str, vmid: int,
                           db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).lxc(vmid).firewall.rules.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/lxc/{vmid}/firewall/rules")
def add_ct_firewall_rule(host_id: int, node: str, vmid: int, rule: dict,
                         db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).lxc(vmid).firewall.rules.post(**rule)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/nodes/{node}/lxc/{vmid}/firewall/rules/{pos}")
def update_ct_firewall_rule(host_id: int, node: str, vmid: int, pos: int, rule: dict,
                            db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).lxc(vmid).firewall.rules(pos).put(**rule)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/nodes/{node}/lxc/{vmid}/firewall/rules/{pos}")
def delete_ct_firewall_rule(host_id: int, node: str, vmid: int, pos: int,
                            db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).lxc(vmid).firewall.rules(pos).delete()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/lxc/{vmid}/firewall/options")
def get_ct_firewall_options(host_id: int, node: str, vmid: int,
                            db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).lxc(vmid).firewall.options.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/nodes/{node}/lxc/{vmid}/firewall/options")
def update_ct_firewall_options(host_id: int, node: str, vmid: int, opts: dict,
                               db: Session = Depends(get_db), current_user=Depends(require_operator)):
    host = _get_host(host_id, db)
    try:
        _pve(host).nodes(node).lxc(vmid).firewall.options.put(**opts)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/lxc/{vmid}/rrddata")
def ct_rrddata(host_id: int, node: str, vmid: int,
               timeframe: str = "hour", cf: str = "AVERAGE",
               db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """LXC container performance/RRD data."""
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:nodes/{node}/lxc/{vmid}/rrddata:{timeframe}:{cf}"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(host).nodes(node).lxc(vmid).rrddata.get(timeframe=timeframe, cf=cf)
        pve_cache.set(cache_key, result, ttl=60)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── VM restore from backup ────────────────────────────────────────────────────

@router.post("/{host_id}/nodes/{node}/qemu/{vmid}/restore")
def restore_vm_backup(host_id: int, node: str, vmid: int, restore: dict,
                      db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Restore a QEMU VM from a vzdump backup archive. Pass 'archive' and restore options in body."""
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).qemu.post(**{"vmid": vmid, **restore})
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/lxc/{vmid}/restore")
def restore_lxc_backup(host_id: int, node: str, vmid: int, restore: dict,
                       db: Session = Depends(get_db), current_user=Depends(require_operator)):
    """Restore an LXC container from a vzdump backup archive. Pass 'ostemplate' (archive path) and options."""
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).lxc.post(**{"vmid": vmid, **restore})
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
        vmid = data.get("vmid")
        task_tracker.register(
            upid, host_id, node,
            f"Create VM {vmid}" if vmid else "Create VM",
            user_id=getattr(current_user, "id", None),
            vmid=int(vmid) if vmid else None,
            task_type="qmcreate",
        )
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
        vmid = data.get("vmid")
        task_tracker.register(
            upid, host_id, node,
            f"Create LXC {vmid}" if vmid else "Create LXC",
            user_id=getattr(current_user, "id", None),
            vmid=int(vmid) if vmid else None,
            task_type="vzcreate",
        )
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


# ── Disk / SMART ──────────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/disks/list")
def node_disk_list(host_id: int, node: str, db: Session = Depends(get_db),
                   current_user=Depends(get_current_user)):
    """List physical disks on a node."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).disks.list.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/disks/{disk}/smart")
def node_disk_smart(host_id: int, node: str, disk: str, db: Session = Depends(get_db),
                    current_user=Depends(get_current_user)):
    """SMART data for a physical disk on a node."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).disks.smart.get(disk=disk)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Services ──────────────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/services")
def list_services(host_id: int, node: str, db: Session = Depends(get_db),
                  current_user=Depends(get_current_user)):
    """List system services on a node."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).services.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/services/{service}/{command}")
def service_action(host_id: int, node: str, service: str, command: str,
                   db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """Perform an action (start/stop/restart/reload) on a node service."""
    allowed = {"start", "stop", "restart", "reload"}
    if command not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid command. Allowed: {allowed}")
    host = _get_host(host_id, db)
    try:
        result = getattr(_pve(host).nodes(node).services(service), command).post()
        return {"upid": result} if result else {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Certificates ──────────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/certificates/info")
def get_certificates(host_id: int, node: str, db: Session = Depends(get_db),
                     current_user=Depends(get_current_user)):
    """List TLS certificates installed on a node."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).certificates.info.get()
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


# ── Storage download-url ──────────────────────────────────────────────────────

@router.post("/{host_id}/nodes/{node}/storage/{storage}/download-url")
def download_url_to_storage(host_id: int, node: str, storage: str,
                             data: dict = Body(default={}),
                             db: Session = Depends(get_db),
                             current_user=Depends(require_operator)):
    """Instruct Proxmox to download a URL directly to node storage."""
    host = _get_host(host_id, db)
    try:
        result = _pve(host).nodes(node).storage(storage)("download-url").post(**data)
        return {"upid": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Storage management (cluster-wide) ─────────────────────────────────────────

@router.get("/{host_id}/storage")
def list_all_storage(host_id: int, db: Session = Depends(get_db),
                     current_user=Depends(get_current_user)):
    """List all storage definitions on a Proxmox host (cluster-wide)."""
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:storage"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(host).storage.get()
        pve_cache.set(cache_key, result, ttl=30)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/storage")
def create_storage(host_id: int, data: dict = Body(default={}),
                   db: Session = Depends(get_db),
                   current_user=Depends(require_admin)):
    """Create a new storage definition."""
    host = _get_host(host_id, db)
    try:
        _pve(host).storage.post(**data)
        pve_cache.clear_prefix(f"pve:{host_id}:storage")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{host_id}/storage/{storage_id}")
def update_storage(host_id: int, storage_id: str, data: dict = Body(default={}),
                   db: Session = Depends(get_db),
                   current_user=Depends(require_admin)):
    """Update a storage definition."""
    host = _get_host(host_id, db)
    try:
        _pve(host).storage(storage_id).put(**data)
        pve_cache.clear_prefix(f"pve:{host_id}:storage")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{host_id}/storage/{storage_id}")
def delete_storage(host_id: int, storage_id: str,
                   db: Session = Depends(get_db),
                   current_user=Depends(require_admin)):
    """Delete a storage definition."""
    host = _get_host(host_id, db)
    try:
        _pve(host).storage(storage_id).delete()
        pve_cache.clear_prefix(f"pve:{host_id}:storage")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── ZFS pool management ───────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/disks/zfs")
def list_zfs_pools(host_id: int, node: str, db: Session = Depends(get_db),
                   current_user=Depends(get_current_user)):
    """List ZFS pools on a node."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).disks.zfs.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/disks/zfs")
def create_zfs_pool(host_id: int, node: str, data: dict = Body(default={}),
                    db: Session = Depends(get_db),
                    current_user=Depends(require_admin)):
    """Create a new ZFS pool on a node."""
    host = _get_host(host_id, db)
    try:
        result = _pve(host).nodes(node).disks.zfs.post(**data)
        pve_cache.clear_prefix(f"pve:{host_id}:")
        return {"upid": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/disks/zfs/{name}")
def get_zfs_pool(host_id: int, node: str, name: str, db: Session = Depends(get_db),
                 current_user=Depends(get_current_user)):
    """Get ZFS pool details including vdev tree."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).disks.zfs(name).get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/disks/zfs/{name}/scrub")
def scrub_zfs_pool(host_id: int, node: str, name: str,
                   db: Session = Depends(get_db),
                   current_user=Depends(require_admin)):
    """Start a scrub on a ZFS pool."""
    host = _get_host(host_id, db)
    try:
        result = _pve(host).nodes(node).disks.zfs(name).scrub.post()
        return {"upid": result} if result else {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Ceph management ───────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/ceph/status")
def ceph_status(host_id: int, node: str, db: Session = Depends(get_db),
                current_user=Depends(get_current_user)):
    """Get Ceph cluster status from a node."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).ceph.status.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/ceph/osd")
def ceph_osd(host_id: int, node: str, db: Session = Depends(get_db),
             current_user=Depends(get_current_user)):
    """List Ceph OSDs."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).ceph.osd.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/ceph/mon")
def ceph_mon(host_id: int, node: str, db: Session = Depends(get_db),
             current_user=Depends(get_current_user)):
    """List Ceph monitors."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).ceph.mon.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/ceph/pools")
def ceph_pools(host_id: int, node: str, db: Session = Depends(get_db),
               current_user=Depends(get_current_user)):
    """List Ceph pools."""
    host = _get_host(host_id, db)
    try:
        return _pve(host).nodes(node).ceph.pools.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── APT / Package updates ──────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/apt/update")
def apt_list_updates(host_id: int, node: str, db: Session = Depends(get_db),
                     current_user=Depends(get_current_user)):
    """List available package updates on a node."""
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:nodes/{node}/apt/update"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(host).nodes(node).apt.update.get()
        pve_cache.set(cache_key, result, ttl=120)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/apt/update")
def apt_refresh_packages(host_id: int, node: str, db: Session = Depends(get_db),
                         current_user=Depends(require_operator)):
    """Refresh package list (apt-get update) on a node."""
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).apt.update.post()
        pve_cache.clear_prefix(f"pve:{host_id}:nodes/{node}/apt")
        task_tracker.register(
            upid, host_id, node,
            f"APT refresh packages on {node}",
            user_id=getattr(current_user, "id", None),
            task_type="aptupdate",
        )
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host_id}/nodes/{node}/apt/upgrade")
def apt_upgrade_all(host_id: int, node: str, db: Session = Depends(get_db),
                    current_user=Depends(require_admin)):
    """Upgrade all packages on a node (dist-upgrade)."""
    host = _get_host(host_id, db)
    try:
        upid = _pve(host).nodes(node).apt.upgrade.post()
        pve_cache.clear_prefix(f"pve:{host_id}:nodes/{node}/apt")
        task_tracker.register(
            upid, host_id, node,
            f"APT upgrade all packages on {node}",
            user_id=getattr(current_user, "id", None),
            task_type="aptupgrade",
        )
        return {"upid": upid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/apt/versions")
def apt_installed_versions(host_id: int, node: str, db: Session = Depends(get_db),
                           current_user=Depends(get_current_user)):
    """Get currently installed Proxmox package versions."""
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:nodes/{node}/apt/versions"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(host).nodes(node).apt.versions.get()
        pve_cache.set(cache_key, result, ttl=300)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Hardware info ──────────────────────────────────────────────────────────────

@router.get("/{host_id}/nodes/{node}/hardware/pci")
def list_pci_devices(host_id: int, node: str, db: Session = Depends(get_db),
                     current_user=Depends(get_current_user)):
    """List PCI devices on a node (passthrough candidates)."""
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:nodes/{node}/hardware/pci"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(host).nodes(node).hardware.pci.get()
        pve_cache.set(cache_key, result, ttl=300)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host_id}/nodes/{node}/hardware/usb")
def list_usb_devices(host_id: int, node: str, db: Session = Depends(get_db),
                     current_user=Depends(get_current_user)):
    """List USB devices on a node."""
    host = _get_host(host_id, db)
    cache_key = f"pve:{host_id}:nodes/{node}/hardware/usb"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _pve(host).nodes(node).hardware.usb.get()
        pve_cache.set(cache_key, result, ttl=300)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
