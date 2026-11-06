"""VM-agent enrollment: only an admin-issued, single-use, VM-bound token can register an agent."""
import threading
import types
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import vm_agent
from app.api.auth import get_current_user, require_admin
from app.core.database import SessionLocal, engine
from app.models.database import Base
from app.middleware.body_limit import BodySizeLimitMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.models.database import (
    AuditLog, OSType, SystemSettings, User, UserRole, VirtualMachine, VmAgent,
    VmAgentEnrollment, VmScanResult,
)

PREFIX = "/api/v1/vm-agent"


@pytest.fixture(autouse=True)
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    s.add(User(id=1, username="admin", email="a@example.com", hashed_password="x", role=UserRole.ADMIN))
    s.add(User(id=2, username="viewer", email="v@example.com", hashed_password="x", role=UserRole.VIEWER))
    for vid in (10, 11):
        s.add(VirtualMachine(id=vid, name=f"vm{vid}", hostname=f"vm{vid}", proxmox_host_id=1,
                             os_type=OSType.UBUNTU, cpu_cores=1, memory=512, disk_size=8, username="ubuntu", password="x", created_by=1))
    s.add(SystemSettings(key="linux_vm_agent_enabled", value="true"))
    s.commit()
    yield s
    s.close()


def _app(user_id=1, rate_limit=False):
    app = FastAPI()
    app.include_router(vm_agent.router, prefix=PREFIX)
    app.add_middleware(BodySizeLimitMiddleware, limits={
        f"{PREFIX}/register": vm_agent.REGISTER_BODY_LIMIT,
        f"{PREFIX}/report": vm_agent.REPORT_BODY_LIMIT,
    })
    if rate_limit:
        app.add_middleware(RateLimitMiddleware, requests_per_minute=1000)

    def current_user():
        s = SessionLocal()
        try:
            return s.query(User).filter(User.id == user_id).first()
        finally:
            s.close()
    app.dependency_overrides[get_current_user] = current_user
    if user_id == 1:
        app.dependency_overrides[require_admin] = current_user
    return app


@pytest.fixture
def client():
    return TestClient(_app())


def _enroll(client, vm_id=10, ttl=60):
    r = client.post(f"{PREFIX}/enrollments", json={"vm_id": vm_id, "ttl_minutes": ttl})
    assert r.status_code == 201, r.text
    return r.json()


def _register(client, token=None, **body):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post(f"{PREFIX}/register", json={"hostname": "vm-a", **body}, headers=headers)


def _agents():
    s = SessionLocal()
    try:
        return s.query(VmAgent).all()
    finally:
        s.close()


# ── Enrollment issuance ─────────────────────────────────────────────────────

def test_enrollment_token_is_stored_hashed_and_shown_once(client):
    e = _enroll(client)
    assert len(e["token"]) >= 40 and e["token"] in e["install_command"]
    s = SessionLocal()
    row = s.query(VmAgentEnrollment).one()
    assert row.token_hash != e["token"] and len(row.token_hash) == 64
    assert row.vm_id == 10 and row.created_by == 1
    s.close()
    listed = client.get(f"{PREFIX}/enrollments").json()
    assert listed[0]["status"] == "pending" and "token" not in listed[0]


def test_non_admin_cannot_issue_enrollment():
    r = TestClient(_app(user_id=2)).post(f"{PREFIX}/enrollments", json={"vm_id": 10})
    assert r.status_code == 403


def test_enrollment_ttl_is_bounded(client):
    for ttl in (0, 4, 24 * 60 + 1):
        assert client.post(f"{PREFIX}/enrollments", json={"vm_id": 10, "ttl_minutes": ttl}).status_code == 422


def test_enrollment_for_unknown_vm_is_refused(client):
    assert client.post(f"{PREFIX}/enrollments", json={"vm_id": 999}).status_code == 404


# ── Registration ────────────────────────────────────────────────────────────

def test_missing_token_is_rejected(client):
    r = _register(client, vm_id=10)
    assert r.status_code == 401
    assert _agents() == []


def test_invalid_token_is_rejected(client):
    _enroll(client)
    r = _register(client, token="not-a-real-token", vm_id=10)
    assert r.status_code == 401
    assert _agents() == []


def test_expired_token_is_rejected(client):
    e = _enroll(client)
    s = SessionLocal()
    s.query(VmAgentEnrollment).update({"expires_at": datetime.utcnow() - timedelta(seconds=1)})
    s.commit()
    s.close()
    assert _register(client, token=e["token"]).status_code == 401
    assert _agents() == []


def test_valid_token_registers_agent_bound_to_enrolled_vm(client):
    e = _enroll(client, vm_id=11)
    r = _register(client, token=e["token"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["vm_id"] == 11 and body["token"] != e["token"]
    [agent] = _agents()
    assert agent.vm_id == 11 and agent.token == body["token"]
    s = SessionLocal()
    row = s.query(VmAgentEnrollment).one()
    assert row.used_at is not None and row.agent_id == agent.id
    assert s.query(AuditLog).filter(AuditLog.action == "vm_agent_registered").count() == 1
    s.close()


def test_reused_token_is_rejected(client):
    e = _enroll(client)
    assert _register(client, token=e["token"]).status_code == 201
    assert _register(client, token=e["token"]).status_code == 401
    assert len(_agents()) == 1


def test_concurrent_reuse_registers_exactly_once(client):
    e = _enroll(client)
    n = 12
    barrier = threading.Barrier(n)
    outcomes = []
    request = types.SimpleNamespace(client=types.SimpleNamespace(host="127.0.0.1"), headers={})

    def worker():
        s = SessionLocal()
        try:
            barrier.wait()
            vm_agent.register_agent(vm_agent.AgentRegisterRequest(hostname="race"), request, s,
                                    authorization=f"Bearer {e['token']}")
            outcomes.append(201)
        except HTTPException as exc:
            outcomes.append(exc.status_code)
        except Exception as exc:  # e.g. sqlite "database is locked" — still not a registration
            outcomes.append(type(exc).__name__)
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count(201) == 1, outcomes
    assert len(_agents()) == 1


def test_substituted_vm_id_is_rejected_and_token_stays_usable(client):
    e = _enroll(client, vm_id=10)
    r = _register(client, token=e["token"], vm_id=11)
    assert r.status_code == 403
    assert _agents() == []
    # Not consumed by the rejected attempt: the intended VM can still enroll.
    ok = _register(client, token=e["token"], vm_id=10)
    assert ok.status_code == 201 and ok.json()["vm_id"] == 10


def test_registration_refused_when_feature_disabled(client, db):
    e = _enroll(client)
    db.query(SystemSettings).filter(SystemSettings.key == "linux_vm_agent_enabled").update({"value": "false"})
    db.commit()
    assert _register(client, token=e["token"]).status_code == 403
    assert client.post(f"{PREFIX}/enrollments", json={"vm_id": 10}).status_code == 403
    assert _agents() == []


def test_feature_missing_setting_counts_as_disabled(client, db):
    db.query(SystemSettings).delete()
    db.commit()
    assert _register(client, token="anything").status_code == 403


def test_registration_field_sizes_are_bounded(client):
    e = _enroll(client)
    assert _register(client, token=e["token"], hostname="h" * 254).status_code == 422
    assert _register(client, token=e["token"], agent_version="v" * 51).status_code == 422
    # Validation failures do not burn the token.
    assert _register(client, token=e["token"]).status_code == 201


def test_registration_body_size_is_capped(client):
    e = _enroll(client)
    big = {"hostname": "a", "os_info": "x" * (vm_agent.REGISTER_BODY_LIMIT + 1)}
    r = client.post(f"{PREFIX}/register", json=big, headers={"Authorization": f"Bearer {e['token']}"})
    assert r.status_code == 413


def test_registration_is_rate_limited_per_ip(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH", 5)
    c = TestClient(_app(rate_limit=True))
    codes = [_register(c, token=f"guess-{i}").status_code for i in range(7)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]


# ── Reporting ───────────────────────────────────────────────────────────────

def _scan(**kw):
    return {"scan_type": "security", "status": "completed", "summary": "ok", **kw}


def _existing_agent(db, last_seen=None):
    a = VmAgent(vm_id=10, token="11111111-2222-3333-4444-555555555555", hostname="old", enabled=True,
                registered_at=datetime.utcnow(), last_seen=last_seen)
    db.add(a)
    db.commit()
    return a


def test_existing_authorized_agent_can_still_report(client, db):
    a = _existing_agent(db)
    r = client.post(f"{PREFIX}/report", json={"hostname": "new", "scans": [_scan(), _scan()]},
                    headers={"Authorization": f"Bearer {a.token}"})
    assert r.status_code == 200 and r.json() == {"received": 2}
    db.expire_all()
    assert db.query(VmScanResult).filter(VmScanResult.vm_agent_id == a.id).count() == 2
    assert db.query(VmAgent).get(a.id).hostname == "new"


def test_newly_enrolled_agent_can_report(client):
    e = _enroll(client)
    token = _register(client, token=e["token"]).json()["token"]
    r = client.post(f"{PREFIX}/report", json={"scans": [_scan()]}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_enrollment_token_cannot_be_used_to_report(client):
    e = _enroll(client)
    r = client.post(f"{PREFIX}/report", json={"scans": []}, headers={"Authorization": f"Bearer {e['token']}"})
    assert r.status_code == 401


def test_report_scan_count_and_sizes_are_bounded(client, db):
    a = _existing_agent(db)
    h = {"Authorization": f"Bearer {a.token}"}
    too_many = [_scan() for _ in range(vm_agent.MAX_SCANS_PER_REPORT + 1)]
    assert client.post(f"{PREFIX}/report", json={"scans": too_many}, headers=h).status_code == 422
    big = [_scan(result_json="x" * (vm_agent.MAX_RESULT_JSON + 1))]
    assert client.post(f"{PREFIX}/report", json={"scans": big}, headers=h).status_code == 422
    assert db.query(VmScanResult).count() == 0


def test_report_body_size_is_capped_including_chunked(client, db):
    a = _existing_agent(db)
    h = {"Authorization": f"Bearer {a.token}", "Content-Type": "application/json"}
    blob = b'{"scans": [], "os_info": "' + b"x" * (vm_agent.REPORT_BODY_LIMIT + 10) + b'"}'
    assert client.post(f"{PREFIX}/report", content=blob, headers=h).status_code == 413

    def chunks():  # no Content-Length: counted as it streams
        for i in range(0, len(blob), 64 * 1024):
            yield blob[i:i + 64 * 1024]
    assert client.post(f"{PREFIX}/report", content=chunks(), headers=h).status_code == 413


def test_report_rate_is_limited_per_agent(client, db):
    a = _existing_agent(db, last_seen=datetime.utcnow())
    r = client.post(f"{PREFIX}/report", json={"scans": [_scan()]}, headers={"Authorization": f"Bearer {a.token}"})
    assert r.status_code == 429


def test_stored_scan_history_is_bounded(client, db, monkeypatch):
    monkeypatch.setattr(vm_agent, "MAX_STORED_SCANS_PER_AGENT", 3)
    monkeypatch.setattr(vm_agent, "MIN_REPORT_INTERVAL_S", 0)
    a = _existing_agent(db)
    for _ in range(3):
        client.post(f"{PREFIX}/report", json={"scans": [_scan(), _scan()]},
                    headers={"Authorization": f"Bearer {a.token}"})
    assert db.query(VmScanResult).count() == 3


def test_report_refused_when_feature_disabled(client, db):
    a = _existing_agent(db)
    db.query(SystemSettings).update({"value": "false"})
    db.commit()
    r = client.post(f"{PREFIX}/report", json={"scans": [_scan()]}, headers={"Authorization": f"Bearer {a.token}"})
    assert r.status_code == 403


# ── Install script ──────────────────────────────────────────────────────────

def test_enrollment_install_script_holds_no_secret(client, db):
    _existing_agent(db)
    script = client.get(f"{PREFIX}/install.sh").text
    assert "11111111-2222" not in script
    assert 'ENROLL_TOKEN="${1:-$DEPL0Y_ENROLL_TOKEN}"' in script and "/api/v1/vm-agent/register" in script
    assert "chmod 600 /opt/depl0y-agent/env" in script


def test_install_script_for_unknown_agent_token_is_404(client):
    assert client.get(f"{PREFIX}/install.sh", params={"token": "nope"}).status_code == 404


def test_revoked_enrollment_cannot_register(client):
    e = _enroll(client)
    assert client.delete(f"{PREFIX}/enrollments/{e['id']}").status_code == 200
    assert _register(client, token=e["token"]).status_code == 401


def test_main_app_wires_body_limits_rate_limit_and_routes():
    import app.main as main
    from app.middleware import rate_limit
    paths = set(main.app.openapi()["paths"])
    assert {f"{PREFIX}/register", f"{PREFIX}/enrollments", "/api/v1/ssh-host-keys/"} <= paths
    assert any(m.cls is BodySizeLimitMiddleware for m in main.app.user_middleware)
    assert f"{PREFIX}/register" in rate_limit._AUTH_PATHS
