"""Console WebSocket tickets, and the mandatory-2FA policy on every auth path."""
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.database import SessionLocal, engine
from app.core.security import create_access_token, get_password_hash
from app.models.database import (
    ApiKey, Base, ProxmoxHost, SystemSettings, TlsCertificate, User, UserHostPermission, UserRole,
)
from app.services import ws_tickets

API = "/api/v1"
HOST_ID = 999          # inactive host the operator may access: an authenticated socket closes 4404
OTHER_HOST = 998       # inactive host nobody but admins may access

TARGETS = {
    "vm": ({"kind": "vm", "host_id": HOST_ID, "node": "pve", "vmid": 100}, f"/ws/vm/{HOST_ID}/pve/100"),
    "lxc": ({"kind": "lxc", "host_id": HOST_ID, "node": "pve", "vmid": 101}, f"/ws/lxc/{HOST_ID}/pve/101"),
    "node": ({"kind": "node", "host_id": HOST_ID, "node": "pve"}, f"/ws/node/{HOST_ID}/pve"),
}


@pytest.fixture(autouse=True)
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ws_tickets.clear()
    s = SessionLocal()
    for uid, name, role in ((1, "admin", UserRole.ADMIN), (2, "oper", UserRole.OPERATOR), (3, "viewer", UserRole.VIEWER)):
        s.add(User(id=uid, username=name, email=f"{name}@example.com", hashed_password="x", role=role))
    for hid in (HOST_ID, OTHER_HOST):
        s.add(ProxmoxHost(id=hid, name=f"h{hid}", hostname=f"h{hid}.invalid", username="root@pam", is_active=False))
    s.flush()
    s.add(UserHostPermission(user_id=2, host_id=HOST_ID, can_view=True))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _bearer(username):
    return {"Authorization": "Bearer " + create_access_token({"sub": username, "tv": 0})}


def _policy(db, value):
    db.add(SystemSettings(key="require_totp", value=value))
    db.commit()


def _enrol(db, uid):
    db.query(User).filter(User.id == uid).update({"totp_enabled": True, "totp_secret": "JBSWY3DPEHPK3PXP"})
    db.commit()


def _ticket(client, username, kind):
    return client.post(f"{API}/pve-console/ws-ticket", json=TARGETS[kind][0], headers=_bearer(username))


def _ws_close_code(client, path, query):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"{API}/pve-console{path}?{query}"):
            pass
    return exc.value.code


def _connect(client, kind, ticket):
    return _ws_close_code(client, TARGETS[kind][1], f"ws_ticket={ticket}")


def _add_key(db, uid, key):
    db.add(ApiKey(user_id=uid, name="k", key_prefix=key[:8], key_hash=get_password_hash(key), is_active=True))
    db.commit()


# ── tickets ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind,user", [("vm", "oper"), ("lxc", "oper"), ("node", "admin")])
def test_ticket_opens_its_socket_once(client, kind, user):
    r = _ticket(client, user, kind)
    assert r.status_code == 200, r.text
    t = r.json()["ticket"]
    assert _connect(client, kind, t) == 4404      # authenticated; host 999 does not exist
    assert _connect(client, kind, t) == 4401      # single use


@pytest.mark.parametrize("kind", ["vm", "lxc", "node"])
def test_access_token_in_url_is_not_accepted(client, kind):
    tok = create_access_token({"sub": "admin", "tv": 0})
    assert _ws_close_code(client, TARGETS[kind][1], f"token={tok}") == 4401
    assert _ws_close_code(client, TARGETS[kind][1], f"ws_ticket={tok}") == 4401


def test_ticket_is_bound_to_its_target(client):
    t = _ticket(client, "admin", "vm").json()["ticket"]
    assert _ws_close_code(client, f"/ws/vm/{HOST_ID}/pve/200", f"ws_ticket={t}") == 4401
    assert _connect(client, "vm", t) == 4401      # a failed try still burns it
    t = _ticket(client, "admin", "lxc").json()["ticket"]
    assert _connect(client, "node", t) == 4401


def test_ticket_expires(client, monkeypatch):
    t = _ticket(client, "admin", "node").json()["ticket"]
    real = time.monotonic
    monkeypatch.setattr(ws_tickets.time, "monotonic", lambda: real() + ws_tickets.TICKET_TTL + 1)
    assert _connect(client, "node", t) == 4401


def test_ticket_dies_with_revoked_session_or_role(client, db):
    t = _ticket(client, "admin", "node").json()["ticket"]
    db.query(User).filter(User.id == 1).update({"token_version": 1}); db.commit()
    assert _connect(client, "node", t) == 4401
    t = _ticket(client, "oper", "vm").json()["ticket"]
    db.query(User).filter(User.id == 2).update({"role": UserRole.VIEWER}); db.commit()
    assert _connect(client, "vm", t) == 4401


def test_ticket_role_requirements(client):
    assert _ticket(client, "viewer", "vm").status_code == 403
    assert _ticket(client, "viewer", "lxc").status_code == 403
    assert _ticket(client, "oper", "node").status_code == 403
    assert client.post(f"{API}/pve-console/ws-ticket", json=TARGETS["node"][0]).status_code == 401


def test_ticket_request_validates_vmid(client):
    body = {"kind": "node", "host_id": 1, "node": "pve", "vmid": 5}
    assert client.post(f"{API}/pve-console/ws-ticket", json=body, headers=_bearer("admin")).status_code == 422
    body = {"kind": "vm", "host_id": 1, "node": "pve"}
    assert client.post(f"{API}/pve-console/ws-ticket", json=body, headers=_bearer("admin")).status_code == 422


def test_api_key_cannot_mint_console_ticket(client, db):
    key = "dk_" + "c" * 40
    _add_key(db, 1, key)
    r = client.post(f"{API}/pve-console/ws-ticket", json=TARGETS["node"][0], headers={"X-API-Key": key})
    assert r.status_code == 403


# ── mandatory 2FA on console sockets ──────────────────────────────────────

@pytest.mark.parametrize("policy,user,kind", [
    ("admins", "admin", "node"), ("admins", "admin", "vm"), ("admins", "admin", "lxc"),
    ("all", "admin", "node"), ("all", "oper", "vm"), ("all", "oper", "lxc"),
])
def test_unenrolled_user_refused_on_console_socket(client, db, policy, user, kind):
    # A ticket minted before the policy was switched on must not get through.
    t = _ticket(client, user, kind).json()["ticket"]
    _policy(db, policy)
    assert _connect(client, kind, t) == 4403
    # Nor can a new one be minted.
    r = _ticket(client, user, kind)
    assert r.status_code == 403 and r.json()["detail"] == "totp_enrollment_required"


@pytest.mark.parametrize("policy,user,kind", [("admins", "oper", "vm"), ("all", "admin", "node")])
def test_enrolled_or_exempt_user_allowed_on_console_socket(client, db, policy, user, kind):
    _policy(db, policy)
    if policy == "all":
        _enrol(db, 1)
    t = _ticket(client, user, kind).json()["ticket"]
    assert _connect(client, kind, t) == 4404


# ── mandatory 2FA on API keys ─────────────────────────────────────────────

@pytest.mark.parametrize("policy,uid,blocked", [
    ("admins", 1, True), ("admins", 2, False), ("admins", 3, False),
    ("all", 1, True), ("all", 2, True), ("all", 3, True),
    ("off", 1, False),
])
def test_api_key_subject_to_totp_policy(client, db, policy, uid, blocked):
    key = f"dk_{uid}" + "k" * 40
    _add_key(db, uid, key)
    _policy(db, policy)
    r = client.get(f"{API}/auth/sessions", headers={"X-API-Key": key})
    if blocked:
        assert r.status_code == 403 and r.json()["detail"] == "totp_enrollment_required"
    else:
        assert r.status_code == 200, r.text


def test_api_key_cannot_reach_enrolment_routes(client, db):
    key = "dk_" + "e" * 40
    _add_key(db, 1, key)
    _policy(db, "all")
    for method, path in (("get", "/auth/me"), ("post", "/auth/totp/setup")):
        r = getattr(client, method)(f"{API}{path}", headers={"X-API-Key": key})
        assert r.status_code == 403, (path, r.status_code)


def test_api_key_of_enrolled_user_still_works(client, db):
    key = "dk_" + "f" * 40
    _add_key(db, 1, key)
    _enrol(db, 1)
    _policy(db, "all")
    assert client.get(f"{API}/auth/sessions", headers={"X-API-Key": key}).status_code == 200


# ── first-use trust confirmation ──────────────────────────────────────────

def test_confirming_automatic_ca_certificate_keeps_ca_mode(client, db):
    db.add(TlsCertificate(id=5, host="pve.example", port=8006, mode="ca", fingerprint="ab" * 32,
                          pem="-", status="approved", approved_by=None))
    db.commit()
    before = client.get(f"{API}/tls-certificates/", headers=_bearer("admin")).json()
    assert before[0]["automatic"] is True
    r = client.post(f"{API}/tls-certificates/5/approve", headers=_bearer("admin"))
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "ca" and r.json()["automatic"] is False and r.json()["approved_by"] == 1


# ── per-host access (Users → Host Access) ─────────────────────────────────

CONSOLE_REST = [
    ("get", f"/pve-console/ticket/{OTHER_HOST}/pve/100"),
    ("get", f"/pve-console/lxc-ticket/{OTHER_HOST}/pve/101"),
    ("get", f"/pve-console/spice/{OTHER_HOST}/pve/100"),
    ("post", f"/pve-vm/{OTHER_HOST}/pve/100/vncticket"),
    # /pve-node/.../lxc/{vmid}/termproxy is shadowed by the generic lxc/{action} route.
]


@pytest.mark.parametrize("method,path", CONSOLE_REST)
def test_console_rest_refused_on_host_without_access(client, method, path):
    r = getattr(client, method)(API + path, headers=_bearer("oper"))
    assert r.status_code == 403 and r.json()["detail"] == "No access to this Proxmox host", r.text


@pytest.mark.parametrize("kind", ["vm", "lxc"])
def test_ws_ticket_refused_on_host_without_access(client, kind):
    body = dict(TARGETS[kind][0], host_id=OTHER_HOST)
    r = client.post(f"{API}/pve-console/ws-ticket", json=body, headers=_bearer("oper"))
    assert r.status_code == 403


def test_revoked_host_access_refuses_issued_ticket(client, db):
    t = _ticket(client, "oper", "vm").json()["ticket"]
    db.query(UserHostPermission).filter(UserHostPermission.user_id == 2).delete(); db.commit()
    assert _connect(client, "vm", t) == 4403


def test_host_permission_with_no_rights_is_no_access(client, db):
    db.query(UserHostPermission).filter(UserHostPermission.user_id == 2).update({"can_view": False}); db.commit()
    assert _ticket(client, "oper", "vm").status_code == 403


def test_admin_reaches_every_host(client):
    body = dict(TARGETS["node"][0], host_id=OTHER_HOST)
    t = client.post(f"{API}/pve-console/ws-ticket", json=body, headers=_bearer("admin")).json()["ticket"]
    assert _ws_close_code(client, f"/ws/node/{OTHER_HOST}/pve", f"ws_ticket={t}") == 4404
