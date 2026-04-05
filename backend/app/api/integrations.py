"""Integrations API — Slack, PagerDuty, Grafana/InfluxDB, OIDC settings"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.core.database import get_db
from app.models.database import SystemSettings
from app.api.auth import require_admin
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    return row.value if row else default


def _set_setting(db: Session, key: str, value: str, description: str = "") -> None:
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if row:
        row.value = value
    else:
        row = SystemSettings(key=key, value=value, description=description)
        db.add(row)
    db.commit()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SlackSettings(BaseModel):
    webhook_url: Optional[str] = ""
    channel: Optional[str] = ""
    events: List[str] = []


class PagerDutySettings(BaseModel):
    integration_key: Optional[str] = ""
    routing_key: Optional[str] = ""
    alert_node_offline: bool = True
    alert_storage_critical: bool = True
    alert_backup_failure: bool = True
    severity_vm_stopped: str = "warning"
    severity_node_offline: str = "critical"


class InfluxDBSettings(BaseModel):
    host: Optional[str] = ""
    database: Optional[str] = ""
    token: Optional[str] = ""
    interval_seconds: int = 60


class OIDCSettings(BaseModel):
    provider_url: Optional[str] = ""
    client_id: Optional[str] = ""
    client_secret: Optional[str] = ""
    scopes: Optional[str] = "openid email profile"
    callback_url: Optional[str] = ""
    enabled: bool = False


# ── Slack ─────────────────────────────────────────────────────────────────────

@router.get("/slack")
async def get_slack_settings(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get current Slack integration settings."""
    url = _get_setting(db, "slack_webhook_url")
    channel = _get_setting(db, "slack_channel")
    events_raw = _get_setting(db, "slack_events", "[]")
    try:
        events = json.loads(events_raw)
    except Exception:
        events = []
    # Mask webhook URL — return only last 8 chars after the last slash
    masked_url = ""
    if url:
        parts = url.rsplit("/", 1)
        masked_url = (parts[0] + "/****" + parts[1][-8:]) if len(parts) > 1 and len(parts[1]) > 8 else url
    return {"webhook_url": masked_url, "channel": channel, "events": events, "configured": bool(url)}


@router.put("/slack")
async def save_slack_settings(
    data: SlackSettings,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Save Slack integration settings."""
    if data.webhook_url and not data.webhook_url.startswith("****"):
        _set_setting(db, "slack_webhook_url", data.webhook_url, "Slack incoming webhook URL")
    if data.channel is not None:
        _set_setting(db, "slack_channel", data.channel, "Slack channel name")
    _set_setting(db, "slack_events", json.dumps(data.events), "Slack notification event whitelist")
    logger.info(f"Slack settings updated by {current_user.username}")
    return {"success": True}


@router.post("/slack/test")
async def test_slack(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Send a test Slack message."""
    import httpx
    url = _get_setting(db, "slack_webhook_url")
    if not url:
        raise HTTPException(status_code=400, detail="Slack webhook URL is not configured")
    payload = {
        "text": f":white_check_mark: *Depl0y test notification* — Slack integration is working correctly! (sent by {current_user.username})",
        "attachments": [
            {
                "color": "#36a64f",
                "fields": [
                    {"title": "Source", "value": "Depl0y", "short": True},
                    {"title": "Event", "value": "test", "short": True},
                ],
            }
        ],
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Slack returned HTTP {resp.status_code}: {resp.text[:200]}",
            )
        return {"success": True, "message": "Test message sent to Slack"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to reach Slack: {exc}")


# ── PagerDuty ─────────────────────────────────────────────────────────────────

@router.get("/pagerduty")
async def get_pagerduty_settings(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get PagerDuty integration settings."""
    raw = _get_setting(db, "pagerduty_settings", "{}")
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    # Mask integration/routing keys
    for k in ("integration_key", "routing_key"):
        v = data.get(k, "")
        if v and len(v) > 8:
            data[k] = "****" + v[-4:]
    return data


@router.put("/pagerduty")
async def save_pagerduty_settings(
    data: PagerDutySettings,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Save PagerDuty integration settings."""
    existing_raw = _get_setting(db, "pagerduty_settings", "{}")
    try:
        existing = json.loads(existing_raw)
    except Exception:
        existing = {}

    new_data = data.dict()
    # Preserve existing keys if masked values submitted
    for k in ("integration_key", "routing_key"):
        v = new_data.get(k, "")
        if v and v.startswith("****"):
            new_data[k] = existing.get(k, "")

    _set_setting(db, "pagerduty_settings", json.dumps(new_data), "PagerDuty integration settings")
    logger.info(f"PagerDuty settings updated by {current_user.username}")
    return {"success": True}


# ── InfluxDB / Grafana ────────────────────────────────────────────────────────

@router.get("/influxdb")
async def get_influxdb_settings(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get InfluxDB push settings."""
    raw = _get_setting(db, "influxdb_settings", "{}")
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    # Mask token
    tok = data.get("token", "")
    if tok and len(tok) > 8:
        data["token"] = "****" + tok[-4:]
    return data


@router.put("/influxdb")
async def save_influxdb_settings(
    data: InfluxDBSettings,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Save InfluxDB push settings."""
    existing_raw = _get_setting(db, "influxdb_settings", "{}")
    try:
        existing = json.loads(existing_raw)
    except Exception:
        existing = {}

    new_data = data.dict()
    # Preserve existing token if masked
    tok = new_data.get("token", "")
    if tok and tok.startswith("****"):
        new_data["token"] = existing.get("token", "")

    _set_setting(db, "influxdb_settings", json.dumps(new_data), "InfluxDB push metrics settings")
    logger.info(f"InfluxDB settings updated by {current_user.username}")
    return {"success": True}


# ── OIDC / SSO ────────────────────────────────────────────────────────────────

@router.get("/oidc")
async def get_oidc_settings(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get OIDC/SSO configuration."""
    raw = _get_setting(db, "oidc_settings", "{}")
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    # Mask client_secret
    sec = data.get("client_secret", "")
    if sec and len(sec) > 8:
        data["client_secret"] = "****" + sec[-4:]
    return data


@router.put("/oidc")
async def save_oidc_settings(
    data: OIDCSettings,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Save OIDC/SSO configuration (UI only — actual auth flow is not yet implemented)."""
    existing_raw = _get_setting(db, "oidc_settings", "{}")
    try:
        existing = json.loads(existing_raw)
    except Exception:
        existing = {}

    new_data = data.dict()
    sec = new_data.get("client_secret", "")
    if sec and sec.startswith("****"):
        new_data["client_secret"] = existing.get("client_secret", "")

    _set_setting(db, "oidc_settings", json.dumps(new_data), "OIDC/SSO provider configuration")
    logger.info(f"OIDC settings updated by {current_user.username}")
    return {"success": True}


# ── Aggregated get/save for the Integrations.vue UI ──────────────────────────

@router.get("/all")
async def get_all_integration_settings(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return all integration settings in one call (Slack, PagerDuty, InfluxDB, OIDC)."""
    # Slack
    slack_url = _get_setting(db, "slack_webhook_url")
    slack_channel = _get_setting(db, "slack_channel")
    try:
        slack_events = json.loads(_get_setting(db, "slack_events", "[]"))
    except Exception:
        slack_events = []
    masked_slack_url = ""
    if slack_url:
        parts = slack_url.rsplit("/", 1)
        masked_slack_url = (parts[0] + "/****" + parts[1][-8:]) if len(parts) > 1 and len(parts[1]) > 8 else slack_url

    # PagerDuty
    pd_raw = _get_setting(db, "pagerduty_settings", "{}")
    try:
        pd = json.loads(pd_raw)
    except Exception:
        pd = {}
    for k in ("integration_key", "routing_key"):
        v = pd.get(k, "")
        if v and len(v) > 8:
            pd[k] = "****" + v[-4:]

    # InfluxDB
    influx_raw = _get_setting(db, "influxdb_settings", "{}")
    try:
        influx = json.loads(influx_raw)
    except Exception:
        influx = {}
    tok = influx.get("token", "")
    if tok and len(tok) > 8:
        influx["token"] = "****" + tok[-4:]

    # OIDC
    oidc_raw = _get_setting(db, "oidc_settings", "{}")
    try:
        oidc = json.loads(oidc_raw)
    except Exception:
        oidc = {}
    sec = oidc.get("client_secret", "")
    if sec and len(sec) > 8:
        oidc["client_secret"] = "****" + sec[-4:]

    return {
        "slack": {
            "webhook_url": masked_slack_url,
            "channel": slack_channel,
            "events": slack_events,
            "configured": bool(slack_url),
        },
        "pagerduty": pd,
        "influxdb": influx,
        "oidc": oidc,
    }
