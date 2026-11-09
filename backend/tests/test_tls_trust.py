"""TLS certificate pinning for verify=False connections (services/tls_trust.py)."""
import datetime as dt
import socket
import ssl
import threading

import pytest
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.core.database import SessionLocal, engine
from app.models.database import AuditLog, Base, SystemSettings, TlsCertificate
from app.services import tls_trust


def _self_signed(tmp_path, name):
    key = ec.generate_private_key(ec.SECP256R1())
    subj = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subj).issuer_name(subj)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=30))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False)
            .sign(key, hashes.SHA256()))
    c, k = tmp_path / f"{name}.crt", tmp_path / f"{name}.key"
    c.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    k.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()))
    return str(c), str(k)


class _Server:
    """Tiny HTTPS server on 127.0.0.1 whose certificate can be swapped."""

    def __init__(self, cert, key):
        self.sock = socket.socket(); self.sock.bind(("127.0.0.1", 0)); self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self.seen = []  # request heads received
        self.use(cert, key)
        threading.Thread(target=self._loop, daemon=True).start()

    def use(self, cert, key):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(cert, key)
        self.ctx = ctx

    def _loop(self):
        while True:
            try:
                raw, _ = self.sock.accept()
            except OSError:
                return
            try:
                with self.ctx.wrap_socket(raw, server_side=True) as s:
                    s.settimeout(2)
                    data = s.recv(65536)
                    if data:
                        self.seen.append(data)
                        s.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
            except Exception:
                pass


@pytest.fixture(autouse=True)
def db():
    Base.metadata.drop_all(bind=engine); Base.metadata.create_all(bind=engine)
    tls_trust.invalidate()
    tls_trust.install()
    s = SessionLocal(); yield s; s.close()


@pytest.fixture
def server(tmp_path):
    a = _self_signed(tmp_path, "pve-a.test")
    b = _self_signed(tmp_path, "pve-b.test")
    srv = _Server(*a)
    srv.certs = {"a": a, "b": b}
    yield srv
    srv.sock.close()


def _get(srv):
    return requests.get(f"https://127.0.0.1:{srv.port}/x", verify=False, timeout=5,
                        headers={"Authorization": "PVEAPIToken=secret"})


def test_first_use_pins_and_changed_cert_is_refused_before_sending(server, db):
    assert _get(server).status_code == 200
    row = db.query(TlsCertificate).one()
    assert (row.status, row.mode, row.approved_by) == ("approved", "pin", None)
    sent_before = len(server.seen)

    server.use(*server.certs["b"]); tls_trust.invalidate()
    with pytest.raises(tls_trust.CertificateChangedError):
        _get(server)
    assert len(server.seen) == sent_before, "credentials must not reach the new certificate"
    statuses = sorted(r.status for r in SessionLocal().query(TlsCertificate).all())
    assert statuses == ["approved", "pending"]
    assert SessionLocal().query(AuditLog).filter(AuditLog.action == "tls_cert_changed_rejected").count() == 1


def test_admin_approval_moves_the_pin(server, db):
    _get(server)
    server.use(*server.certs["b"])
    with pytest.raises(tls_trust.CertificateChangedError):
        _get(server)
    s = SessionLocal()
    pending = s.query(TlsCertificate).filter_by(status="pending").one()
    tls_trust.approve(s, pending, user_id=None)
    assert _get(server).status_code == 200
    assert SessionLocal().query(TlsCertificate).count() == 1


def test_strict_policy_refuses_unknown_host(server, db):
    db.add(SystemSettings(key="tls_cert_policy", value="strict")); db.commit()
    with pytest.raises(tls_trust.CertificateNotTrustedError):
        _get(server)
    assert server.seen == []
    assert db.query(TlsCertificate).one().status == "pending"


def test_verified_requests_are_untouched(server):
    # verify=True keeps normal CA checks: a self-signed server simply fails.
    with pytest.raises(requests.exceptions.SSLError):
        requests.get(f"https://127.0.0.1:{server.port}/x", timeout=5)
    assert SessionLocal().query(TlsCertificate).count() == 0


def test_ca_issued_renewal_for_same_names_is_accepted(server, db, monkeypatch):
    _get(server)
    server.use(*server.certs["b"])
    real_probe = tls_trust.probe

    def fake_probe(host, port, legacy=False, timeout=10):
        pr = real_probe(host, port, legacy, timeout)
        if pr.dns_names == ["pve-b.test"]:
            pr.ca_chain_valid = True
            pr.dns_names = ["pve-a.test", "pve-b.test"]
        return pr
    monkeypatch.setattr(tls_trust, "probe", fake_probe)
    assert _get(server).status_code == 200
    rows = SessionLocal().query(TlsCertificate).all()
    assert len(rows) == 1 and rows[0].status == "approved" and "pve-b.test" in rows[0].dns_names


def test_websocket_context_accepts_only_the_pin(server):
    _get(server)
    ctx = tls_trust.websocket_ssl_context("127.0.0.1", server.port)
    with socket.create_connection(("127.0.0.1", server.port)) as s, ctx.wrap_socket(s, server_hostname="127.0.0.1"):
        pass
    server.use(*server.certs["b"])
    with pytest.raises(ssl.SSLCertVerificationError):
        with socket.create_connection(("127.0.0.1", server.port)) as s, ctx.wrap_socket(s, server_hostname="127.0.0.1"):
            pass
    with pytest.raises(tls_trust.CertificateChangedError):
        tls_trust.recheck_after_failure("127.0.0.1", server.port)


def test_bmc_legacy_adapter_pins_too(server):
    from app.services.idrac import RedfishClient
    svc = RedfishClient("127.0.0.1", "root", "pw", port=server.port)
    assert svc.session.get(f"https://127.0.0.1:{server.port}/redfish/v1", timeout=5).status_code == 200
    server.use(*server.certs["b"])
    with pytest.raises(tls_trust.CertificateChangedError):
        svc.session.get(f"https://127.0.0.1:{server.port}/redfish/v1", timeout=5)
