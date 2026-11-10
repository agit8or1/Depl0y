"""Per-host access (Users → Host Access) across the API.

Host 1 is granted to the operator and the viewer; host 2 to nobody. Both
hosts are inactive with unresolvable hostnames, so a refused request never
reaches Proxmox and an accepted one fails fast.
"""
import re
from datetime import datetime

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.core.database import SessionLocal, engine
from app.core.security import create_access_token
from app.models.analysis_models import Recommendation
from app.models.database import (
    AuditLog, Base, LLMDeployment, OSType, ProxmoxHost, ProxmoxNode, ReportRun, UpdateLog, User,
    UserHostPermission, UserRole, VirtualMachine, VMGroup, VmScanCache,
)

API = "/api/v1"
MINE, OTHER = 1, 2
VM_MINE, VM_OTHER = 40, 50
NODE_MINE, NODE_OTHER = 10, 20
DENIED = "No access to this Proxmox host"


@pytest.fixture(autouse=True)
def db(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    for uid, name, role in ((1, "admin", UserRole.ADMIN), (2, "oper", UserRole.OPERATOR), (3, "viewer", UserRole.VIEWER)):
        s.add(User(id=uid, username=name, email=f"{name}@example.com", hashed_password="x", role=role))
    for hid in (MINE, OTHER):
        s.add(ProxmoxHost(id=hid, name=f"h{hid}", hostname=f"h{hid}.invalid", username="root@pam", is_active=False))
    s.flush()
    s.add_all([
        UserHostPermission(user_id=2, host_id=MINE, can_view=True),
        UserHostPermission(user_id=3, host_id=MINE, can_view=True),
        ProxmoxNode(id=NODE_MINE, host_id=MINE, node_name="pve-a", idrac_hostname="bmc-a.invalid"),
        ProxmoxNode(id=NODE_OTHER, host_id=OTHER, node_name="pve-b", idrac_hostname="bmc-b.invalid"),
    ])
    for vid, hid in ((VM_MINE, MINE), (VM_OTHER, OTHER)):
        s.add(VirtualMachine(id=vid, name=f"vm{vid}", hostname=f"vm{vid}", proxmox_host_id=hid, vmid=vid,
                             os_type=OSType.UBUNTU, cpu_cores=1, memory=512, disk_size=8,
                             username="u", password="p", created_by=1))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _h(username):
    return {"Authorization": "Bearer " + create_access_token({"sub": username, "tv": 0})}


# ── every route addressed by host_id / vm_id / node_id ────────────────────

def _routes():
    from app.main import app
    from app.api.auth import require_admin

    def walk(routes, prefix=""):
        for r in routes:
            if type(r).__name__ == "_IncludedRouter":
                yield from walk(r.original_router.routes, prefix + r.include_context.prefix)
            elif isinstance(r, APIRoute):
                yield prefix + r.path, r

    def calls(dep, acc):
        if dep.call is not None:
            acc.add(dep.call)
        for d in dep.dependencies:
            calls(d, acc)
        return acc

    for path, r in walk(app.routes):
        if require_admin in calls(r.dependant, set()):
            continue  # admins reach every host
        for method in sorted(r.methods - {"HEAD", "OPTIONS"}):
            yield method, path


def _fill(path, **ids):
    def sub(m):
        name = m.group(1)
        return str(ids.get(name, "100"))
    return re.sub(r"{(\w+)(?::\w+)?}", sub, path)


def _scoped(param):
    return [(m, p) for m, p in _routes() if re.search(r"{%s(?::\w+)?}" % param, p)]


HOST_ROUTES = _scoped("host_id")
VM_ROUTES = _scoped("vm_id")
NODE_ROUTES = _scoped("node_id")


def test_route_inventory_is_not_empty():
    # Guard against the walker silently finding nothing after a FastAPI change.
    assert len(HOST_ROUTES) > 150 and len(VM_ROUTES) > 20 and len(NODE_ROUTES) > 15


@pytest.mark.parametrize("method,path", HOST_ROUTES)
def test_host_id_routes_refuse_other_host(client, method, path):
    r = client.request(method, _fill(path, host_id=OTHER, vm_id=VM_MINE, node_id=NODE_MINE),
                       headers=_h("oper"), json={})
    assert r.status_code == 403 and r.json().get("detail") == DENIED, (method, path, r.status_code, r.text[:200])


@pytest.mark.parametrize("method,path", VM_ROUTES)
def test_vm_id_routes_refuse_vm_on_other_host(client, method, path):
    r = client.request(method, _fill(path, vm_id=VM_OTHER), headers=_h("oper"), json={})
    assert r.status_code == 403 and r.json().get("detail") == DENIED, (method, path, r.status_code, r.text[:200])


@pytest.mark.parametrize("method,path", NODE_ROUTES)
def test_node_id_routes_refuse_node_on_other_host(client, method, path):
    r = client.request(method, _fill(path, node_id=NODE_OTHER), headers=_h("oper"), json={})
    assert r.status_code == 403 and r.json().get("detail") == DENIED, (method, path, r.status_code, r.text[:200])


def test_granted_host_and_admin_pass_the_scope_check(client):
    assert client.get(f"{API}/proxmox/{MINE}", headers=_h("oper")).status_code == 200
    assert client.get(f"{API}/proxmox/{OTHER}", headers=_h("admin")).status_code == 200
    assert client.get(f"{API}/vms/{VM_MINE}", headers=_h("oper")).status_code == 200
    assert client.get(f"{API}/proxmox/nodes/{NODE_MINE}", headers=_h("oper")).status_code == 200


def test_permission_row_without_rights_is_no_access(client, db):
    db.query(UserHostPermission).filter(UserHostPermission.user_id == 2).update({"can_view": False})
    db.commit()
    assert client.get(f"{API}/proxmox/{MINE}", headers=_h("oper")).status_code == 403


def test_api_key_follows_host_scope(client, db):
    from app.core.security import get_password_hash
    from app.models.database import ApiKey
    key = "dk_" + "s" * 40
    db.add(ApiKey(user_id=2, name="k", key_prefix=key[:8], key_hash=get_password_hash(key), is_active=True))
    db.commit()
    assert client.get(f"{API}/proxmox/{OTHER}", headers={"X-API-Key": key}).status_code == 403
    assert client.get(f"{API}/proxmox/{MINE}", headers={"X-API-Key": key}).status_code == 200


# ── host named in the query or body ───────────────────────────────────────

@pytest.mark.parametrize("path", [
    f"/pve-vm/search?host_id={OTHER}",
    f"/pve-vm/tags?host_id={OTHER}",
    f"/llm/gpu-devices?host_id={OTHER}&node_id={NODE_OTHER}",
])
def test_query_host_id_refused(client, path):
    r = client.get(API + path, headers=_h("oper"))
    assert r.status_code == 403 and r.json()["detail"] == DENIED


VMT = {"host_id": OTHER, "node": "pve-b", "vmid": 100}
BODY_CASES = [
    ("/vms/", {"name": "x", "hostname": "x", "proxmox_host_id": OTHER, "node_id": NODE_OTHER, "os_type": "ubuntu",
               "cpu_cores": 1, "memory": 512, "disk_size": 8, "username": "u", "password": "Passw0rd!x"}),
    ("/vms/adopt", {"vmid": 100, "proxmox_host_id": OTHER, "node": "pve-b"}),
    ("/pve-vm/bulk/power", {"vms": [VMT], "action": "start"}),
    ("/pve-vm/bulk/snapshot", {"vms": [VMT], "snapname": "s"}),
    ("/pve-vm/bulk/migrate", {"vms": [VMT], "target_node": "pve-c"}),
    ("/pve-vm/scripts/resource-audit", {"host_id": OTHER}),
    ("/pve-vm/bulk-tag", {"vmids": [VMT], "tags_add": ["t"]}),
    ("/vm-import/from-url", {"url": "https://example.invalid/x.qcow2", "proxmox_host_id": OTHER, "node": "pve-b",
                             "storage": "local", "vm_name": "x"}),
    ("/vm-import/convert-disk", {"proxmox_host_id": OTHER, "node": "pve-b", "source_volid": "local:iso/a.vmdk",
                                 "target_storage": "local-lvm"}),
    ("/vm-groups/", {"name": "g", "host_id": OTHER}),
    ("/cloud-images/setup-templates", {"node_id": NODE_OTHER, "cloud_image_ids": []}),
    ("/ai-reports/reports", {"report_type": "health", "scope_type": "cluster", "scope_ref": str(OTHER)}),
    ("/ai-reports/reports", {"report_type": "health", "scope_type": "global"}),
]


@pytest.mark.parametrize("path,body", BODY_CASES)
def test_body_host_refused(client, path, body):
    r = client.post(API + path, json=body, headers=_h("oper"))
    assert r.status_code == 403, (path, r.status_code, r.text[:300])


def test_mixed_bulk_request_refused_entirely(client):
    mine = {"host_id": MINE, "node": "pve-a", "vmid": 100}
    r = client.post(f"{API}/pve-vm/bulk/power", json={"vms": [mine, VMT], "action": "start"}, headers=_h("oper"))
    assert r.status_code == 403


def test_create_vm_rejects_node_from_another_host(client):
    body = dict(BODY_CASES[0][1], proxmox_host_id=MINE)   # node_id still on host 2
    r = client.post(f"{API}/vms/", json=body, headers=_h("oper"))
    assert r.status_code == 400


# ── lists only show the caller's hosts ────────────────────────────────────

def test_host_and_vm_lists_are_scoped(client, db):
    assert [h["id"] for h in client.get(f"{API}/proxmox/", headers=_h("oper")).json()] == [MINE]
    assert len(client.get(f"{API}/proxmox/", headers=_h("admin")).json()) == 2
    db.query(VirtualMachine).update({"status": "running"}); db.commit()
    assert [v["id"] for v in client.get(f"{API}/vms/managed", headers=_h("oper")).json()] == [VM_MINE]
    recent = client.get(f"{API}/dashboard/activity", headers=_h("oper")).json()["recent_vms"]
    assert [v["id"] for v in recent] == [VM_MINE]
    nodes = client.get(f"{API}/idrac/node/list", headers=_h("oper")).json()
    assert [n["id"] for n in nodes] == [NODE_MINE]


def test_scan_cache_update_logs_and_llm_deployments_are_scoped(client, db):
    for vid in (VM_MINE, VM_OTHER):
        db.add(VmScanCache(vm_id=vid, scan_type="updates"))
        db.add(UpdateLog(id=vid, vm_id=vid, initiated_by=1, status="done", started_at=datetime.utcnow()))
        db.add(LLMDeployment(vm_id=vid, engine="ollama", model="m", ui_type="none", os_variant="u", created_by=1))
    db.commit()
    assert [r["vm_id"] for r in client.get(f"{API}/updates/cache", headers=_h("oper")).json()] == [VM_MINE]
    assert client.get(f"{API}/updates/log/{VM_OTHER}", headers=_h("oper")).status_code == 403
    assert client.get(f"{API}/updates/log/{VM_MINE}", headers=_h("oper")).status_code == 200
    assert [d["vm_id"] for d in client.get(f"{API}/llm/deployments", headers=_h("oper")).json()] == [VM_MINE]
    other_dep = db.query(LLMDeployment).filter(LLMDeployment.vm_id == VM_OTHER).first().id
    assert client.get(f"{API}/llm/deployments/{other_dep}", headers=_h("oper")).status_code == 403


def test_recommendations_are_scoped(client, db):
    for i, hid in ((1, MINE), (2, OTHER)):
        db.add(Recommendation(id=i, host_id=hid, category="storage", rule_type="r", severity="warning",
                              title=f"t{hid}", dismissed=False, created_at=datetime.utcnow()))
    db.commit()
    recs = client.get(f"{API}/analysis/recommendations", headers=_h("oper")).json()
    assert [r["host_id"] for r in (recs if isinstance(recs, list) else recs["recommendations"])] == [MINE]
    assert client.get(f"{API}/analysis/summary", headers=_h("oper")).json()["total"] == 1
    assert client.post(f"{API}/analysis/recommendations/2/dismiss", headers=_h("oper")).status_code == 403
    client.post(f"{API}/analysis/recommendations/dismiss-all", headers=_h("oper"))
    assert db.query(Recommendation).filter(Recommendation.id == 2).one().dismissed is False


def test_vm_groups_are_scoped(client, db):
    db.add_all([VMGroup(id=1, name="mine", host_id=MINE), VMGroup(id=2, name="other", host_id=OTHER),
                VMGroup(id=3, name="unbound", host_id=None)])
    db.commit()
    names = {g["name"] for g in client.get(f"{API}/vm-groups/", headers=_h("oper")).json()}
    assert names == {"mine", "unbound"}
    assert client.get(f"{API}/vm-groups/2", headers=_h("oper")).status_code == 403
    assert client.put(f"{API}/vm-groups/1", json={"host_id": OTHER}, headers=_h("oper")).status_code == 403


def test_ai_reports_are_scoped(client, db):
    db.add_all([
        ReportRun(id=1, title="mine", report_type="health", scope_type="cluster", scope_ref=str(MINE)),
        ReportRun(id=2, title="other", report_type="health", scope_type="cluster", scope_ref=str(OTHER)),
        ReportRun(id=3, title="global", report_type="health", scope_type="global"),
        ReportRun(id=4, title="node-a", report_type="health", scope_type="node", scope_ref="pve-a"),
    ])
    db.commit()
    titles = {r["title"] for r in client.get(f"{API}/ai-reports/reports", headers=_h("oper")).json()}
    assert titles == {"mine", "node-a"}
    assert len(client.get(f"{API}/ai-reports/reports", headers=_h("admin")).json()) == 4
    for rid in (2, 3):
        assert client.get(f"{API}/ai-reports/reports/{rid}", headers=_h("oper")).status_code == 403
        assert client.delete(f"{API}/ai-reports/reports/{rid}", headers=_h("oper")).status_code == 403


def test_audit_feeds_show_only_own_entries(client, db):
    db.add_all([AuditLog(action="vm_start", user_id=2), AuditLog(action="vm_delete", user_id=1)])
    db.commit()
    feed = client.get(f"{API}/audit/feed", headers=_h("oper")).json()
    assert [e["user"] for e in (feed if isinstance(feed, list) else feed["items"])] == ["oper"]
    assert [e["user"] for e in client.get(f"{API}/dashboard/recent-activity", headers=_h("oper")).json()] == ["oper"]


def test_bmc_status_and_history_are_scoped(client, monkeypatch):
    from app.api import idrac
    monkeypatch.setattr(idrac, "bmc_status_cache", {
        f"pve:{MINE}": {"h": 1}, f"pve:{OTHER}": {"h": 2},
        f"pve_node:{NODE_MINE}": {"n": 1}, f"pve_node:{NODE_OTHER}": {"n": 2},
        "pbs:1": {"p": 1}, "standalone:1": {"s": 1},
    })
    keys = set(client.get(f"{API}/idrac/status", headers=_h("viewer")).json())
    assert keys == {f"pve:{MINE}", f"pve_node:{NODE_MINE}", "pbs:1", "standalone:1"}
    assert client.get(f"{API}/idrac/history/pve_node:{NODE_OTHER}", headers=_h("viewer")).status_code == 403
    assert client.get(f"{API}/idrac/history/pve:{OTHER}", headers=_h("viewer")).status_code == 403
    assert client.get(f"{API}/idrac/history/pve_node:{NODE_MINE}", headers=_h("viewer")).status_code == 200


def test_running_tasks_are_scoped(client, monkeypatch):
    from app.api import tasks
    monkeypatch.setattr(tasks.task_tracker, "get_running", lambda: [
        {"upid": "a", "host_id": MINE, "user_id": 1}, {"upid": "b", "host_id": OTHER, "user_id": 2},
        {"upid": "c", "host_id": None, "user_id": 2}, {"upid": "d", "host_id": None, "user_id": 1},
    ])
    monkeypatch.setattr(tasks.task_tracker, "estimate_progress", lambda t: 0.0)
    upids = {t["upid"] for t in client.get(f"{API}/tasks/running", headers=_h("oper")).json()}
    assert upids == {"a", "c"}
    assert len(client.get(f"{API}/tasks/running", headers=_h("admin")).json()) == 4


def test_federation_summary_is_trimmed_per_user(client, db):
    from app.api.proxmox import _federation_for_user, _federation_response
    rows = [{"host_id": hid, "vm_count": hid, "lxc_count": 0, "node_count": 1, "storage_total_gb": 1.0,
             "storage_used_gb": 0.5, "status": "online"} for hid in (MINE, OTHER)]
    full = _federation_response(rows, "now")
    oper = db.query(User).filter(User.id == 2).one()
    mine = _federation_for_user(full, oper, db)
    assert [h["host_id"] for h in mine["hosts"]] == [MINE] and mine["total_vms"] == MINE


def test_time_sync_targets_are_trimmed_per_user(db):
    from app.api.time_sync import _status_for_user
    payload = {"generated_at": "now", "drift_threshold_seconds": 5, "summary": {}, "targets": [
        {"kind": "pve_node", "id": NODE_MINE, "drift_seconds": 0}, {"kind": "pve_node", "id": NODE_OTHER},
        {"kind": "bmc_node", "id": NODE_OTHER}, {"kind": "pbs", "id": 1, "drift_seconds": 0},
    ]}
    oper = db.query(User).filter(User.id == 2).one()
    out = _status_for_user(payload, oper, db)
    assert [(t["kind"], t["id"]) for t in out["targets"]] == [("pve_node", NODE_MINE), ("pbs", 1)]
    assert out["summary"]["total"] == 2
