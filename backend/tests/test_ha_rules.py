"""Tests for HA rules management on the HA page (Proxmox VE 9 node/resource affinity rules)."""
import inspect
import types

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import node
from app.api.auth import get_current_user, require_admin
from tests.test_ha_failover import FakePVE

ADMIN = types.SimpleNamespace(id=1)


@pytest.fixture
def pve(monkeypatch):
    fake = FakePVE(replies={("GET", "version"): {"version": "9.2.20"}, ("GET", "cluster/ha/rules"): []})
    monkeypatch.setattr(node, "_get_host", lambda host_id, db: object())
    monkeypatch.setattr(node, "_pve", lambda host: fake)
    return fake


def writes(fake):
    return [c for c in fake._calls if c[0] != "GET"]


def req(**kw):
    base = {"rule": "web-apart", "type": "resource-affinity", "resources": ["vm:101", "vm:102"]}
    base.update(kw)
    return node.HaRuleRequest(**base)


def test_list_reports_support_by_version(pve):
    pve._replies[("GET", "cluster/ha/rules")] = [{"rule": "r1", "type": "node-affinity"}]
    res = node.ha_rules(1, db=None, current_user=ADMIN)
    assert res["supported"] and res["rules"] == [{"rule": "r1", "type": "node-affinity"}]
    pve._replies[("GET", "version")] = {"version": "8.4.1"}
    res = node.ha_rules(1, db=None, current_user=ADMIN)
    assert res == {"supported": False, "pve_version": "8.4.1", "rules": []}


def test_create_node_affinity_sends_nodes_with_priorities(pve):
    body = req(rule="db-pref", type="node-affinity", resources=["vm:103", "ct:150"],
               nodes=[{"node": "pve1", "priority": 2}, {"node": "pve2", "priority": 1}, {"node": "pve3"}],
               strict=True, comment="keep db near storage")
    node.create_ha_rule(1, body, db=None, current_user=ADMIN)
    assert writes(pve) == [("POST", "cluster/ha/rules", {
        "rule": "db-pref", "type": "node-affinity", "resources": "vm:103,ct:150", "disable": 0,
        "nodes": "pve1:2,pve2:1,pve3", "strict": 1, "comment": "keep db near storage"})]


def test_create_resource_affinity_sends_affinity_only(pve):
    node.create_ha_rule(1, req(affinity="negative", disable=True), db=None, current_user=ADMIN)
    assert writes(pve) == [("POST", "cluster/ha/rules", {
        "rule": "web-apart", "type": "resource-affinity", "resources": "vm:101,vm:102", "disable": 1,
        "affinity": "negative"})]


@pytest.mark.parametrize("kw, message", [
    ({"rule": "9bad"}, "Rule ID"),
    ({"rule": "a b"}, "Rule ID"),
    ({"type": "node-affinity", "nodes": []}, "at least one node"),
    ({"resources": ["vm:101"]}, "at least two"),
    ({"type": "node-affinity", "nodes": [{"node": "pve1;rm -rf"}]}, "Invalid node name"),
])
def test_create_rejects_bad_input_before_calling_proxmox(pve, kw, message):
    with pytest.raises(HTTPException) as e:
        node.create_ha_rule(1, req(**kw), db=None, current_user=ADMIN)
    assert e.value.status_code == 422 and message in e.value.detail
    assert writes(pve) == []


@pytest.mark.parametrize("kw", [
    {"resources": ["vm:101", "100"]},
    {"resources": []},
    {"type": "group"},
    {"affinity": "sideways"},
    {"comment": "two\nlines"},
    {"nodes": [{"node": "pve1", "priority": 5000}], "type": "node-affinity"},
])
def test_model_validation(kw):
    with pytest.raises(ValidationError):
        req(**kw)


def test_update_clears_comment_and_keeps_type(pve):
    body = req(rule=None, type="node-affinity", resources=["vm:101"], nodes=[{"node": "pve2", "priority": 1}])
    node.update_ha_rule(1, "depl0y-vm-101", body, db=None, current_user=ADMIN)
    assert writes(pve) == [("PUT", "cluster/ha/rules/depl0y-vm-101", {
        "type": "node-affinity", "resources": "vm:101", "disable": 0, "nodes": "pve2:1", "strict": 0,
        "delete": "comment"})]


def test_delete_and_proxmox_errors_are_passed_on(pve):
    node.delete_ha_rule(1, "web-apart", db=None, current_user=ADMIN)
    assert writes(pve) == [("DELETE", "cluster/ha/rules/web-apart", {})]
    pve._replies[("DELETE", "cluster/ha/rules/gone")] = RuntimeError("500 Internal Server Error: no such rule 'gone'")
    with pytest.raises(HTTPException) as e:
        node.delete_ha_rule(1, "gone", db=None, current_user=ADMIN)
    assert "no such rule" in e.value.detail
    with pytest.raises(HTTPException) as e:
        node.delete_ha_rule(1, "../x", db=None, current_user=ADMIN)
    assert e.value.status_code == 422


def test_roles_and_routes():
    def dependency(fn):
        return inspect.signature(fn).parameters["current_user"].default.dependency
    assert dependency(node.ha_rules) is get_current_user
    for fn in (node.create_ha_rule, node.update_ha_rule, node.delete_ha_rule):
        assert dependency(fn) is require_admin
    from app.main import app
    paths = app.openapi()["paths"]
    assert set(paths["/api/v1/pve-node/{host_id}/cluster/ha/rules"]) == {"get", "post"}
    assert set(paths["/api/v1/pve-node/{host_id}/cluster/ha/rules/{rule}"]) == {"put", "delete"}
