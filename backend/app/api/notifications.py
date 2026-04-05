"""Webhook notifications for VM events"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import get_db
from app.api.auth import require_admin
from app.models.database import SystemSettings
import logging
import json
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()


class WebhookCreate(BaseModel):
    url: str
    name: str
    events: List[str]  # ["vm.start", "vm.stop", "vm.create", "vm.delete", "vm.error"]
    secret: Optional[str] = None
    enabled: bool = True


@router.get("/webhooks")
async def list_webhooks(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List configured webhooks"""
    setting = db.query(SystemSettings).filter(SystemSettings.key == "webhooks").first()
    if not setting:
        return {"webhooks": []}
    return {"webhooks": json.loads(setting.value or "[]")}


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
    """Send a test payload to a webhook"""
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
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(hook["url"], json=payload, headers=headers, timeout=10)
        logger.info(f"Test webhook sent to {hook['url']}: HTTP {resp.status_code}")
        return {"status": "sent", "response_code": resp.status_code, "response_text": resp.text[:500]}
    except Exception as e:
        logger.error(f"Failed to send test webhook to {hook['url']}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send webhook: {str(e)}")
