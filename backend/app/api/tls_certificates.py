"""Admin review of pinned TLS certificates (Proxmox, PBS, BMC, VMware)."""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.core.database import get_db
from app.models.database import PBSServer, ProxmoxHost, SystemSettings, TlsCertificate, User
from app.services import tls_trust

logger = logging.getLogger(__name__)

router = APIRouter()


class CertificateResponse(BaseModel):
    id: int
    host: str
    port: int
    mode: str
    fingerprint: str
    subject: Optional[str]
    issuer: Optional[str]
    dns_names: List[str]
    not_after: Optional[datetime]
    status: str
    first_seen: datetime
    last_seen: datetime
    approved_at: Optional[datetime]
    approved_by: Optional[int]
    automatic: bool
    used_by: List[str]


class ScanRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=443, ge=1, le=65535)


class PolicyBody(BaseModel):
    policy: str = Field(pattern="^(tofu|strict)$")


def _users_of(db: Session) -> dict:
    out: dict = {}
    for h in db.query(ProxmoxHost).all():
        out.setdefault((h.hostname, h.port), []).append(f"Proxmox: {h.name}")
    for s in db.query(PBSServer).all():
        out.setdefault((s.hostname, s.port), []).append(f"PBS: {s.name}")
    return out


def _out(r: TlsCertificate, users: dict) -> CertificateResponse:
    return CertificateResponse(
        id=r.id, host=r.host, port=r.port, mode=r.mode,
        fingerprint=tls_trust.format_fingerprint(r.fingerprint),
        subject=r.subject, issuer=r.issuer,
        dns_names=[n for n in (r.dns_names or "").split(",") if n],
        not_after=r.not_after, status=r.status, first_seen=r.first_seen, last_seen=r.last_seen,
        approved_at=r.approved_at, approved_by=r.approved_by,
        automatic=r.status == "approved" and r.approved_by is None,
        used_by=users.get((r.host, r.port), []),
    )


def _get(db: Session, cert_id: int) -> TlsCertificate:
    row = db.query(TlsCertificate).filter(TlsCertificate.id == cert_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return row


@router.get("/", response_model=List[CertificateResponse])
def list_certificates(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    users = _users_of(db)
    rows = db.query(TlsCertificate).order_by(
        TlsCertificate.status.desc(), TlsCertificate.host, TlsCertificate.port).all()
    return [_out(r, users) for r in rows]


@router.post("/scan", response_model=CertificateResponse)
def scan_certificate(body: ScanRequest, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin)):
    """Fetch a host's certificate (nothing is sent) and store it as pending, so
    the admin can compare the fingerprint before approving it."""
    try:
        row = tls_trust.enroll(db, body.host, body.port, current_user.id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not read the TLS certificate: {exc}")
    return _out(row, _users_of(db))


@router.post("/{cert_id}/approve", response_model=CertificateResponse)
def approve_certificate(cert_id: int, db: Session = Depends(get_db),
                        current_user: User = Depends(require_admin)):
    """Pin this certificate; any other certificate for the same host:port is removed.

    On a certificate that was trusted automatically (first use), this records
    the admin's confirmation of the fingerprint and keeps its mode, so a
    CA-validated host stays in ``ca`` mode."""
    row = _get(db, cert_id)
    mode = row.mode if row.status == "approved" else "pin"
    return _out(tls_trust.approve(db, row, current_user.id, mode=mode), _users_of(db))


@router.delete("/{cert_id}")
def delete_certificate(cert_id: int, db: Session = Depends(get_db),
                       current_user: User = Depends(require_admin)):
    """Reject a pending certificate, or forget an approved one (the next
    connection then applies the first-use policy again)."""
    tls_trust.delete(db, _get(db, cert_id), current_user.id)
    return {"deleted": cert_id}


@router.get("/policy")
def get_policy(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return {"policy": tls_trust.get_policy(db)}


@router.put("/policy")
def set_policy(body: PolicyBody, db: Session = Depends(get_db),
               current_user: User = Depends(require_admin)):
    from app.api.audit import log_audit_event
    row = db.query(SystemSettings).filter(SystemSettings.key == tls_trust.POLICY_SETTING).first()
    old = row.value if row else "tofu"
    if row:
        row.value = body.policy
    else:
        db.add(SystemSettings(key=tls_trust.POLICY_SETTING, value=body.policy,
                              description="TLS unknown-host policy: tofu or strict"))
    db.commit()
    log_audit_event(db, "tls_cert_policy_changed", user_id=current_user.id,
                    resource_type="system", details={"from": old, "to": body.policy})
    return {"policy": body.policy}
