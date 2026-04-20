"""Deterministic rules engine over a snapshot from data_collector.

Produces Finding records independent of any AI provider.
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"


@dataclass
class Finding:
    severity: str
    category: str            # performance | reliability | capacity | cost | hardware | redundancy | backup
    rule_type: str
    title: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    affected_resources: List[str] = field(default_factory=list)
    recommendation: str = ""
    estimated_impact: str = ""
    confidence: str = "medium"   # low | medium | high
    auto_safe: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── helpers ──────────────────────────────────────────────────────────────────

def _pct(node_field_avg: Optional[float], node_field_now: Optional[float]) -> Optional[float]:
    if node_field_avg is not None:
        return float(node_field_avg)
    if node_field_now is not None:
        return float(node_field_now)
    return None


def _cluster_size(snapshot: Dict[str, Any]) -> int:
    return len(snapshot.get("nodes", []))


# ── individual rules ─────────────────────────────────────────────────────────

def _rule_cpu_hot(node: Dict[str, Any]) -> Optional[Finding]:
    cpu = _pct(node.get("cpu_avg_24h"), node.get("cpu_usage"))
    if cpu is None or cpu < 80:
        return None
    sev = SEVERITY_CRITICAL if cpu >= 90 else SEVERITY_WARNING
    return Finding(
        severity=sev,
        category="performance",
        rule_type="node_cpu_high",
        title=f"Node {node['node_name']} CPU at {cpu:.0f}% (sustained)",
        evidence={"cpu_avg_24h": node.get("cpu_avg_24h"), "cpu_usage": node.get("cpu_usage"), "cores": node.get("cpu_cores")},
        affected_resources=[node["node_name"]],
        recommendation="Rebalance workloads, add a node, or downsize noisy VMs. Investigate runaway guest processes.",
        estimated_impact="Increased latency and risk of thermal/throttling events.",
        confidence="high" if node.get("history_samples", 0) >= 5 else "medium",
    )


def _rule_mem_hot(node: Dict[str, Any]) -> Optional[Finding]:
    mem = _pct(node.get("memory_avg_24h"), node.get("memory_pct"))
    if mem is None or mem < 85:
        return None
    sev = SEVERITY_CRITICAL if mem >= 95 else SEVERITY_WARNING
    return Finding(
        severity=sev,
        category="performance",
        rule_type="node_memory_high",
        title=f"Node {node['node_name']} memory at {mem:.0f}%",
        evidence={"memory_pct": node.get("memory_pct"), "memory_avg_24h": node.get("memory_avg_24h")},
        affected_resources=[node["node_name"]],
        recommendation="Add RAM, migrate memory-heavy VMs, or enable/increase ballooning where appropriate.",
        estimated_impact="Swap pressure and OOM risk for guests on this host.",
        confidence="high",
    )


def _rule_disk_full(node: Dict[str, Any]) -> Optional[Finding]:
    d = node.get("disk_pct")
    if d is None or d < 80:
        return None
    sev = SEVERITY_CRITICAL if d >= 90 else SEVERITY_WARNING
    return Finding(
        severity=sev,
        category="capacity",
        rule_type="node_disk_high",
        title=f"Node {node['node_name']} root/local storage {d:.0f}% full",
        evidence={"disk_pct": d, "disk_used_bytes": node.get("disk_used_bytes"), "disk_total_bytes": node.get("disk_total_bytes")},
        affected_resources=[node["node_name"]],
        recommendation="Prune old ISOs/backups, expand storage, or migrate VMs to another datastore.",
        estimated_impact="Out-of-space risk will stop running VMs from writing.",
        confidence="high",
    )


def _rule_no_ha(snapshot: Dict[str, Any]) -> Optional[Finding]:
    nodes = snapshot.get("nodes", [])
    if len(nodes) <= 1:
        return None
    # Heuristic: we don't have HA state in the snapshot, but we do have cluster grouping
    # by host. If the cluster has >1 node but vms are concentrated on one node only,
    # flag absence of HA redundancy. True HA state would require pvesh /cluster/ha.
    vm_host_ids = [n.get("host_id") for n in nodes]
    unique_hosts = set(vm_host_ids)
    if len(unique_hosts) <= 1:
        return None  # all one cluster/host — no cross-host redundancy question
    return Finding(
        severity=SEVERITY_WARNING,
        category="redundancy",
        rule_type="ha_not_configured",
        title="Multi-node cluster has no detected HA group coverage",
        evidence={"node_count": len(nodes)},
        affected_resources=[n["node_name"] for n in nodes],
        recommendation="Create an HA group covering all nodes and mark critical VMs as managed.",
        estimated_impact="A single-host failure will leave VMs down until manual intervention.",
        confidence="low",
    )


def _rule_backup(snapshot: Dict[str, Any]) -> Optional[Finding]:
    if snapshot.get("pbs_servers"):
        return None
    return Finding(
        severity=SEVERITY_WARNING,
        category="backup",
        rule_type="no_pbs_configured",
        title="No Proxmox Backup Server configured",
        evidence={},
        affected_resources=["cluster"],
        recommendation="Attach a PBS server and schedule VM-level backups on a retention plan (e.g. 7 daily / 4 weekly / 3 monthly).",
        estimated_impact="A node loss risks data loss — there is no off-host backup target.",
        confidence="medium",
    )


def _rule_uneven_distribution(snapshot: Dict[str, Any]) -> Optional[Finding]:
    nodes = snapshot.get("nodes", [])
    if len(nodes) < 2:
        return None
    counts = [(n.get("vm_count") or 0) + (n.get("lxc_count") or 0) for n in nodes]
    if sum(counts) == 0:
        return None
    mean = statistics.fmean(counts)
    if mean <= 0:
        return None
    try:
        stdev = statistics.pstdev(counts)
    except statistics.StatisticsError:
        return None
    if stdev / mean < 0.5:
        return None
    maxi = max(counts)
    max_node = nodes[counts.index(maxi)]["node_name"]
    return Finding(
        severity=SEVERITY_WARNING,
        category="performance",
        rule_type="uneven_distribution",
        title="Uneven workload distribution across nodes",
        evidence={"counts": counts, "stdev": round(stdev, 2), "mean": round(mean, 2), "hotspot": max_node},
        affected_resources=[n["node_name"] for n in nodes],
        recommendation=f"Migrate a subset of guests off {max_node} to balance the cluster.",
        estimated_impact="Hot node is bottlenecking while others are idle.",
        confidence="medium",
    )


def _rule_underutilized_node(node: Dict[str, Any]) -> Optional[Finding]:
    cpu = _pct(node.get("cpu_avg_24h"), node.get("cpu_usage"))
    mem = _pct(node.get("memory_avg_24h"), node.get("memory_pct"))
    if cpu is None or mem is None:
        return None
    if cpu >= 15 or mem >= 30:
        return None
    return Finding(
        severity=SEVERITY_INFO,
        category="cost",
        rule_type="node_underutilized",
        title=f"Node {node['node_name']} is underutilized ({cpu:.0f}% CPU / {mem:.0f}% mem avg)",
        evidence={"cpu_avg": cpu, "memory_avg": mem},
        affected_resources=[node["node_name"]],
        recommendation="Consolidate guests onto fewer nodes and power down or repurpose this hardware.",
        estimated_impact="Idle hardware wastes electricity and cooling budget.",
        confidence="medium",
    )


def _rule_low_headroom(snapshot: Dict[str, Any]) -> Optional[Finding]:
    nodes = snapshot.get("nodes", [])
    if len(nodes) < 2:
        return None
    cpu_vals = []
    cores_vals = []
    for n in nodes:
        c = _pct(n.get("cpu_avg_24h"), n.get("cpu_usage"))
        cores = n.get("cpu_cores") or 0
        if c is None or cores <= 0:
            continue
        cpu_vals.append(c)
        cores_vals.append(cores)
    if len(cpu_vals) < 2:
        return None
    busiest = max(zip(cpu_vals, cores_vals))
    total_cores = sum(cores_vals)
    total_used = sum(c * cr / 100.0 for c, cr in zip(cpu_vals, cores_vals))
    remaining_cores = total_cores - busiest[1]
    if remaining_cores <= 0:
        return None
    projected = total_used / remaining_cores * 100.0
    if projected < 80:
        return None
    return Finding(
        severity=SEVERITY_WARNING,
        category="capacity",
        rule_type="low_n1_headroom",
        title="Cluster lacks N+1 headroom",
        evidence={"projected_cpu_if_busiest_down_pct": round(projected, 1)},
        affected_resources=[n["node_name"] for n in nodes],
        recommendation="Add capacity or migrate workloads — a single-node loss would push the cluster past 80% CPU.",
        estimated_impact="Failover would cascade into overload and performance collapse.",
        confidence="medium",
    )


def _rule_oversize_vm(snapshot: Dict[str, Any]) -> Optional[Finding]:
    nodes = snapshot.get("nodes", [])
    # Without per-VM utilization history we degrade: flag clusters where the
    # avg node CPU <10% but aggregate core count is high (>=24). That's a
    # strong signal of oversized VMs overall.
    if not nodes:
        return None
    total_cores = sum((n.get("cpu_cores") or 0) for n in nodes)
    cpu_vals = [_pct(n.get("cpu_avg_24h"), n.get("cpu_usage")) for n in nodes]
    cpu_vals = [v for v in cpu_vals if v is not None]
    if not cpu_vals or total_cores < 24:
        return None
    avg = statistics.fmean(cpu_vals)
    if avg >= 10:
        return None
    return Finding(
        severity=SEVERITY_INFO,
        category="cost",
        rule_type="likely_oversized_vms",
        title="Likely oversized VM allocations across the cluster",
        evidence={"total_cores": total_cores, "avg_cluster_cpu_pct": round(avg, 1)},
        affected_resources=["cluster"],
        recommendation="Audit VMs with >4 vCPUs that show <10% sustained CPU usage and rightsize.",
        estimated_impact="Smaller VMs increase density and reduce license/cooling overhead.",
        confidence="low",
    )


def _rule_bmc_health(snapshot: Dict[str, Any]) -> List[Finding]:
    out: List[Finding] = []
    for n in snapshot.get("nodes", []):
        bmc = n.get("bmc") or {}
        if bmc.get("error"):
            out.append(Finding(
                severity=SEVERITY_WARNING,
                category="reliability",
                rule_type="bmc_unreachable",
                title=f"BMC unreachable for node {n['node_name']}",
                evidence={"error": bmc.get("error")},
                affected_resources=[n["node_name"]],
                recommendation="Verify iDRAC/iLO network and credentials; restore out-of-band visibility.",
                estimated_impact="Hardware events and thermal alarms will not be detected.",
                confidence="high",
            ))
            continue
        health = (bmc.get("health") or "").lower()
        if health in ("warning", "critical"):
            out.append(Finding(
                severity=SEVERITY_CRITICAL if health == "critical" else SEVERITY_WARNING,
                category="reliability",
                rule_type="bmc_health_degraded",
                title=f"BMC reports {health} on {n['node_name']}",
                evidence={"health": bmc.get("health"), "model": bmc.get("model")},
                affected_resources=[n["node_name"]],
                recommendation="Inspect hardware event log (iDRAC/iLO) and replace failing component.",
                estimated_impact="Node may fail without warning.",
                confidence="high",
            ))
    return out


def _rule_aging_hardware(snapshot: Dict[str, Any]) -> List[Finding]:
    out: List[Finding] = []
    for aging in snapshot.get("aging_hardware", []):
        out.append(Finding(
            severity=SEVERITY_INFO,
            category="hardware",
            rule_type="aging_hardware",
            title=f"Aging hardware: {aging.get('model') or 'unknown'} on {aging['node_name']}",
            evidence={"model": aging.get("model")},
            affected_resources=[aging["node_name"]],
            recommendation="Plan refresh to current-gen Dell/HPE (PowerEdge R750/R760 or HPE Gen10+) for power efficiency, NVMe, DDR5 where applicable.",
            estimated_impact="Older gear has higher watts/VM ratio and limited remaining vendor support.",
            confidence="medium",
        ))
    return out


def _rule_cost_low_util(snapshot: Dict[str, Any]) -> List[Finding]:
    """Node with high idle watts profile (not in snapshot — passed via estimate)
    combined with low utilization flags as cost inefficiency. Checked after
    power_cost.estimate via a post-pass (see report_service)."""
    return []


# ── public ───────────────────────────────────────────────────────────────────

def analyze(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run all rules and return a list of finding dicts."""
    findings: List[Finding] = []

    nodes = snapshot.get("nodes", [])
    for node in nodes:
        for r in (_rule_cpu_hot, _rule_mem_hot, _rule_disk_full, _rule_underutilized_node):
            f = r(node)
            if f:
                findings.append(f)

    for cluster_rule in (_rule_no_ha, _rule_backup, _rule_uneven_distribution, _rule_low_headroom, _rule_oversize_vm):
        f = cluster_rule(snapshot)
        if f:
            findings.append(f)

    findings.extend(_rule_bmc_health(snapshot))
    findings.extend(_rule_aging_hardware(snapshot))

    return [f.to_dict() for f in findings]
