"""TLS server identity checks for connections made without CA verification.

Proxmox, PBS and BMC web interfaces usually have self-signed certificates, so
depl0y historically connected to them with ``verify=False`` and accepted any
certificate. This module makes those connections check the server instead:

- A host whose certificate already validates against the system CAs for the
  name we connect to is recorded in mode ``ca``: from then on it must keep
  presenting a CA-valid certificate (normal verification, so routine renewals
  such as Let's Encrypt just work).
- Any other host is recorded in mode ``pin``: only that exact certificate
  (SHA-256 of the DER) is accepted.

A host we have never seen is handled by the ``tls_cert_policy`` setting:
``tofu`` (default) trusts the first certificate automatically and audits it;
``strict`` stores it as pending and refuses the connection until an
administrator approves it. A changed certificate is always refused and kept as
pending for review, with one exception: if the new certificate is CA-issued
and covers every DNS name of the pinned one, it is a normal renewal and the
pin moves to it automatically (audited).

Coverage: `install()` makes `PinningAdapter` the default HTTPS adapter for
every `requests` session, and the adapter only acts on requests sent with
``verify=False`` — in depl0y those are exactly the connections to managed
infrastructure (Proxmox via proxmoxer, PBS, Redfish/BMC, VMware). Requests
with normal verification (GitHub, webhooks, ...) are untouched. The console
WebSocket proxy uses `websocket_ssl_context()`.
"""
import hashlib
import logging
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urlsplit

import requests
import requests.adapters
import requests.sessions

logger = logging.getLogger(__name__)

POLICY_SETTING = "tls_cert_policy"
POLICIES = ("tofu", "strict")

_CACHE_TTL = 30.0
_cache: dict = {}            # (host, port) -> (monotonic, Trust|None)
_cache_lock = threading.Lock()
_resolve_locks: dict = {}    # (host, port) -> Lock, so one probe per host at a time
_resolve_locks_guard = threading.Lock()


class CertificateNotTrustedError(requests.exceptions.SSLError):
    """The server's certificate is not approved; nothing was sent to it."""

    def __init__(self, message: str, host: str, port: int, fingerprint: str = ""):
        super().__init__(message)
        self.host = host
        self.port = port
        self.fingerprint = fingerprint


class CertificateChangedError(CertificateNotTrustedError):
    """The server presented a different certificate than the approved one."""


@dataclass(frozen=True)
class Trust:
    mode: str          # "pin" | "ca"
    fingerprint: str   # sha256 hex (for "ca": the certificate last seen)
    pem: str


@dataclass
class Probe:
    der: bytes
    fingerprint: str
    pem: str
    ca_valid_for_host: bool
    ca_chain_valid: bool
    subject: str
    issuer: str
    dns_names: List[str]
    not_after: Optional[datetime]


def fingerprint_der(der: bytes) -> str:
    return hashlib.sha256(der).hexdigest()


def format_fingerprint(fp: str) -> str:
    """AA:BB:... form, as `openssl x509 -noout -fingerprint -sha256` prints it."""
    fp = fp.upper()
    return ":".join(fp[i:i + 2] for i in range(0, len(fp), 2))


# ── probing ───────────────────────────────────────────────────────────────

def _legacy_context() -> ssl.SSLContext:
    """No-verification context that still talks to old BMC TLS (iDRAC 7/8)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1
    except (AttributeError, ValueError):
        pass
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    except ssl.SSLError:
        pass
    if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
    return ctx


def _handshake(host: str, port: int, ctx: ssl.SSLContext, timeout: float) -> bytes:
    # server_hostname drives SNI and (with check_hostname) the name/IP match;
    # Python sends no SNI for IP literals.
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            return tls.getpeercert(binary_form=True)


def _describe(der: bytes) -> Tuple[str, str, List[str], Optional[datetime]]:
    try:
        from cryptography import x509
        cert = x509.load_der_x509_certificate(der)
        try:
            san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            names = sorted({n.lower() for n in san.get_values_for_type(x509.DNSName)})
        except x509.ExtensionNotFound:
            names = []
        not_after = cert.not_valid_after_utc.replace(tzinfo=None)
        return cert.subject.rfc4514_string()[:512], cert.issuer.rfc4514_string()[:512], names, not_after
    except Exception as exc:  # unparsable certificate: still pinnable by hash
        logger.debug("TLS: cannot parse certificate: %s", exc)
        return "", "", [], None


def probe(host: str, port: int, legacy: bool = False, timeout: float = 10) -> Probe:
    """Fetch the server's certificate (without sending anything) and check
    whether it is CA-valid. Raises OSError/ssl.SSLError if unreachable."""
    der = _handshake(host, port, _legacy_context() if legacy else _no_verify_context(), timeout)
    ca_host = ca_chain = False
    if not legacy:
        try:
            _handshake(host, port, ssl.create_default_context(), timeout)
            ca_host = ca_chain = True
        except ssl.SSLCertVerificationError:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            try:
                _handshake(host, port, ctx, timeout)
                ca_chain = True
            except (ssl.SSLError, OSError):
                pass
        except (ssl.SSLError, OSError):
            pass
    subject, issuer, names, not_after = _describe(der)
    return Probe(der=der, fingerprint=fingerprint_der(der), pem=ssl.DER_cert_to_PEM_cert(der),
                 ca_valid_for_host=ca_host, ca_chain_valid=ca_chain, subject=subject,
                 issuer=issuer, dns_names=names, not_after=not_after)


def _no_verify_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ── store ─────────────────────────────────────────────────────────────────

def get_policy(db) -> str:
    from app.models.database import SystemSettings
    row = db.query(SystemSettings).filter(SystemSettings.key == POLICY_SETTING).first()
    value = (row.value if row else "") or "tofu"
    return value if value in POLICIES else "tofu"


def _audit(db, action: str, row, user_id: Optional[int] = None, **details):
    try:
        from app.api.audit import log_audit_event
        log_audit_event(
            db, action, user_id=user_id, resource_type="tls_certificate",
            resource_id=row.id if row is not None else None,
            details={"host": row.host, "port": row.port, "mode": row.mode,
                     "fingerprint": row.fingerprint, **details} if row is not None else details,
        )
    except Exception as exc:
        logger.warning("TLS: audit write failed: %s", exc)


def _record(db, host: str, port: int, pr: Probe, mode: str, status: str,
            user_id: Optional[int] = None):
    """Insert or refresh the row for this exact certificate and return it."""
    from sqlalchemy.exc import IntegrityError
    from app.models.database import TlsCertificate

    q = db.query(TlsCertificate).filter_by(host=host, port=port, fingerprint=pr.fingerprint)
    row = q.first()
    now = datetime.utcnow()
    if row is None:
        row = TlsCertificate(
            host=host, port=port, mode=mode, fingerprint=pr.fingerprint, pem=pr.pem,
            subject=pr.subject, issuer=pr.issuer, dns_names=",".join(pr.dns_names),
            not_after=pr.not_after, status=status, first_seen=now, last_seen=now,
            approved_at=now if status == "approved" else None, approved_by=user_id,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = q.first()
    else:
        row.last_seen = now
        db.commit()
    return row


def _approve(db, row, mode: str, user_id: Optional[int]):
    """Make *row* the only approved certificate for its host:port."""
    from app.models.database import TlsCertificate
    db.query(TlsCertificate).filter(
        TlsCertificate.host == row.host, TlsCertificate.port == row.port,
        TlsCertificate.id != row.id,
    ).delete(synchronize_session=False)
    row.mode = mode
    row.status = "approved"
    row.approved_at = datetime.utcnow()
    row.approved_by = user_id
    db.commit()
    invalidate(row.host, row.port)
    return row


def _approved(db, host: str, port: int):
    from app.models.database import TlsCertificate
    return db.query(TlsCertificate).filter_by(host=host, port=port, status="approved").first()


def invalidate(host: Optional[str] = None, port: Optional[int] = None):
    with _cache_lock:
        if host is None:
            _cache.clear()
        else:
            _cache.pop((host, port), None)


def _cached(host: str, port: int):
    with _cache_lock:
        hit = _cache.get((host, port))
    if hit and time.monotonic() - hit[0] < _CACHE_TTL:
        return hit[1]
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        row = _approved(db, host, port)
        trust = Trust(row.mode, row.fingerprint, row.pem) if row else None
    finally:
        db.close()
    with _cache_lock:
        _cache[(host, port)] = (time.monotonic(), trust)
    return trust


def _lock_for(host: str, port: int) -> threading.Lock:
    with _resolve_locks_guard:
        return _resolve_locks.setdefault((host, port), threading.Lock())


def resolve(host: str, port: int, legacy: bool = False, timeout: float = 10) -> Trust:
    """Return the approved trust for host:port, applying the unknown-host
    policy (first use) if there is none. Raises CertificateNotTrustedError."""
    trust = _cached(host, port)
    if trust is not None:
        return trust
    with _lock_for(host, port):
        invalidate(host, port)
        trust = _cached(host, port)
        if trust is not None:
            return trust
        try:
            pr = probe(host, port, legacy=legacy, timeout=timeout)
        except socket.timeout as exc:
            raise requests.exceptions.ConnectTimeout(f"TLS probe of {host}:{port} timed out: {exc}")
        except (OSError, ssl.SSLError) as exc:
            raise requests.exceptions.ConnectionError(f"TLS probe of {host}:{port} failed: {exc}")
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            mode = "ca" if pr.ca_valid_for_host else "pin"
            if mode == "pin" and get_policy(db) == "strict":
                row = _record(db, host, port, pr, mode, "pending")
                _audit(db, "tls_cert_unknown_rejected", row)
                raise CertificateNotTrustedError(
                    f"TLS certificate for {host}:{port} is not approved yet "
                    f"(SHA-256 {format_fingerprint(pr.fingerprint)}). "
                    "Approve it under Settings → TLS certificates.", host, port, pr.fingerprint)
            row = _record(db, host, port, pr, mode, "approved")
            if row.status != "approved":
                raise CertificateNotTrustedError(
                    f"TLS certificate for {host}:{port} is pending approval "
                    f"(SHA-256 {format_fingerprint(pr.fingerprint)}).", host, port, pr.fingerprint)
            _audit(db, "tls_cert_trusted_first_use", row)
            logger.warning("TLS: trusting %s:%s on first use (%s, %s)", host, port, mode,
                           format_fingerprint(pr.fingerprint))
            trust = Trust(row.mode, row.fingerprint, row.pem)
        finally:
            db.close()
        invalidate(host, port)
        return trust


def handle_failure(host: str, port: int, trust: Trust, legacy: bool = False) -> bool:
    """Called after a TLS failure against an approved trust.

    Returns True if the certificate was a legitimate CA-issued renewal and the
    pin was moved to it (caller may retry once). Otherwise records the new
    certificate as pending and raises CertificateChangedError. Returns False
    if the host could not be probed or still matches (not a trust problem).
    """
    try:
        pr = probe(host, port, legacy=legacy)
    except (OSError, ssl.SSLError):
        return False
    if trust.mode == "pin" and pr.fingerprint == trust.fingerprint:
        return False
    if trust.mode == "ca" and pr.ca_valid_for_host:
        return False
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        old = _approved(db, host, port)
        old_names = set((old.dns_names or "").split(",")) - {""} if old else set()
        if (trust.mode == "pin" and pr.ca_chain_valid and old_names
                and old_names <= set(pr.dns_names)):
            row = _record(db, host, port, pr, "pin", "pending")
            _approve(db, row, "pin", None)
            _audit(db, "tls_cert_renewal_accepted", row,
                   previous_fingerprint=trust.fingerprint, reason="CA-issued for the same names")
            logger.warning("TLS: %s:%s renewed its CA-issued certificate; pin moved to %s",
                           host, port, format_fingerprint(pr.fingerprint))
            return True
        row = _record(db, host, port, pr, "pin", "pending")
        _audit(db, "tls_cert_changed_rejected", row, approved_fingerprint=trust.fingerprint)
    finally:
        db.close()
    raise CertificateChangedError(
        f"TLS certificate for {host}:{port} has changed (now SHA-256 "
        f"{format_fingerprint(pr.fingerprint)}). The connection was refused. If the change is "
        "expected, approve the new certificate under Settings → TLS certificates.",
        host, port, pr.fingerprint)


def recheck_after_failure(host: str, port: int, legacy: bool = False) -> bool:
    """For callers outside requests (WebSockets): after a TLS verification
    failure, record a changed certificate (raises CertificateChangedError) or
    accept a CA-issued renewal (returns True; retry)."""
    trust = _cached(host, port)
    if trust is None:
        return False
    return handle_failure(host, port, trust, legacy=legacy)


# ── admin actions ─────────────────────────────────────────────────────────

def enroll(db, host: str, port: int, user_id: int):
    """Fetch a host's certificate and store it as pending for review."""
    pr = probe(host, port, legacy=True)
    row = _record(db, host, port, pr, "pin", "pending")
    if row.status == "pending":
        _audit(db, "tls_cert_scanned", row, user_id=user_id)
    return row


def approve(db, row, user_id: int, mode: str = "pin"):
    row = _approve(db, row, mode, user_id)
    _audit(db, "tls_cert_approved", row, user_id=user_id)
    return row


def delete(db, row, user_id: int):
    _audit(db, "tls_cert_deleted", row, user_id=user_id, status=row.status)
    host, port = row.host, row.port
    db.delete(row)
    db.commit()
    invalidate(host, port)


# ── requests integration ──────────────────────────────────────────────────

def _host_port(url: str) -> Tuple[str, int]:
    parts = urlsplit(url)
    return (parts.hostname or ""), (parts.port or 443)


class PinningAdapter(requests.adapters.HTTPAdapter):
    """HTTPS adapter that verifies servers reached with verify=False."""

    legacy_tls = False

    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        kwargs = dict(stream=stream, timeout=timeout, verify=verify, cert=cert, proxies=proxies)
        if verify is not False or not request.url.lower().startswith("https://"):
            return super().send(request, **kwargs)
        host, port = _host_port(request.url)
        # First contact probes the server; keep that within the caller's connect timeout.
        connect_timeout = timeout[0] if isinstance(timeout, tuple) else timeout
        trust = resolve(host, port, legacy=self.legacy_tls, timeout=connect_timeout or 10)
        try:
            return super().send(request, **kwargs)
        except requests.exceptions.SSLError:
            # TLS fails before the request is written, so a retry is safe.
            if handle_failure(host, port, trust, legacy=self.legacy_tls):
                return super().send(request, **kwargs)
            raise

    def build_connection_pool_key_attributes(self, request, verify, cert=None):
        # Called by requests for direct and proxied connections alike.
        if verify is not False or not request.url.lower().startswith("https://"):
            return super().build_connection_pool_key_attributes(request, verify, cert)
        host, port = _host_port(request.url)
        trust = resolve(host, port, legacy=self.legacy_tls)
        if trust.mode == "ca":
            # Normal CA + hostname verification.
            return super().build_connection_pool_key_attributes(request, True, cert)
        host_params, pool_kwargs = super().build_connection_pool_key_attributes(request, False, cert)
        pool_kwargs = {k: v for k, v in pool_kwargs.items() if k not in ("ca_certs", "ca_cert_dir")}
        pool_kwargs["cert_reqs"] = "CERT_NONE"
        pool_kwargs["assert_fingerprint"] = trust.fingerprint
        return host_params, pool_kwargs


class LegacyPinningAdapter(PinningAdapter):
    """PinningAdapter for old BMC TLS stacks (TLS 1.0, legacy renegotiation)."""

    legacy_tls = True

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = _legacy_context()
        super().init_poolmanager(*args, **kwargs)


_installed = False


def install():
    """Mount PinningAdapter for https:// on every new requests.Session.

    Covers sessions created anywhere — proxmoxer's, ours, and the one-off
    sessions behind requests.get/post. Code that mounts its own adapter (the
    BMC client) mounts LegacyPinningAdapter instead."""
    global _installed
    if _installed:
        return
    original_init = requests.Session.__init__

    def _init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.mount("https://", PinningAdapter())

    requests.Session.__init__ = _init
    _installed = True


# ── WebSocket (console proxy) ─────────────────────────────────────────────

def websocket_ssl_context(host: str, port: int) -> ssl.SSLContext:
    """SSL context for a non-requests connection (wss://, pyVmomi) to a managed host.

    Mode ``ca``: normal verification. Mode ``pin``: the pinned certificate is
    the only trust anchor (partial-chain), so the handshake itself fails for
    any other certificate — before the auth header is sent."""
    trust = resolve(host, port)
    if trust.mode == "ca":
        return ssl.create_default_context()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_verify_locations(cadata=trust.pem)
    ctx.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    return ctx
