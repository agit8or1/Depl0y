"""Minimum roles for infrastructure-level actions.

Operators manage guests; physical servers (BMC power, event logs, OS package
updates), cluster/node-wide operations, shared storage and global settings
are admin-only. Viewers may read, but not trigger logins to infrastructure.
"""
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.core.database import SessionLocal, engine
from app.core.security import create_access_token
from app.models.database import Base, User, UserRole

API = "/api/v1"

EXPECTED = {
    # BMC power actions
    ("POST", "/idrac/{host_id}/power/{action}"): "admin",
    ("POST", "/idrac/node/{node_id}/power/{action}"): "admin",
    ("POST", "/idrac/standalone/{bmc_id}/power/{action}"): "admin",
    ("POST", "/pbs/{server_id}/idrac/power/{action}"): "admin",
    # clearing BMC event logs
    ("POST", "/idrac/{host_id}/clear-sel"): "admin",
    ("POST", "/idrac/node/{node_id}/clear-sel"): "admin",
    ("POST", "/idrac/standalone/{bmc_id}/clear-sel"): "admin",
    ("POST", "/pbs/{server_id}/idrac/clear-sel"): "admin",
    # OS package upgrade on the physical server, as root
    ("POST", "/idrac/{host_id}/ssh/update"): "admin",
    ("POST", "/idrac/node/{node_id}/ssh/update"): "admin",
    ("POST", "/idrac/standalone/{bmc_id}/ssh/update"): "admin",
    ("POST", "/pbs/{server_id}/idrac/ssh/update"): "admin",
    # cluster / node / shared resources / global settings
    ("POST", "/cluster/{host_id}/nodes/{node}/evacuate"): "admin",
    ("GET", "/cluster/{host_id}/config/join"): "admin",
    ("DELETE", "/pve-node/{host_id}/nodes/{node}/storage/{storage}/content/{volid:path}"): "admin",
    ("GET", "/pve-node/{host_id}/access/acl"): "admin",
    ("POST", "/pbs-mgmt/{server_id}/sync-jobs"): "admin",
    ("PUT", "/updates/schedule"): "admin",
    ("DELETE", "/isos/{iso_id}"): "admin",
    ("GET", "/system-updates/log"): "admin",
    # logs into a Proxmox host as root
    ("GET", "/cloud-images/ssh-status"): "operator",
    # unchanged guest-level actions stay operator (guards against over-tightening)
    ("POST", "/pve-vm/{host_id}/{node}/{vmid}/start"): "operator",
    ("POST", "/pbs-mgmt/{server_id}/jobs/{job_id}/run"): "operator",
    ("POST", "/cloud-images/{image_id}/download"): "operator",
}


def _routes():
    from app.main import app

    def walk(routes, prefix=""):
        for r in routes:
            if type(r).__name__ == "_IncludedRouter":
                yield from walk(r.original_router.routes, prefix + r.include_context.prefix)
            elif isinstance(r, APIRoute):
                yield prefix + r.path, r

    return {(m, p[len(API):]): r for p, r in walk(app.routes) for m in r.methods}


def _min_role(route):
    from app.api.auth import get_current_user, require_admin, require_operator
    seen = set()

    def calls(dep):
        if dep.call is not None:
            seen.add(dep.call)
        for d in dep.dependencies:
            calls(d)
    calls(route.dependant)
    if require_admin in seen:
        return "admin"
    if require_operator in seen:
        return "operator"
    return "viewer" if get_current_user in seen else "none"


@pytest.mark.parametrize("key,expected", sorted(EXPECTED.items()))
def test_minimum_role(key, expected):
    routes = _routes()
    assert key in routes, f"route moved: {key}"
    assert _min_role(routes[key]) == expected


# ── the same, end to end ─────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    from app.core.config import settings
    from app.main import app
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    for uid, name, role in ((1, "admin", UserRole.ADMIN), (2, "oper", UserRole.OPERATOR), (3, "viewer", UserRole.VIEWER)):
        s.add(User(id=uid, username=name, email=f"{name}@example.com", hashed_password="x", role=role))
    s.commit()
    s.close()
    return TestClient(app)


def _h(username):
    return {"Authorization": "Bearer " + create_access_token({"sub": username, "tv": 0})}


@pytest.mark.parametrize("method,path", [
    ("post", "/idrac/standalone/1/power/off"),
    ("post", "/idrac/standalone/1/clear-sel"),
    ("post", "/idrac/standalone/1/ssh/update"),
    ("put", "/updates/schedule"),
    ("delete", "/isos/1"),
    ("get", "/system-updates/log"),
])
def test_operator_refused_admin_reaches_handler(client, method, path):
    kw = {"json": {}} if method in ("post", "put") else {}
    r = getattr(client, method)(API + path, headers=_h("oper"), **kw)
    assert r.status_code == 403, (path, r.status_code)
    r = getattr(client, method)(API + path, headers=_h("admin"), **kw)
    assert r.status_code != 403, (path, r.status_code, r.text[:200])


def test_viewer_cannot_trigger_ssh_status_check(client):
    assert client.get(f"{API}/cloud-images/ssh-status", headers=_h("viewer")).status_code == 403
