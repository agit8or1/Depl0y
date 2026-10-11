"""Tests for the failover wizard's planner and its Proxmox calls (no cluster needed)."""
import copy

import pytest

from app.services import ha_failover as hf

GiB = 1 << 30


def storage(type_, shared=False, avail=500 * GiB, content="images,rootdir", active=True):
    return {"type": type_, "shared": shared, "active": active, "avail": avail, "content": content}


def node(storages, online=True, lrm=True, mem_free=64 * GiB):
    return {"online": online, "lrm": lrm, "mem_free": mem_free, "storages": storages}


def facts(config, nodes, vmtype="qemu", running=True, **extra):
    f = {
        "vmtype": vmtype, "vmid": 100, "node": "pve1", "name": "web", "running": running,
        "maxmem": 8 * GiB, "config": config, "quorate": True, "clustered": True, "qdevice": False,
        "pve_major": 9, "nodes": nodes, "ha_resources": [], "ha_rules": [], "ha_groups": [],
        "replication": [], "cluster_options": {},
    }
    f.update(extra)
    return f


NFS = storage("nfs", shared=True)
ZFS = storage("zfspool")
LVM = storage("lvmthin")
ISO_LOCAL = storage("dir", content="iso,vztmpl,backup")


def three_nodes(**overrides):
    nodes = {
        "pve1": node({"nfs": NFS, "tank": ZFS, "local-lvm": LVM, "local": ISO_LOCAL}),
        "pve2": node({"nfs": NFS, "tank": ZFS, "local-lvm": LVM, "local": ISO_LOCAL}, mem_free=32 * GiB),
        "pve3": node({"nfs": NFS, "tank": ZFS, "local-lvm": LVM, "local": ISO_LOCAL}, mem_free=96 * GiB),
    }
    for name, value in overrides.items():
        nodes[name] = value
    return nodes


def statuses(plan):
    return {c["title"]: c["status"] for c in plan["checks"]}


# ── Planner ─────────────────────────────────────────────────────────────────────

def test_shared_storage_is_eligible_and_picks_node_with_most_free_memory():
    plan = hf.build_plan(facts({"scsi0": "nfs:100/vm-100-disk-0.qcow2,size=32G"}, three_nodes()))
    assert plan["eligible"] and plan["mode"] == "shared"
    assert plan["target"] == "pve3"                      # 96 GiB free beats 32 GiB
    s = plan["settings"]
    assert s["ha_resource"] == {"sid": "vm:100", "state": "started", "max_restart": 1, "max_relocate": 1,
                                "failback": 1, "comment": hf.MANAGED_COMMENT}
    assert s["rule"]["nodes"] == "pve1:2,pve3:1" and s["rule"]["strict"] == 0
    assert s["rule"]["type"] == "node-affinity" and s["rule"]["rule"] == "depl0y-vm-100"
    assert "replication" not in s
    assert s["cluster_ha_option"] == "shutdown_policy=migrate"


def test_zfs_uses_strict_rule_and_replication_every_two_minutes():
    plan = hf.build_plan(facts({"scsi0": "tank:vm-100-disk-0,size=32G",
                                "efidisk0": "tank:vm-100-disk-1,size=1M"}, three_nodes()))
    assert plan["eligible"] and plan["mode"] == "replication" and plan["target"] == "pve3"
    s = plan["settings"]
    assert s["rule"]["strict"] == 1
    assert s["replication"] == {"id": "100-0", "target": "pve3", "type": "local",
                                "schedule": "*/2", "comment": hf.MANAGED_COMMENT}


def test_replication_job_id_skips_numbers_in_use():
    plan = hf.build_plan(facts({"scsi0": "tank:vm-100-disk-0,size=8G"}, three_nodes(),
                               replication=[{"id": "100-0", "guest": 100}, {"id": "100-2", "guest": 100},
                                            {"id": "101-1", "guest": 101}]))
    assert plan["settings"]["replication"]["id"] == "100-1"


def test_local_lvm_is_blocked_and_offers_moves_shared_first():
    plan = hf.build_plan(facts({"scsi0": "local-lvm:vm-100-disk-0,size=32G"}, three_nodes()))
    assert not plan["eligible"] and plan["mode"] is None
    assert statuses(plan)["Disks are on node-local storage"] == "fail"
    assert [o["storage"] for o in plan["move_options"]] == ["nfs", "tank"]
    assert plan["move_options"][0]["needed"] == 32 * GiB


def test_no_move_option_when_storage_too_small_or_only_on_one_node():
    nodes = three_nodes()
    nodes["pve1"]["storages"]["nfs"] = storage("nfs", shared=True, avail=10 * GiB)   # too small
    for n in ("pve2", "pve3"):
        del nodes[n]["storages"]["tank"]                                              # ZFS only on pve1
    plan = hf.build_plan(facts({"scsi0": "local-lvm:vm-100-disk-0,size=32G"}, nodes))
    assert plan["move_options"] == []
    assert statuses(plan)["No suitable storage to move to"] == "info"


def test_mixed_local_and_shared_disks_is_blocked():
    plan = hf.build_plan(facts({"scsi0": "nfs:100/vm-100-disk-0.qcow2,size=8G",
                                "scsi1": "local-lvm:vm-100-disk-1,size=8G"}, three_nodes()))
    assert not plan["eligible"]


def test_passthrough_blocks():
    plan = hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G", "hostpci0": "0000:01:00.0,pcie=1"},
                               three_nodes()))
    assert not plan["eligible"] and statuses(plan)["Passthrough device"] == "fail"


def test_local_iso_is_ejected_shared_iso_is_kept():
    cfg = {"scsi0": "nfs:100/a.qcow2,size=8G", "ide2": "local:iso/debian.iso,media=cdrom",
           "ide0": "nfs:iso/other.iso,media=cdrom", "ide3": "none,media=cdrom"}
    plan = hf.build_plan(facts(cfg, three_nodes()))
    assert plan["eligible"]
    ejects = [a for a in plan["actions"] if a["type"] == "eject_iso"]
    assert [a["key"] for a in ejects] == ["ide2"]


def test_unused_local_disk_blocks():
    plan = hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G", "unused0": "local-lvm:vm-100-disk-9"},
                               three_nodes()))
    assert not plan["eligible"] and statuses(plan)["Unused disk on local storage"] == "fail"


def test_two_nodes_without_qdevice_is_blocked_with_qdevice_ok():
    nodes = three_nodes()
    del nodes["pve3"]
    assert not hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G"}, nodes))["eligible"]
    plan = hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G"}, nodes, qdevice=True))
    assert plan["eligible"] and plan["target"] == "pve2"


def test_not_quorate_blocks():
    plan = hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G"}, three_nodes(), quorate=False))
    assert not plan["eligible"]


def test_nodes_without_ha_service_or_offline_are_not_targets():
    nodes = three_nodes()
    nodes["pve3"]["lrm"] = False
    nodes["pve2"]["online"] = False
    plan = hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G"}, nodes))
    assert not plan["eligible"] and statuses(plan)["No failover node"] == "fail"


def test_target_without_enough_zfs_space_blocks():
    nodes = three_nodes()
    nodes["pve3"]["storages"]["tank"] = storage("zfspool", avail=4 * GiB)
    nodes["pve2"]["storages"]["tank"] = storage("zfspool", avail=4 * GiB)
    plan = hf.build_plan(facts({"scsi0": "tank:vm-100-disk-0,size=32G"}, nodes))
    assert not plan["eligible"] and statuses(plan)["Not enough space for the replica"] == "fail"


def test_low_memory_target_is_only_a_warning():
    nodes = three_nodes()
    for n in ("pve2", "pve3"):
        nodes[n]["mem_free"] = 1 * GiB
    plan = hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G"}, nodes))
    assert plan["eligible"] and statuses(plan)["Failover node is short on memory"] == "warn"


def test_stopped_guest_added_as_stopped():
    plan = hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G"}, three_nodes(), running=False))
    assert plan["eligible"] and plan["settings"]["ha_resource"]["state"] == "stopped"


def test_existing_shutdown_policy_is_left_alone():
    plan = hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G"}, three_nodes(),
                               cluster_options={"ha": "shutdown_policy=failover"}))
    assert "cluster_ha_option" not in plan["settings"]


def test_already_protected_reports_existing_setup():
    plan = hf.build_plan(facts({"scsi0": "tank:vm-100-disk-0,size=8G"}, three_nodes(),
                               ha_resources=[{"sid": "vm:100", "state": "started"}],
                               ha_rules=[{"rule": "depl0y-vm-100", "type": "node-affinity", "resources": "vm:100"}],
                               replication=[{"id": "100-0", "guest": 100, "comment": hf.MANAGED_COMMENT}]))
    assert plan["already_protected"] and not plan["eligible"]
    assert [r["rule"] for r in plan["existing"]["rules"]] == ["depl0y-vm-100"]


def test_container_rootfs_and_bind_mount():
    nodes = three_nodes()
    ok = hf.build_plan(facts({"rootfs": "nfs:subvol-100-disk-0,size=8G"}, nodes, vmtype="lxc"))
    assert ok["eligible"] and ok["sid"] == "ct:100" and ok["settings"]["rule"]["rule"] == "depl0y-ct-100"
    bind = hf.build_plan(facts({"rootfs": "nfs:subvol-100-disk-0,size=8G", "mp0": "/srv/data,mp=/data"},
                               nodes, vmtype="lxc"))
    assert not bind["eligible"]


def test_running_container_gets_no_move_option():
    plan = hf.build_plan(facts({"rootfs": "local-lvm:vm-100-disk-0,size=8G"}, three_nodes(), vmtype="lxc"))
    assert plan["move_options"] == [] and statuses(plan)["Stop the container to move its disks"] == "info"
    stopped = hf.build_plan(facts({"rootfs": "local-lvm:vm-100-disk-0,size=8G"}, three_nodes(),
                                  vmtype="lxc", running=False))
    assert [o["storage"] for o in stopped["move_options"]] == ["nfs", "tank"]


# ── Proxmox calls ───────────────────────────────────────────────────────────────

class FakePVE:
    """Records proxmoxer-style calls: pve.cluster.ha.resources.post(**kw) -> ('POST', 'cluster/ha/resources', kw)."""

    def __init__(self, calls=None, path=(), replies=None):
        self._calls = [] if calls is None else calls
        self._path = path
        self._replies = replies if replies is not None else {}

    def __getattr__(self, name):
        return FakePVE(self._calls, self._path + (name,), self._replies)

    def __call__(self, *args):
        return FakePVE(self._calls, self._path + tuple(str(a) for a in args), self._replies)

    def _do(self, method, **kw):
        path = "/".join(self._path)
        self._calls.append((method, path, kw))
        reply = self._replies.get((method, path))
        if isinstance(reply, Exception):
            raise reply
        return reply(kw) if callable(reply) else reply

    def get(self, **kw):
        return self._do("GET", **kw)

    def post(self, **kw):
        return self._do("POST", **kw)

    def put(self, **kw):
        return self._do("PUT", **kw)

    def delete(self, **kw):
        return self._do("DELETE", **kw)


def writes(pve):
    return [c for c in pve._calls if c[0] != "GET"]


def test_apply_shared_makes_exactly_the_expected_calls():
    cfg = {"scsi0": "nfs:100/a.qcow2,size=8G", "ide2": "local:iso/x.iso,media=cdrom"}
    plan = hf.build_plan(facts(cfg, three_nodes()))
    pve, log = FakePVE(), []
    hf.apply_plan(pve, plan, log.append)
    assert writes(pve) == [
        ("PUT", "nodes/pve1/qemu/100/config", {"ide2": "none,media=cdrom"}),
        ("PUT", "cluster/options", {"ha": "shutdown_policy=migrate"}),
        ("POST", "cluster/ha/resources", plan["settings"]["ha_resource"]),
        ("POST", "cluster/ha/rules", plan["settings"]["rule"]),
    ]


def test_apply_replication_waits_for_first_sync_before_ha(monkeypatch):
    monkeypatch.setattr(hf.time, "sleep", lambda s: None)
    plan = hf.build_plan(facts({"scsi0": "tank:vm-100-disk-0,size=8G"}, three_nodes(),
                               cluster_options={"ha": "shutdown_policy=migrate"}))
    syncs = iter([{}, {"last_sync": 0}, {"last_sync": 1791673267}])
    pve = FakePVE(replies={("GET", "nodes/pve1/replication/100-0/status"): lambda kw: next(syncs)})
    hf.apply_plan(pve, plan, lambda t: None)
    kinds = [(m, p) for m, p, _ in writes(pve)]
    assert kinds == [("POST", "cluster/replication"), ("POST", "nodes/pve1/replication/100-0/schedule_now"),
                     ("POST", "cluster/ha/resources"), ("POST", "cluster/ha/rules")]
    status_polls = [c for c in pve._calls if c[1].endswith("/status")]
    assert len(status_polls) == 3


def test_apply_replication_error_stops_before_ha(monkeypatch):
    monkeypatch.setattr(hf.time, "sleep", lambda s: None)
    plan = hf.build_plan(facts({"scsi0": "tank:vm-100-disk-0,size=8G"}, three_nodes()))
    pve = FakePVE(replies={("GET", "nodes/pve1/replication/100-0/status"): {"error": "no space"}})
    with pytest.raises(RuntimeError, match="replication failed: no space"):
        hf.apply_plan(pve, plan, lambda t: None)
    assert not any(p.startswith("cluster/ha") for _, p, _ in writes(pve))


def test_failed_rule_rolls_back_ha_resource():
    plan = hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G"}, three_nodes(),
                               cluster_options={"ha": "shutdown_policy=migrate"}))
    pve = FakePVE(replies={("POST", "cluster/ha/rules"): RuntimeError("rule rejected")})
    with pytest.raises(RuntimeError):
        hf.apply_plan(pve, plan, lambda t: None)
    assert writes(pve)[-1] == ("DELETE", "cluster/ha/resources/vm:100", {})


def test_move_disks_then_waits_for_each_task(monkeypatch):
    monkeypatch.setattr(hf.time, "sleep", lambda s: None)
    plan = hf.build_plan(facts({"scsi0": "local-lvm:vm-100-disk-0,size=32G",
                                "scsi1": "local-lvm:vm-100-disk-1,size=8G"}, three_nodes()))
    pve = FakePVE(replies={("POST", "nodes/pve1/qemu/100/move_disk"): lambda kw: f"UPID:{kw['disk']}"})
    for upid in ("UPID:scsi0", "UPID:scsi1"):
        pve._replies[("GET", f"nodes/pve1/tasks/{upid}/status")] = {"status": "stopped", "exitstatus": "OK"}
    hf.move_disks(pve, plan, "nfs", lambda t: None)
    assert [c[2] for c in writes(pve)] == [{"disk": "scsi0", "storage": "nfs", "delete": 1},
                                           {"disk": "scsi1", "storage": "nfs", "delete": 1}]


def test_move_disk_failure_raises(monkeypatch):
    monkeypatch.setattr(hf.time, "sleep", lambda s: None)
    plan = hf.build_plan(facts({"scsi0": "local-lvm:vm-100-disk-0,size=32G"}, three_nodes()))
    pve = FakePVE(replies={("POST", "nodes/pve1/qemu/100/move_disk"): "UPID:x",
                           ("GET", "nodes/pve1/tasks/UPID:x/status"): {"status": "stopped", "exitstatus": "ERR"}})
    with pytest.raises(RuntimeError, match="task failed"):
        hf.move_disks(pve, plan, "nfs", lambda t: None)


def test_remove_deletes_rule_resource_and_managed_replication_only():
    plan = hf.build_plan(facts(
        {"scsi0": "tank:vm-100-disk-0,size=8G"}, three_nodes(),
        ha_resources=[{"sid": "vm:100", "state": "started"}],
        ha_rules=[{"rule": "depl0y-vm-100", "type": "node-affinity", "resources": "vm:100"},
                  {"rule": "shared", "type": "node-affinity", "resources": "vm:100,vm:101"}],
        replication=[{"id": "100-0", "guest": 100, "target": "pve3", "comment": hf.MANAGED_COMMENT},
                     {"id": "100-1", "guest": 100, "target": "pve2", "comment": "made by hand"}]))
    pve = FakePVE()
    hf.remove_protection(pve, plan, lambda t: None)
    assert writes(pve) == [
        ("DELETE", "cluster/ha/rules/depl0y-vm-100", {}),
        ("PUT", "cluster/ha/rules/shared", {"type": "node-affinity", "resources": "vm:101"}),
        ("DELETE", "cluster/ha/resources/vm:100", {}),
        ("DELETE", "cluster/replication/100-0", {}),
    ]


def test_gather_facts_reads_cluster_through_proxmox_api():
    replies = {
        ("GET", "cluster/status"): [{"type": "cluster", "quorate": 1}],
        ("GET", "cluster/resources"): [{"node": "pve1", "status": "online", "maxmem": 64 * GiB, "mem": 16 * GiB}],
        ("GET", "nodes/pve1/services/pve-ha-lrm/state"): {"state": "running"},
        ("GET", "nodes/pve1/storage"): [{"storage": "nfs", "type": "nfs", "shared": 1, "active": 1,
                                         "enabled": 1, "avail": 100, "content": "images"}],
        ("GET", "cluster/config/qdevice"): {},
        ("GET", "version"): {"version": "8.4.1"},
        ("GET", "cluster/ha/resources"): [], ("GET", "cluster/ha/rules"): [],
        ("GET", "cluster/replication"): [], ("GET", "cluster/options"): {},
        ("GET", "nodes/pve1/qemu/100/status/current"): {"name": "web", "status": "running", "maxmem": 1},
        ("GET", "nodes/pve1/qemu/100/config"): {"scsi0": "nfs:100/a.qcow2,size=8G"},
    }
    f = hf.gather_facts(FakePVE(replies=replies), "pve1", "qemu", 100)
    assert f["quorate"] and f["nodes"]["pve1"]["lrm"] and f["nodes"]["pve1"]["mem_free"] == 48 * GiB
    assert f["nodes"]["pve1"]["storages"]["nfs"]["shared"] and f["running"] and f["name"] == "web"
    assert f["pve_major"] == 8


# ── Proxmox VE 8 (HA groups instead of rules) ───────────────────────────────────

def test_pve8_uses_restricted_group_and_no_failback_param():
    plan = hf.build_plan(facts({"scsi0": "tank:vm-100-disk-0,size=8G"}, three_nodes(), pve_major=8,
                               cluster_options={"ha": "shutdown_policy=migrate"}))
    s = plan["settings"]
    assert "rule" not in s and "failback" not in s["ha_resource"]
    assert s["group"] == {"group": "depl0y-vm-100", "type": "group", "nodes": "pve1:2,pve3:1",
                          "restricted": 1, "nofailback": 0, "comment": hf.MANAGED_COMMENT}
    assert s["ha_resource"]["group"] == "depl0y-vm-100"


def test_pve8_apply_creates_group_before_resource(monkeypatch):
    monkeypatch.setattr(hf.time, "sleep", lambda s: None)
    plan = hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G"}, three_nodes(), pve_major=8,
                               cluster_options={"ha": "shutdown_policy=migrate"}))
    pve = FakePVE()
    hf.apply_plan(pve, plan, lambda t: None)
    assert [(m, p) for m, p, _ in writes(pve)] == [("POST", "cluster/ha/groups"), ("POST", "cluster/ha/resources")]
    assert writes(pve)[0][2]["restricted"] == 0


def test_pve8_failed_resource_removes_group():
    plan = hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G"}, three_nodes(), pve_major=8,
                               cluster_options={"ha": "shutdown_policy=migrate"}))
    pve = FakePVE(replies={("POST", "cluster/ha/resources"): RuntimeError("no")})
    with pytest.raises(RuntimeError):
        hf.apply_plan(pve, plan, lambda t: None)
    assert writes(pve)[-1] == ("DELETE", "cluster/ha/groups/depl0y-vm-100", {})


def test_pve8_remove_deletes_managed_group_but_not_others():
    base = dict(pve_major=8, ha_resources=[{"sid": "vm:100", "state": "started", "group": "depl0y-vm-100"}],
                ha_groups=[{"group": "depl0y-vm-100", "comment": hf.MANAGED_COMMENT, "nodes": "pve1:2,pve3:1"}])
    plan = hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G"}, three_nodes(), **base))
    pve = FakePVE()
    hf.remove_protection(pve, plan, lambda t: None)
    assert writes(pve) == [("DELETE", "cluster/ha/resources/vm:100", {}),
                           ("DELETE", "cluster/ha/groups/depl0y-vm-100", {})]
    other = dict(base, ha_resources=[{"sid": "vm:100", "state": "started", "group": "prod"}],
                 ha_groups=[{"group": "prod", "comment": "hand made"}])
    pve = FakePVE()
    hf.remove_protection(pve, hf.build_plan(facts({"scsi0": "nfs:100/a.qcow2,size=8G"}, three_nodes(), **other)),
                         lambda t: None)
    assert writes(pve) == [("DELETE", "cluster/ha/resources/vm:100", {})]


def test_no_move_reason_names_zfs_pool_missing_on_other_nodes():
    nodes = three_nodes()
    for n in ("pve1", "pve2", "pve3"):
        del nodes[n]["storages"]["nfs"]
    for n in ("pve2", "pve3"):
        del nodes[n]["storages"]["tank"]                                              # ZFS only on pve1
    plan = hf.build_plan(facts({"scsi0": "local-lvm:vm-100-disk-0,size=32G"}, nodes))
    detail = next(c["detail"] for c in plan["checks"] if c["title"] == "No suitable storage to move to")
    assert "ZFS storage tank is not available on any other online node" in detail
    assert "same ID" in detail


def test_no_move_reason_when_cluster_has_no_zfs_or_shared_storage():
    nodes = three_nodes()
    for n in ("pve1", "pve2", "pve3"):
        del nodes[n]["storages"]["nfs"], nodes[n]["storages"]["tank"]
    plan = hf.build_plan(facts({"scsi0": "local-lvm:vm-100-disk-0,size=32G"}, nodes))
    detail = next(c["detail"] for c in plan["checks"] if c["title"] == "No suitable storage to move to")
    assert detail.startswith("pve1 has no shared storage and no ZFS pool.")


def test_no_move_reason_when_zfs_storage_is_not_set_up_for_this_node():
    nodes = three_nodes()
    for n in ("pve1", "pve2", "pve3"):
        del nodes[n]["storages"]["nfs"]
    nodes["pve1"]["storages"]["tank"] = {**nodes["pve1"]["storages"]["tank"], "active": False, "enabled": False}
    plan = hf.build_plan(facts({"scsi0": "local-lvm:vm-100-disk-0,size=32G"}, nodes))
    detail = next(c["detail"] for c in plan["checks"] if c["title"] == "No suitable storage to move to")
    assert detail.startswith("ZFS storage tank is not set up for pve1: pve1 needs the same ZFS pool")
    assert "inactive" not in detail
