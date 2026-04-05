"""Webhook dispatcher — automatic event dispatch to configured webhook endpoints, Slack, and PagerDuty"""
import httpx
import hmac
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── Canonical event type registry ────────────────────────────────────────────

EVENT_TYPES: List[str] = [
    # VM lifecycle
    "vm.start",
    "vm.stop",
    "vm.create",
    "vm.delete",
    "vm.migrate",
    "vm.shutdown",
    "vm.reboot",
    "vm.reset",
    "vm.suspend",
    "vm.resume",
    # Backup
    "backup.complete",
    "backup.failed",
    # Alerts
    "alert.fired",
    "alert.resolved",
    # Auth
    "user.login",
    "user.login_failed",
    # Tasks
    "task.failed",
    # Nodes
    "node.offline",
    "node.online",
]


class WebhookDispatcher:
    """Dispatches webhook events to all configured endpoints, Slack, and PagerDuty."""

    # ── Core webhook dispatch ────────────────────────────────────────────────

    async def dispatch(
        self,
        db: Session,
        event_type: str,
        payload: Dict[str, Any],
        host_id: Optional[int] = None,
    ) -> None:
        """
        Fetch all active webhooks matching this event_type, sign and POST to each,
        record delivery result in webhook_deliveries table.
        """
        from app.models.database import SystemSettings, WebhookDelivery

        setting = db.query(SystemSettings).filter(SystemSettings.key == "webhooks").first()
        if not setting or not setting.value:
            return
        try:
            webhooks = json.loads(setting.value)
        except Exception:
            return

        # Build the outer envelope — event type is part of the signed body
        envelope = {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "depl0y",
            "data": payload,
        }
        body_bytes = json.dumps(envelope).encode()

        for hook in webhooks:
            if not hook.get("enabled", True):
                continue
            hook_events = hook.get("events", [])
            # Accept if the hook subscribes to this event or to a wildcard category
            event_base = event_type.split(".")[0]  # e.g. "vm" from "vm.start"
            if hook_events and event_type not in hook_events and f"{event_base}.*" not in hook_events:
                continue

            hook_id = hook.get("id", "")
            secret = hook.get("secret", "")

            # Sign the payload (event type is already embedded in body_bytes)
            sig = self.sign_payload(secret, body_bytes) if secret else ""
            headers = {
                "Content-Type": "application/json",
                "X-Depl0y-Event": event_type,
                "X-Depl0y-Delivery": hook_id,
            }
            if sig:
                headers["X-Depl0y-Signature"] = f"sha256={sig}"
                envelope["signature"] = f"sha256={sig}"

            status_code: Optional[int] = None
            success = False
            response_text = ""
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        hook["url"],
                        content=json.dumps(envelope).encode(),
                        headers=headers,
                        timeout=10,
                    )
                status_code = resp.status_code
                success = 200 <= resp.status_code < 300
                response_text = resp.text[:500]
                logger.info(
                    f"Webhook dispatched event={event_type} to {hook['url']}: HTTP {resp.status_code}"
                )
            except Exception as exc:
                response_text = str(exc)[:500]
                logger.error(
                    f"Webhook dispatch failed event={event_type} to {hook.get('url')}: {exc}"
                )

            # Record delivery
            try:
                delivery = WebhookDelivery(
                    webhook_id=hook_id,
                    event=event_type,
                    status_code=status_code,
                    success=success,
                    response_body=response_text,
                )
                db.add(delivery)
                db.commit()
            except Exception as exc:
                logger.error(f"Failed to record webhook delivery: {exc}")
                try:
                    db.rollback()
                except Exception:
                    pass

    def sign_payload(self, secret: str, payload_bytes: bytes) -> str:
        """HMAC-SHA256 signature of the payload bytes."""
        return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

    # ── Slack helpers ────────────────────────────────────────────────────────

    async def send_slack_message(
        self,
        webhook_url: str,
        message: str,
        blocks: Optional[list] = None,
    ) -> bool:
        """
        Post a message to an arbitrary Slack webhook URL.
        Returns True on success, False on failure.
        """
        payload: Dict[str, Any] = {"text": message}
        if blocks:
            payload["blocks"] = blocks
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=payload, timeout=10)
            if resp.status_code >= 400:
                logger.warning(f"Slack webhook returned HTTP {resp.status_code}: {resp.text[:200]}")
                return False
            logger.info(f"Slack message sent: {message[:80]}")
            return True
        except Exception as exc:
            logger.error(f"Failed to send Slack message: {exc}")
            return False

    def _build_vm_slack_blocks(
        self,
        event_type: str,
        vm_data: Dict[str, Any],
        host_name: str,
    ) -> list:
        """Build Slack Block Kit message with a color bar for VM events."""
        color_map = {
            "vm.start":    "#22c55e",   # green
            "vm.create":   "#3b82f6",   # blue
            "vm.stop":     "#ef4444",   # red
            "vm.delete":   "#dc2626",   # dark red
            "vm.shutdown": "#f59e0b",   # amber
            "vm.migrate":  "#8b5cf6",   # purple
            "vm.reboot":   "#f97316",   # orange
        }
        emoji_map = {
            "vm.start":    ":arrow_forward:",
            "vm.create":   ":sparkles:",
            "vm.stop":     ":stop_sign:",
            "vm.delete":   ":wastebasket:",
            "vm.shutdown": ":zzz:",
            "vm.migrate":  ":truck:",
            "vm.reboot":   ":arrows_counterclockwise:",
        }
        color = color_map.get(event_type, "#6b7280")
        emoji = emoji_map.get(event_type, ":gear:")
        action = event_type.split(".")[-1].capitalize()
        vmid = vm_data.get("vm_id", vm_data.get("vmid", "?"))
        node = vm_data.get("node", "?")
        user = vm_data.get("user", "")
        vm_name = vm_data.get("name", f"VM {vmid}")

        text = f"{emoji} *VM {action}*: `{vm_name}` (VMID {vmid})\nNode: `{node}` on *{host_name}*"
        if user:
            text += f"  ·  by `{user}`"

        return [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Host: *{host_name}* · Event: `{event_type}`"}
                ],
            },
        ]

    def _build_alert_slack_blocks(
        self,
        event_type: str,
        title: str,
        message: str,
        severity: str,
        threshold: Optional[float] = None,
    ) -> list:
        """Build Slack Block Kit message for alert.fired / alert.resolved."""
        if event_type == "alert.resolved":
            emoji = ":white_check_mark:"
            color_word = "RESOLVED"
        else:
            severity_emoji = {
                "critical": ":red_circle:",
                "warning": ":warning:",
                "info": ":information_source:",
            }
            emoji = severity_emoji.get(severity, ":bell:")
            color_word = severity.upper()

        header = f"{emoji} *[{color_word}] {title}*"
        body = message
        if threshold is not None:
            body += f"\nThreshold: `{threshold}`"

        return [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": header},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": body},
            },
        ]

    # ── Slack dispatch ───────────────────────────────────────────────────────

    async def dispatch_slack(
        self,
        db: Session,
        message: str,
        blocks: Optional[list] = None,
        event_type: Optional[str] = None,
    ) -> None:
        """
        Send a Slack notification via the configured webhook URL.
        Respects the slack_events whitelist if set.
        """
        from app.models.database import SystemSettings

        url_row = db.query(SystemSettings).filter(SystemSettings.key == "slack_webhook_url").first()
        url = url_row.value if url_row else None
        if not url:
            return

        # Check event whitelist
        if event_type:
            events_row = db.query(SystemSettings).filter(SystemSettings.key == "slack_events").first()
            if events_row and events_row.value:
                try:
                    allowed = json.loads(events_row.value)
                    if allowed and event_type not in allowed:
                        return
                except Exception:
                    pass

        await self.send_slack_message(url, message, blocks=blocks)

    # ── PagerDuty integration ────────────────────────────────────────────────

    async def send_pagerduty_event(
        self,
        routing_key: str,
        event_action: str,          # "trigger" | "acknowledge" | "resolve"
        summary: str,
        severity: str,              # "critical" | "error" | "warning" | "info"
        source: str,
        dedup_key: Optional[str] = None,
        custom_details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send an event to PagerDuty Events API v2.
        Returns True on success, False on failure.

        event_action values:
          - "trigger"     — create or re-trigger an incident
          - "acknowledge" — acknowledge an existing incident (requires dedup_key)
          - "resolve"     — resolve an existing incident (requires dedup_key)
        """
        pd_url = "https://events.pagerduty.com/v2/enqueue"

        payload: Dict[str, Any] = {
            "routing_key": routing_key,
            "event_action": event_action,
            "payload": {
                "summary": summary,
                "severity": severity,
                "source": source,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        }
        if dedup_key:
            payload["dedup_key"] = dedup_key
        if custom_details:
            payload["payload"]["custom_details"] = custom_details

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    pd_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=15,
                )
            if resp.status_code in (200, 202):
                logger.info(f"PagerDuty event sent: action={event_action} summary={summary[:60]}")
                return True
            else:
                logger.warning(f"PagerDuty returned HTTP {resp.status_code}: {resp.text[:200]}")
                return False
        except Exception as exc:
            logger.error(f"Failed to send PagerDuty event: {exc}")
            return False

    async def dispatch_pagerduty(
        self,
        db: Session,
        event_action: str,
        summary: str,
        severity: str,
        source: str,
        dedup_key: Optional[str] = None,
        custom_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send a PagerDuty event using the routing key stored in system settings.
        Maps internal severity labels (critical/warning) to PD severity levels.
        """
        from app.models.database import SystemSettings

        pd_row = db.query(SystemSettings).filter(SystemSettings.key == "pagerduty_routing_key").first()
        routing_key = pd_row.value.strip() if pd_row and pd_row.value else None
        if not routing_key:
            return

        # Map internal severity to PagerDuty severity
        pd_severity_map = {
            "critical": "critical",
            "error":    "error",
            "warning":  "warning",
            "info":     "info",
        }
        pd_severity = pd_severity_map.get(severity.lower(), "error")

        await self.send_pagerduty_event(
            routing_key=routing_key,
            event_action=event_action,
            summary=summary,
            severity=pd_severity,
            source=source,
            dedup_key=dedup_key,
            custom_details=custom_details,
        )

    # ── Typed convenience dispatchers ────────────────────────────────────────

    async def dispatch_vm_event(
        self,
        db: Session,
        event_type: str,
        vm_data: Dict[str, Any],
        host_name: str,
    ) -> None:
        """
        Dispatch a VM lifecycle event to webhooks and Slack.

        vm_data should contain: vm_id/vmid, node, name, user, host_id, etc.
        event_type should be one of: vm.start, vm.stop, vm.create, vm.delete, vm.migrate, ...
        """
        blocks = self._build_vm_slack_blocks(event_type, vm_data, host_name)
        emoji_map = {
            "vm.start":    ":arrow_forward:",
            "vm.create":   ":sparkles:",
            "vm.stop":     ":stop_sign:",
            "vm.delete":   ":wastebasket:",
            "vm.shutdown": ":zzz:",
            "vm.migrate":  ":truck:",
            "vm.reboot":   ":arrows_counterclockwise:",
        }
        emoji = emoji_map.get(event_type, ":gear:")
        vmid = vm_data.get("vm_id", vm_data.get("vmid", "?"))
        node = vm_data.get("node", "?")
        action = event_type.split(".")[-1]
        user = vm_data.get("user", "")
        fallback = f"{emoji} VM *{vmid}* on `{node}` ({host_name}) {action}"
        if user:
            fallback += f" by `{user}`"

        await self.dispatch(db, event_type, vm_data, host_id=vm_data.get("host_id"))
        await self.dispatch_slack(db, fallback, blocks=blocks, event_type=event_type)

    async def dispatch_task_event(
        self,
        db: Session,
        event_type: str,
        task_data: Dict[str, Any],
    ) -> None:
        """
        Dispatch a task lifecycle event (e.g. task.failed) to webhooks and Slack.

        task_data should contain: task_id/upid, task_type, description, user, node, host_id, etc.
        """
        upid = task_data.get("upid", task_data.get("task_id", "?"))
        task_type = task_data.get("task_type", "unknown")
        description = task_data.get("description", "")
        node = task_data.get("node", "?")
        user = task_data.get("user", "")

        fallback = f":x: Task *failed*: `{task_type}` on `{node}` — {description}"
        if user:
            fallback += f" (by `{user}`)"

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":x: *Task Failed*\n"
                        f"Type: `{task_type}` · Node: `{node}`\n"
                        f"{description}"
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"UPID: `{upid}`" + (f" · by `{user}`" if user else "")}
                ],
            },
        ]

        await self.dispatch(db, event_type, task_data, host_id=task_data.get("host_id"))
        await self.dispatch_slack(db, fallback, blocks=blocks, event_type=event_type)

    # ── Convenience helpers ──────────────────────────────────────────────────

    async def dispatch_and_slack(
        self,
        db: Session,
        event_type: str,
        payload: Dict[str, Any],
        slack_message: str,
        host_id: Optional[int] = None,
        slack_blocks: Optional[list] = None,
    ) -> None:
        """Fire webhook dispatch and Slack notification concurrently."""
        await self.dispatch(db, event_type, payload, host_id=host_id)
        await self.dispatch_slack(db, slack_message, blocks=slack_blocks, event_type=event_type)

    async def dispatch_alert_event(
        self,
        db: Session,
        event_type: str,
        title: str,
        message: str,
        severity: str,
        rule_id: Optional[int] = None,
        rule_name: Optional[str] = None,
        threshold: Optional[float] = None,
        dedup_key: Optional[str] = None,
    ) -> None:
        """
        Dispatch an alert.fired or alert.resolved event to webhooks, Slack,
        and PagerDuty (for critical alerts on trigger, resolve on resolved).
        """
        payload = {
            "title": title,
            "message": message,
            "severity": severity,
            "rule_id": rule_id,
            "rule_name": rule_name,
            "threshold": threshold,
        }
        blocks = self._build_alert_slack_blocks(event_type, title, message, severity, threshold)
        emoji = ":white_check_mark:" if event_type == "alert.resolved" else {
            "critical": ":red_circle:",
            "warning":  ":warning:",
        }.get(severity, ":bell:")
        fallback = f"{emoji} *[{severity.upper()}] {title}*\n{message}"

        await self.dispatch(db, event_type, payload)
        await self.dispatch_slack(db, fallback, blocks=blocks, event_type=event_type)

        # PagerDuty: trigger on critical alert.fired, resolve on alert.resolved
        if event_type == "alert.fired" and severity == "critical":
            await self.dispatch_pagerduty(
                db,
                event_action="trigger",
                summary=f"[{severity.upper()}] {title}",
                severity=severity,
                source="depl0y",
                dedup_key=dedup_key or (f"alert:{rule_id}" if rule_id else None),
                custom_details={"message": message, "rule_name": rule_name, "threshold": threshold},
            )
        elif event_type == "alert.resolved" and dedup_key:
            await self.dispatch_pagerduty(
                db,
                event_action="resolve",
                summary=f"[RESOLVED] {title}",
                severity="info",
                source="depl0y",
                dedup_key=dedup_key,
            )


dispatcher = WebhookDispatcher()
