"""VM Agent API — push agent enrollment, registration, scan reporting, and management

Onboarding: an administrator issues a short-lived, single-use enrollment token
for one VM (POST /enrollments). The VM runs the install command, which calls
/register with that token and receives its own agent token. The VM the agent
belongs to comes from the enrollment, never from the request.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import update
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
    VmAgentEnrollment,
    VmScanResult,
)
from app.models import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Limits on what an agent can send. The request-body caps for these paths are
# enforced before parsing by BodySizeLimitMiddleware (see main.py).
MAX_SCANS_PER_REPORT = 10
MAX_RESULT_JSON = 256 * 1024
MAX_STORED_SCANS_PER_AGENT = 500
MIN_REPORT_INTERVAL_S = 10
ENROLLMENT_TTL_DEFAULT_MIN = 60
ENROLLMENT_TTL_MAX_MIN = 24 * 60
REGISTER_BODY_LIMIT = 16 * 1024
REPORT_BODY_LIMIT = 4 * 1024 * 1024


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AgentRegisterRequest(BaseModel):
    hostname: str = Field(min_length=1, max_length=253)
    os_info: Optional[str] = Field(default=None, max_length=255)
    agent_version: Optional[str] = Field(default=None, max_length=50)
    # Optional cross-check only: it must match the VM the enrollment was issued for.
    vm_id: Optional[int] = None


class AgentRegisterResponse(BaseModel):
    agent_id: int
    token: str
    hostname: str
    vm_id: int


class ScanResultItem(BaseModel):
    scan_type: ScanType
    status: ScanStatus
    result_json: Optional[str] = Field(default=None, max_length=MAX_RESULT_JSON)
    summary: Optional[str] = Field(default=None, max_length=2000)
    severity: Optional[ScanSeverity] = ScanSeverity.INFO


class AgentReportRequest(BaseModel):
    hostname: Optional[str] = Field(default=None, max_length=253)
    os_info: Optional[str] = Field(default=None, max_length=255)
    agent_version: Optional[str] = Field(default=None, max_length=50)
    scans: List[ScanResultItem] = Field(max_length=MAX_SCANS_PER_REPORT)


class EnrollmentCreateRequest(BaseModel):
    vm_id: int
    ttl_minutes: int = Field(default=ENROLLMENT_TTL_DEFAULT_MIN, ge=5, le=ENROLLMENT_TTL_MAX_MIN)


class EnrollmentResponse(BaseModel):
    id: int
    vm_id: int
    vm_name: Optional[str]
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime]
    agent_id: Optional[int]
    status: str  # pending | used | expired


class EnrollmentCreatedResponse(EnrollmentResponse):
    token: str
    install_command: str


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
# Helpers
# ---------------------------------------------------------------------------

def _bearer(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[len("Bearer "):].strip()
    if not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return token


def _get_agent_by_token(authorization: str, db: Session) -> VmAgent:
    token = _bearer(authorization)
    agent = db.query(VmAgent).filter(VmAgent.token == token, VmAgent.enabled == True).first()
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid or revoked agent token")
    return agent


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _feature_enabled(db: Session) -> bool:
    row = db.query(SystemSettings).filter(SystemSettings.key == "linux_vm_agent_enabled").first()
    # Same default as GET /settings/linux-agent: off until an admin turns it on.
    return bool(row and row.value == "true")


def _require_feature(db: Session):
    if not _feature_enabled(db):
        raise HTTPException(status_code=403, detail="Linux VM agent feature is disabled")


def _audit(db: Session, action: str, request: Request, user_id=None, resource_id=None, **details):
    from app.api.audit import log_audit_event
    log_audit_event(db, action, user_id=user_id, resource_type="vm_agent", resource_id=resource_id,
                    details=details or None,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"))


def _get_depl0y_host() -> str:
    return getattr(settings, "DEPL0Y_HOST", "http://localhost")


def _enrollment_out(e: VmAgentEnrollment, db: Session) -> dict:
    vm = db.query(VirtualMachine).filter(VirtualMachine.id == e.vm_id).first()
    status = "used" if e.used_at else ("expired" if e.expires_at <= datetime.utcnow() else "pending")
    return dict(id=e.id, vm_id=e.vm_id, vm_name=vm.name if vm else None, created_at=e.created_at,
                expires_at=e.expires_at, used_at=e.used_at, agent_id=e.agent_id, status=status)


# ---------------------------------------------------------------------------
# Enrollment tokens (admin)
# ---------------------------------------------------------------------------

@router.post("/enrollments", response_model=EnrollmentCreatedResponse, status_code=201)
def create_enrollment(
    payload: EnrollmentCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Issue a single-use enrollment token bound to one VM. The token is shown once."""
    _require_feature(db)
    vm = db.query(VirtualMachine).filter(VirtualMachine.id == payload.vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    e = VmAgentEnrollment(token_hash=_hash_token(token), vm_id=vm.id, created_by=current_user.id,
                          created_at=now, expires_at=now + timedelta(minutes=payload.ttl_minutes))
    db.add(e)
    db.commit()
    db.refresh(e)
    _audit(db, "vm_agent_enrollment_created", request, user_id=current_user.id, resource_id=e.id,
           vm_id=vm.id, expires_at=e.expires_at.isoformat())
    command = (f"curl -fsSL '{_get_depl0y_host()}/api/v1/vm-agent/install.sh' "
               f"| sudo bash -s -- '{token}'")
    return EnrollmentCreatedResponse(**_enrollment_out(e, db), token=token, install_command=command)


@router.get("/enrollments", response_model=List[EnrollmentResponse])
def list_enrollments(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    rows = db.query(VmAgentEnrollment).order_by(VmAgentEnrollment.created_at.desc()).limit(200).all()
    return [EnrollmentResponse(**_enrollment_out(e, db)) for e in rows]


@router.delete("/enrollments/{enrollment_id}")
def revoke_enrollment(
    enrollment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Revoke an unused enrollment token."""
    e = db.query(VmAgentEnrollment).filter(VmAgentEnrollment.id == enrollment_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    if e.used_at:
        raise HTTPException(status_code=409, detail="Enrollment already used; delete the agent instead")
    vm_id = e.vm_id
    db.delete(e)
    db.commit()
    _audit(db, "vm_agent_enrollment_revoked", request, user_id=current_user.id,
           resource_id=enrollment_id, vm_id=vm_id)
    return {"deleted": enrollment_id}


# ---------------------------------------------------------------------------
# Agent registration (enrollment-token auth)
# ---------------------------------------------------------------------------

_BAD_ENROLLMENT = "Invalid, expired or already used enrollment token"


@router.post("/register", response_model=AgentRegisterResponse, status_code=201)
def register_agent(
    payload: AgentRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """VM calls this once with its enrollment token and receives an agent token."""
    _require_feature(db)
    token_hash = _hash_token(_bearer(authorization))
    now = datetime.utcnow()

    e = db.query(VmAgentEnrollment).filter(VmAgentEnrollment.token_hash == token_hash).first()
    if not e or e.used_at or e.expires_at <= now:
        _audit(db, "vm_agent_register_rejected", request, reason="bad_token",
               enrollment_id=e.id if e else None)
        raise HTTPException(status_code=401, detail=_BAD_ENROLLMENT)
    if payload.vm_id is not None and payload.vm_id != e.vm_id:
        # Not consumed, so the VM it was issued for can still use it.
        _audit(db, "vm_agent_register_rejected", request, reason="vm_mismatch",
               enrollment_id=e.id, requested_vm_id=payload.vm_id, enrolled_vm_id=e.vm_id)
        raise HTTPException(status_code=403, detail="Enrollment token was issued for a different VM")
    enrollment_id, vm_id = e.id, e.vm_id
    if not db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first():
        raise HTTPException(status_code=404, detail="VM not found")

    # Consume atomically: only one request can flip used_at from NULL.
    claimed = db.execute(
        update(VmAgentEnrollment)
        .where(VmAgentEnrollment.id == enrollment_id, VmAgentEnrollment.used_at.is_(None),
               VmAgentEnrollment.expires_at > now)
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    ).rowcount
    if claimed != 1:
        db.rollback()
        _audit(db, "vm_agent_register_rejected", request, reason="reused", enrollment_id=enrollment_id)
        raise HTTPException(status_code=401, detail=_BAD_ENROLLMENT)

    agent = VmAgent(
        vm_id=vm_id,
        token=str(uuid.uuid4()),
        hostname=payload.hostname,
        os_info=payload.os_info,
        agent_version=payload.agent_version,
        enabled=True,
        registered_at=now,
    )
    db.add(agent)
    db.flush()
    db.execute(update(VmAgentEnrollment).where(VmAgentEnrollment.id == enrollment_id)
               .values(agent_id=agent.id).execution_options(synchronize_session=False))
    db.commit()
    db.refresh(agent)
    _audit(db, "vm_agent_registered", request, resource_id=agent.id, vm_id=vm_id,
           enrollment_id=enrollment_id, hostname=payload.hostname)
    logger.info(f"VM agent registered: hostname={payload.hostname}, agent_id={agent.id}, vm_id={vm_id}")
    return AgentRegisterResponse(agent_id=agent.id, token=agent.token,
                                 hostname=agent.hostname or "", vm_id=vm_id)


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
    _require_feature(db)

    now = datetime.utcnow()
    if agent.last_seen and (now - agent.last_seen).total_seconds() < MIN_REPORT_INTERVAL_S:
        raise HTTPException(status_code=429, detail="Reporting too often",
                            headers={"Retry-After": str(MIN_REPORT_INTERVAL_S)})

    agent.last_seen = now
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
            scanned_at=now,
        )
        db.add(result)
    db.flush()

    # Keep each agent's stored history bounded.
    keep = (db.query(VmScanResult.id).filter(VmScanResult.vm_agent_id == agent.id)
            .order_by(VmScanResult.scanned_at.desc(), VmScanResult.id.desc())
            .limit(MAX_STORED_SCANS_PER_AGENT))
    db.query(VmScanResult).filter(
        VmScanResult.vm_agent_id == agent.id, VmScanResult.id.notin_(keep.scalar_subquery())
    ).delete(synchronize_session=False)

    db.commit()
    logger.info(f"Agent {agent.id} ({agent.hostname}) reported {len(payload.scans)} scan(s)")
    return {"received": len(payload.scans)}


# ---------------------------------------------------------------------------
# Install script (no user auth; holds no secret unless an agent token is given)
# ---------------------------------------------------------------------------

_REGISTER_SNIPPET = r'''ENROLL_TOKEN="${1:-$DEPL0Y_ENROLL_TOKEN}"
if [ -z "$ENROLL_TOKEN" ]; then
  echo "Usage: curl -fsSL '<depl0y>/api/v1/vm-agent/install.sh' | sudo bash -s -- <enrollment-token>" >&2
  exit 1
fi
AGENT_TOKEN=$(DEPL0Y_HOST="$DEPL0Y_HOST" ENROLL_TOKEN="$ENROLL_TOKEN" python3 - <<'REGISTER_EOF'
import json, os, socket, sys, urllib.request, urllib.error
body = json.dumps({"hostname": socket.gethostname()[:253], "agent_version": "1.1.0"}).encode()
req = urllib.request.Request(
    os.environ["DEPL0Y_HOST"] + "/api/v1/vm-agent/register", data=body, method="POST",
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["ENROLL_TOKEN"]})
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(json.load(resp)["token"])
except urllib.error.HTTPError as e:
    sys.stderr.write("Registration failed: HTTP %d %s\n" % (e.code, e.read().decode(errors="replace")[:300]))
    sys.exit(1)
REGISTER_EOF
)
unset ENROLL_TOKEN'''


def _agent_py(depl0y_host: str) -> str:
    return f"""#!/usr/bin/env python3
# Depl0y VM Agent - runs scans and reports results
import json, os, subprocess, urllib.request, urllib.error

DEPL0Y_HOST = os.environ.get("DEPL0Y_HOST", "{depl0y_host}")
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "")
REPORT_URL = f"{{DEPL0Y_HOST}}/api/v1/vm-agent/report"
MAX_RESULT_JSON = {MAX_RESULT_JSON}


# Run a command as an argument list (no shell). Returns stdout, or None if it failed.
def run(argv):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    except Exception:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def os_pretty_name():
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def scan_os_updates():
    out = run(["apt", "list", "--upgradable"]) or ""
    pkgs = [l for l in out.splitlines() if l.strip() and not l.startswith("Listing")]
    return {{
        "scan_type": "os_updates", "status": "completed",
        "result_json": json.dumps({{"count": len(pkgs), "packages": pkgs[:50]}}),
        "summary": f"{{len(pkgs)}} package(s) available for update",
        "severity": "warning" if pkgs else "info",
    }}


def scan_security():
    ports = run(["ss", "-tlnp"]) or ""
    checks = {{
        "open_ports": "\\n".join(ports.splitlines()[1:200]),
        "failed_logins": run(["lastb", "-n", "10"]) or "N/A",
    }}
    return {{
        "scan_type": "security", "status": "completed",
        "result_json": json.dumps(checks)[:MAX_RESULT_JSON],
        "summary": "Basic security checks completed",
        "severity": "info",
    }}


def scan_dependencies():
    out = run(["pip3", "list", "--outdated", "--format=json"]) or "[]"
    if len(out) > MAX_RESULT_JSON:
        out = json.dumps({{"truncated": True}})
    return {{
        "scan_type": "dependencies", "status": "completed",
        "result_json": out,
        "summary": "Dependency scan completed",
        "severity": "info",
    }}


def report(scans):
    data = {{
        "hostname": (run(["hostname"]) or "")[:253],
        "os_info": os_pretty_name()[:255],
        "agent_version": "1.1.0",
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
"""


def _install_script(depl0y_host: str, agent_token: Optional[str]) -> str:
    # With an agent token: reinstall an agent that is already registered.
    # Without: a new VM trades its one-time enrollment token (first argument)
    # for an agent token.
    get_token = f'AGENT_TOKEN="{agent_token}"' if agent_token else _REGISTER_SNIPPET
    return f"""#!/bin/bash
set -e
umask 077
DEPL0Y_HOST="{depl0y_host}"
AGENT_SCRIPT="/opt/depl0y-agent/agent.py"

echo "Installing Depl0y VM Agent..."
{get_token}
mkdir -p /opt/depl0y-agent

cat > "$AGENT_SCRIPT" << 'AGENT_SCRIPT_EOF'
{_agent_py(depl0y_host)}AGENT_SCRIPT_EOF

chmod 700 "$AGENT_SCRIPT"

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
chmod 644 /etc/systemd/system/depl0y-agent.service /etc/systemd/system/depl0y-agent.timer

printf 'DEPL0Y_HOST=%s\\nAGENT_TOKEN=%s\\n' "$DEPL0Y_HOST" "$AGENT_TOKEN" > /opt/depl0y-agent/env
chmod 600 /opt/depl0y-agent/env

systemctl daemon-reload
systemctl enable depl0y-agent.timer
systemctl start depl0y-agent.timer

echo "Running initial scan..."
DEPL0Y_HOST="$DEPL0Y_HOST" AGENT_TOKEN="$AGENT_TOKEN" python3 "$AGENT_SCRIPT"
echo "Depl0y agent installed successfully."
"""


@router.get("/install.sh", response_class=PlainTextResponse)
def get_install_script(token: Optional[str] = None, db: Session = Depends(get_db)):
    """Serve the agent install script.

    Without `token` the script contains no secret: it takes the enrollment
    token as its first argument. With an existing agent's token (from the
    admin-only install-command endpoint) it reinstalls that agent.
    """
    _require_feature(db)
    if token is not None:
        agent = db.query(VmAgent).filter(VmAgent.token == token, VmAgent.enabled == True).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Invalid token")
    return PlainTextResponse(_install_script(_get_depl0y_host(), token), media_type="text/plain")


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
