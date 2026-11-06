"""Admin review of SSH server keys (enrollment, approval/rotation, removal)."""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.core.database import get_db
from app.models.database import SshHostKey, SystemSettings, User
from app.services import ssh_trust

logger = logging.getLogger(__name__)

router = APIRouter()


class HostKeyResponse(BaseModel):
    id: int
    host: str
    port: int
    key_type: str
    fingerprint: str
    status: str
    first_seen: datetime
    last_seen: datetime
    approved_at: Optional[datetime]
    approved_by: Optional[int]
    trusted_on_first_use: bool


class ScanRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)


class PolicyBody(BaseModel):
    policy: str = Field(pattern="^(tofu|strict)$")


def _out(r: SshHostKey) -> HostKeyResponse:
    return HostKeyResponse(
        id=r.id, host=r.host, port=r.port, key_type=r.key_type, fingerprint=r.fingerprint,
        status=r.status, first_seen=r.first_seen, last_seen=r.last_seen,
        approved_at=r.approved_at, approved_by=r.approved_by,
        trusted_on_first_use=r.status == "approved" and r.approved_by is None,
    )


def _get(db: Session, key_id: int) -> SshHostKey:
    row = db.query(SshHostKey).filter(SshHostKey.id == key_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Host key not found")
    return row


@router.get("/", response_model=List[HostKeyResponse])
def list_host_keys(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    rows = db.query(SshHostKey).order_by(SshHostKey.status.desc(), SshHostKey.host, SshHostKey.port).all()
    return [_out(r) for r in rows]


@router.post("/scan", response_model=HostKeyResponse)
def scan_host_key(body: ScanRequest, db: Session = Depends(get_db),
                  current_user: User = Depends(require_admin)):
    """Fetch a host's key (no login) and store it as pending, so the admin can
    compare the fingerprint with `ssh-keygen -lf /etc/ssh/ssh_host_*_key.pub`
    on the host before approving it."""
    try:
        row = ssh_trust.enroll_host_key(db, body.host, body.port, current_user.id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not read the SSH host key: {exc}")
    return _out(row)


@router.post("/{key_id}/approve", response_model=HostKeyResponse)
def approve_host_key(key_id: int, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin)):
    """Trust this key; any other approved key for the same host is retired."""
    return _out(ssh_trust.approve_host_key(db, _get(db, key_id), current_user.id))


@router.delete("/{key_id}")
def delete_host_key(key_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(require_admin)):
    """Reject a pending key, or forget an approved one."""
    ssh_trust.delete_host_key(db, _get(db, key_id), current_user.id)
    return {"deleted": key_id}


@router.get("/policy")
def get_policy(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return {"policy": ssh_trust.get_policy(db)}


@router.put("/policy")
def set_policy(body: PolicyBody, db: Session = Depends(get_db),
               current_user: User = Depends(require_admin)):
    from app.api.audit import log_audit_event
    row = db.query(SystemSettings).filter(SystemSettings.key == ssh_trust.POLICY_SETTING).first()
    old = row.value if row else "tofu"
    if row:
        row.value = body.policy
    else:
        db.add(SystemSettings(key=ssh_trust.POLICY_SETTING, value=body.policy,
                              description="SSH unknown-host policy: tofu or strict"))
    db.commit()
    log_audit_event(db, "ssh_host_key_policy_changed", user_id=current_user.id,
                    resource_type="system", details={"from": old, "to": body.policy})
    return {"policy": body.policy}
