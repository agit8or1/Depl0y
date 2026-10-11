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
