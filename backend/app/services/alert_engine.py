"""
Alert rules engine — runs periodically to check conditions and fire alerts
"""
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class AlertEngine:
    """Background engine that evaluates alert rules and fires alert events."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._running = False
        # Maps rule_key → datetime of last fired event (cooldown tracking)
        self._alert_states: Dict[str, datetime] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        """Start background alert checking thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="alert-engine")
        self._thread.start()
        logger.info("Alert engine started")

    def stop(self):
        """Signal the background thread to stop."""
        self._running = False

    def _run(self):
        """Poll every 60 s and evaluate all alert rules."""
        # Initial delay so the app finishes starting up before the first check
        time.sleep(30)
        while self._running:
            try:
                self._evaluate_all()
            except Exception as exc:
                logger.exception(f"Alert engine evaluation error: {exc}")
            time.sleep(60)

    # ── Core evaluation ───────────────────────────────────────────────────────

    def _evaluate_all(self):
        """Evaluate built-in and DB-stored alert rules against current state."""
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            self._check_builtin_rules(db)
            self._check_user_rules(db)
        except Exception as exc:
            logger.exception(f"Alert engine _evaluate_all error: {exc}")
        finally:
            db.close()

    # ── Built-in rule helpers ─────────────────────────────────────────────────

    def _should_fire(self, rule_key: str, cooldown_minutes: int) -> bool:
        """Return True if the cooldown period has passed for this rule key."""
        last = self._alert_states.get(rule_key)
        if last is None:
            return True
        return datetime.utcnow() - last > timedelta(minutes=cooldown_minutes)

    def _record_fire(self, rule_key: str):
        """Record that a rule just fired."""
        self._alert_states[rule_key] = datetime.utcnow()

    def _fire_builtin(self, db, rule_key: str, severity: str, title: str, message: str,
                      cooldown_minutes: int = 60, action_url: str = "/alerts"):
        """Create an AlertEvent, broadcast in-app notifications, dispatch webhooks/Slack/PagerDuty."""
        if not self._should_fire(rule_key, cooldown_minutes):
            return

        try:
            from app.models.alert_models import AlertEvent
            from app.models.database import User, UserRole
            from sqlalchemy import or_

            # Dedup: skip if an active (unacknowledged) or snoozed event already exists
            # for this rule_key. This prevents duplicates after restarts and respects
            # permanent silence (which sets snooze_until to a far-future date).
            now = datetime.utcnow()
            existing = db.query(AlertEvent).filter(
                AlertEvent.rule_key == rule_key,
                or_(
                    AlertEvent.acknowledged == False,
                    AlertEvent.snooze_until > now,
                )
            ).first()
            if existing:
                return

            event = AlertEvent(
                rule_id=None,
                rule_key=rule_key,
                severity=severity,
                title=title,
                message=message,
                fired_at=datetime.utcnow(),
                acknowledged=False,
            )
            db.add(event)
            db.flush()

            # Broadcast to all admins
            admins = db.query(User).filter(
                User.is_active == True,
                User.role == UserRole.ADMIN,
            ).all()
            from app.models.database import Notification
            for admin in admins:
                notif = Notification(
                    user_id=admin.id,
                    title=title,
                    message=message,
                    type=self._severity_to_notif_type(severity),
                    action_url=action_url,
                )
                db.add(notif)

            db.commit()
            self._record_fire(rule_key)
            logger.info(f"Alert fired [{severity}] {rule_key}: {title}")

            # Webhook + Slack + PagerDuty dispatch (fire-and-forget thread)
            threading.Thread(
                target=self._dispatch_alert_fired,
                args=(rule_key, severity, title, message),
                daemon=True,
            ).start()
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to fire alert {rule_key}: {exc}")

    @staticmethod
    def _severity_to_notif_type(severity: str) -> str:
        return {"critical": "error", "warning": "warning"}.get(severity, "info")

    # ── Built-in rules ────────────────────────────────────────────────────────

    def _check_builtin_rules(self, db):
        """Run all hard-coded alert rule checks."""
        self._check_node_offline(db)
        self._check_storage_usage(db)
        self._check_vm_stopped_unexpectedly(db)
        self._check_backup_failed(db)
        self._check_long_running_tasks(db)
        self._check_high_cpu(db)
        self._check_high_memory(db)
        self._check_login_failures(db)
        self._check_pbs_sync_failed(db)

    def _check_pbs_sync_failed(self, db):
        """Fire when a configured PBS sync job's last run ended in an error state.
        Also resolves (acks) the alert when the job's next run comes back OK.

        rule_key: pbs_sync_fail:{server_id}:{job_id}  — one per job per server.
        """
        try:
            from app.models.database import PBSServer, AlertEvent
            from app.services.pbs import PBSService
            from sqlalchemy import and_

            for server in db.query(PBSServer).filter(PBSServer.is_active == True).all():
                if not ((server.username and server.password) or (server.api_token_id and server.api_token_secret)):
                    continue
                try:
                    svc = PBSService(server)
                    jobs = svc.get_sync_jobs() or []
                except Exception as e:
                    logger.debug("PBS %s sync-check skipped: %s", server.name, e)
                    continue

                for j in jobs:
                    if (j.get("job-type") or "sync") != "sync":
                        continue
                    job_id = j.get("id") or j.get("job-id")
                    if not job_id:
                        continue
                    state = (j.get("last-run-state") or "").lower()
                    rule_key = f"pbs_sync_fail:{server.id}:{job_id}"

                    if state and "error" in state:
                        remote = j.get("remote") or "?"
                        remote_store = j.get("remote-store") or "?"
                        local_store = j.get("store") or "?"
                        endtime = j.get("last-run-endtime")
                        when = ""
                        if endtime:
                            from datetime import datetime as _dt
                            try:
                                when = f" at {_dt.fromtimestamp(int(endtime)).strftime('%Y-%m-%d %H:%M')}"
                            except Exception:
                                pass
                        title = f"PBS sync failed: {server.name} / {job_id}"
                        message = (
                            f"Sync job '{job_id}' on PBS '{server.name}' failed{when}. "
                            f"Pulling {remote_store} from remote '{remote}' into local datastore '{local_store}'. "
                            f"State reported by PBS: {j.get('last-run-state') or state}. "
                            "Open PBS Management and click Run Now on this job to retry."
                        )
                        self._fire_builtin(
                            db, rule_key, "warning", title, message,
                            action_url=f"/pbs-management?highlight=sync:{server.id}:{job_id}",
                            cooldown_minutes=30,
                        )
                    elif state in ("ok", ""):
                        # Auto-acknowledge any open events for this job now that it's back to OK.
                        open_evts = db.query(AlertEvent).filter(
                            and_(AlertEvent.rule_key == rule_key, AlertEvent.acknowledged == False)
                        ).all()
                        if open_evts:
                            from datetime import datetime as _dt
                            for e in open_evts:
                                e.acknowledged = True
                                e.acknowledged_at = _dt.utcnow()
                            db.commit()
                            logger.info("Auto-acked %d PBS sync alerts for %s", len(open_evts), rule_key)
        except Exception as e:
            logger.debug("PBS sync-alert check errored: %s", e)

    def _check_node_offline(self, db):
        """Fire if any Proxmox node hasn't been updated for > 10 minutes."""
        try:
            from app.models.database import ProxmoxNode, ProxmoxHost
            cutoff = datetime.utcnow() - timedelta(minutes=10)
            # Only check nodes whose host still exists and is active
            active_host_ids = {h.id for h in db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()}
            stale_nodes = db.query(ProxmoxNode).filter(
                ProxmoxNode.last_updated < cutoff,
                ProxmoxNode.status == "online",
                ProxmoxNode.host_id.in_(active_host_ids),
            ).all()
            for node in stale_nodes:
                key = f"node_offline:{node.id}"
                self._fire_builtin(
                    db, key, "critical",
                    f"Node offline: {node.node_name}",
                    f"Proxmox node '{node.node_name}' has not reported in over 5 minutes. "
                    f"Last update: {node.last_updated.isoformat() if node.last_updated else 'never'}",
                    cooldown_minutes=30,
                )
        except Exception as exc:
            logger.debug(f"check_node_offline error: {exc}")

    def _check_storage_usage(self, db):
        """Check all Proxmox hosts for storage pools exceeding 85% / 95%."""
        try:
            from app.models.database import ProxmoxHost
            from app.services.proxmox import ProxmoxService

            hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()
            for host in hosts:
                try:
                    svc = ProxmoxService(host)
                    nodes = svc.get_nodes()
                    for node_info in nodes:
                        node_name = node_info.get("node")
                        if not node_name:
                            continue
                        try:
                            storage_list = svc.proxmox.nodes(node_name).storage.get(content="images")
                        except Exception:
                            continue
                        for store in storage_list:
                            total = store.get("total", 0)
                            used = store.get("used", 0)
                            if not total:
                                continue
                            pct = (used / total) * 100
                            store_name = store.get("storage", "unknown")
                            key95 = f"storage_critical:{host.id}:{node_name}:{store_name}"
                            key85 = f"storage_warning:{host.id}:{node_name}:{store_name}"
                            if pct >= 95:
                                self._fire_builtin(
                                    db, key95, "critical",
                                    f"Storage critically full: {store_name}",
                                    f"Storage pool '{store_name}' on {node_name} ({host.name}) is "
                                    f"{pct:.1f}% full (>= 95%). Immediate action required.",
                                    cooldown_minutes=60,
                                )
                            elif pct >= 85:
                                self._fire_builtin(
                                    db, key85, "warning",
                                    f"Storage high usage: {store_name}",
                                    f"Storage pool '{store_name}' on {node_name} ({host.name}) is "
                                    f"{pct:.1f}% full (>= 85%).",
                                    cooldown_minutes=120,
                                )
                except Exception as host_exc:
                    logger.debug(f"check_storage_usage host {host.id} error: {host_exc}")
        except Exception as exc:
            logger.debug(f"check_storage_usage error: {exc}")

    def _check_vm_stopped_unexpectedly(self, db):
        """Detect VMs that were running but now stopped with no user-initiated stop task in last 5 min."""
        try:
            from app.models.database import ProxmoxHost
            from app.services.proxmox import ProxmoxService

            hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()
            for host in hosts:
                try:
                    svc = ProxmoxService(host)
                    nodes = svc.get_nodes()
                    for node_info in nodes:
                        node_name = node_info.get("node")
                        if not node_name:
                            continue
                        try:
                            vms = svc.proxmox.nodes(node_name).qemu.get()
                        except Exception:
                            continue
                        # Get recent tasks for this node
                        try:
                            tasks = svc.proxmox.nodes(node_name).tasks.get(limit=50)
                        except Exception:
                            tasks = []

                        # Tasks started in the last 5 minutes that are stop/shutdown
                        cutoff_ts = time.time() - 300
                        recent_stop_vmids = set()
                        for t in tasks:
                            start_ts = t.get("starttime", 0)
                            task_type = (t.get("type") or "").lower()
                            vmid_str = str(t.get("id", ""))
                            if start_ts >= cutoff_ts and any(
                                kw in task_type for kw in ("stop", "shutdown", "halt")
                            ):
                                recent_stop_vmids.add(vmid_str)

                        # Load muted VMs for this host
                        try:
                            import json
                            from app.models.database import SystemSettings
                            mute_row = db.query(SystemSettings).filter(SystemSettings.key == "vm_alert_mutes").first()
                            muted_vmids = set()
                            if mute_row:
                                for m in json.loads(mute_row.value or "[]"):
                                    if m.get("host_id") == host.id:
                                        muted_vmids.add(str(m.get("vmid", "")))
                        except Exception:
                            muted_vmids = set()

                        for vm in vms:
                            status = vm.get("status", "")
                            vmid = str(vm.get("vmid", ""))
                            name = vm.get("name", vmid)
                            # Skip templates and cloud-init base images — they are intentionally stopped
                            if vm.get("template") == 1 or vm.get("template") is True:
                                continue
                            if status == "stopped" and vmid not in recent_stop_vmids and vmid not in muted_vmids:
                                key = f"vm_unexpected_stop:{host.id}:{node_name}:{vmid}"
                                # Only fire once per cooldown — don't spam for long-stopped VMs
                                self._fire_builtin(
                                    db, key, "warning",
                                    f"VM stopped unexpectedly: {name}",
                                    f"VM '{name}' (VMID {vmid}) on {node_name} ({host.name}) "
                                    f"is stopped with no matching stop task in the last 5 minutes.",
                                    cooldown_minutes=1440,  # once per day max
                                )
                except Exception as host_exc:
                    logger.debug(f"check_vm_stopped host {host.id} error: {host_exc}")
        except Exception as exc:
            logger.debug(f"check_vm_stopped error: {exc}")

    def _check_backup_failed(self, db):
        """Check for failed vzdump tasks in the last 24h."""
        try:
            from app.models.database import ProxmoxHost
            from app.services.proxmox import ProxmoxService

            hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()
            cutoff_ts = time.time() - 86400
            for host in hosts:
                try:
                    svc = ProxmoxService(host)
                    nodes = svc.get_nodes()
                    for node_info in nodes:
                        node_name = node_info.get("node")
                        if not node_name:
                            continue
                        try:
                            tasks = svc.proxmox.nodes(node_name).tasks.get(limit=200)
                        except Exception:
                            continue
                        for t in tasks:
                            if (t.get("type", "") == "vzdump" and
                                    t.get("status", "") == "ERROR" and
                                    t.get("starttime", 0) >= cutoff_ts):
                                upid = t.get("upid", "")
                                key = f"backup_failed:{host.id}:{node_name}:{upid}"
                                vmid = t.get("id", "?")
                                self._fire_builtin(
                                    db, key, "warning",
                                    f"Backup failed on {node_name}",
                                    f"A backup (vzdump) for VM/CT {vmid} on {node_name} ({host.name}) "
                                    f"failed within the last 24 hours. UPID: {upid}",
                                    cooldown_minutes=1440,
                                )
                except Exception as host_exc:
                    logger.debug(f"check_backup_failed host {host.id} error: {host_exc}")
        except Exception as exc:
            logger.debug(f"check_backup_failed error: {exc}")

    def _check_long_running_tasks(self, db):
        """Fire if any Proxmox task has been running for > 2 hours."""
        try:
            from app.models.database import ProxmoxHost
            from app.services.proxmox import ProxmoxService

            hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()
            cutoff_ts = time.time() - 7200  # 2 hours ago
            for host in hosts:
                try:
                    svc = ProxmoxService(host)
                    nodes = svc.get_nodes()
                    for node_info in nodes:
                        node_name = node_info.get("node")
                        if not node_name:
                            continue
                        try:
                            tasks = svc.proxmox.nodes(node_name).tasks.get(limit=50)
                        except Exception:
                            continue
                        for t in tasks:
                            # Running tasks have no endtime
                            if t.get("endtime"):
                                continue
                            start_ts = t.get("starttime", 0)
                            if start_ts and start_ts <= cutoff_ts:
                                upid = t.get("upid", "")
                                task_type = t.get("type", "unknown")
                                key = f"long_task:{host.id}:{node_name}:{upid}"
                                duration_h = (time.time() - start_ts) / 3600
                                self._fire_builtin(
                                    db, key, "warning",
                                    f"Long-running task on {node_name}",
                                    f"Task '{task_type}' on {node_name} ({host.name}) has been running "
                                    f"for {duration_h:.1f} hours. UPID: {upid}",
                                    cooldown_minutes=120,
                                )
                except Exception as host_exc:
                    logger.debug(f"check_long_tasks host {host.id} error: {host_exc}")
        except Exception as exc:
            logger.debug(f"check_long_tasks error: {exc}")

    def _check_high_cpu(self, db):
        """Fire if any node CPU average is > 90%."""
        try:
            from app.models.database import ProxmoxNode
            high_cpu_nodes = db.query(ProxmoxNode).filter(
                ProxmoxNode.cpu_usage > 90,
                ProxmoxNode.status == "online",
            ).all()
            for node in high_cpu_nodes:
                key = f"high_cpu:{node.id}"
                self._fire_builtin(
                    db, key, "warning",
                    f"High CPU: {node.node_name}",
                    f"Node '{node.node_name}' has CPU usage at {node.cpu_usage}% (threshold: 90%).",
                    cooldown_minutes=30,
                )
        except Exception as exc:
            logger.debug(f"check_high_cpu error: {exc}")

    def _check_high_memory(self, db):
        """Fire if any node memory usage is > 95%."""
        try:
            from app.models.database import ProxmoxNode
            nodes = db.query(ProxmoxNode).filter(
                ProxmoxNode.memory_total > 0,
                ProxmoxNode.memory_used > 0,
                ProxmoxNode.status == "online",
            ).all()
            for node in nodes:
                pct = (node.memory_used / node.memory_total) * 100
                if pct >= 95:
                    key = f"high_memory:{node.id}"
                    self._fire_builtin(
                        db, key, "critical",
                        f"High memory: {node.node_name}",
                        f"Node '{node.node_name}' has memory usage at {pct:.1f}% (threshold: 95%).",
                        cooldown_minutes=30,
                    )
        except Exception as exc:
            logger.debug(f"check_high_memory error: {exc}")

    def _check_login_failures(self, db):
        """Fire if > 5 failed logins from the same IP in the last 10 minutes."""
        try:
            from sqlalchemy import text
            cutoff = datetime.utcnow() - timedelta(minutes=10)
            rows = db.execute(text(
                "SELECT ip_address, COUNT(*) as cnt FROM login_attempts "
                "WHERE success = 0 AND timestamp >= :cutoff "
                "GROUP BY ip_address HAVING cnt > 5"
            ), {"cutoff": cutoff}).fetchall()
            for row in rows:
                ip = row[0]
                cnt = row[1]
                key = f"login_failures:{ip}"
                self._fire_builtin(
                    db, key, "warning",
                    f"Login failures from {ip}",
                    f"{cnt} failed login attempts from IP {ip} in the last 10 minutes.",
                    cooldown_minutes=30,
                )
        except Exception as exc:
            logger.debug(f"check_login_failures error: {exc}")

    # ── User-configured rule evaluation ──────────────────────────────────────

    def _check_user_rules(self, db):
        """Evaluate DB-stored user-configured alert rules."""
        try:
            from app.models.alert_models import AlertRule
            rules = db.query(AlertRule).filter(AlertRule.enabled == True).all()
            for rule in rules:
                try:
                    self._evaluate_user_rule(db, rule)
                except Exception as exc:
                    logger.debug(f"Error evaluating user rule {rule.id}: {exc}")
        except Exception as exc:
            logger.debug(f"check_user_rules error: {exc}")

    def _evaluate_user_rule(self, db, rule):
        """Evaluate a single user-configured rule."""
        from app.models.alert_models import AlertRule, AlertEvent
        from app.models.database import Notification, User, UserRole

        rule_key = f"user_rule:{rule.id}"
        if not self._should_fire(rule_key, rule.cooldown_minutes):
            return

        triggered = False
        title = ""
        message = ""
        severity = "warning"

        try:
            if rule.rule_type == "storage_usage":
                triggered, title, message = self._eval_storage_usage_rule(db, rule)
            elif rule.rule_type == "node_cpu":
                triggered, title, message = self._eval_node_cpu_rule(db, rule)
            elif rule.rule_type == "node_memory":
                triggered, title, message = self._eval_node_memory_rule(db, rule)
            elif rule.rule_type == "vm_stopped":
                triggered, title, message = self._eval_vm_stopped_rule(db, rule)
            elif rule.rule_type == "backup_failed":
                triggered, title, message = self._eval_backup_failed_rule(db, rule)
            elif rule.rule_type == "login_failures":
                triggered, title, message = self._eval_login_failures_rule(db, rule)
        except Exception as exc:
            logger.debug(f"User rule {rule.id} eval error: {exc}")
            return

        if not triggered:
            return

        # Record event
        event = AlertEvent(
            rule_id=rule.id,
            rule_key=rule_key,
            severity=severity,
            title=title,
            message=message,
            fired_at=datetime.utcnow(),
            acknowledged=False,
        )
        db.add(event)
        db.flush()

        # Update last_fired on rule
        rule.last_fired_at = datetime.utcnow()

        # In-app notifications
        if rule.notify_in_app:
            admins = db.query(User).filter(
                User.is_active == True,
                User.role == UserRole.ADMIN,
            ).all()
            for admin in admins:
                notif = Notification(
                    user_id=admin.id,
                    title=title,
                    message=message,
                    type=self._severity_to_notif_type(severity),
                    action_url="/alerts",
                )
                db.add(notif)

        db.commit()
        self._record_fire(rule_key)

        # Webhook + Slack + PagerDuty dispatch (fire-and-forget thread)
        if rule.notify_webhook or rule.notify_slack:
            threading.Thread(
                target=self._dispatch_alert_fired,
                args=(f"user_rule:{rule.id}", severity, title, message, rule.id, rule.name),
                daemon=True,
            ).start()

    def _eval_storage_usage_rule(self, db, rule):
        from app.models.database import ProxmoxHost
        from app.services.proxmox import ProxmoxService

        threshold = rule.threshold or 85.0
        hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True)
        if rule.host_id:
            hosts = hosts.filter(ProxmoxHost.id == rule.host_id)
        for host in hosts.all():
            try:
                svc = ProxmoxService(host)
                nodes = svc.get_nodes()
                for node_info in nodes:
                    node_name = node_info.get("node")
                    if rule.node and node_name != rule.node:
                        continue
                    stores = svc.proxmox.nodes(node_name).storage.get(content="images")
                    for store in stores:
                        total = store.get("total", 0)
                        used = store.get("used", 0)
                        if not total:
                            continue
                        pct = (used / total) * 100
                        if pct >= threshold:
                            return True, \
                                f"[{rule.name}] Storage at {pct:.1f}%", \
                                f"Storage pool '{store.get('storage')}' on {node_name} ({host.name}) " \
                                f"is {pct:.1f}% full (threshold {threshold}%)."
            except Exception:
                pass
        return False, "", ""

    def _eval_node_cpu_rule(self, db, rule):
        from app.models.database import ProxmoxNode
        threshold = rule.threshold or 90.0
        query = db.query(ProxmoxNode).filter(
            ProxmoxNode.cpu_usage >= threshold,
            ProxmoxNode.status == "online",
        )
        if rule.node:
            query = query.filter(ProxmoxNode.node_name == rule.node)
        node = query.first()
        if node:
            return True, \
                f"[{rule.name}] High CPU: {node.node_name}", \
                f"Node '{node.node_name}' CPU at {node.cpu_usage}% (threshold {threshold}%)."
        return False, "", ""

    def _eval_node_memory_rule(self, db, rule):
        from app.models.database import ProxmoxNode
        threshold = rule.threshold or 95.0
        query = db.query(ProxmoxNode).filter(
            ProxmoxNode.memory_total > 0,
            ProxmoxNode.memory_used > 0,
            ProxmoxNode.status == "online",
        )
        if rule.node:
            query = query.filter(ProxmoxNode.node_name == rule.node)
        for node in query.all():
            pct = (node.memory_used / node.memory_total) * 100
            if pct >= threshold:
                return True, \
                    f"[{rule.name}] High memory: {node.node_name}", \
                    f"Node '{node.node_name}' memory at {pct:.1f}% (threshold {threshold}%)."
        return False, "", ""

    def _eval_vm_stopped_rule(self, db, rule):
        # Delegates to built-in logic pattern
        return False, "", ""

    def _eval_backup_failed_rule(self, db, rule):
        return False, "", ""

    def _eval_login_failures_rule(self, db, rule):
        from sqlalchemy import text
        threshold = int(rule.threshold or 5)
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        rows = db.execute(text(
            "SELECT ip_address, COUNT(*) as cnt FROM login_attempts "
            "WHERE success = 0 AND timestamp >= :cutoff "
            "GROUP BY ip_address HAVING cnt > :threshold"
        ), {"cutoff": cutoff, "threshold": threshold}).fetchall()
        if rows:
            ip, cnt = rows[0][0], rows[0][1]
            return True, \
                f"[{rule.name}] Login failures from {ip}", \
                f"{cnt} failed login attempts from {ip} in last 10 min (threshold {threshold})."
        return False, "", ""

    # ── Webhook / Slack / PagerDuty dispatch ─────────────────────────────────

    def _dispatch_alert_fired(
        self,
        rule_key: str,
        severity: str,
        title: str,
        message: str,
        rule_id: Optional[int] = None,
        rule_name: Optional[str] = None,
    ):
        """Dispatch alert.fired to webhooks, Slack, and PagerDuty (runs in a separate thread)."""
        try:
            import asyncio
            from app.core.database import SessionLocal
            from app.services.webhook_dispatcher import dispatcher

            db = SessionLocal()
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        dispatcher.dispatch_alert_event(
                            db,
                            event_type="alert.fired",
                            title=title,
                            message=message,
                            severity=severity,
                            rule_id=rule_id,
                            rule_name=rule_name,
                            dedup_key=rule_key,
                        )
                    )
                finally:
                    loop.close()
            finally:
                db.close()
        except Exception as exc:
            logger.debug(f"_dispatch_alert_fired error: {exc}")

    def dispatch_alert_resolved(
        self,
        rule_key: str,
        title: str,
        message: str,
        rule_id: Optional[int] = None,
        rule_name: Optional[str] = None,
    ):
        """
        Public helper: dispatch alert.resolved to webhooks, Slack, and PagerDuty.
        Intended to be called when an alert is acknowledged/resolved.
        Runs in a background thread.
        """
        threading.Thread(
            target=self._dispatch_alert_resolved_sync,
            args=(rule_key, title, message, rule_id, rule_name),
            daemon=True,
        ).start()

    def _dispatch_alert_resolved_sync(
        self,
        rule_key: str,
        title: str,
        message: str,
        rule_id: Optional[int],
        rule_name: Optional[str],
    ):
        """Synchronous worker for alert.resolved dispatch."""
        try:
            import asyncio
            from app.core.database import SessionLocal
            from app.services.webhook_dispatcher import dispatcher

            db = SessionLocal()
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        dispatcher.dispatch_alert_event(
                            db,
                            event_type="alert.resolved",
                            title=title,
                            message=message,
                            severity="info",
                            rule_id=rule_id,
                            rule_name=rule_name,
                            dedup_key=rule_key,
                        )
                    )
                finally:
                    loop.close()
            finally:
                db.close()
        except Exception as exc:
            logger.debug(f"_dispatch_alert_resolved error: {exc}")

    # ── Public helper: manually trigger rule evaluation ───────────────────────

    def evaluate_now(self):
        """Trigger an immediate evaluation outside the polling loop."""
        threading.Thread(target=self._evaluate_all, daemon=True).start()


alert_engine = AlertEngine()
