"""VM Agent API — push agent registration, scan reporting, and management"""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_admin
from app.core.config import settings
from app.core.database import get_db
from app.models.database import (
    ScanSeverity,
    ScanStatus,
    ScanType,
    SystemSettings,
    VirtualMachine,
    VmAgent,
    VmScanResult,
)
from app.models import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AgentRegisterRequest(BaseModel):
    hostname: str
    os_info: Optional[str] = None
    agent_version: Optional[str] = None
    vm_id: Optional[int] = None


class AgentRegisterResponse(BaseModel):
    agent_id: int
    token: str
    hostname: str


class ScanResultItem(BaseModel):
    scan_type: ScanType
    status: ScanStatus
    result_json: Optional[str] = None
    summary: Optional[str] = None
    severity: Optional[ScanSeverity] = ScanSeverity.INFO


class AgentReportRequest(BaseModel):
    hostname: Optional[str] = None
    os_info: Optional[str] = None
    agent_version: Optional[str] = None
    scans: List[ScanResultItem]


class AgentResponse(BaseModel):
    id: int
    vm_id: Optional[int]
    hostname: Optional[str]
    os_info: Optional[str]
    agent_version: Optional[str]
    enabled: bool
    last_seen: Optional[datetime]
    registered_at: datetime
    scan_count: int


class ScanResultResponse(BaseModel):
    id: int
    vm_agent_id: int
    scan_type: str
    status: str
    result_json: Optional[str]
    summary: Optional[str]
    severity: str
    scanned_at: datetime


class LinuxAgentSettings(BaseModel):
    enabled: bool
    ai_enabled: bool = False


# ---------------------------------------------------------------------------
# Helper: token-authenticated agent lookup
# ---------------------------------------------------------------------------

def _get_agent_by_token(authorization: str, db: Session) -> VmAgent:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[len("Bearer "):]
    agent = db.query(VmAgent).filter(VmAgent.token == token, VmAgent.enabled == True).first()
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid or revoked agent token")
    return agent


def _get_depl0y_host() -> str:
    return getattr(settings, "DEPL0Y_HOST", "http://localhost")


# ---------------------------------------------------------------------------
# Agent self-registration (no user auth)
# ---------------------------------------------------------------------------

@router.post("/register", response_model=AgentRegisterResponse, status_code=201)
def register_agent(
    payload: AgentRegisterRequest,
    db: Session = Depends(get_db),
):
    """VM calls this once to register itself and receive a bearer token."""
    setting = db.query(SystemSettings).filter(
        SystemSettings.key == "linux_vm_agent_enabled"
    ).first()
    if setting and setting.value == "false":
        raise HTTPException(status_code=403, detail="Linux VM agent feature is disabled")

    if payload.vm_id:
        vm = db.query(VirtualMachine).filter(VirtualMachine.id == payload.vm_id).first()
        if not vm:
            raise HTTPException(status_code=404, detail="VM not found")

    token = str(uuid.uuid4())
    agent = VmAgent(
        vm_id=payload.vm_id,
        token=token,
        hostname=payload.hostname,
        os_info=payload.os_info,
        agent_version=payload.agent_version,
        enabled=True,
        registered_at=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    logger.info(f"VM agent registered: hostname={payload.hostname}, agent_id={agent.id}")
    return AgentRegisterResponse(agent_id=agent.id, token=token, hostname=agent.hostname or "")


# ---------------------------------------------------------------------------
# Agent scan report (bearer token auth)
# ---------------------------------------------------------------------------

@router.post("/report", status_code=200)
def report_scans(
    payload: AgentReportRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """Agent POSTs scan results authenticated via Bearer token."""
    agent = _get_agent_by_token(authorization or "", db)

    agent.last_seen = datetime.utcnow()
    if payload.hostname:
        agent.hostname = payload.hostname
    if payload.os_info:
        agent.os_info = payload.os_info
    if payload.agent_version:
        agent.agent_version = payload.agent_version

    for scan in payload.scans:
        result = VmScanResult(
            vm_agent_id=agent.id,
            scan_type=scan.scan_type,
            status=scan.status,
            result_json=scan.result_json,
            summary=scan.summary,
            severity=scan.severity or ScanSeverity.INFO,
            scanned_at=datetime.utcnow(),
        )
        db.add(result)

    db.commit()
    logger.info(f"Agent {agent.id} ({agent.hostname}) reported {len(payload.scans)} scan(s)")
    return {"received": len(payload.scans)}


# ---------------------------------------------------------------------------
# Install script (served by token, no user auth)
# ---------------------------------------------------------------------------

@router.get("/install.sh", response_class=PlainTextResponse)
def get_install_script(token: str, db: Session = Depends(get_db)):
    """Serve the agent install shell script for a given token."""
    agent = db.query(VmAgent).filter(VmAgent.token == token).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Invalid token")

    depl0y_host = _get_depl0y_host()

    script = f"""#!/bin/bash
set -e
DEPL0Y_HOST="{depl0y_host}"
AGENT_TOKEN="{token}"
AGENT_SCRIPT="/opt/depl0y-agent/agent.py"

echo "Installing Depl0y VM Agent..."
mkdir -p /opt/depl0y-agent

cat > "$AGENT_SCRIPT" << 'AGENT_SCRIPT_EOF'
#!/usr/bin/env python3
# Depl0y VM Agent - runs scans and reports results
import json, os, subprocess, urllib.request, urllib.error

DEPL0Y_HOST = os.environ.get("DEPL0Y_HOST", "{depl0y_host}")
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "{token}")
REPORT_URL = f"{{DEPL0Y_HOST}}/api/v1/vm-agent/report"


def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        return r.stdout.strip()
    except Exception as e:
        return f"ERROR: {{e}}"


def scan_os_updates():
    out = run("apt list --upgradable 2>/dev/null | tail -n +2")
    pkgs = [l for l in out.splitlines() if l.strip()]
    return {{
        "scan_type": "os_updates", "status": "completed",
        "result_json": json.dumps({{"count": len(pkgs), "packages": pkgs[:50]}}),
        "summary": f"{{len(pkgs)}} package(s) available for update",
        "severity": "warning" if pkgs else "info",
    }}


def scan_security():
    checks = {{
        "open_ports": run("ss -tlnp 2>/dev/null | tail -n +2"),
        "failed_logins": run("lastb -n 10 2>/dev/null || echo N/A"),
    }}
    return {{
        "scan_type": "security", "status": "completed",
        "result_json": json.dumps(checks),
        "summary": "Basic security checks completed",
        "severity": "info",
    }}


def scan_dependencies():
    out = run("pip3 list --outdated --format=json 2>/dev/null || echo '[]'")
    return {{
        "scan_type": "dependencies", "status": "completed",
        "result_json": out,
        "summary": "Dependency scan completed",
        "severity": "info",
    }}


def report(scans):
    data = {{
        "hostname": run("hostname"),
        "os_info": run("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'"),
        "agent_version": "1.0.0",
        "scans": scans,
    }}
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        REPORT_URL, data=body,
        headers={{"Content-Type": "application/json", "Authorization": f"Bearer {{AGENT_TOKEN}}"}},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"Reported {{len(scans)}} scan(s): HTTP {{resp.status}}")
    except urllib.error.URLError as e:
        print(f"Report failed: {{e}}")


if __name__ == "__main__":
    report([scan_os_updates(), scan_security(), scan_dependencies()])
AGENT_SCRIPT_EOF

chmod +x "$AGENT_SCRIPT"

cat > /etc/systemd/system/depl0y-agent.service << 'SERVICE_EOF'
[Unit]
Description=Depl0y VM Agent
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/depl0y-agent/agent.py
EnvironmentFile=/opt/depl0y-agent/env
StandardOutput=journal
StandardError=journal
SERVICE_EOF

cat > /etc/systemd/system/depl0y-agent.timer << 'TIMER_EOF'
[Unit]
Description=Run Depl0y VM Agent every 12 hours

[Timer]
OnBootSec=5min
OnUnitActiveSec=12h

[Install]
WantedBy=timers.target
TIMER_EOF

printf 'DEPL0Y_HOST=%s\\nAGENT_TOKEN=%s\\n' "$DEPL0Y_HOST" "$AGENT_TOKEN" > /opt/depl0y-agent/env

systemctl daemon-reload
systemctl enable depl0y-agent.timer
systemctl start depl0y-agent.timer

echo "Running initial scan..."
DEPL0Y_HOST="$DEPL0Y_HOST" AGENT_TOKEN="$AGENT_TOKEN" python3 "$AGENT_SCRIPT"
echo "Depl0y agent installed successfully."
"""
    return PlainTextResponse(script, media_type="text/plain")


# ---------------------------------------------------------------------------
# Admin / management endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[AgentResponse])
def list_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all registered agents (admin only)."""
    agents = db.query(VmAgent).all()
    return [
        AgentResponse(
            id=a.id, vm_id=a.vm_id, hostname=a.hostname, os_info=a.os_info,
            agent_version=a.agent_version, enabled=a.enabled, last_seen=a.last_seen,
            registered_at=a.registered_at, scan_count=len(a.scan_results),
        )
        for a in agents
    ]


@router.get("/settings/linux-agent")
def get_linux_agent_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get Linux VM agent feature settings."""
    enabled_s = db.query(SystemSettings).filter(SystemSettings.key == "linux_vm_agent_enabled").first()
    ai_s = db.query(SystemSettings).filter(SystemSettings.key == "linux_vm_agent_ai_enabled").first()
    return {
        "enabled": (enabled_s.value == "true") if enabled_s else False,
        "ai_enabled": (ai_s.value == "true") if ai_s else False,
    }


@router.put("/settings/linux-agent")
def update_linux_agent_settings(
    payload: LinuxAgentSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Toggle Linux VM agent feature on/off."""
    for key, value in [
        ("linux_vm_agent_enabled", str(payload.enabled).lower()),
        ("linux_vm_agent_ai_enabled", str(payload.ai_enabled).lower()),
    ]:
        setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
        if setting:
            setting.value = value
        else:
            db.add(SystemSettings(key=key, value=value))
    db.commit()
    return {"enabled": payload.enabled, "ai_enabled": payload.ai_enabled}


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get agent status for a specific agent."""
    agent = db.query(VmAgent).filter(VmAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse(
        id=agent.id, vm_id=agent.vm_id, hostname=agent.hostname, os_info=agent.os_info,
        agent_version=agent.agent_version, enabled=agent.enabled, last_seen=agent.last_seen,
        registered_at=agent.registered_at, scan_count=len(agent.scan_results),
    )


@router.get("/{agent_id}/scans", response_model=List[ScanResultResponse])
def get_agent_scans(
    agent_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get scan results for a specific agent."""
    agent = db.query(VmAgent).filter(VmAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    scans = (
        db.query(VmScanResult)
        .filter(VmScanResult.vm_agent_id == agent_id)
        .order_by(VmScanResult.scanned_at.desc())
        .limit(limit)
        .all()
    )
    return [
        ScanResultResponse(
            id=s.id, vm_agent_id=s.vm_agent_id, scan_type=s.scan_type.value,
            status=s.status.value, result_json=s.result_json, summary=s.summary,
            severity=s.severity.value, scanned_at=s.scanned_at,
        )
        for s in scans
    ]


@router.delete("/{agent_id}", status_code=200)
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Remove an agent registration."""
    agent = db.query(VmAgent).filter(VmAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()
    return {"deleted": agent_id}


@router.get("/{agent_id}/install-command")
def get_install_command(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Return the curl install command for this agent."""
    agent = db.query(VmAgent).filter(VmAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    depl0y_host = _get_depl0y_host()
    command = f"curl -fsSL '{depl0y_host}/api/v1/vm-agent/install.sh?token={agent.token}' | bash"
    return {"command": command, "token": agent.token}
