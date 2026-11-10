"""Regression tests for the 2026-11-09 security review (roles, tokens, audit, 2FA policy, keys)."""
import os
import stat
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal, engine
from app.core.security import create_access_token, create_refresh_token, get_password_hash
from app.models.database import ApiKey, AuditLog, Base, SystemSettings, User, UserRole

API = "/api/v1"


@pytest.fixture(autouse=True)
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    for uid, name, role in ((1, "admin", UserRole.ADMIN), (2, "oper", UserRole.OPERATOR), (3, "viewer", UserRole.VIEWER)):
        s.add(User(id=uid, username=name, email=f"{name}@example.com", hashed_password="x", role=role))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _bearer(username, **extra):
    return {"Authorization": "Bearer " + create_access_token({"sub": username, "tv": 0, **extra})}


# ── tokens ────────────────────────────────────────────────────────────────

def test_refresh_token_is_not_a_bearer_token(client):
    refresh = create_refresh_token({"sub": "admin", "tv": 0})
    r = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert r.status_code == 401
    assert client.get(f"{API}/auth/me", headers=_bearer("admin")).status_code == 200


def test_revoked_token_version_is_refused(client, db):
    db.query(User).filter(User.id == 1).update({"token_version": 3}); db.commit()
    assert client.get(f"{API}/auth/me", headers=_bearer("admin")).status_code == 401


# ── viewer is read-only ───────────────────────────────────────────────────

VIEWER_FORBIDDEN = [
    ("delete", "/pbs-mgmt/1/datastores/ds/snapshots?backup_type=vm&backup_id=100&backup_time=1"),
    ("post", "/pbs-mgmt/1/datastores/ds/prune"),
    ("post", "/pbs-mgmt/1/datastores/ds/verify"),
    ("delete", "/cloud-images/1"),
    ("post", "/cloud-images/fetch-latest"),
    ("post", "/pve-node/1/nodes/pve/lxc/100/termproxy"),
    ("post", "/pve-vm/1/pve/100/vncticket"),
    ("get", "/pve-console/ticket/1/pve/100"),
    ("get", "/pve-console/spice/1/pve/100"),
    ("post", "/proxmox/1/poll"),
]


def _route_exists(client, method, path):
    from starlette.routing import Match
    scope = {"type": "http", "path": API + path.split("?")[0], "method": method.upper()}
    return any(r.matches(scope)[0] == Match.FULL for r in client.app.routes)


@pytest.mark.parametrize("method,path", VIEWER_FORBIDDEN)
def test_viewer_cannot_mutate(client, method, path):
    assert _route_exists(client, method, path), f"route moved: {method} {path}"
    kwargs = {"json": {}} if method in ("post", "put") else {}
    r = getattr(client, method)(API + path, headers=_bearer("viewer"), **kwargs)
    assert r.status_code == 403, (path, r.status_code, r.text)


@pytest.mark.parametrize("method,path", [
    ("delete", "/pbs-mgmt/1/datastores/ds/snapshots?backup_type=vm&backup_id=100&backup_time=1"),
    ("post", "/pbs-mgmt/1/datastores/ds/prune"),
    ("delete", "/cloud-images/1"),
])
def test_operator_cannot_do_admin_only(client, method, path):
    kwargs = {"json": {}} if method == "post" else {}
    assert getattr(client, method)(API + path, headers=_bearer("oper"), **kwargs).status_code == 403


def test_system_version_requires_admin(client):
    assert client.put(f"{API}/system/version?new_version=9.9.9").status_code == 401
    assert client.put(f"{API}/system/version?new_version=9.9.9", headers=_bearer("viewer")).status_code == 403


# ── audit of API-key calls ────────────────────────────────────────────────

def test_api_key_calls_are_audited(client, db):
    key = "dk_" + "a" * 40
    db.add(ApiKey(id=7, user_id=3, name="t", key_prefix=key[:8], key_hash=get_password_hash(key), is_active=True))
    db.commit()
    r = client.post(f"{API}/notifications/in-app/read-all", headers={"X-API-Key": key})
    assert r.status_code < 400, r.text
    s = SessionLocal()
    try:
        rows = s.query(AuditLog).filter(AuditLog.request_path == f"{API}/notifications/in-app/read-all").all()
    finally:
        s.close()
    assert rows and rows[-1].user_id == 3
    assert rows[-1].details["auth"] == "api_key" and rows[-1].details["api_key_id"] == 7


# ── mandatory 2FA ─────────────────────────────────────────────────────────

def test_totp_policy_blocks_until_enrolled(client, db):
    db.add(SystemSettings(key="require_totp", value="all")); db.commit()
    h = _bearer("viewer")
    me = client.get(f"{API}/auth/me", headers=h)
    assert me.status_code == 200 and me.json()["totp_required"] is True
    r = client.get(f"{API}/auth/sessions", headers=h)
    assert r.status_code == 403 and r.json()["detail"] == "totp_enrollment_required"
    assert client.post(f"{API}/auth/totp/setup", headers=h).status_code == 200


def test_totp_policy_admins_only(client, db):
    db.add(SystemSettings(key="require_totp", value="admins")); db.commit()
    assert client.get(f"{API}/auth/sessions", headers=_bearer("viewer")).status_code == 200
    assert client.get(f"{API}/auth/sessions", headers=_bearer("admin")).status_code == 403


def test_admin_cannot_require_totp_without_own_2fa(client):
    r = client.put(f"{API}/security/settings", json={"require_totp": "all"}, headers=_bearer("admin"))
    assert r.status_code == 400


def test_cannot_disable_totp_while_required(client, db):
    db.query(User).filter(User.id == 3).update({"totp_enabled": True, "totp_secret": "JBSWY3DPEHPK3PXP"})
    db.add(SystemSettings(key="require_totp", value="all")); db.commit()
    r = client.post(f"{API}/auth/totp/disable", json={"code": "000000"}, headers=_bearer("viewer"))
    assert r.status_code == 403


# ── persistent secrets ────────────────────────────────────────────────────

def test_persistent_secret_survives_restart(tmp_path, monkeypatch):
    from app.core.config import _persistent_secret
    monkeypatch.setenv("DEPL0Y_KEY_DIR", str(tmp_path))
    monkeypatch.delenv("X_TEST_KEY", raising=False)
    first = _persistent_secret("X_TEST_KEY", "x.key", lambda: "generated-1")
    second = _persistent_secret("X_TEST_KEY", "x.key", lambda: "generated-2")
    assert first == second == "generated-1"
    assert stat.S_IMODE(os.stat(tmp_path / "x.key").st_mode) == 0o600
    monkeypatch.setenv("X_TEST_KEY", "from-env")
    assert _persistent_secret("X_TEST_KEY", "x.key", lambda: "nope") == "from-env"


# ── refresh token in an httpOnly cookie ───────────────────────────────────

def test_login_sets_httponly_refresh_cookie_and_refresh_uses_it(client, db):
    db.query(User).filter(User.id == 2).update({"hashed_password": get_password_hash("pw-123456")}); db.commit()
    r = client.post(f"{API}/auth/login", json={"username": "oper", "password": "pw-123456"})
    assert r.status_code == 200, r.text
    set_cookie = r.headers["set-cookie"].lower()
    assert "depl0y_refresh=" in set_cookie and "httponly" in set_cookie
    assert "path=/api/v1/auth" in set_cookie and "samesite=strict" in set_cookie
    old_refresh = r.json()["refresh_token"]

    # Cookie only, no body — what the browser does after a page load.
    r2 = client.post(f"{API}/auth/refresh")
    assert r2.status_code == 200, r2.text
    assert client.get(f"{API}/auth/me", headers={"Authorization": "Bearer " + r2.json()["access_token"]}).status_code == 200
    # Rotation: the old refresh token is now spent.
    client.cookies.clear()
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": old_refresh}).status_code == 401


def test_logout_revokes_cookie_session(client, db):
    db.query(User).filter(User.id == 2).update({"hashed_password": get_password_hash("pw-123456")}); db.commit()
    client.post(f"{API}/auth/login", json={"username": "oper", "password": "pw-123456"})
    cookie = client.cookies.get("depl0y_refresh")
    r = client.post(f"{API}/auth/logout")
    assert r.status_code == 200
    client.cookies.clear()
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": cookie}).status_code == 401


def test_secure_cookie_behind_https_proxy(client, db):
    db.query(User).filter(User.id == 2).update({"hashed_password": get_password_hash("pw-123456")}); db.commit()
    r = client.post(f"{API}/auth/login", json={"username": "oper", "password": "pw-123456"},
                    headers={"X-Forwarded-Proto": "https"})
    assert "secure" in r.headers["set-cookie"].lower()
