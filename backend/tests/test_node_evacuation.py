"""Node maintenance preview and verified evacuation, against a simulated Proxmox cluster.

`SimPVE` answers the proxmoxer calls node_evacuation makes and keeps state: guests really
change node when a migration task finishes, tasks run for a few polls, nodes can go offline,
and failures can be injected. No real cluster is touched.
"""
import copy
import itertools
import re

import pytest

from app.services import node_evacuation as ne

GiB = 1 << 30
ALL_PRIVS = {p: 1 for p in ("Sys.Audit", "VM.Audit", "Datastore.Audit", "VM.Migrate", "VM.PowerMgmt",
                            "Datastore.AllocateSpace", "Mapping.Use", "Mapping.Audit")}
AUDITOR = {"/": {"Sys.Audit": 1, "VM.Audit": 1, "Datastore.Audit": 1, "Mapping.Audit": 1, "Pool.Audit": 1,
                 "SDN.Audit": 1}}


class Forbidden(Exception):
    pass


class _Path:
    def __init__(self, sim, path=()):
        self._sim, self._path = sim, path

    def __getattr__(self, name):
        return _Path(self._sim, self._path + (name,))

    def __call__(self, *args):
        return _Path(self._sim, self._path + tuple(str(a) for a in args))

    def get(self, **kw):
        return self._sim.handle("GET", self._path, kw)

    def post(self, **kw):
        return self._sim.handle("POST", self._path, kw)

    def put(self, **kw):
        return self._sim.handle("PUT", self._path, kw)

    def delete(self, **kw):
        return self._sim.handle("DELETE", self._path, kw)


def stor(type_, shared=False, avail=1000 * GiB, content="images,rootdir"):
    return {"type": type_, "shared": int(shared), "active": 1, "enabled": 1, "avail": avail, "content": content}


class SimPVE(_Path):
    """A small, stateful Proxmox cluster."""

    def __init__(self):
        super().__init__(self)
        self.calls = []
        self.nds = {}
        self.guests = {}
        self.ha_resources, self.ha_rules, self.ha_groups, self.replication = [], [], [], []
        self.ha_node_status = {}
        self.mappings = {"pci": [], "usb": []}
        self.permissions = {"/": dict(ALL_PRIVS)}
        self.quorate = True
        self.qdevice = False
        self.tasks = {}
        self.task_polls = 2              # polls a task stays "running"
        self.fail_migrate = {}           # vmid -> exitstatus
        self.ignore_migrate = set()      # vmid: task ends OK but the guest stays put
        self.ha_ignores = set()          # sid: HA queues the request and never acts
        self.precondition_forbidden = False
        self.on_task_done = None         # callback(sim, task)
        self._seq = itertools.count(1)

    # ── setup helpers ──
    def add_node(self, name, mem_free=64 * GiB, maxmem=128 * GiB, maxcpu=32, storages=None, online=True, lrm=True):
        self.nds[name] = {"online": online, "maxmem": maxmem, "mem": maxmem - mem_free, "maxcpu": maxcpu,
                            "lrm": lrm, "storages": copy.deepcopy(storages or {})}

    def add_guest(self, vmid, node, config, vmtype="qemu", status="running", maxmem=4 * GiB, maxcpu=2,
                  name=None, template=False):
        cfg = dict(config, digest=f"d{vmid}-1")
        self.guests[vmid] = {"type": vmtype, "node": node, "status": status, "maxmem": maxmem,
                             "maxcpu": maxcpu, "name": name or f"g{vmid}", "config": cfg, "template": template}
        if status == "running":
            self.nds[node]["mem"] += maxmem

    def sid(self, vmid):
        return f"{'ct' if self.guests[vmid]['type'] == 'lxc' else 'vm'}:{vmid}"

    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]

    # ── dispatcher ──
    def handle(self, method, path, kw):
        p = "/".join(path)
        self.calls.append((method, p, kw))
        if method == "GET":
            return self._get(path, p, kw)
        return self._write(method, path, p, kw)

    def _get(self, path, p, kw):
        if p == "cluster/status":
            out = [{"type": "cluster", "quorate": int(self.quorate), "nodes": len(self.nds)}]
            return out + [{"type": "node", "name": n, "online": int(i["online"])} for n, i in self.nds.items()]
        if p == "cluster/resources":
            if kw.get("type") == "node":
                return [{"node": n, "status": "online" if i["online"] else "offline", "maxmem": i["maxmem"],
                         "mem": i["mem"], "maxcpu": i["maxcpu"]} for n, i in self.nds.items()]
            out = []
            for vmid, g in self.guests.items():
                online = self.nds[g["node"]]["online"]
                out.append({"vmid": vmid, "type": g["type"], "node": g["node"], "name": g["name"],
                            "status": g["status"] if online else "unknown", "maxmem": g["maxmem"],
                            "maxcpu": g["maxcpu"], "template": int(g["template"]),
                            "lock": g["config"].get("lock"),
                            "hastate": "started" if any(r["sid"] == self.sid(vmid) for r in self.ha_resources)
                            else None})
            return out
        if p == "version":
            return {"version": "9.1.1"}
        if p == "cluster/config/qdevice":
            return {"status": "ok"} if self.qdevice else {}
        if p == "cluster/ha/resources":
            return self.ha_resources
        if p == "cluster/ha/rules":
            return self.ha_rules
        if p == "cluster/ha/groups":
            return self.ha_groups
        if p == "cluster/replication":
            return self.replication
        if p == "cluster/options":
            return {}
        if p == "cluster/ha/status/manager_status":
            return {"manager_status": {"node_status": dict(self.ha_node_status)}}
        if p == "cluster/ha/status/current":
            return [{"type": "service", "sid": r["sid"], "state": r.get("_state", "started"),
                     "node": self.guests[int(r["sid"].split(":")[1])]["node"]} for r in self.ha_resources]
        if p.startswith("cluster/mapping/"):
            return self.mappings[path[2]]
        if p == "access/permissions":
            return self.permissions
        if path[0] == "nodes":
            node = path[1]
            if not self.nds[node]["online"]:
                raise ConnectionError(f"{node} unreachable")
            if path[2:] == ("services", "pve-ha-lrm", "state"):
                return {"state": "running" if self.nds[node]["lrm"] else "stopped"}
            if path[2:] == ("storage",):
                return [dict(v, storage=k) for k, v in self.nds[node]["storages"].items()]
            if path[2] in ("qemu", "lxc"):
                vmid = int(path[3])
                g = self.guests.get(vmid)
                if not g or g["node"] != node:
                    raise RuntimeError(f"Configuration file 'nodes/{node}/{path[2]}/{vmid}.conf' does not exist")
                if path[4:] == ("config",):
                    return dict(g["config"])
                if path[4:] == ("migrate",):
                    if self.precondition_forbidden:
                        raise Forbidden("403 Forbidden: Permission check failed (/vms/%d, VM.Migrate)" % vmid)
                    return {"running": int(g["status"] == "running"), "local_resources": [],
                            "not_allowed_nodes": {}, "allowed_nodes": [n for n in self.nds if n != node]}
            if path[2] == "tasks":
                return self._task_get(path[3], path[4])
        raise KeyError(f"SimPVE: unhandled GET {p}")

    def _new_task(self, node, kind, vmid, done, exit_status="OK", polls=None):
        upid = f"UPID:{node}:{next(self._seq):08X}:00000000:00000000:{kind}:{vmid}:root@pam:"
        self.tasks[upid] = {"node": node, "kind": kind, "vmid": vmid, "polls": self.task_polls if polls is None
                            else polls, "done": done, "exit": exit_status, "finished": False}
        return upid

    def _task_get(self, upid, what):
        t = self.tasks[upid]
        if what == "log":
            return [{"n": 1, "t": "starting"}, {"n": 2, "t": f"ERROR: {t['exit']}"}]
        if t["polls"] > 0:
            t["polls"] -= 1
            return {"status": "running"}
        if not t["finished"]:
            t["finished"] = True
            if t["exit"] == "OK" and t["done"]:
                t["done"]()
            if self.on_task_done:
                self.on_task_done(self, t)
        return {"status": "stopped", "exitstatus": t["exit"]}

    def _move_guest(self, vmid, target, mapping):
        g = self.guests[vmid]
        src = g["node"]
        if g["status"] == "running":
            self.nds[src]["mem"] -= g["maxmem"]
            self.nds[target]["mem"] += g["maxmem"]
        for k, v in list(g["config"].items()):
            if not isinstance(v, str) or k == "digest" or "media=cdrom" in v:
                continue
            st = v.split(",")[0].split(":")[0]
            if st in mapping and mapping[st] != st and ":" in v:
                g["config"][k] = mapping[st] + v[len(st):]
        g["node"] = target

    def _write(self, method, path, p, kw):
        if path[0] == "nodes" and path[2] in ("qemu", "lxc"):
            node, vmid = path[1], int(path[3])
            g = self.guests[vmid]
            assert g["node"] == node, f"write to {p} but the guest is on {g['node']}"
            if path[4:] == ("migrate",):
                target = kw["target"]
                mapping = {}
                for pair in str(kw.get("targetstorage") or kw.get("target-storage") or "").split(","):
                    if ":" in pair:
                        a, b = pair.split(":")
                        mapping[a] = b
                if g["status"] == "running" and g["type"] == "qemu" and not kw.get("online"):
                    raise RuntimeError("can't migrate running VM without --online")
                if g["status"] == "running" and g["type"] == "lxc" and not kw.get("restart"):
                    raise RuntimeError("lxc live migration is currently not implemented")
                sid = self.sid(vmid)
                if any(r["sid"] == sid for r in self.ha_resources):
                    def ha_done():
                        if sid not in self.ha_ignores:
                            self._move_guest(vmid, target, mapping)
                    return self._new_task(node, "hamigrate", vmid, ha_done, polls=0)
                if vmid in self.fail_migrate:
                    return self._new_task(node, "qmigrate", vmid, None, self.fail_migrate[vmid])
                done = None if vmid in self.ignore_migrate else (lambda: self._move_guest(vmid, target, mapping))
                return self._new_task(node, "qmigrate" if g["type"] == "qemu" else "vzmigrate", vmid, done)
            if path[4:] == ("status", "shutdown"):
                def stop():
                    g["status"] = "stopped"
                    self.nds[node]["mem"] -= g["maxmem"]
                return self._new_task(node, "qmshutdown", vmid, stop)
            if path[4:] == ("status", "start"):
                def start():
                    g["status"] = "running"
                    self.nds[node]["mem"] += g["maxmem"]
                return self._new_task(node, "qmstart", vmid, start)
        raise KeyError(f"SimPVE: unhandled {method} {p}")


@pytest.fixture(autouse=True)
def fast_clock(monkeypatch):
    clock = {"t": 1_800_000_000.0}
    monkeypatch.setattr(ne, "_now", lambda: clock["t"])

    def sleep(s):
        clock["t"] += s
    monkeypatch.setattr(ne, "_sleep", sleep)
    return clock


def mixed_cluster():
    """pve1 (being evacuated) with VMs and containers; pve2 and pve3 as targets."""
    sim = SimPVE()
    common = {"nfs": stor("nfs", shared=True), "local": stor("dir", content="iso,vztmpl,snippets")}
    sim.add_node("pve1", storages={**common, "local-lvm": stor("lvmthin")})
    sim.add_node("pve2", mem_free=40 * GiB, storages={**common, "local-lvm": stor("lvmthin")})
    sim.add_node("pve3", mem_free=80 * GiB, storages={**common, "local-lvm": stor("lvmthin")})
    sim.add_guest(100, "pve1", {"scsi0": "nfs:100/vm-100-disk-0.qcow2,size=32G",
                                "ide2": "local-lvm:vm-100-cloudinit,media=cdrom"}, maxmem=8 * GiB)
    sim.add_guest(101, "pve1", {"scsi0": "local-lvm:vm-101-disk-0,size=50G"}, maxmem=4 * GiB)
    sim.add_guest(102, "pve1", {"scsi0": "local-lvm:vm-102-disk-0,size=20G"}, status="stopped", maxmem=16 * GiB)
    sim.add_guest(200, "pve1", {"rootfs": "local-lvm:vm-200-disk-0,size=8G"}, vmtype="lxc", maxmem=2 * GiB)
    sim.add_guest(201, "pve1", {"rootfs": "nfs:201/vm-201-disk-0.raw,size=8G"}, vmtype="lxc", status="stopped",
                  maxmem=1 * GiB)
    return sim


def preview(sim, node="pve1"):
    return ne.build_preview(ne.gather_facts(sim, node))


def by_sid(p):
    return {e["sid"]: e for e in p["guests"]}


def run(sim, entries, node="pve1"):
    job = ne.Job(1, node, "plan", 1, entries)
    ne.run_evacuation(sim, job, entries)
    return job


# ── Preview ─────────────────────────────────────────────────────────────────────

def test_mixed_node_classifies_every_vm_and_container():
    p = preview(mixed_cluster())
    g = by_sid(p)
    assert set(g) == {"vm:100", "vm:101", "vm:102", "ct:200", "ct:201"}
    assert (g["vm:100"]["class"], g["vm:100"]["method"]) == ("online", "live")
    # shared disk; the local cloud-init drive is not an ISO but travels with the VM
    assert g["vm:100"]["storage_map"] == {"local-lvm": "local-lvm"} and g["vm:100"]["copy_bytes"] == 4 << 20
    assert (g["vm:101"]["class"], g["vm:101"]["method"]) == ("online", "live")
    assert g["vm:101"]["storage_map"] == {"local-lvm": "local-lvm"} and g["vm:101"]["copy_bytes"] == 50 * GiB
    assert (g["vm:102"]["class"], g["vm:102"]["method"]) == ("online", "offline")
    assert g["vm:102"]["mem_needed"] == 0              # stopped: needs no RAM on the target
    assert (g["ct:200"]["class"], g["ct:200"]["method"]) == ("downtime", "restart")
    assert (g["ct:201"]["class"], g["ct:201"]["method"]) == ("online", "offline")
    for e in p["guests"]:
        assert e["target"] in ("pve2", "pve3") and e["reason"]
    assert p["summary"]["online"] == 4 and p["summary"]["downtime"] == 1 and p["summary"]["empty_after"]
    assert p["executable"]


def test_preview_is_read_only():
    sim = mixed_cluster()
    preview(sim)
    assert sim.writes() == []


def test_placement_counts_ram_cumulatively_and_prefers_most_room():
    sim = SimPVE()
    sim.add_node("pve1", storages={"nfs": stor("nfs", shared=True)})
    # 40 GiB free on each target, 10% of 128 GiB reserved -> 27.2 GiB usable each
    sim.add_node("pve2", mem_free=40 * GiB, storages={"nfs": stor("nfs", shared=True)})
    sim.add_node("pve3", mem_free=40 * GiB, storages={"nfs": stor("nfs", shared=True)})
    for vmid in (100, 101, 102):
        sim.add_guest(vmid, "pve1", {"scsi0": f"nfs:{vmid}/a.raw,size=8G"}, maxmem=20 * GiB)
    p = preview(sim)
    g = by_sid(p)
    assert {g["vm:100"]["target"], g["vm:101"]["target"]} == {"pve2", "pve3"}
    assert g["vm:102"]["class"] == "blocked" and g["vm:102"].get("capacity")
    assert "after earlier moves" in g["vm:102"]["reason"]
    assert not p["summary"]["aggregate_ok"]
    assert any(c["title"] == "Not enough RAM on the other nodes" and c["status"] == "fail" for c in p["checks"])


def test_enough_ram_in_total_but_not_on_one_node_is_explained():
    sim = SimPVE()
    sim.add_node("pve1", storages={"nfs": stor("nfs", shared=True)})
    sim.add_node("pve2", mem_free=30 * GiB, storages={"nfs": stor("nfs", shared=True)})
    sim.add_node("pve3", mem_free=30 * GiB, storages={"nfs": stor("nfs", shared=True)})
    sim.add_guest(100, "pve1", {"scsi0": "nfs:100/a.raw,size=8G"}, maxmem=24 * GiB)
    p = preview(sim)
    assert by_sid(p)["vm:100"]["class"] == "blocked"
    assert p["summary"]["aggregate_ok"]       # 2 x 17.2 GiB usable >= 24 GiB, but neither node alone
    assert any(c["title"] == "Some guests do not fit" for c in p["checks"])


def test_disk_space_is_reserved_across_moves_and_falls_back_to_another_storage():
    sim = SimPVE()
    sim.add_node("pve1", storages={"local-lvm": stor("lvmthin")})
    sim.add_node("pve2", storages={"local-lvm": stor("lvmthin", avail=500 * GiB),
                                   "big": stor("lvm", avail=400 * GiB)})
    for vmid in (100, 101):
        sim.add_guest(vmid, "pve1", {"scsi0": f"local-lvm:vm-{vmid}-disk-0,size=300G"})
    sim.add_guest(102, "pve1", {"scsi0": "local-lvm:vm-102-disk-0,size=300G"})
    g = by_sid(preview(sim))
    maps = sorted(tuple(g[s]["storage_map"].items()) for s in ("vm:100", "vm:101"))
    assert maps == [(("local-lvm", "big"),), (("local-lvm", "local-lvm"),)]
    assert g["vm:102"]["class"] == "blocked" and "lack room for 300.0 GiB" in g["vm:102"]["reason"]


def test_per_node_storage_ids_map_to_the_targets_storage():
    """The real-world layout: each node has its own LVM storage with its own ID."""
    sim = SimPVE()
    sim.add_node("pve1", storages={"pve1-Storage": stor("lvmthin")})
    sim.add_node("pve2", storages={"pve2-Storage": stor("lvmthin"), "pve1-Storage": dict(stor("lvmthin"), active=0)})
    sim.add_guest(100, "pve1", {"scsi0": "pve1-Storage:vm-100-disk-0,size=100G",
                                "ide2": "pve1-Storage:vm-100-cloudinit,media=cdrom"})
    e = by_sid(preview(sim))["vm:100"]
    assert e["class"] == "online" and e["storage_map"] == {"pve1-Storage": "pve2-Storage"}
    assert ne._migrate_params(e, live=True) == {"target": "pve2", "online": 1, "with-local-disks": 1,
                                                "targetstorage": "pve1-Storage:pve2-Storage"}


def test_passthrough_iso_and_bind_mounts():
    sim = mixed_cluster()
    sim.guests.clear()
    for n in sim.nds.values():
        n["mem"] = n["maxmem"] - (64 * GiB)
    sim.add_guest(110, "pve1", {"scsi0": "nfs:110/a.raw,size=8G", "hostpci0": "0000:01:00.0,pcie=1"})
    sim.add_guest(111, "pve1", {"scsi0": "nfs:111/a.raw,size=8G", "usb0": "host=1234:5678"})
    sim.add_guest(112, "pve1", {"scsi0": "nfs:112/a.raw,size=8G", "ide2": "local:iso/debian.iso,media=cdrom"})
    sim.add_guest(113, "pve1", {"scsi0": "nfs:113/a.raw,size=8G", "usb0": "spice"})
    sim.add_guest(210, "pve1", {"rootfs": "nfs:210/r.raw,size=8G", "mp0": "/srv/data,mp=/data"}, vmtype="lxc")
    sim.add_guest(211, "pve1", {"rootfs": "nfs:211/r.raw,size=8G", "mp0": "/mnt/pve/nfs,mp=/d,shared=1"},
                  vmtype="lxc")
    sim.add_guest(212, "pve1", {"rootfs": "nfs:212/r.raw,size=8G", "dev0": "/dev/ttyUSB0"}, vmtype="lxc")
    g = by_sid(preview(sim))
    assert g["vm:110"]["class"] == "blocked" and "PCI device 0000:01:00.0" in g["vm:110"]["reason"]
    assert g["vm:111"]["class"] == "blocked" and "USB" in g["vm:111"]["reason"]
    assert g["vm:112"]["class"] == "blocked" and "Eject it" in g["vm:112"]["reason"]
    assert g["vm:113"]["class"] == "online"        # SPICE USB redirection is not passthrough
    assert g["ct:210"]["class"] == "blocked" and "bind mount of /srv/data" in g["ct:210"]["reason"]
    assert g["ct:211"]["class"] == "downtime" and any("marked shared" in w for w in g["ct:211"]["warnings"])
    assert g["ct:212"]["class"] == "blocked" and "/dev/ttyUSB0" in g["ct:212"]["reason"]


def test_mapped_pci_needs_a_cold_move_to_a_node_with_the_device():
    sim = mixed_cluster()
    sim.guests.clear()
    sim.mappings["pci"] = [{"id": "gpu", "map": ["node=pve1,path=0000:01:00.0", "node=pve2,path=0000:41:00.0"]}]
    sim.add_guest(120, "pve1", {"scsi0": "nfs:120/a.raw,size=8G", "hostpci0": "mapping=gpu,pcie=1"})
    e = by_sid(preview(sim))["vm:120"]
    assert (e["class"], e["method"], e["target"]) == ("downtime", "cold", "pve2")
    assert "mapped PCI device gpu has no device on pve3" in e["targets"]["pve3"]


def test_shared_iso_needs_the_storage_on_the_target():
    sim = mixed_cluster()
    sim.guests.clear()
    sim.nds["pve1"]["storages"]["isos"] = stor("cifs", shared=True, content="iso")
    sim.nds["pve3"]["storages"]["isos"] = stor("cifs", shared=True, content="iso")
    sim.add_guest(130, "pve1", {"scsi0": "nfs:130/a.raw,size=8G", "ide2": "isos:iso/x.iso,media=cdrom"})
    e = by_sid(preview(sim))["vm:130"]
    assert e["target"] == "pve3" and "ISO storage isos is not available on pve2" in e["targets"]["pve2"]


def test_vcpus_and_lock():
    sim = mixed_cluster()
    sim.guests.clear()
    sim.nds["pve2"]["maxcpu"] = 8
    sim.add_guest(140, "pve1", {"scsi0": "nfs:140/a.raw,size=8G"}, maxcpu=16)
    sim.add_guest(141, "pve1", {"scsi0": "nfs:141/a.raw,size=8G", "lock": "backup"})
    g = by_sid(preview(sim))
    assert g["vm:140"]["target"] == "pve3" and "16 vCPUs" in g["vm:140"]["targets"]["pve2"][0]
    assert g["vm:141"]["class"] == "blocked" and "Locked (backup)" in g["vm:141"]["reason"]


def test_template_with_linked_clones_on_local_storage_is_blocked():
    sim = mixed_cluster()
    sim.guests.clear()
    sim.add_guest(9000, "pve1", {"scsi0": "local-lvm:base-9000-disk-0,size=4G"}, status="stopped", template=True)
    sim.add_guest(150, "pve1", {"scsi0": "local-lvm:base-9000-disk-0/vm-150-disk-0,size=4G"})
    g = by_sid(preview(sim))
    assert g["vm:9000"]["class"] == "blocked" and "Linked clones (vm:150)" in g["vm:9000"]["reason"]


def test_unreadable_guest_is_unknown():
    sim = mixed_cluster()
    real = sim._get

    def broken(path, p, kw):
        if p == "nodes/pve1/qemu/101/config":
            raise RuntimeError("500 Internal Server Error")
        return real(path, p, kw)
    sim._get = broken
    e = by_sid(preview(sim))["vm:101"]
    assert e["class"] == "unknown" and "500 Internal Server Error" in e["reason"]


# ── HA placement and quorum ─────────────────────────────────────────────────────

def ha_cluster():
    sim = mixed_cluster()
    sim.guests.clear()
    sim.add_guest(100, "pve1", {"scsi0": "nfs:100/a.raw,size=8G"})
    sim.ha_resources = [{"sid": "vm:100", "state": "started", "failback": 1}]
    return sim


def test_ha_strict_rule_limits_targets():
    sim = ha_cluster()
    sim.ha_rules = [{"rule": "r1", "type": "node-affinity", "resources": "vm:100", "nodes": "pve1:1,pve2:1",
                     "strict": 1}]
    e = by_sid(preview(sim))["vm:100"]
    assert e["target"] == "pve2" and e["ha"]
    assert "HA r1 only allows pve1, pve2" in e["targets"]["pve3"]


def test_ha_rule_that_prefers_the_source_blocks_until_ha_maintenance():
    sim = ha_cluster()
    sim.ha_rules = [{"rule": "r1", "type": "node-affinity", "resources": "vm:100", "nodes": "pve1:2,pve2:1,pve3:1",
                     "strict": 0}]
    e = by_sid(preview(sim))["vm:100"]
    assert e["class"] == "blocked" and "node-maintenance enable pve1" in e["reason"]
    sim.ha_node_status = {"pve1": "maintenance"}
    p = preview(sim)
    assert by_sid(p)["vm:100"]["class"] == "online"
    assert any(c["title"] == "pve1 is in HA maintenance mode" for c in p["checks"])


def test_ha_negative_affinity_and_missing_lrm():
    sim = ha_cluster()
    sim.add_guest(300, "pve3", {"scsi0": "nfs:300/a.raw,size=8G"})
    sim.ha_resources.append({"sid": "vm:300", "state": "started"})
    sim.ha_rules = [{"rule": "apart", "type": "resource-affinity", "affinity": "negative",
                     "resources": "vm:100,vm:300"}]
    e = by_sid(preview(sim))["vm:100"]
    assert e["target"] == "pve2" and "keeps it apart from vm:300" in e["targets"]["pve3"][0]
    sim.nds["pve2"]["lrm"] = False
    e = by_sid(preview(sim))["vm:100"]
    assert e["class"] == "blocked" and "pve-ha-lrm" in e["reason"]


def test_ha_guest_on_local_lvm_is_blocked():
    sim = ha_cluster()
    sim.add_guest(101, "pve1", {"scsi0": "local-lvm:vm-101-disk-0,size=8G"})
    sim.ha_resources.append({"sid": "vm:101", "state": "started"})
    e = by_sid(preview(sim))["vm:101"]
    assert e["class"] == "blocked" and "HA migrations do not copy local disks" in e["reason"]


def test_quorum_warning_and_not_quorate_blocks_everything():
    sim = mixed_cluster()
    sim.nds["pve3"]["online"] = False
    p = preview(sim)
    assert any(c["title"] == "Taking pve1 down loses quorum" for c in p["checks"])
    assert {e["target"] for e in p["guests"] if e["target"]} == {"pve2"}
    sim.quorate = False
    p = preview(sim)
    assert not p["executable"] and all(e["class"] == "blocked" for e in p["guests"])


def test_offline_source_makes_guests_unknown():
    sim = mixed_cluster()
    sim.nds["pve1"]["online"] = False
    p = preview(sim)
    assert not p["executable"] and all(e["class"] == "unknown" for e in p["guests"])


# ── Permissions ─────────────────────────────────────────────────────────────────

def test_read_only_token_can_preview_but_not_execute():
    sim = mixed_cluster()
    sim.permissions = AUDITOR
    sim.precondition_forbidden = True     # GET .../migrate needs VM.Migrate
    p = preview(sim)
    assert sim.writes() == []
    assert p["permissions"]["preview"]["ok"] is True
    assert p["permissions"]["execute"]["ok"] is False
    missing = {(m["privilege"], m["path"]) for m in p["permissions"]["execute"]["missing"]}
    assert ("VM.Migrate", "/vms/100") in missing and ("Datastore.AllocateSpace", "/storage/local-lvm") in missing
    assert by_sid(p)["vm:100"]["class"] == "online"     # falls back to the config analysis
    assert any("migration check was not available" in w for w in by_sid(p)["vm:100"]["warnings"])


def test_minimum_privileges_for_evacuation():
    p = preview(mixed_cluster())
    g = by_sid(p)
    need = ne.required_privileges([g["vm:100"], g["vm:101"]])
    assert sorted(set((n[0], n[1]) for n in need)) == [
        ("Datastore.AllocateSpace", "/storage/local-lvm"), ("VM.Migrate", "/vms/100"), ("VM.Migrate", "/vms/101")]
    scoped = {"/vms": {"VM.Migrate": 1}, "/storage/local-lvm": {"Datastore.AllocateSpace": 1},
              "/": {"Sys.Audit": 1, "VM.Audit": 1, "Datastore.Audit": 1}}
    assert ne.check_permissions(scoped, [g["vm:100"], g["vm:101"]])["execute"]["ok"]


# ── Execution ───────────────────────────────────────────────────────────────────

def test_execute_moves_and_verifies_each_guest():
    sim = mixed_cluster()
    p = preview(sim)
    entries = [e for e in p["guests"] if e["class"] in ("online", "downtime")]
    job = run(sim, entries)
    assert job.status == "done", job.snapshot()
    for e in entries:
        assert job.results[e["sid"]]["status"] == "moved"
        assert sim.guests[e["vmid"]]["node"] == e["target"]
    migrates = {c[1]: c[2] for c in sim.writes() if c[1].endswith("/migrate")}
    assert migrates["nodes/pve1/qemu/100/migrate"] == {"target": by_sid(p)["vm:100"]["target"], "online": 1,
                                                       "with-local-disks": 1}
    assert migrates["nodes/pve1/qemu/101/migrate"]["with-local-disks"] == 1
    assert migrates["nodes/pve1/lxc/200/migrate"]["restart"] == 1
    assert "online" not in migrates["nodes/pve1/qemu/102/migrate"]
    assert job.remaining == []


def test_a_finished_task_does_not_count_until_the_guest_is_on_the_target():
    sim = mixed_cluster()
    sim.ignore_migrate.add(100)
    e = by_sid(preview(sim))["vm:100"]
    job = run(sim, [e])
    r = job.results["vm:100"]
    assert r["status"] == "failed" and "task ended OK but not on" in r["detail"]
    assert job.status == "failed"


def test_ha_migration_queued_is_not_a_move():
    sim = ha_cluster()
    sim.ha_ignores.add("vm:100")
    e = by_sid(preview(sim))["vm:100"]
    job = run(sim, [e])
    r = job.results["vm:100"]
    assert ":hamigrate:" in r["upid"]
    assert r["status"] == "failed" and "HA left it on pve1" in r["detail"]
    sim.ha_ignores.clear()
    job = run(sim, [e])
    assert job.results["vm:100"]["status"] == "moved"


def test_failed_migration_is_reported_and_the_rest_continues_then_retry_is_safe():
    sim = mixed_cluster()
    sim.fail_migrate[101] = "migration aborted: target storage full"
    p = preview(sim)
    entries = [e for e in p["guests"] if e["class"] == "online"]
    job = run(sim, entries)
    r = job.results["vm:101"]
    assert r["status"] == "failed" and "target storage full" in r["detail"] and r["location"] == "pve1"
    assert job.results["vm:100"]["status"] == "moved"
    assert job.status == "partial" and job.remaining == ["vm:101", "ct:200"]
    # Retry the same reviewed plan: finished moves are recognised, the failed one runs again.
    del sim.fail_migrate[101]
    n_before = len([c for c in sim.writes() if c[1].endswith("/migrate")])
    job2 = run(sim, entries)
    assert job2.results["vm:100"]["status"] == "already_moved"
    assert job2.results["vm:101"]["status"] == "moved"
    assert len([c for c in sim.writes() if c[1].endswith("/migrate")]) == n_before + 1
    assert job2.status == "done"


def test_target_going_offline_skips_the_next_move_instead_of_rerouting():
    sim = mixed_cluster()
    p = preview(sim)
    entries = [e for e in p["guests"] if e["class"] == "online"]
    first = entries[0]
    victim = next(e for e in entries[1:] if e["target"] == first["target"]) if any(
        e["target"] == first["target"] for e in entries[1:]) else None
    assert victim, "the test needs two guests on one target"

    def drop_target(s, task):
        if task["vmid"] == first["vmid"]:
            s.nds[first["target"]]["online"] = False
    sim.on_task_done = drop_target
    job = run(sim, entries)
    assert job.results[first["sid"]]["status"] in ("moved", "failed")
    r = job.results[victim["sid"]]
    assert r["status"] == "skipped" and f"{first['target']} is offline" in r["detail"]
    assert sim.guests[victim["vmid"]]["node"] == "pve1"
    assert not any(c[1] == f"nodes/pve1/qemu/{victim['vmid']}/migrate" for c in sim.writes())


def test_changed_config_or_state_since_review_is_skipped():
    sim = mixed_cluster()
    p = by_sid(preview(sim))
    sim.guests[100]["config"]["digest"] = "changed"
    sim.guests[102]["status"] = "running"
    sim.nds["pve1"]["mem"] += sim.guests[102]["maxmem"]
    job = run(sim, [p["vm:100"], p["vm:102"]])
    assert job.results["vm:100"]["status"] == "skipped" and "configuration changed" in job.results["vm:100"]["detail"]
    assert job.results["vm:102"]["status"] == "skipped" and "live move instead of the reviewed offline" in \
        job.results["vm:102"]["detail"]
    assert sim.writes() == []


def test_capacity_is_rechecked_before_each_move():
    sim = mixed_cluster()
    e = by_sid(preview(sim))["vm:100"]
    sim.nds[e["target"]]["mem"] = sim.nds[e["target"]]["maxmem"] - GiB   # someone filled the target
    job = run(sim, [e])
    assert job.results["vm:100"]["status"] == "skipped" and "needs 8.0 GiB RAM" in job.results["vm:100"]["detail"]


def test_cold_move_shuts_down_migrates_and_starts():
    sim = mixed_cluster()
    sim.guests.clear()
    sim.mappings["pci"] = [{"id": "gpu", "map": ["node=pve1,path=0000:01:00.0", "node=pve2,path=0000:41:00.0"]}]
    sim.add_guest(120, "pve1", {"scsi0": "nfs:120/a.raw,size=8G", "hostpci0": "mapping=gpu"})
    e = by_sid(preview(sim))["vm:120"]
    job = run(sim, [e])
    assert job.results["vm:120"]["status"] == "moved"
    assert [(c[0], c[1]) for c in sim.writes()] == [
        ("POST", "nodes/pve1/qemu/120/status/shutdown"), ("POST", "nodes/pve1/qemu/120/migrate"),
        ("POST", "nodes/pve2/qemu/120/status/start")]
    assert sim.guests[120]["status"] == "running" and sim.guests[120]["node"] == "pve2"


def test_failed_cold_move_starts_the_guest_again_on_the_source():
    sim = mixed_cluster()
    sim.guests.clear()
    sim.mappings["pci"] = [{"id": "gpu", "map": ["node=pve1,path=a", "node=pve2,path=b"]}]
    sim.add_guest(120, "pve1", {"scsi0": "nfs:120/a.raw,size=8G", "hostpci0": "mapping=gpu"})
    sim.fail_migrate[120] = "mapping check failed"
    e = by_sid(preview(sim))["vm:120"]
    job = run(sim, [e])
    r = job.results["vm:120"]
    assert r["status"] == "failed" and "started again on pve1" in r["detail"]
    assert sim.guests[120]["status"] == "running" and sim.guests[120]["node"] == "pve1"


def test_cancel_stops_before_the_next_guest():
    sim = mixed_cluster()
    entries = [e for e in preview(sim)["guests"] if e["class"] == "online"]
    job = ne.Job(1, "pve1", "plan", 1, entries)
    sim.on_task_done = lambda s, t: job.cancel.set()
    ne.run_evacuation(sim, job, entries)
    statuses = [job.results[e["sid"]]["status"] for e in entries]
    assert statuses[0] == "moved" and set(statuses[1:]) == {"cancelled"}
    assert job.status == "cancelled"


def test_task_status_lost_then_reported():
    sim = mixed_cluster()
    e = by_sid(preview(sim))["vm:100"]
    real = sim._task_get
    sim._task_get = lambda upid, what: (_ for _ in ()).throw(ConnectionError("node gone"))
    job = run(sim, [e])
    assert job.results["vm:100"]["status"] == "failed" and "lost track of the task" in job.results["vm:100"]["detail"]
    sim._task_get = real


# ── API ─────────────────────────────────────────────────────────────────────────

@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient
    from app.api import cluster
    from app.core.config import settings
    from app.core.database import SessionLocal, engine
    from app.main import app
    from app.models.database import Base, ProxmoxHost, User, UserHostPermission, UserRole

    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    for uid, name, role in ((1, "admin", UserRole.ADMIN), (2, "oper", UserRole.OPERATOR),
                            (3, "viewer", UserRole.VIEWER), (4, "admin2", UserRole.ADMIN)):
        s.add(User(id=uid, username=name, email=f"{name}@example.com", hashed_password="x", role=role))
    s.add(ProxmoxHost(id=1, name="h1", hostname="h1.invalid", username="root@pam", is_active=True))
    s.flush()
    s.add_all([UserHostPermission(user_id=2, host_id=1, can_view=True, can_manage=True),
               UserHostPermission(user_id=3, host_id=1, can_view=True)])
    s.commit()
    s.close()
    sim = mixed_cluster()
    monkeypatch.setattr(cluster, "_pve", lambda host: sim)
    ran = []
    real_start = ne.start_job

    def start_inline(host_id, node, plan_id, user_id, entries, pve, target=None):
        job = real_start(host_id, node, plan_id, user_id, entries, pve, target=lambda p, j, e: ran.append(j))
        return job
    monkeypatch.setattr(ne, "start_job", start_inline)
    client = TestClient(app)
    client.sim, client.ran = sim, ran
    return client


def _h(username):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({"sub": username, "tv": 0})}


URL = "/api/v1/cluster/1/nodes/pve1"


def test_api_viewer_previews_but_only_admin_executes(api):
    r = api.get(f"{URL}/maintenance/preview", headers=_h("viewer"))
    assert r.status_code == 200 and r.json()["plan_id"]
    assert api.sim.writes() == []
    for who in ("viewer", "oper"):
        r2 = api.post(f"{URL}/evacuate", headers=_h(who), json={"plan_id": r.json()["plan_id"]})
        assert r2.status_code == 403


def test_api_execute_runs_only_the_reviewed_plan(api):
    plan = api.get(f"{URL}/maintenance/preview", headers=_h("admin")).json()
    pid = plan["plan_id"]
    # someone else's plan
    assert api.post(f"{URL}/evacuate", headers=_h("admin2"), json={"plan_id": pid}).status_code == 403
    # unknown plan, wrong node
    assert api.post(f"{URL}/evacuate", headers=_h("admin"), json={"plan_id": "nope"}).status_code == 404
    assert api.post("/api/v1/cluster/1/nodes/pve2/evacuate", headers=_h("admin"),
                    json={"plan_id": pid}).status_code == 404
    # the downtime guest needs an explicit decision
    r = api.post(f"{URL}/evacuate", headers=_h("admin"), json={"plan_id": pid, "guests": ["ct:200"]})
    assert r.status_code == 400 and "allow_downtime" in r.json()["detail"]
    # default: every online guest, nothing else
    r = api.post(f"{URL}/evacuate", headers=_h("admin"), json={"plan_id": pid})
    assert r.status_code == 200
    assert sorted(r.json()["guests"]) == ["ct:201", "vm:100", "vm:101", "vm:102"]
    r = api.get(f"/api/v1/cluster/1/evacuations/{r.json()['job_id']}", headers=_h("viewer"))
    assert r.status_code == 200 and r.json()["node"] == "pve1"


def test_api_explicit_downtime_and_blocked_guests(api):
    api.sim.add_guest(110, "pve1", {"scsi0": "nfs:110/a.raw,size=8G", "hostpci0": "0000:01:00.0"})
    pid = api.get(f"{URL}/maintenance/preview", headers=_h("admin")).json()["plan_id"]
    r = api.post(f"{URL}/evacuate", headers=_h("admin"), json={"plan_id": pid, "guests": ["vm:110"]})
    assert r.status_code == 400 and "blocked" in r.json()["detail"]
    r = api.post(f"{URL}/evacuate", headers=_h("admin"), json={"plan_id": pid, "allow_downtime": ["ct:200"]})
    assert r.status_code == 200 and "ct:200" in r.json()["guests"]


def test_api_refuses_when_token_lacks_migrate(api):
    api.sim.permissions = AUDITOR
    pid = api.get(f"{URL}/maintenance/preview", headers=_h("admin")).json()["plan_id"]
    r = api.post(f"{URL}/evacuate", headers=_h("admin"), json={"plan_id": pid})
    assert r.status_code == 403 and "VM.Migrate on /vms/100" in r.json()["detail"]
    assert api.ran == []


def test_api_refuses_a_second_evacuation_while_one_runs(api):
    pid = api.get(f"{URL}/maintenance/preview", headers=_h("admin")).json()["plan_id"]
    job = ne.Job(1, "pve1", pid, 1, [])
    ne._jobs[job.id] = job
    ne._active[1] = job.id
    try:
        r = api.post(f"{URL}/evacuate", headers=_h("admin"), json={"plan_id": pid})
        assert r.status_code == 409 and "still running" in r.json()["detail"]
    finally:
        ne._active.pop(1, None)
        ne._jobs.pop(job.id, None)


def test_destination_prefers_same_storage_type_and_keeps_the_ha_zfs_pool_last():
    sim = SimPVE()
    sim.add_node("pve1", storages={"pve1-Storage": stor("lvmthin")})
    sim.add_node("pve2", storages={"ha-zfs": stor("zfspool", avail=9000 * GiB), "big-lvm": stor("lvm", avail=2000 * GiB),
                                   "thin": stor("lvmthin", avail=500 * GiB)})
    sim.add_guest(100, "pve1", {"scsi0": "pve1-Storage:vm-100-disk-0,size=100G"})
    sim.add_guest(101, "pve1", {"scsi0": "pve1-Storage:vm-101-disk-0,size=100G"}, vmtype="qemu")
    e = by_sid(preview(sim))["vm:100"]
    assert e["storage_map"] == {"pve1-Storage": "thin"}
    sim.nds["pve2"]["storages"]["thin"]["avail"] = 10 * GiB
    assert by_sid(preview(sim))["vm:100"]["storage_map"] == {"pve1-Storage": "big-lvm"}
    sim.nds["pve2"]["storages"]["big-lvm"]["avail"] = 10 * GiB
    assert by_sid(preview(sim))["vm:100"]["storage_map"] == {"pve1-Storage": "ha-zfs"}


def test_guest_already_moved_off_the_node_by_ha_is_recorded_not_moved_again():
    sim = ha_cluster()
    e = by_sid(preview(sim))["vm:100"]
    other = "pve2" if e["target"] == "pve3" else "pve3"
    sim._move_guest(100, other, {})          # HA maintenance mode moved it first
    job = run(sim, [e])
    r = job.results["vm:100"]
    assert r["status"] == "moved_elsewhere" and r["location"] == other and "HA placed it" in r["detail"]
    assert sim.writes() == [] and job.status == "deviated"   # off the node, but not where planned


def test_api_old_style_evacuate_without_plan_is_refused(api):
    r = api.post(f"{URL}/evacuate", headers=_h("admin"), json={"target": "pve2"})
    assert r.status_code == 422
    assert api.sim.writes() == [] and api.ran == []


def test_task_ending_with_warnings_counts_once_the_guest_is_verified():
    sim = mixed_cluster()
    e = by_sid(preview(sim))["vm:101"]
    real = sim._new_task
    sim._new_task = lambda node, kind, vmid, done, exit_status="OK", polls=None: real(
        node, kind, vmid, done, "WARNINGS: 1" if kind == "qmigrate" else exit_status, polls)
    real_get = sim._task_get

    def get(upid, what):
        t = sim.tasks[upid]
        if t["exit"].startswith("WARNINGS") and t["polls"] == 0 and not t["finished"]:
            t["finished"] = True
            t["done"]()
            return {"status": "stopped", "exitstatus": t["exit"]}
        return real_get(upid, what)
    sim._task_get = get
    job = run(sim, [e])
    assert job.results["vm:101"]["status"] == "moved"


def test_ha_guest_on_local_zfs_needs_a_replication_job():
    sim = ha_cluster()
    for n in sim.nds.values():
        n["storages"]["tank"] = stor("zfspool")
    sim.add_guest(101, "pve1", {"scsi0": "tank:vm-101-disk-0,size=8G"})
    sim.ha_resources.append({"sid": "vm:101", "state": "started"})
    e = by_sid(preview(sim))["vm:101"]
    assert e["class"] == "blocked" and "no replication job" in e["reason"]
    sim.replication = [{"id": "101-0", "guest": 101, "target": "pve2"}]
    e = by_sid(preview(sim))["vm:101"]
    assert e["class"] == "online" and e["target"] == "pve2" and e["copy_bytes"] == 0


def test_ignored_ha_resource_still_gets_no_storage_mapping():
    sim = SimPVE()
    sim.add_node("pve1", storages={"pve1-Storage": stor("lvmthin")})
    sim.add_node("pve2", storages={"pve2-Storage": stor("lvmthin")})
    sim.add_guest(100, "pve1", {"scsi0": "pve1-Storage:vm-100-disk-0,size=8G"})
    sim.ha_resources = [{"sid": "vm:100", "state": "ignored"}]
    e = by_sid(preview(sim))["vm:100"]
    assert e["class"] == "blocked" and "HA migrations do not copy local disks" in e["reason"]


def test_unreachable_task_node_keeps_waiting_while_the_guest_is_locked():
    sim = mixed_cluster()
    e = by_sid(preview(sim))["vm:100"]
    real = sim._task_get
    state = {"fails": 15}

    def flaky(upid, what):
        if state["fails"] > 0:
            state["fails"] -= 1
            sim.guests[100]["config"]["lock"] = "migrate"
            raise ConnectionError("pveproxy restarting")
        sim.guests[100]["config"].pop("lock", None)
        return real(upid, what)
    sim._task_get = flaky
    job = run(sim, [e])
    assert job.results["vm:100"]["status"] == "moved", job.results["vm:100"]
