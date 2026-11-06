"""SSH host-key pinning against a disposable in-process SSH server.

The server records every authentication attempt, so the tests can prove a
changed or unapproved key is refused *before* any password is sent.
"""
import pathlib
import socket
import threading

import paramiko
import pytest

from app.core.database import SessionLocal, engine
from app.models.database import AuditLog, Base, SshHostKey, SystemSettings
from app.services import ssh_trust
from app.services.ssh_trust import HostKeyChangedError, HostKeyNotTrustedError, ssh_connect


class _Server(paramiko.ServerInterface):
    def __init__(self, log, allow_none=False):
        self.log = log
        self.allow_none = allow_none

    def get_allowed_auths(self, username):
        return "none,password" if self.allow_none else "password"

    def check_auth_none(self, username):
        if not self.allow_none:
            return paramiko.AUTH_FAILED
        self.log.append((username, None))
        return paramiko.AUTH_SUCCESSFUL

    def check_auth_password(self, username, password):
        self.log.append((username, password))
        return paramiko.AUTH_SUCCESSFUL if password == "pw" else paramiko.AUTH_FAILED

    # Enough of a shell for the OpenSSH client: every command prints "ok".
    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_exec_request(self, channel, command):
        def reply():
            channel.sendall(b"ok\n")
            channel.send_exit_status(0)
            channel.close()
        threading.Thread(target=reply, daemon=True).start()
        return True


class DisposableSSHServer:
    """Accepts connections on 127.0.0.1 with the given host key until stopped."""

    def __init__(self, host_key, port=0, server_disabled_algorithms=None, allow_none=False):
        self.host_key = host_key
        self.allow_none = allow_none
        self.auth_attempts = []
        self.disabled = server_disabled_algorithms
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", port))
        self.sock.listen(8)
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self._stop = threading.Event()
        self._transports = []
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except (socket.timeout, OSError):
                continue
            t = paramiko.Transport(conn, disabled_algorithms=self.disabled)
            t.add_server_key(self.host_key)
            self._transports.append(t)
            try:
                t.start_server(server=_Server(self.auth_attempts, self.allow_none))
            except Exception:
                pass

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
        for t in self._transports:
            t.close()
        self.sock.close()


@pytest.fixture(autouse=True)
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def servers():
    started = []

    def start(key, port=0, **kw):
        srv = DisposableSSHServer(key, port=port, **kw)
        started.append(srv)
        return srv
    yield start
    for srv in started:
        srv.stop()


def _connect(port, **kw):
    return ssh_connect("127.0.0.1", port=port, username="root", password="pw", timeout=5,
                       allow_agent=False, look_for_keys=False, **kw)


def _rows(db, **filters):
    db.expire_all()
    return db.query(SshHostKey).filter_by(**filters).all()


def _restart_with(servers, srv, key, **kw):
    port = srv.port
    srv.stop()
    return servers(key, port=port, **kw)


def test_first_contact_is_pinned_and_audited(db, servers):
    key = paramiko.Ed25519Key.generate() if hasattr(paramiko.Ed25519Key, "generate") else paramiko.ECDSAKey.generate()
    srv = servers(key)
    _connect(srv.port).close()
    [row] = _rows(db)
    assert row.status == "approved" and row.approved_by is None
    assert row.fingerprint == ssh_trust.fingerprint(key)
    assert srv.auth_attempts == [("root", "pw")]
    assert db.query(AuditLog).filter(AuditLog.action == "ssh_host_key_trusted_first_use").count() == 1
    # Same key again: still accepted, no extra rows.
    _connect(srv.port).close()
    assert len(_rows(db)) == 1


def test_changed_key_is_refused_before_authentication(db, servers):
    srv = servers(paramiko.ECDSAKey.generate())
    _connect(srv.port).close()

    impostor_key = paramiko.ECDSAKey.generate()
    impostor = _restart_with(servers, srv, impostor_key)
    with pytest.raises(HostKeyChangedError):
        _connect(impostor.port)
    assert impostor.auth_attempts == [], "credentials were sent to a server with the wrong key"

    [pending] = _rows(db, status="pending")
    assert pending.fingerprint == ssh_trust.fingerprint(impostor_key)
    assert db.query(AuditLog).filter(AuditLog.action == "ssh_host_key_changed_rejected").count() == 1


def test_changed_key_type_is_also_refused(db, servers):
    srv = servers(paramiko.ECDSAKey.generate())
    _connect(srv.port).close()
    other_type = _restart_with(servers, srv, paramiko.RSAKey.generate(2048))
    with pytest.raises(HostKeyChangedError):
        _connect(other_type.port)
    assert other_type.auth_attempts == []


def test_approving_a_rotated_key_replaces_the_old_one(db, servers):
    srv = servers(paramiko.ECDSAKey.generate())
    _connect(srv.port).close()
    new_key = paramiko.ECDSAKey.generate()
    rotated = _restart_with(servers, srv, new_key)
    with pytest.raises(HostKeyChangedError):
        _connect(rotated.port)

    [pending] = _rows(db, status="pending")
    ssh_trust.approve_host_key(db, pending, user_id=7)
    _connect(rotated.port).close()
    assert rotated.auth_attempts == [("root", "pw")]
    [only] = _rows(db)
    assert only.fingerprint == ssh_trust.fingerprint(new_key) and only.approved_by == 7
    approved = db.query(AuditLog).filter(AuditLog.action == "ssh_host_key_approved").one()
    assert approved.user_id == 7 and approved.details["replaced_fingerprints"]


def test_strict_policy_refuses_unknown_host_until_approved(db, servers):
    db.add(SystemSettings(key=ssh_trust.POLICY_SETTING, value="strict"))
    db.commit()
    srv = servers(paramiko.ECDSAKey.generate())
    with pytest.raises(HostKeyNotTrustedError):
        _connect(srv.port)
    assert srv.auth_attempts == []
    [pending] = _rows(db, status="pending")

    ssh_trust.approve_host_key(db, pending, user_id=1)
    _connect(srv.port).close()
    assert srv.auth_attempts == [("root", "pw")]


def test_tofu_does_not_auto_approve_a_key_already_pending(db, servers):
    db.add(SystemSettings(key=ssh_trust.POLICY_SETTING, value="strict"))
    db.commit()
    srv = servers(paramiko.ECDSAKey.generate())
    with pytest.raises(HostKeyNotTrustedError):
        _connect(srv.port)
    db.query(SystemSettings).update({"value": "tofu"})
    db.commit()
    with pytest.raises(HostKeyNotTrustedError):
        _connect(srv.port)
    assert srv.auth_attempts == []


def test_explicit_enrollment_scans_without_logging_in(db, servers):
    key = paramiko.ECDSAKey.generate()
    srv = servers(key)
    row = ssh_trust.enroll_host_key(db, "127.0.0.1", srv.port, user_id=1)
    assert row.status == "pending" and row.fingerprint == ssh_trust.fingerprint(key)
    assert srv.auth_attempts == []


def test_rsa_host_key_works_over_sha2(db, servers):
    srv = servers(paramiko.RSAKey.generate(2048))
    c = _connect(srv.port)
    assert c.get_transport().host_key_type in ("rsa-sha2-512", "rsa-sha2-256")
    c.close()
    c = _connect(srv.port)  # pinned RSA key verifies on the second connection too
    c.close()


def test_sha1_ssh_rsa_stays_refused_even_if_a_caller_asks_otherwise(db, servers):
    # Server that can only sign its host key with SHA-1 "ssh-rsa".
    srv = servers(paramiko.RSAKey.generate(2048),
                  server_disabled_algorithms={"keys": ["rsa-sha2-512", "rsa-sha2-256"]})
    with pytest.raises(paramiko.SSHException):
        _connect(srv.port, disabled_algorithms={})
    assert srv.auth_attempts == []
    assert "ssh-rsa" in ssh_trust._merged_disabled({})["keys"]
    assert "ssh-rsa" in ssh_trust._merged_disabled({"keys": []})["pubkeys"]


def test_ssh_hw_connections_are_verified(db, servers):
    from app.services import ssh_hw
    srv = servers(paramiko.ECDSAKey.generate())
    ssh_hw.get_ssh_client("127.0.0.1", "root", "pw", port=srv.port).close()
    impostor = _restart_with(servers, srv, paramiko.ECDSAKey.generate())
    with pytest.raises(HostKeyChangedError):
        ssh_hw.get_ssh_client("127.0.0.1", "root", "pw", port=impostor.port)
    assert impostor.auth_attempts == []


def test_update_service_connections_are_verified(db, servers, monkeypatch):
    import app.services.updates as updates
    srv = servers(paramiko.ECDSAKey.generate())
    # UpdateService always dials port 22; point it at the disposable server.
    real = updates.ssh_connect
    monkeypatch.setattr(updates, "ssh_connect", lambda **kw: real(port=srv.port, **kw))
    svc = updates.UpdateService(db)
    svc._connect_ssh("127.0.0.1", "root", "pw").close()
    assert srv.auth_attempts == [("root", "pw")]

    impostor = _restart_with(servers, srv, paramiko.ECDSAKey.generate())
    monkeypatch.setattr(updates, "ssh_connect", lambda **kw: real(port=impostor.port, **kw))
    assert svc._connect_ssh("127.0.0.1", "root", "pw") is None  # logged and refused
    assert impostor.auth_attempts == []


def test_no_unverified_paramiko_clients_remain_also_for_openssh():
    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    banned = ("StrictHostKeyChecking=no", "StrictHostKeyChecking=accept-new",
              "UserKnownHostsFile=/dev/null", "ProxyJump=")
    offenders = [f"{p.relative_to(root)}: {b}" for p in root.rglob("*.py") for b in banned
                 if b in p.read_text()]
    assert offenders == []


def test_no_unverified_paramiko_clients_remain():
    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    offenders = [str(p.relative_to(root)) for p in root.rglob("*.py")
                 if "AutoAddPolicy()" in p.read_text() or "WarningPolicy()" in p.read_text()]
    assert offenders == []


def test_llm_quick_ssh_is_verified(db, servers):
    from app.api import llm
    srv = servers(paramiko.ECDSAKey.generate())
    _connect(srv.port).close()
    impostor = _restart_with(servers, srv, paramiko.ECDSAKey.generate())
    real = llm.ssh_connect
    llm.ssh_connect = lambda ip, **kw: real(ip, port=impostor.port, **kw)
    try:
        with pytest.raises(HostKeyChangedError):
            llm._ssh_run_quick("127.0.0.1", "root", "pw", "true")
    finally:
        llm.ssh_connect = real
    assert impostor.auth_attempts == []


def _api(user):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import ssh_host_keys
    from app.api.auth import get_current_user, require_admin
    app = FastAPI()
    app.include_router(ssh_host_keys.router, prefix="/k")
    app.dependency_overrides[get_current_user] = lambda: user
    if user.role == "admin":
        app.dependency_overrides[require_admin] = lambda: user
    return TestClient(app)


def test_host_key_api_is_admin_only_and_audited(db, servers):
    import types
    from app.models.database import UserRole
    viewer = types.SimpleNamespace(id=2, role=UserRole.VIEWER)
    assert _api(viewer).get("/k/").status_code == 403

    admin = types.SimpleNamespace(id=1, role="admin")
    c = _api(admin)
    key = paramiko.ECDSAKey.generate()
    srv = servers(key)
    scanned = c.post("/k/scan", json={"host": "127.0.0.1", "port": srv.port}).json()
    assert scanned["status"] == "pending" and scanned["fingerprint"] == ssh_trust.fingerprint(key)
    assert c.post(f"/k/{scanned['id']}/approve").json()["status"] == "approved"
    _connect(srv.port).close()
    assert c.put("/k/policy", json={"policy": "strict"}).json() == {"policy": "strict"}
    assert c.put("/k/policy", json={"policy": "off"}).status_code == 422
    assert c.delete(f"/k/{scanned['id']}").status_code == 200
    actions = {a.action for a in db.query(AuditLog).all()}
    assert {"ssh_host_key_scanned", "ssh_host_key_approved", "ssh_host_key_deleted",
            "ssh_host_key_policy_changed"} <= actions
