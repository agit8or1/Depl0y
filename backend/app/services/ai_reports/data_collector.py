"""Collects a full snapshot of infrastructure state for AI report generation.

Prefers existing cached data (bmc_status_cache, proxmox_nodes table) over
live polling to keep the generation step fast and non-intrusive.
"""
from __future__ import annotations

import json
import logging
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.database import (
    ProxmoxHost,
    ProxmoxNode,
    VirtualMachine,
    PBSServer,
    VMStatus,
    NodeMetricSnapshot,
)

logger = logging.getLogger(__name__)


_AGING_MODEL_HINTS = ("R720", "R620", "R420", "R520", "R710", "R610", "R410")


def _utc_now() -> datetime:
    return datetime.utcnow()


def _age_seconds(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    return int((_utc_now() - dt).total_seconds())


def _safe_decrypt(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        from app.core.security import decrypt_data
        return decrypt_data(value)
    except Exception:
        return value  # fall through — legacy plaintext


def _collect_node_history(db: Session, node_id: int, window_hours: int = 24) -> List[Dict[str, Any]]:
    cutoff = _utc_now() - timedelta(hours=window_hours)
    rows = (
        db.query(NodeMetricSnapshot)
        .filter(NodeMetricSnapshot.node_id == node_id, NodeMetricSnapshot.captured_at >= cutoff)
        .order_by(NodeMetricSnapshot.captured_at.desc())
        .limit(500)
        .all()
    )
    return [
        {
            "captured_at": r.captured_at.isoformat() if r.captured_at else None,
            "cpu_pct": r.cpu_pct,
            "memory_pct": r.memory_pct,
            "disk_pct": r.disk_pct,
            "vm_count": r.vm_count,
            "lxc_count": r.lxc_count,
        }
        for r in rows
    ]


def _bmc_status_for_node(bmc_cache: Dict[str, Any], host_id: int, node_id: int) -> Dict[str, Any]:
    """Find BMC status entry covering this node, preferring pve_node over pve."""
    candidates = []
    node_key = f"pve_node:{node_id}"
    if node_key in bmc_cache:
        candidates.append(bmc_cache[node_key])
    host_key = f"pve:{host_id}"
    if host_key in bmc_cache:
        candidates.append(bmc_cache[host_key])
    if not candidates:
        return {}
    # Merge — prefer first (pve_node) but fill gaps from pve
    merged: Dict[str, Any] = {}
    for c in reversed(candidates):
        merged.update({k: v for k, v in c.items() if v is not None})
    return merged


def collect_snapshot(db: Session, scope_type: str = "global", scope_ref: Optional[str] = None) -> Dict[str, Any]:
    """Build an infrastructure snapshot dict.

    scope_type ∈ {"global", "cluster", "node"}; scope_ref is host_id (str) for
    cluster or node_name for node.
    """
    from app.api.idrac import bmc_status_cache as bmc_cache  # local import to avoid cycles

    now = _utc_now()
    snapshot: Dict[str, Any] = {
        "collected_at": now.isoformat(),
        "scope": {"type": scope_type, "ref": scope_ref},
        "clusters": [],
        "hosts": [],
        "nodes": [],
        "vms_summary": {},
        "pbs_servers": [],
        "storage": [],
        "aging_hardware": [],
        "data_freshness_seconds": 0,
    }

    host_query = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True)
    if scope_type == "cluster" and scope_ref:
        try:
            host_query = host_query.filter(ProxmoxHost.id == int(scope_ref))
        except (TypeError, ValueError):
            pass
    hosts = host_query.all()

    freshness_candidates: List[int] = []

    for host in hosts:
        host_info = {
            "id": host.id,
            "name": host.name,
            "hostname": host.hostname,
            "last_poll": host.last_poll.isoformat() if host.last_poll else None,
            "last_poll_age_s": _age_seconds(host.last_poll),
            "node_count": 0,
            "total_vm_count": 0,
            "total_lxc_count": 0,
        }
        if host.last_poll:
            freshness_candidates.append(_age_seconds(host.last_poll) or 0)

        nodes_q = db.query(ProxmoxNode).filter(ProxmoxNode.host_id == host.id)
        if scope_type == "node" and scope_ref:
            nodes_q = nodes_q.filter(ProxmoxNode.node_name == scope_ref)
        nodes = nodes_q.all()
        host_info["node_count"] = len(nodes)

        for node in nodes:
            mem_pct = None
            if node.memory_total and node.memory_used is not None and node.memory_total > 0:
                mem_pct = round((node.memory_used / node.memory_total) * 100, 1)
            disk_pct = None
            if node.disk_total and node.disk_used is not None and node.disk_total > 0:
                disk_pct = round((node.disk_used / node.disk_total) * 100, 1)

            bmc = _bmc_status_for_node(bmc_cache, host.id, node.id)
            model = bmc.get("model") or ""
            aging = any(h in model.upper() for h in _AGING_MODEL_HINTS)

            history = _collect_node_history(db, node.id, window_hours=24)
            if history:
                cpu_hist = [h["cpu_pct"] for h in history if h.get("cpu_pct") is not None]
                mem_hist = [h["memory_pct"] for h in history if h.get("memory_pct") is not None]
                avg_cpu = round(statistics.fmean(cpu_hist), 1) if cpu_hist else node.cpu_usage
                avg_mem = round(statistics.fmean(mem_hist), 1) if mem_hist else mem_pct
                peak_cpu = round(max(cpu_hist), 1) if cpu_hist else node.cpu_usage
            else:
                avg_cpu = node.cpu_usage
                avg_mem = mem_pct
                peak_cpu = node.cpu_usage

            node_info = {
                "id": node.id,
                "host_id": host.id,
                "host_name": host.name,
                "node_name": node.node_name,
                "status": node.status,
                "cpu_cores": node.cpu_cores,
                "cpu_usage": node.cpu_usage,
                "cpu_avg_24h": avg_cpu,
                "cpu_peak_24h": peak_cpu,
                "memory_total_bytes": node.memory_total,
                "memory_used_bytes": node.memory_used,
                "memory_pct": mem_pct,
                "memory_avg_24h": avg_mem,
                "disk_total_bytes": node.disk_total,
                "disk_used_bytes": node.disk_used,
                "disk_pct": disk_pct,
                "uptime_seconds": node.uptime,
                "vm_count": node.vm_count or 0,
                "lxc_count": node.lxc_count or 0,
                "last_updated": node.last_updated.isoformat() if node.last_updated else None,
                "last_updated_age_s": _age_seconds(node.last_updated),
                "history_samples": len(history),
                "bmc": {
                    "model": bmc.get("model"),
                    "serial_number": bmc.get("serial_number"),
                    "power_state": bmc.get("power_state"),
                    "health": bmc.get("health"),
                    "consumed_watts": bmc.get("consumed_watts"),
                    "max_temp_c": bmc.get("max_temp_c"),
                    "idrac_fw_version": bmc.get("idrac_fw_version"),
                    "bios_version": bmc.get("bios_version"),
                    "error": bmc.get("error"),
                },
                "aging_hardware": aging,
            }
            if node.last_updated:
                freshness_candidates.append(_age_seconds(node.last_updated) or 0)
            if aging:
                snapshot["aging_hardware"].append({
                    "node_name": node.node_name,
                    "host_name": host.name,
                    "model": model,
                })
            snapshot["nodes"].append(node_info)
            host_info["total_vm_count"] += node.vm_count or 0
            host_info["total_lxc_count"] += node.lxc_count or 0

        snapshot["hosts"].append(host_info)

    # VMs summary (by host)
    vm_rows = db.query(VirtualMachine).all()
    by_status: Dict[str, int] = {}
    by_host: Dict[int, int] = {}
    for vm in vm_rows:
        status = vm.status.value if hasattr(vm.status, "value") else str(vm.status)
        by_status[status] = by_status.get(status, 0) + 1
        by_host[vm.proxmox_host_id] = by_host.get(vm.proxmox_host_id, 0) + 1
    snapshot["vms_summary"] = {
        "total": len(vm_rows),
        "by_status": by_status,
        "by_host_id": by_host,
    }

    # PBS servers
    for pbs in db.query(PBSServer).filter(PBSServer.is_active == True).all():
        snapshot["pbs_servers"].append({
            "id": pbs.id,
            "name": pbs.name,
            "hostname": pbs.hostname,
        })

    snapshot["data_freshness_seconds"] = max(freshness_candidates) if freshness_candidates else 0
    return snapshot
