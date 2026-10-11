"""Tests for the HA page's service status and start endpoints (no cluster needed)."""
import types

import pytest
from fastapi import HTTPException

from app.api import node
from tests.test_ha_failover import FakePVE


def cluster(states, quorate=1, clustered=True, offline=()):
    """states: {node: {"pve-ha-crm": "running", "pve-ha-lrm": "stopped"}}"""
    replies = {
        ("GET", "cluster/status"): ([{"type": "cluster", "quorate": quorate}] if clustered else [])
        + [{"type": "node", "name": n} for n in states],
        ("GET", "cluster/resources"): [{"node": n, "status": "offline" if n in offline else "online"} for n in states],
    }
    for n, svcs in states.items():
        for svc, state in svcs.items():
            replies[("GET", f"nodes/{n}/services/{svc}/state")] = {"state": state}
            replies[("POST", f"nodes/{n}/services/{svc}/start")] = f"UPID:{n}:{svc}"
    return FakePVE(replies=replies)


RUNNING = {"pve-ha-crm": "running", "pve-ha-lrm": "running"}
ADMIN = types.SimpleNamespace(id=1)


@pytest.fixture
def patched(monkeypatch):
    registered = []
    monkeypatch.setattr(node, "_get_host", lambda host_id, db: object())
    monkeypatch.setattr(node.task_tracker, "register", lambda *a, **k: registered.append(a))

    def use(pve):
        monkeypatch.setattr(node, "_pve", lambda host: pve)
        return pve
    use.registered = registered
    return use


def test_status_counts_nodes_with_both_services_running(patched):
    patched(cluster({"a": RUNNING, "b": {"pve-ha-crm": "running", "pve-ha-lrm": "stopped"}, "c": RUNNING},
                    offline=("c",)))
    res = node.ha_services(1, db=None, current_user=ADMIN)
    assert (res["online"], res["running"], res["all_running"]) == (2, 1, False)
    assert {n["node"]: n["lrm"] for n in res["nodes"]} == {"a": "running", "b": "stopped", "c": "unknown"}


def test_start_only_starts_what_is_stopped_on_online_nodes(patched):
    pve = patched(cluster({"a": RUNNING, "b": {"pve-ha-crm": "stopped", "pve-ha-lrm": "stopped"},
                           "c": {"pve-ha-crm": "stopped", "pve-ha-lrm": "stopped"}}, offline=("c",)))
    res = node.start_ha_services(1, db=None, current_user=ADMIN)
    posts = [p for m, p, _ in pve._calls if m == "POST"]
    assert posts == ["nodes/b/services/pve-ha-crm/start", "nodes/b/services/pve-ha-lrm/start"]
    assert res["started"] == ["pve-ha-crm on b", "pve-ha-lrm on b"] and len(patched.registered) == 2


def test_start_when_all_running_changes_nothing(patched):
    pve = patched(cluster({"a": RUNNING, "b": RUNNING}))
    res = node.start_ha_services(1, db=None, current_user=ADMIN)
    assert not [c for c in pve._calls if c[0] == "POST"] and "already running" in res["message"]


def test_start_refuses_without_quorum_or_cluster(patched):
    patched(cluster({"a": {"pve-ha-crm": "stopped", "pve-ha-lrm": "stopped"}}, quorate=0))
    with pytest.raises(HTTPException) as e:
        node.start_ha_services(1, db=None, current_user=ADMIN)
    assert e.value.status_code == 400 and "quorate" in e.value.detail
    patched(cluster({"a": {"pve-ha-crm": "stopped", "pve-ha-lrm": "stopped"}}, clustered=False))
    with pytest.raises(HTTPException) as e:
        node.start_ha_services(1, db=None, current_user=ADMIN)
    assert e.value.status_code == 400 and "not part of a cluster" in e.value.detail


def test_routes_and_roles():
    import inspect
    from app.main import app
    from app.api.auth import require_admin, get_current_user

    def dependency(fn):
        return inspect.signature(fn).parameters["current_user"].default.dependency
    assert dependency(node.start_ha_services) is require_admin
    assert dependency(node.ha_services) is get_current_user
    paths = app.openapi()["paths"]
    assert "post" in paths["/api/v1/pve-node/{host_id}/cluster/ha/services/start"]
    assert "get" in paths["/api/v1/pve-node/{host_id}/cluster/ha/services"]
    assert "/api/v1/ha/enable" not in paths and "/api/v1/ha/disable" not in paths


# ── /ha/status (Settings summary) ───────────────────────────────────────────────

def test_ha_status_covers_every_active_host(monkeypatch):
    from app.api import ha

    class Host:
        def __init__(self, id, name):
            self.id, self.name = id, name

    hosts = [Host(1, "east"), Host(2, "west"), Host(3, "lab")]

    class Query:
        def filter(self, *a): return self
        def order_by(self, *a): return self
        def all(self): return hosts

    class DB:
        def query(self, *a): return Query()

    replies = {
        1: {("GET", "cluster/ha/status/manager_status"): {"manager_status": {"master_node": "a",
                "node_status": {"a": "online", "b": "online", "c": "online"}}, "quorum": {"quorate": "1"}},
            ("GET", "cluster/ha/resources"): [{"sid": "vm:1"}, {"sid": "vm:2"}]},
        2: {("GET", "cluster/ha/status/manager_status"): {"manager_status": {"node_status": {"d": "online"}},
                                                          "quorum": {"quorate": "1"}},
            ("GET", "cluster/ha/resources"): []},
        3: {("GET", "cluster/ha/status/manager_status"): RuntimeError("connection refused")},
    }
    monkeypatch.setattr(ha, "ProxmoxService",
                        lambda host: types.SimpleNamespace(proxmox=FakePVE(replies=replies[host.id])))
    res = ha.check_ha_status(current_user=ADMIN, db=DB())
    assert res["enabled"] and res["protected_vms"] == 2
    by = {h["name"]: h for h in res["hosts"]}
    assert (by["east"]["manager_status"], by["east"]["nodes_online"], by["east"]["quorum"]) == ("active", 3, True)
    assert by["west"]["manager_status"] == "no-master" and by["west"]["protected_vms"] == 0
    assert by["lab"]["error"] and by["lab"]["manager_status"] == "unknown"
    assert "1 endpoint" in res["message"]


def test_legacy_ha_group_and_resource_routes_are_gone():
    from app.main import app
    paths = app.openapi()["paths"]
    legacy = [p for p in paths if p.startswith("/api/v1/ha/")]
    assert legacy == ["/api/v1/ha/status"]
    assert "/api/v1/pve-node/{host_id}/cluster/ha/resources" in paths
    assert "/api/v1/pve-node/{host_id}/cluster/ha/groups" in paths
