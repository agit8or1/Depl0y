"""
Network / Server Topology graph endpoint.

Returns a directed graph of the whole depl0y-managed environment:
Proxmox hosts -> nodes -> VMs/LXC/bridges/storage, plus PBS servers and
iDRAC/BMC references. Used by the frontend /topology view and for
draw.io / PNG / SVG exports.
"""
from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.database import (
    PBSServer,
    ProxmoxHost,
    ProxmoxNode,
    StandaloneBMC,
    User,
)
from app.services.pbs import PBSService
from app.services.proxmox import ProxmoxService

logger = logging.getLogger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------
# Simple in-process TTL cache dedicated to the topology endpoint so we don't
# fan out to every Proxmox/PBS server every time a user clicks Refresh.
# --------------------------------------------------------------------------
_TOPOLOGY_TTL_SECONDS = 60
_topology_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_topology_lock = Lock()


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    with _topology_lock:
        entry = _topology_cache.get(key)
        if entry and entry[0] > time.time():
            return entry[1]
        if entry:
            _topology_cache.pop(key, None)
    return None


def _cache_set(key: str, value: Dict[str, Any], ttl: int = _TOPOLOGY_TTL_SECONDS) -> None:
    with _topology_lock:
        _topology_cache[key] = (time.time() + ttl, value)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

_BRIDGE_RE = re.compile(r"bridge=([A-Za-z0-9_\-]+)")
_IP_RE = re.compile(r"ip=([0-9a-fA-F:.]+)")


def _extract_bridges(vm_cfg: Dict[str, Any]) -> List[str]:
    """Scan a VM config dict and return a list of bridge names referenced by
    any netN entry (Proxmox serialises net devices as
    'virtio,bridge=vmbr0,...')."""
    bridges: List[str] = []
    for key, val in (vm_cfg or {}).items():
        if not isinstance(key, str) or not key.startswith("net"):
            continue
        if not isinstance(val, str):
            continue
        m = _BRIDGE_RE.search(val)
        if m:
            br = m.group(1)
            if br not in bridges:
                bridges.append(br)
    return bridges


def _extract_storage_refs(vm_cfg: Dict[str, Any]) -> List[str]:
    """Pull storage names out of disk entries in a VM config
    (e.g. 'local-zfs:vm-120-disk-0,size=32G' -> 'local-zfs')."""
    storages: List[str] = []
    disk_prefixes = ("scsi", "virtio", "ide", "sata", "efidisk", "tpmstate", "unused")
    for key, val in (vm_cfg or {}).items():
        if not isinstance(key, str) or not isinstance(val, str):
            continue
        if not any(key.startswith(p) for p in disk_prefixes):
            continue
        first = val.split(",", 1)[0]
        # Skip CD-ROM / "none" / etc
        if first in ("none", "cdrom") or "media=cdrom" in val:
            continue
        if ":" in first:
            storage = first.split(":", 1)[0]
            if storage and storage not in storages:
                storages.append(storage)
    return storages


def _bmc_key(kind: str, obj_id: int) -> str:
    return f"bmc:{kind}:{obj_id}"


def _bmc_node_for(
    kind: str,
    obj_id: int,
    idrac_hostname: Optional[str],
    idrac_type: Optional[str],
    owner_label: str,
    bmc_status_cache: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build a BMC node dict if the owner has an iDRAC/iLO configured."""
    if not idrac_hostname:
        return None
    cache_key = f"{kind}:{obj_id}"
    cache_entry = bmc_status_cache.get(cache_key, {}) if isinstance(bmc_status_cache, dict) else {}
    return {
        "id": _bmc_key(kind, obj_id),
        "type": "bmc",
        "label": f"{owner_label} BMC @ {idrac_hostname}",
        "data": {
            "idrac_hostname": idrac_hostname,
            "idrac_type": idrac_type or "idrac",
            "power_state": cache_entry.get("power_state"),
            "health": cache_entry.get("health"),
            "model": cache_entry.get("model"),
            "serial_number": cache_entry.get("serial_number"),
            "error": cache_entry.get("error"),
        },
    }


# --------------------------------------------------------------------------
# Per-subsystem collectors
# --------------------------------------------------------------------------

def _collect_host_subtree(
    host: ProxmoxHost,
    include_stopped: bool,
    include_bridges: bool,
    include_storage: bool,
    include_lxc: bool,
) -> Dict[str, Any]:
    """Fetch nodes / VMs / LXC / storage / bridges for a single Proxmox host.
    Returns a partial graph {nodes, edges, error?}."""
    out: Dict[str, Any] = {"nodes": [], "edges": []}
    try:
        service = ProxmoxService(host)
    except Exception as e:
        logger.warning("topology: failed to init ProxmoxService for host %s: %s", host.name, e)
        out["error"] = f"connection init failed: {e}"
        return out

    host_node_id = f"host:{host.id}"
    out["nodes"].append(
        {
            "id": host_node_id,
            "type": "pve_host",
            "label": host.name or host.hostname,
            "data": {
                "hostname": host.hostname,
                "port": host.port,
                "last_poll": host.last_poll.isoformat() if host.last_poll else None,
                "latitude": host.latitude,
                "longitude": host.longitude,
            },
        }
    )

    try:
        pve_nodes = service.get_nodes()
    except Exception as e:
        out["error"] = f"get_nodes failed: {e}"
        return out

    def _process_node(node_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Collect VMs/LXC/bridges/storage for one node."""
        node_name = node_entry.get("node")
        node_result: Dict[str, Any] = {"nodes": [], "edges": []}

        node_id = f"node:{host.id}:{node_name}"
        try:
            resources = service.get_node_resources(node_name) or {}
        except Exception:
            resources = {}

        node_data = {
            "node": node_name,
            "status": node_entry.get("status") or resources.get("status"),
            "cpu_cores": resources.get("cpu_cores"),
            "cpu_usage": resources.get("cpu_usage"),
            "memory_total": resources.get("memory_total"),
            "memory_used": resources.get("memory_used"),
            "uptime": resources.get("uptime"),
        }
        node_result["nodes"].append(
            {
                "id": node_id,
                "type": "pve_node",
                "label": node_name,
                "data": node_data,
            }
        )
        node_result["edges"].append(
            {"from": host_node_id, "to": node_id, "kind": "contains"}
        )

        # VMs
        try:
            vms = service.get_vms(node_name)
        except Exception as e:
            node_result["edges"].append(
                {"from": host_node_id, "to": node_id, "kind": "error", "label": str(e)}
            )
            vms = []
        for vm in vms:
            status = (vm.get("status") or "").lower()
            if not include_stopped and status != "running":
                continue
            vmid = vm.get("vmid")
            vm_id = f"vm:{host.id}:{node_name}:{vmid}"
            vm_node = {
                "id": vm_id,
                "type": "vm",
                "label": f"{vm.get('name') or vmid} ({vmid})",
                "data": {
                    "vmid": vmid,
                    "name": vm.get("name"),
                    "status": status or "unknown",
                    "cpu_cores": vm.get("cpus"),
                    "memory_mb": int((vm.get("maxmem") or 0) / (1024 * 1024)) if vm.get("maxmem") else None,
                    "disk_bytes": vm.get("maxdisk"),
                    "uptime": vm.get("uptime"),
                    "host_id": host.id,
                    "node": node_name,
                },
            }
            node_result["nodes"].append(vm_node)
            node_result["edges"].append(
                {"from": node_id, "to": vm_id, "kind": "hosts"}
            )

            # For running VMs, look up config for bridge / storage refs.
            # Skip for stopped unless include_stopped+include_bridges; config
            # fetch is cheap anyway.
            if include_bridges or include_storage:
                try:
                    cfg = service.get_vm_config(node_name, vmid) or {}
                except Exception:
                    cfg = {}
                if include_bridges:
                    for br in _extract_bridges(cfg):
                        br_id = f"bridge:{host.id}:{node_name}:{br}"
                        node_result["edges"].append(
                            {"from": vm_id, "to": br_id, "kind": "attached"}
                        )
                if include_storage:
                    for st in _extract_storage_refs(cfg):
                        st_id = f"storage:{host.id}:{node_name}:{st}"
                        node_result["edges"].append(
                            {"from": vm_id, "to": st_id, "kind": "disk-on"}
                        )
                # Also pull ipconfig0 if present for display
                ipc0 = cfg.get("ipconfig0")
                if isinstance(ipc0, str):
                    m = _IP_RE.search(ipc0)
                    if m:
                        vm_node["data"]["ip"] = m.group(1).split("/")[0]

        # LXC containers
        if include_lxc:
            try:
                cts = service.get_lxc(node_name)
            except Exception:
                cts = []
            for ct in cts:
                status = (ct.get("status") or "").lower()
                if not include_stopped and status != "running":
                    continue
                ctid = ct.get("vmid")
                ct_id = f"ct:{host.id}:{node_name}:{ctid}"
                node_result["nodes"].append(
                    {
                        "id": ct_id,
                        "type": "lxc",
                        "label": f"{ct.get('name') or ctid} ({ctid})",
                        "data": {
                            "vmid": ctid,
                            "name": ct.get("name"),
                            "status": status or "unknown",
                            "cpu_cores": ct.get("cpus"),
                            "memory_mb": int((ct.get("maxmem") or 0) / (1024 * 1024)) if ct.get("maxmem") else None,
                            "host_id": host.id,
                            "node": node_name,
                        },
                    }
                )
                node_result["edges"].append(
                    {"from": node_id, "to": ct_id, "kind": "hosts"}
                )

        # Bridges / bonds / physical NICs
        if include_bridges:
            try:
                ifaces = service.get_network_interfaces(node_name)
            except Exception:
                ifaces = []
            # Pre-index by name for bridge-port / bond-slave lookups
            by_name = {ii.get("iface"): ii for ii in (ifaces or []) if ii.get("iface")}
            for br in ifaces or []:
                name = br.get("iface")
                itype = br.get("type")
                if not name or itype not in ("bridge",):
                    continue
                br_id = f"bridge:{host.id}:{node_name}:{name}"
                node_result["nodes"].append(
                    {
                        "id": br_id,
                        "type": "bridge",
                        "label": name,
                        "data": {
                            "iface_type": itype,
                            "active": br.get("active"),
                            "address": br.get("address"),
                            "gateway": br.get("gateway"),
                            "bridge_ports": br.get("bridge_ports"),
                            "vlan_aware": br.get("bridge_vlan_aware"),
                            "host_id": host.id,
                            "node": node_name,
                        },
                    }
                )
                node_result["edges"].append(
                    {"from": node_id, "to": br_id, "kind": "has-bridge"}
                )
                # In network / combined view, drill into ports
                if vm in ("network", "combined"):
                    ports = (br.get("bridge_ports") or "").split()
                    for p in ports:
                        target = by_name.get(p, {})
                        ptype = target.get("type")
                        if ptype == "bond":
                            bond_id = f"bond:{host.id}:{node_name}:{p}"
                            node_result["nodes"].append(
                                {
                                    "id": bond_id, "type": "bond", "label": p,
                                    "data": {
                                        "bond_mode": target.get("bond_mode"),
                                        "bond_slaves": target.get("bond_slaves"),
                                        "bond_miimon": target.get("bond_miimon"),
                                        "host_id": host.id, "node": node_name,
                                    },
                                }
                            )
                            node_result["edges"].append(
                                {"from": br_id, "to": bond_id, "kind": "bridge-port"}
                            )
                            for slave in (target.get("bond_slaves") or "").split():
                                nic_id = f"nic:{host.id}:{node_name}:{slave}"
                                snic = by_name.get(slave, {})
                                node_result["nodes"].append(
                                    {
                                        "id": nic_id, "type": "nic", "label": slave,
                                        "data": {
                                            "active": snic.get("active"),
                                            "exists": snic.get("exists"),
                                            "host_id": host.id, "node": node_name,
                                        },
                                    }
                                )
                                node_result["edges"].append(
                                    {"from": bond_id, "to": nic_id, "kind": "bond-slave"}
                                )
                        else:
                            # Plain physical NIC or VLAN sub-interface
                            nic_id = f"nic:{host.id}:{node_name}:{p}"
                            node_result["nodes"].append(
                                {
                                    "id": nic_id,
                                    "type": "nic" if ptype != "vlan" else "vlan",
                                    "label": p,
                                    "data": {
                                        "iface_type": ptype,
                                        "active": target.get("active"),
                                        "vlan_id": target.get("vlan-id"),
                                        "host_id": host.id, "node": node_name,
                                    },
                                }
                            )
                            node_result["edges"].append(
                                {"from": br_id, "to": nic_id, "kind": "bridge-port"}
                            )

        # Storage pools
        if include_storage:
            try:
                stores = service.get_storage_list(node_name)
            except Exception:
                stores = []
            for s in stores:
                sname = s.get("storage")
                if not sname:
                    continue
                st_id = f"storage:{host.id}:{node_name}:{sname}"
                node_result["nodes"].append(
                    {
                        "id": st_id,
                        "type": "storage",
                        "label": sname,
                        "data": {
                            "storage_type": s.get("type"),
                            "content": s.get("content"),
                            "active": s.get("active"),
                            "total": s.get("total"),
                            "used": s.get("used"),
                            "available": s.get("available"),
                            "shared": s.get("shared"),
                        },
                    }
                )
                node_result["edges"].append(
                    {"from": node_id, "to": st_id, "kind": "uses"}
                )

        return node_result

    # Fan out one worker per node (most hosts are single-node, clusters are 3-5)
    max_workers = max(2, min(len(pve_nodes) or 1, 8))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_process_node, n) for n in pve_nodes]
        for fut in as_completed(futures):
            try:
                partial = fut.result()
                out["nodes"].extend(partial.get("nodes", []))
                out["edges"].extend(partial.get("edges", []))
            except Exception as e:
                logger.warning("topology: per-node worker failed on host %s: %s", host.name, e)
                out.setdefault("errors", []).append(str(e))

    return out


def _collect_pbs_subtree(server: PBSServer) -> Dict[str, Any]:
    """Fetch datastores, sync jobs, and remotes for a single PBS server."""
    out: Dict[str, Any] = {"nodes": [], "edges": []}

    pbs_node_id = f"pbs:{server.id}"
    data: Dict[str, Any] = {
        "hostname": server.hostname,
        "port": server.port,
    }

    try:
        svc = PBSService(server)
    except Exception as e:
        data["error"] = f"init failed: {e}"
        out["nodes"].append(
            {"id": pbs_node_id, "type": "pbs", "label": server.name, "data": data}
        )
        return out

    try:
        datastores = svc.get_datastores()
    except Exception as e:
        datastores = []
        data["datastore_error"] = str(e)

    try:
        sync_jobs = svc.get_sync_jobs()
    except Exception as e:
        sync_jobs = []
        data["sync_error"] = str(e)

    try:
        remotes = svc.get_remotes() or []
    except Exception:
        remotes = []

    data["datastore_count"] = len(datastores)
    data["sync_job_count"] = len(sync_jobs)

    out["nodes"].append(
        {"id": pbs_node_id, "type": "pbs", "label": server.name, "data": data}
    )

    # Map remote name -> remote host, so we can resolve sync_job.remote
    remote_by_name: Dict[str, str] = {}
    for r in remotes:
        rname = r.get("name") or r.get("id")
        rhost = r.get("host") or ""
        if rname:
            remote_by_name[rname] = rhost

    # Include sync edges (they have their own `sync` flag handled by caller)
    out["sync_edges"] = []
    for job in sync_jobs:
        if (job.get("job-type") or "sync") != "sync":
            continue
        remote_name = job.get("remote") or ""
        remote_host = remote_by_name.get(remote_name, remote_name)
        out["sync_edges"].append(
            {
                "source_pbs_id": server.id,
                "remote_name": remote_name,
                "remote_host": remote_host,
                "job_id": job.get("id") or job.get("job-id"),
                "schedule": job.get("schedule"),
                "last_run_state": job.get("last-run-state"),
                "store": job.get("store"),
                "remote_store": job.get("remote-store"),
            }
        )

    return out


# --------------------------------------------------------------------------
# Main endpoint
# --------------------------------------------------------------------------

@router.get("/graph")
async def get_topology_graph(
    include_stopped: bool = Query(False, description="Include stopped VMs/LXC"),
    include_bridges: bool = Query(True, description="Include network bridges"),
    include_storage: bool = Query(True, description="Include storage pools"),
    include_bmc: bool = Query(True, description="Include iDRAC/BMC nodes"),
    include_pbs: bool = Query(True, description="Include PBS servers"),
    include_lxc: bool = Query(True, description="Include LXC containers"),
    include_sync: bool = Query(True, description="Include PBS sync job edges"),
    view_mode: str = Query("infrastructure", description="infrastructure | network | combined"),
    refresh: bool = Query(False, description="Bypass 60s cache"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return a full topology graph with nodes and edges.

    `view_mode`:
    - `infrastructure` (default): hosts → nodes → VMs / LXC / storage; bridges
      are shown as a single node per node. Storage + BMC + PBS + sync visible.
    - `network`: bridges are exploded into their `bridge_ports`, bonds into
      their `bond_slaves`, and physical NICs appear as leaves. Storage/BMC
      hidden so the network layer reads cleanly. Bridges with the same name
      across different PVE nodes get a virtual "L2 peer" edge so operators
      can see where the same VLAN bridge spans the cluster.
    - `combined`: both layers on one canvas (dense but complete).
    """
    vm = (view_mode or "infrastructure").lower()
    if vm not in ("infrastructure", "network", "combined"):
        vm = "infrastructure"
    # In network mode, force bridges on and storage/bmc off for readability.
    if vm == "network":
        include_bridges = True
        include_storage = False
        include_bmc = False
    cache_key = (
        f"graph|stopped={include_stopped}|br={include_bridges}|st={include_storage}"
        f"|bmc={include_bmc}|pbs={include_pbs}|lxc={include_lxc}|sync={include_sync}"
        f"|view={vm}"
    )
    if not refresh:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    errors: List[str] = []

    # --- Read BMC cache lazily (import here to avoid circular imports) ---
    try:
        from app.api.idrac import bmc_status_cache as _bmc_cache
    except Exception:
        _bmc_cache = {}

    # --- Proxmox hosts ---
    hosts = (
        db.query(ProxmoxHost)
        .filter(ProxmoxHost.is_active == True)  # noqa: E712
        .all()
    )

    # Fan out host subtree collection in parallel — each host is independent.
    if hosts:
        with ThreadPoolExecutor(max_workers=max(2, min(len(hosts), 8))) as pool:
            futs = {
                pool.submit(
                    _collect_host_subtree,
                    h,
                    include_stopped,
                    include_bridges,
                    include_storage,
                    include_lxc,
                ): h
                for h in hosts
            }
            for fut in as_completed(futs):
                h = futs[fut]
                try:
                    partial = fut.result()
                except Exception as e:
                    logger.warning("topology: host subtree failed for %s: %s", h.name, e)
                    errors.append(f"host {h.name}: {e}")
                    nodes.append(
                        {
                            "id": f"host:{h.id}",
                            "type": "pve_host",
                            "label": h.name or h.hostname,
                            "data": {"hostname": h.hostname, "error": str(e)},
                        }
                    )
                    continue
                nodes.extend(partial.get("nodes", []))
                edges.extend(partial.get("edges", []))
                if partial.get("error"):
                    # Annotate the host node with the error
                    for n in nodes:
                        if n["id"] == f"host:{h.id}":
                            n["data"]["error"] = partial["error"]
                            break

    # --- Per-node BMC for each PVE node ---
    # Link BMC to the specific node (not the host) when the iDRAC is configured
    # on a ProxmoxNode row.
    if include_bmc:
        pve_nodes = (
            db.query(ProxmoxNode)
            .filter(ProxmoxNode.idrac_hostname != None)  # noqa: E711
            .all()
        )
        for pn in pve_nodes:
            if not pn.idrac_hostname:
                continue
            bmc = _bmc_node_for(
                kind="node",
                obj_id=pn.id,
                idrac_hostname=pn.idrac_hostname,
                idrac_type=pn.idrac_type,
                owner_label=pn.node_name,
                bmc_status_cache=_bmc_cache,
            )
            if bmc:
                nodes.append(bmc)
                edges.append(
                    {
                        "from": f"node:{pn.host_id}:{pn.node_name}",
                        "to": bmc["id"],
                        "kind": "bmc",
                    }
                )

        # Host-level BMC (fallback when the iDRAC is configured on the host)
        for h in hosts:
            if not getattr(h, "idrac_hostname", None):
                continue
            bmc = _bmc_node_for(
                kind="pve",
                obj_id=h.id,
                idrac_hostname=h.idrac_hostname,
                idrac_type=h.idrac_type,
                owner_label=h.name or h.hostname,
                bmc_status_cache=_bmc_cache,
            )
            if bmc:
                nodes.append(bmc)
                edges.append(
                    {"from": f"host:{h.id}", "to": bmc["id"], "kind": "bmc"}
                )

    # --- PBS servers ---
    pbs_sync_pool: List[Dict[str, Any]] = []
    pbs_servers_by_host: Dict[str, PBSServer] = {}
    pbs_servers_by_name: Dict[str, PBSServer] = {}

    if include_pbs:
        pbs_servers = (
            db.query(PBSServer)
            .filter(PBSServer.is_active == True)  # noqa: E712
            .all()
        )
        if pbs_servers:
            for p in pbs_servers:
                pbs_servers_by_host[(p.hostname or "").lower()] = p
                pbs_servers_by_name[(p.name or "").lower()] = p

            with ThreadPoolExecutor(
                max_workers=max(2, min(len(pbs_servers), 8))
            ) as pool:
                futs = {pool.submit(_collect_pbs_subtree, p): p for p in pbs_servers}
                for fut in as_completed(futs):
                    p = futs[fut]
                    try:
                        partial = fut.result()
                    except Exception as e:
                        logger.warning("topology: pbs subtree failed for %s: %s", p.name, e)
                        errors.append(f"pbs {p.name}: {e}")
                        nodes.append(
                            {
                                "id": f"pbs:{p.id}",
                                "type": "pbs",
                                "label": p.name,
                                "data": {"hostname": p.hostname, "error": str(e)},
                            }
                        )
                        continue
                    nodes.extend(partial.get("nodes", []))
                    edges.extend(partial.get("edges", []))
                    pbs_sync_pool.extend(partial.get("sync_edges", []))

            # BMC for PBS servers
            if include_bmc:
                for p in pbs_servers:
                    if not getattr(p, "idrac_hostname", None):
                        continue
                    bmc = _bmc_node_for(
                        kind="pbs",
                        obj_id=p.id,
                        idrac_hostname=p.idrac_hostname,
                        idrac_type=p.idrac_type,
                        owner_label=p.name,
                        bmc_status_cache=_bmc_cache,
                    )
                    if bmc:
                        nodes.append(bmc)
                        edges.append(
                            {"from": f"pbs:{p.id}", "to": bmc["id"], "kind": "bmc"}
                        )

        # Resolve sync edges — match remote's hostname to another registered PBS.
        if include_sync and pbs_sync_pool:
            for se in pbs_sync_pool:
                target: Optional[PBSServer] = None
                rh = (se.get("remote_host") or "").split(":")[0].strip().lower()
                rn = (se.get("remote_name") or "").strip().lower()
                if rh and rh in pbs_servers_by_host:
                    target = pbs_servers_by_host[rh]
                elif rn and rn in pbs_servers_by_name:
                    target = pbs_servers_by_name[rn]
                if not target:
                    continue
                src_id = f"pbs:{se['source_pbs_id']}"
                dst_id = f"pbs:{target.id}"
                if src_id == dst_id:
                    continue
                edges.append(
                    {
                        "from": src_id,
                        "to": dst_id,
                        "kind": "sync",
                        "label": se.get("job_id") or "sync",
                        "data": {
                            "schedule": se.get("schedule"),
                            "last_run_state": se.get("last_run_state"),
                            "store": se.get("store"),
                            "remote_store": se.get("remote_store"),
                        },
                    }
                )

    # --- Standalone BMC entries ---
    if include_bmc:
        try:
            standalones = (
                db.query(StandaloneBMC).filter(StandaloneBMC.is_active == True).all()  # noqa: E712
            )
        except Exception:
            standalones = []
        for s in standalones:
            bmc = _bmc_node_for(
                kind="standalone",
                obj_id=s.id,
                idrac_hostname=s.idrac_hostname,
                idrac_type=s.idrac_type,
                owner_label=s.name,
                bmc_status_cache=_bmc_cache,
            )
            if bmc:
                nodes.append(bmc)
                # No parent edge — standalones are free-floating.

    # --- De-duplicate bridges / storage nodes that VMs referenced but the
    # Cross-node bridge peer edges — when the same-named bridge exists on
    # multiple PVE nodes (typical for cluster-wide vmbr0), draw a dashed peer
    # link so operators can see where an L2 domain spans.
    if vm in ("network", "combined"):
        by_bridge_name: Dict[str, List[str]] = {}
        for n in nodes:
            if n.get("type") != "bridge":
                continue
            name = (n.get("label") or "").strip()
            if not name:
                continue
            by_bridge_name.setdefault(name, []).append(n["id"])
        for name, ids in by_bridge_name.items():
            if len(ids) < 2:
                continue
            # Link each to the first as a hub rather than full mesh
            hub = ids[0]
            for other in ids[1:]:
                edges.append({"from": hub, "to": other, "kind": "l2-peer",
                              "label": name, "data": {"bridge": name}})

    node_ids = {n["id"] for n in nodes}
    cleaned_edges: List[Dict[str, Any]] = []
    for e in edges:
        if e.get("from") in node_ids and e.get("to") in node_ids:
            cleaned_edges.append(e)
        # else: silently drop dangling edge

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "nodes": nodes,
        "edges": cleaned_edges,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(cleaned_edges),
            "host_count": len(hosts),
        },
        "errors": errors,
    }

    _cache_set(cache_key, result, _TOPOLOGY_TTL_SECONDS)
    return result
