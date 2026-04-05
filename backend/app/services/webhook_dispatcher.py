"""Webhook dispatcher — automatic event dispatch to configured webhook endpoints and Slack"""
import httpx
import hmac
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    """Dispatches webhook events to all configured endpoints and Slack."""

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

        # Build the outer envelope
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
            event_base = event_type.split(".")[0]  # e.g. "vm" from "vm.started"
            if hook_events and event_type not in hook_events and f"{event_base}.*" not in hook_events:
                continue

            hook_id = hook.get("id", "")
            secret = hook.get("secret", "")

            # Sign the payload
            sig = self.sign_payload(secret, body_bytes) if secret else ""
            headers = {
                "Content-Type": "application/json",
                "X-Depl0y-Event": event_type,
                "X-Depl0y-Delivery": hook_id,
            }
            if sig:
                headers["X-Depl0y-Signature"] = f"sha256={sig}"
                # Also embed signature in the envelope itself
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

    # ── Slack dispatch ───────────────────────────────────────────────────────

    async def dispatch_slack(
        self,
        db: Session,
        message: str,
        attachments: Optional[list] = None,
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

        payload = {"text": message, "attachments": attachments or []}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code >= 400:
                logger.warning(f"Slack notification returned HTTP {resp.status_code}: {resp.text[:200]}")
            else:
                logger.info(f"Slack notification sent: {message[:80]}")
        except Exception as exc:
            logger.error(f"Failed to send Slack notification: {exc}")

    # ── Convenience helpers ──────────────────────────────────────────────────

    async def dispatch_and_slack(
        self,
        db: Session,
        event_type: str,
        payload: Dict[str, Any],
        slack_message: str,
        host_id: Optional[int] = None,
    ) -> None:
        """Fire webhook dispatch and Slack notification concurrently."""
        await self.dispatch(db, event_type, payload, host_id=host_id)
        await self.dispatch_slack(db, slack_message, event_type=event_type)


dispatcher = WebhookDispatcher()
