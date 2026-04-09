"""
Analysis engine — runs periodically to generate optimization recommendations.
Distinct from the alert engine: alerts fire on threshold breaches NOW;
analysis looks at patterns, trends, and best practices to suggest improvements.
"""
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# How often to run (seconds)
ANALYSIS_INTERVAL = 600  # 10 minutes
INITIAL_DELAY = 60       # wait for app to fully start


class AnalysisEngine:
    """Background engine that evaluates infrastructure and emits recommendations."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="analysis-engine")
        self._thread.start()
        logger.info("Analysis engine started")

    def stop(self):
        self._running = False

    def _run(self):
        time.sleep(INITIAL_DELAY)
        while self._running:
            try:
                self.run_now()
            except Exception as exc:
                logger.exception(f"Analysis engine error: {exc}")
            time.sleep(ANALYSIS_INTERVAL)

    def run_now(self):
        """Run a full analysis cycle synchronously."""
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            recs: List[Dict] = []
            recs.extend(self._check_node_metrics(db))
            recs.extend(self._check_vms(db))
            recs.extend(self._check_storage(db))
            recs.extend(self._check_cluster_balance(db))
            self._upsert_recommendations(db, recs)
            logger.info(f"Analysis cycle complete — {len(recs)} recommendations generated")
        except Exception as exc:
            logger.exception(f"Analysis run_now error: {exc}")
        finally:
            db.close()

    # ── Node checks (uses DB snapshot — no live API call needed) ──────────────

    def _check_node_metrics(self, db) -> List[Dict]:
        recs = []
        try:
            from app.models.database import ProxmoxNode, ProxmoxHost
            nodes = db.query(ProxmoxNode).all()
            for node in nodes:
                host = db.query(ProxmoxHost).filter(ProxmoxHost.id == node.host_id).first()
                host_name = host.name if host else f"host:{node.host_id}"

                # Skip stale nodes (not updated in >15 min)
                if node.last_updated and (datetime.utcnow() - node.last_updated) > timedelta(minutes=15):
                    continue

                cpu_pct = node.cpu_usage or 0
                mem_pct = round(node.memory_used / node.memory_total * 100, 1) if node.memory_total else 0

                # High load (softer than alert threshold)
                if cpu_pct >= 75:
                    severity = "critical" if cpu_pct >= 90 else "warning"
                    recs.append({
                        "rule_type": "node_high_cpu",
                        "category": "performance",
                        "severity": severity,
                        "host_id": node.host_id,
                        "node": node.name,
                        "title": f"Node {node.name} CPU at {cpu_pct}%",
                        "detail": f"Node {node.name} on {host_name} is running at {cpu_pct}% CPU utilization.",
                        "suggestion": "Consider migrating some VMs to less-loaded nodes, or reviewing which VMs are consuming the most CPU.",
                        "metric_value": float(cpu_pct),
                        "metric_unit": "%",
                        "threshold": 75.0,
                    })

                if mem_pct >= 80:
                    severity = "critical" if mem_pct >= 93 else "warning"
                    recs.append({
                        "rule_type": "node_high_memory",
                        "category": "performance",
                        "severity": severity,
                        "host_id": node.host_id,
                        "node": node.name,
                        "title": f"Node {node.name} memory at {mem_pct}%",
                        "detail": f"Node {node.name} on {host_name} has {mem_pct}% of RAM in use ({_fmt_bytes(node.memory_used)} / {_fmt_bytes(node.memory_total)}).",
                        "suggestion": "Migrate memory-heavy VMs to other nodes, reduce VM RAM allocations, or add physical RAM to the host.",
                        "metric_value": float(mem_pct),
                        "metric_unit": "%",
                        "threshold": 80.0,
                    })

                # Low utilization — consolidation opportunity
                if cpu_pct < 5 and mem_pct < 20:
                    recs.append({
                        "rule_type": "node_underutilized",
                        "category": "performance",
                        "severity": "info",
                        "host_id": node.host_id,
                        "node": node.name,
                        "title": f"Node {node.name} is underutilized",
                        "detail": f"Node {node.name} is only using {cpu_pct}% CPU and {mem_pct}% RAM.",
                        "suggestion": "Consider consolidating VMs from this node onto others and powering it down to save energy.",
                        "metric_value": float(cpu_pct),
                        "metric_unit": "%",
                        "threshold": 5.0,
                    })
        except Exception as exc:
            logger.error(f"_check_node_metrics error: {exc}")
        return recs

    # ── VM checks (calls live Proxmox API) ────────────────────────────────────

    def _check_vms(self, db) -> List[Dict]:
        recs = []
        try:
            from app.models.database import ProxmoxHost
            from app.services.proxmox import ProxmoxService

            hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()
            for host in hosts:
                try:
                    service = ProxmoxService(host)
                    nodes = service.get_nodes()
                    for node_data in nodes:
                        node_name = node_data.get("node")
                        if not node_name:
                            continue
                        try:
                            vms = service.proxmox.nodes(node_name).qemu.get()
                            for vm in vms:
                                vm_recs = self._analyze_vm(host, node_name, vm, service)
                                recs.extend(vm_recs)
                        except Exception as e:
                            logger.debug(f"VM check skip {node_name}: {e}")
                except Exception as e:
                    logger.debug(f"VM check skip host {host.name}: {e}")
        except Exception as exc:
            logger.error(f"_check_vms error: {exc}")
        return recs

    def _analyze_vm(self, host, node_name: str, vm: Dict, service) -> List[Dict]:
        recs = []
        vmid = vm.get("vmid")
        vm_name = vm.get("name", f"VM {vmid}")
        status = vm.get("status", "")
        maxcpu = vm.get("cpus") or vm.get("maxcpu") or 0
        maxmem = vm.get("maxmem") or 0
        mem = vm.get("mem") or 0
        cpu_frac = vm.get("cpu") or 0.0   # fraction of allocated (0.0 – 1.0+)
        uptime = vm.get("uptime") or 0

        # VM stopped (not a template)
        template = vm.get("template", 0)
        if status == "stopped" and not template:
            recs.append({
                "rule_type": "vm_stopped",
                "category": "reliability",
                "severity": "info",
                "host_id": host.id,
                "node": node_name,
                "vmid": vmid,
                "vm_name": vm_name,
                "title": f"VM {vm_name} is powered off",
                "detail": f"VM {vm_name} (ID {vmid}) on {node_name} is not running.",
                "suggestion": "Review whether this VM is still needed. If unused, consider deleting it to free disk space.",
                "metric_value": None,
                "metric_unit": None,
                "threshold": None,
            })

        if status != "running":
            return recs

        # Oversized CPU: ≥4 vCPUs and using less than 3% of what's allocated
        if maxcpu >= 4 and cpu_frac < 0.03:
            actual_pct = round(cpu_frac * 100, 1)
            recs.append({
                "rule_type": "vm_oversized_cpu",
                "category": "performance",
                "severity": "info",
                "host_id": host.id,
                "node": node_name,
                "vmid": vmid,
                "vm_name": vm_name,
                "title": f"VM {vm_name} may have too many vCPUs",
                "detail": f"VM {vm_name} has {maxcpu} vCPUs allocated but is only using {actual_pct}% of that right now.",
                "suggestion": f"Consider reducing vCPUs to 2 or review workload patterns. Over-allocating vCPUs increases scheduler pressure on the node.",
                "metric_value": actual_pct,
                "metric_unit": "%",
                "threshold": 3.0,
            })

        # Oversized memory: >2 GB allocated and using less than 15%
        if maxmem > 2 * 1024 ** 3 and mem > 0:
            mem_pct = mem / maxmem * 100
            if mem_pct < 15:
                recs.append({
                    "rule_type": "vm_oversized_memory",
                    "category": "performance",
                    "severity": "info",
                    "host_id": host.id,
                    "node": node_name,
                    "vmid": vmid,
                    "vm_name": vm_name,
                    "title": f"VM {vm_name} may have excess RAM",
                    "detail": f"VM {vm_name} has {_fmt_bytes(maxmem)} allocated but is only using {_fmt_bytes(mem)} ({mem_pct:.0f}%).",
                    "suggestion": "Consider reducing the memory allocation to free RAM for other VMs on this node.",
                    "metric_value": round(mem_pct, 1),
                    "metric_unit": "%",
                    "threshold": 15.0,
                })

        # No recent backup — check task log
        try:
            tasks = service.proxmox.nodes(node_name).tasks.get(
                vmid=vmid, typefilter="vzdump", limit=5
            )
            recent_backup = False
            cutoff = datetime.utcnow() - timedelta(days=7)
            for task in tasks:
                started = task.get("starttime") or 0
                task_time = datetime.utcfromtimestamp(started) if started else None
                if task_time and task_time > cutoff and task.get("status") == "OK":
                    recent_backup = True
                    break
            if not recent_backup and not template:
                recs.append({
                    "rule_type": "vm_no_backup",
                    "category": "reliability",
                    "severity": "warning",
                    "host_id": host.id,
                    "node": node_name,
                    "vmid": vmid,
                    "vm_name": vm_name,
                    "title": f"VM {vm_name} has no backup in 7 days",
                    "detail": f"No successful vzdump backup found for VM {vm_name} (ID {vmid}) in the last 7 days.",
                    "suggestion": "Add this VM to a backup job in Proxmox datacenter → backup, or configure Depl0y backup schedules.",
                    "metric_value": None,
                    "metric_unit": None,
                    "threshold": None,
                })
        except Exception:
            pass  # task query optional

        # Old snapshots — check if any snapshot is >14 days old
        try:
            snapshots = service.proxmox.nodes(node_name).qemu(vmid).snapshot.get()
            cutoff = (datetime.utcnow() - timedelta(days=14)).timestamp()
            old_snaps = [
                s for s in snapshots
                if s.get("name") != "current" and (s.get("snaptime") or 0) < cutoff
            ]
            if old_snaps:
                oldest_ts = min(s.get("snaptime", 0) for s in old_snaps)
                oldest_dt = datetime.utcfromtimestamp(oldest_ts)
                age_days = (datetime.utcnow() - oldest_dt).days
                recs.append({
                    "rule_type": "vm_old_snapshot",
                    "category": "storage",
                    "severity": "info",
                    "host_id": host.id,
                    "node": node_name,
                    "vmid": vmid,
                    "vm_name": vm_name,
                    "resource_label": f"{len(old_snaps)} snapshot(s)",
                    "title": f"VM {vm_name} has old snapshots",
                    "detail": f"VM {vm_name} has {len(old_snaps)} snapshot(s) older than 14 days (oldest is {age_days} days old). Old snapshots consume disk space.",
                    "suggestion": "Delete snapshots that are no longer needed to reclaim storage space.",
                    "metric_value": float(age_days),
                    "metric_unit": "days",
                    "threshold": 14.0,
                })
        except Exception:
            pass  # snapshot query optional

        return recs

    # ── Storage checks ────────────────────────────────────────────────────────

    def _check_storage(self, db) -> List[Dict]:
        recs = []
        try:
            from app.models.database import ProxmoxHost
            from app.services.proxmox import ProxmoxService

            hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()
            for host in hosts:
                try:
                    service = ProxmoxService(host)
                    nodes = service.get_nodes()
                    seen_storage = set()  # avoid duplicating shared storage
                    for node_data in nodes:
                        node_name = node_data.get("node")
                        if not node_name:
                            continue
                        try:
                            storages = service.get_storage_list(node_name)
                            for st in storages:
                                storage_name = st.get("storage", "")
                                key = f"{host.id}:{storage_name}"
                                if key in seen_storage:
                                    continue
                                total = st.get("total") or 0
                                used = st.get("used") or 0
                                if total == 0:
                                    continue
                                used_pct = used / total * 100
                                if used_pct >= 75:
                                    seen_storage.add(key)
                                    severity = "critical" if used_pct >= 90 else ("warning" if used_pct >= 85 else "info")
                                    recs.append({
                                        "rule_type": "storage_high_usage",
                                        "category": "storage",
                                        "severity": severity,
                                        "host_id": host.id,
                                        "node": node_name,
                                        "resource_label": storage_name,
                                        "title": f"Storage '{storage_name}' is {used_pct:.0f}% full",
                                        "detail": f"Storage pool '{storage_name}' on {host.name}/{node_name} has {_fmt_bytes(used)} used of {_fmt_bytes(total)} total.",
                                        "suggestion": "Delete unused VMs, old snapshots, or ISO images. Consider expanding the storage pool.",
                                        "metric_value": round(used_pct, 1),
                                        "metric_unit": "%",
                                        "threshold": 75.0,
                                    })
                        except Exception as e:
                            logger.debug(f"Storage check skip {node_name}: {e}")
                except Exception as e:
                    logger.debug(f"Storage check skip host {host.name}: {e}")
        except Exception as exc:
            logger.error(f"_check_storage error: {exc}")
        return recs

    # ── Cluster balance check ─────────────────────────────────────────────────

    def _check_cluster_balance(self, db) -> List[Dict]:
        recs = []
        try:
            from app.models.database import ProxmoxNode, ProxmoxHost
            from sqlalchemy import func

            # Group nodes by host and check imbalance within each cluster
            hosts_ids = db.query(ProxmoxNode.host_id).distinct().all()
            for (host_id,) in hosts_ids:
                nodes = db.query(ProxmoxNode).filter(
                    ProxmoxNode.host_id == host_id,
                    ProxmoxNode.status == "online",
                ).all()
                if len(nodes) < 2:
                    continue

                cpu_vals = [n.cpu_usage or 0 for n in nodes]
                max_cpu = max(cpu_vals)
                min_cpu = min(cpu_vals)

                # Significant imbalance: highest node is 3x more loaded than lowest
                # and the highest is actually doing meaningful work (>30%)
                if max_cpu >= 30 and max_cpu >= min_cpu * 3:
                    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
                    host_name = host.name if host else f"host:{host_id}"
                    most_loaded = nodes[cpu_vals.index(max_cpu)]
                    least_loaded = nodes[cpu_vals.index(min_cpu)]
                    recs.append({
                        "rule_type": "cluster_imbalanced",
                        "category": "performance",
                        "severity": "info",
                        "host_id": host_id,
                        "node": most_loaded.name,
                        "title": f"Cluster {host_name} has uneven load distribution",
                        "detail": (
                            f"Node {most_loaded.name} is at {max_cpu}% CPU while "
                            f"{least_loaded.name} is at {min_cpu}% CPU."
                        ),
                        "suggestion": f"Migrate some VMs from {most_loaded.name} to {least_loaded.name} to balance the load.",
                        "metric_value": float(max_cpu),
                        "metric_unit": "%",
                        "threshold": None,
                    })
        except Exception as exc:
            logger.error(f"_check_cluster_balance error: {exc}")
        return recs

    # ── DB upsert ─────────────────────────────────────────────────────────────

    def _upsert_recommendations(self, db, recs: List[Dict]):
        """
        Replace non-dismissed recommendations with fresh results.
        Dismissed recommendations are preserved.
        """
        try:
            from app.models.analysis_models import Recommendation

            # Delete all non-dismissed recommendations (will be re-generated)
            db.query(Recommendation).filter(Recommendation.dismissed == False).delete()

            for r in recs:
                rec = Recommendation(
                    host_id=r.get("host_id"),
                    node=r.get("node"),
                    vmid=r.get("vmid"),
                    vm_name=r.get("vm_name"),
                    resource_label=r.get("resource_label"),
                    category=r["category"],
                    rule_type=r["rule_type"],
                    severity=r["severity"],
                    title=r["title"],
                    detail=r.get("detail"),
                    suggestion=r.get("suggestion"),
                    metric_value=r.get("metric_value"),
                    metric_unit=r.get("metric_unit"),
                    threshold=r.get("threshold"),
                    dismissed=False,
                    created_at=datetime.utcnow(),
                )
                db.add(rec)

            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error(f"_upsert_recommendations error: {exc}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_bytes(b: int) -> str:
    if not b:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


# Singleton instance
analysis_engine = AnalysisEngine()
