"""Notifications API — in-app notifications + webhook management"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.core.database import get_db
from app.api.auth import require_admin, get_current_user
from app.models.database import SystemSettings, Notification, WebhookDelivery, User, UserRole
import logging
import json
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class WebhookCreate(BaseModel):
    url: str
    name: str
    events: List[str]  # ["vm.start", "vm.stop", "vm.create", "vm.delete", "vm.error"]
    secret: Optional[str] = None
    enabled: bool = True


class MarkReadRequest(BaseModel):
    ids: Optional[List[int]] = None
    all: Optional[bool] = False


class NotificationOut(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str
    read: bool
    action_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── In-app notification helpers ───────────────────────────────────────────────

async def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    type: str = "info",
    action_url: Optional[str] = None,
) -> Notification:
    """Create an in-app notification for a specific user."""
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=type,
        action_url=action_url,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


async def broadcast_notification(
    db: Session,
    title: str,
    message: str,
    type: str = "info",
    action_url: Optional[str] = None,
    roles: Optional[List[str]] = None,
):
    """Send a notification to all active users, optionally filtered by role(s)."""
    query = db.query(User).filter(User.is_active == True)
    if roles:
        query = query.filter(User.role.in_([UserRole(r) for r in roles if r in [e.value for e in UserRole]]))
    users = query.all()
    for user in users:
        notif = Notification(
            user_id=user.id,
            title=title,
            message=message,
            type=type,
            action_url=action_url,
        )
        db.add(notif)
    db.commit()


# ── In-app notification endpoints ─────────────────────────────────────────────

@router.get("/in-app", response_model=List[NotificationOut])
async def list_in_app_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List in-app notifications for the current user, newest first, limit 50."""
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return notifications


@router.post("/in-app/mark-read")
async def mark_notifications_read(
    data: MarkReadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark one or more notifications as read (by ids list or all=true)."""
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read == False,
    )
    if data.all:
        query.update({"read": True}, synchronize_session=False)
    elif data.ids:
        query.filter(Notification.id.in_(data.ids)).update(
            {"read": True}, synchronize_session=False
        )
    db.commit()
    return {"status": "ok"}


@router.post("/in-app/{notif_id}/read")
async def mark_notification_read(
    notif_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a single in-app notification as read."""
    notif = (
        db.query(Notification)
        .filter(Notification.id == notif_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.read = True
    db.commit()
    return {"status": "ok", "id": notif_id}


@router.post("/in-app/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all in-app notifications for the current user as read."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read == False,
    ).update({"read": True}, synchronize_session=False)
    db.commit()
    return {"status": "ok"}


@router.delete("/in-app/{notif_id}")
async def delete_notification(
    notif_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a single in-app notification belonging to the current user."""
    notif = (
        db.query(Notification)
        .filter(Notification.id == notif_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.delete(notif)
    db.commit()
    return {"status": "deleted"}


@router.delete("/in-app")
async def delete_all_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete all in-app notifications for the current user."""
    db.query(Notification).filter(Notification.user_id == current_user.id).delete(
        synchronize_session=False
    )
    db.commit()
    return {"status": "cleared"}


@router.post("/in-app/test")
async def send_test_notification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a test in-app notification for the current user."""
    notif = await create_notification(
        db,
        user_id=current_user.id,
        title="Test Notification",
        message="This is a test notification from Depl0y. Everything is working correctly!",
        type="info",
    )
    return {"status": "created", "id": notif.id}


# ── Webhook endpoints ─────────────────────────────────────────────────────────

@router.get("/webhooks")
async def list_webhooks(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List configured webhooks with delivery stats."""
    setting = db.query(SystemSettings).filter(SystemSettings.key == "webhooks").first()
    webhooks = json.loads(setting.value or "[]") if setting else []

    # Attach last 10 delivery log entries per webhook
    for hook in webhooks:
        deliveries = (
            db.query(WebhookDelivery)
            .filter(WebhookDelivery.webhook_id == hook["id"])
            .order_by(WebhookDelivery.created_at.desc())
            .limit(10)
            .all()
        )
        hook["delivery_log"] = [
            {
                "id": d.id,
                "event": d.event,
                "status_code": d.status_code,
                "success": d.success,
                "response_body": d.response_body,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in deliveries
        ]

    return {"webhooks": webhooks}


@router.post("/webhooks")
async def create_webhook(
    data: WebhookCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Add a webhook"""
    setting = db.query(SystemSettings).filter(SystemSettings.key == "webhooks").first()
    webhooks = json.loads(setting.value or "[]") if setting else []
    new_hook = {"id": str(uuid.uuid4()), **data.dict()}
    webhooks.append(new_hook)
    if not setting:
        setting = SystemSettings(
            key="webhooks",
            value=json.dumps(webhooks),
            description="Configured webhook endpoints for VM event notifications"
        )
        db.add(setting)
    else:
        setting.value = json.dumps(webhooks)
    db.commit()
    logger.info(f"Webhook created: {new_hook['name']} -> {new_hook['url']} by user {current_user.username}")
    return new_hook


@router.put("/webhooks/{hook_id}")
async def update_webhook(
    hook_id: str,
    data: WebhookCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a webhook"""
    setting = db.query(SystemSettings).filter(SystemSettings.key == "webhooks").first()
    if not setting:
        raise HTTPException(status_code=404, detail="Webhook not found")
    webhooks = json.loads(setting.value or "[]")
    idx = next((i for i, w in enumerate(webhooks) if w["id"] == hook_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    updated = {"id": hook_id, **data.dict()}
    webhooks[idx] = updated
    setting.value = json.dumps(webhooks)
    db.commit()
    logger.info(f"Webhook updated: {hook_id} by user {current_user.username}")
    return updated


@router.delete("/webhooks/{hook_id}")
async def delete_webhook(
    hook_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a webhook"""
    setting = db.query(SystemSettings).filter(SystemSettings.key == "webhooks").first()
    if not setting:
        raise HTTPException(status_code=404, detail="Webhook not found")
    webhooks = json.loads(setting.value or "[]")
    original_count = len(webhooks)
    webhooks = [w for w in webhooks if w["id"] != hook_id]
    if len(webhooks) == original_count:
        raise HTTPException(status_code=404, detail="Webhook not found")
    setting.value = json.dumps(webhooks)
    db.commit()
    logger.info(f"Webhook deleted: {hook_id} by user {current_user.username}")
    return {"status": "deleted"}


@router.post("/webhooks/{hook_id}/test")
async def test_webhook(
    hook_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Send a test payload to a webhook and record the delivery."""
    import httpx
    setting = db.query(SystemSettings).filter(SystemSettings.key == "webhooks").first()
    if not setting:
        raise HTTPException(status_code=404, detail="Webhook not found")
    hooks = json.loads(setting.value or "[]")
    hook = next((h for h in hooks if h["id"] == hook_id), None)
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    payload = {
        "event": "test",
        "message": "Test webhook from Depl0y",
        "webhook_name": hook["name"],
        "webhook_id": hook_id,
    }
    headers = {"Content-Type": "application/json", "X-Depl0y-Event": "test"}
    if hook.get("secret"):
        import hmac
        import hashlib
        body = json.dumps(payload).encode()
        sig = hmac.new(hook["secret"].encode(), body, hashlib.sha256).hexdigest()
        headers["X-Depl0y-Signature"] = f"sha256={sig}"

    status_code = None
    success = False
    response_text = ""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(hook["url"], json=payload, headers=headers, timeout=10)
        status_code = resp.status_code
        success = 200 <= resp.status_code < 300
        response_text = resp.text[:500]
        logger.info(f"Test webhook sent to {hook['url']}: HTTP {resp.status_code}")
    except Exception as e:
        response_text = str(e)[:500]
        logger.error(f"Failed to send test webhook to {hook['url']}: {e}")
    finally:
        # Record delivery
        delivery = WebhookDelivery(
            webhook_id=hook_id,
            event="test",
            status_code=status_code,
            success=success,
            response_body=response_text,
        )
        db.add(delivery)
        db.commit()

    if not success and status_code is None:
        raise HTTPException(status_code=500, detail=f"Failed to send webhook: {response_text}")

    return {"status": "sent", "response_code": status_code, "response_text": response_text, "success": success}


@router.get("/webhooks/{hook_id}/deliveries")
async def get_webhook_deliveries(
    hook_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get the last 10 delivery attempts for a webhook."""
    deliveries = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.webhook_id == hook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(10)
        .all()
    )
    return {
        "deliveries": [
            {
                "id": d.id,
                "event": d.event,
                "status_code": d.status_code,
                "success": d.success,
                "response_body": d.response_body,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in deliveries
        ]
    }


# ── Notification settings (system-wide, admin only) ──────────────────────────

class NotificationRulesRequest(BaseModel):
    notify_vm_start: bool = False
    notify_vm_stop: bool = False
    notify_task_failure: bool = True
    notify_user_login: bool = False


@router.get("/settings")
async def get_notification_settings(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get system-wide notification rules."""
    setting = db.query(SystemSettings).filter(SystemSettings.key == "notification_rules").first()
    if not setting:
        return {
            "notify_vm_start": False,
            "notify_vm_stop": False,
            "notify_task_failure": True,
            "notify_user_login": False,
        }
    return json.loads(setting.value)


@router.put("/settings")
async def update_notification_settings(
    data: NotificationRulesRequest,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update system-wide notification rules."""
    setting = db.query(SystemSettings).filter(SystemSettings.key == "notification_rules").first()
    value = json.dumps(data.dict())
    if not setting:
        setting = SystemSettings(
            key="notification_rules",
            value=value,
            description="In-app notification trigger rules",
        )
        db.add(setting)
    else:
        setting.value = value
    db.commit()
    return data.dict()
