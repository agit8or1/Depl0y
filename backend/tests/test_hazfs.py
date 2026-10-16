"""Tests for the HA-ZFS wizard's analysis and its node commands (no cluster needed)."""
import json

from app.services import hazfs

GiB = 1 << 30
TiB = 1 << 40


def lv(vg, name, size, attr="Vwi-aotz--", pool="", data=None, meta=None):
    return {"vg_name": vg, "lv_name": name, "lv_size": str(size), "lv_attr": attr, "pool_lv": pool,
            "data_percent": "" if data is None else str(data), "metadata_percent": "" if meta is None else str(meta)}


def thin_node(vg, thin_size, thin_data_pct, pool_size=2 * TiB, extra_lvs=(), pool=True, arc=2 * GiB,
              mem=128 * GiB, dropin=True, quota=0, used=1 * GiB, autotrim="on"):
    lvs = [lv("pve", "root", 100 * GiB, "-wi-ao----"),
           lv(vg, vg, thin_size, "twi-aotz--", data=thin_data_pct, meta=5)] + list(extra_lvs)
    s = {"hostname": "x", "mem_total": mem, "root_vg": "pve",
         "vgs": [{"vg_name": "pve", "vg_size": str(500 * GiB), "vg_free": str(16 * GiB)},
                 {"vg_name": vg, "vg_size": str(thin_size), "vg_free": str(GiB)}],
         "lvs": lvs, "zpools": [], "arc_max": arc, "arc_min": GiB,
         "dropin": f"ExecStartPre=-/sbin/lvchange -ay {vg}/ha-zfs\n" if dropin else None}
    if pool:
        s["lvs"].append(lv(vg, "ha-zfs", pool_size, pool=vg, data=0.1))
        s["zpools"] = [{"name": "hazfs", "size": pool_size, "alloc": used, "free": pool_size - used,
                        "health": "ONLINE", "autotrim": autotrim}]
        s["pool_props"] = {"quota": str(quota), "used": str(used), "available": str(pool_size - used)}
        s["zvols"] = []
    return s


def cluster(names, mem_free=None, storages=None):
    mem_free = mem_free or {}
    return {"nodes": {n: {"online": True, "lrm": True, "mem_free": mem_free.get(n, 64 * GiB),
                          "storages": (storages or {}).get(n, {})} for n in names},
            "replication": [], "quorate": True, "clustered": True}


def guest(vmid, node, volume, size, vmtype="qemu", **kw):
    key = "rootfs" if vmtype == "lxc" else "scsi0"
    return dict({"vmid": vmid, "name": f"g{vmid}", "node": node, "vmtype": vmtype, "template": False,
                 "maxmem": 4 * GiB, "config": {key: f"{volume},size={size // GiB}G"}}, **kw)


def facts(surveys, guests=(), storage_nodes=("a", "b", "c"), clus=None, storage_cfg=None):
    cfg = {"ha-zfs": {"storage": "ha-zfs", "type": "zfspool", "pool": "hazfs",
                      "nodes": ",".join(storage_nodes)}} if storage_nodes is not None else {}
    cfg.update(storage_cfg or {})
    return {"cluster": clus or cluster(list(surveys)), "ips": {n: f"10.0.0.{i}" for i, n in enumerate(surveys)},
            "storage_cfg": cfg, "guests": list(guests), "surveys": surveys}


def kinds(result):
    return {s["id"]: s for s in result["suggestions"]}


def test_healthy_cluster_has_nothing_to_suggest():
    surveys = {n: thin_node(f"vg{n}", 10 * TiB, 5) for n in "abc"}
    r = hazfs.suggest(facts(surveys))
    assert r["suggestions"] == [] and r["notes"] == []


def test_grow_when_guests_and_replicas_need_more_than_the_pool():
    surveys = {n: thin_node(f"vg{n}", 20 * TiB, 5, extra_lvs=[lv(f"vg{n}", f"vm-1{i}-disk-0", 800 * GiB,
                                                                pool=f"vg{n}", data=100) for i in range(3)])
               for n in "abc"}
    cfg = {f"lvm{n}": {"type": "lvmthin", "vgname": f"vg{n}"} for n in "abc"}
    guests = [guest(int(f"1{i}"), n, f"lvm{n}:vm-1{i}-disk-0", 800 * GiB) for n in "abc" for i in range(3)]
    r = hazfs.suggest(facts(surveys, guests, storage_cfg=cfg))
    s = kinds(r)
    assert {"grow:a", "grow:b", "grow:c"} <= set(s)
    # each node holds its own 3 guests and 3 replicas: 6 x 800 GiB x 1.2 plus room for one more guest
    assert s["grow:a"]["action"]["size"] >= 6 * 800 * GiB
    assert s["grow:a"]["action"]["thin"] is True
    assert "quota:a" not in s       # the thin pool can back the grown pool


def test_quota_when_thin_pool_cannot_back_the_pool():
    surveys = {n: thin_node(f"vg{n}", 3 * TiB, 60) for n in "abc"}   # ~1.2 TiB really free, pool 2 TiB
    s = kinds(hazfs.suggest(facts(surveys)))
    q = s["quota:a"]["action"]["quota"]
    assert q < 2 * TiB and q % (64 * GiB) == 0
    assert q <= int(3 * TiB * 0.4) - 100 * GiB


def test_existing_close_quota_is_left_alone():
    base = thin_node("vga", 3 * TiB, 60)
    safe = 1 * GiB + int(3 * TiB * 0.4) - max(int(3 * TiB * 0.05), 100 * GiB)
    surveys = {"a": thin_node("vga", 3 * TiB, 60, quota=safe - 10 * GiB),
               "b": thin_node("vgb", 10 * TiB, 5), "c": thin_node("vgc", 10 * TiB, 5)}
    assert base and "quota:a" not in kinds(hazfs.suggest(facts(surveys)))


def test_missing_dropin_autotrim_and_arc_cap():
    surveys = {"a": thin_node("vga", 10 * TiB, 5, dropin=False, autotrim="off", arc=0, mem=256 * GiB),
               "b": thin_node("vgb", 10 * TiB, 5), "c": thin_node("vgc", 10 * TiB, 5)}
    s = kinds(hazfs.suggest(facts(surveys)))
    assert s["dropin:a"]["action"]["vg"] == "vga"
    assert "autotrim:a" in s
    assert s["arc:a"]["action"]["arc_max"] == 16 * GiB


def test_arc_target():
    assert hazfs.arc_target(8 * GiB) == GiB
    assert hazfs.arc_target(128 * GiB) == 8 * GiB
    assert hazfs.arc_target(1024 * GiB) == 16 * GiB


def test_setup_on_node_with_room_and_note_for_node_without():
    surveys = {"a": thin_node("vga", 10 * TiB, 5), "b": thin_node("vgb", 10 * TiB, 5),
               "c": thin_node("vgc", 10 * TiB, 5, pool=False),
               "d": {"hostname": "d", "mem_total": 32 * GiB, "root_vg": "pve", "lvs": [], "zpools": [],
                     "vgs": [{"vg_name": "pve", "vg_size": str(4 * TiB), "vg_free": str(5 * GiB)}]}}
    r = hazfs.suggest(facts(surveys, storage_nodes=("a", "b")))
    s = kinds(r)
    assert s["setup:c"]["action"] == {"vg": "vgc", "thin_pool": "vgc", "size": TiB, "kind": "setup", "node": "c"}
    assert "setup:d" not in s
    assert any("d has no room" in n["text"] and "no data storage" in n["text"] for n in r["notes"])


def test_pool_missing_from_storage_and_storage_missing():
    surveys = {n: thin_node(f"vg{n}", 10 * TiB, 5) for n in "abc"}
    assert kinds(hazfs.suggest(facts(surveys, storage_nodes=("a", "b"))))["storage_node:c"]["action"]["nodes"] == ["a", "b", "c"]
    s = kinds(hazfs.suggest(facts(surveys, storage_nodes=None)))
    assert s["storage_create:cluster"]["action"]["nodes"] == ["a", "b", "c"]


def test_unused_volume_is_destructive_suggestion_but_used_open_and_linked_ones_are_not():
    vols = [lv("vga", "vm-100-disk-0", 100 * GiB, "-wi-a-----"),      # leftover, guest moved to b
            lv("vga", "vm-101-disk-0", 100 * GiB, "-wi-ao----"),      # open
            lv("vga", "vm-102-disk-0", 100 * GiB, "-wi-a-----"),      # used by guest 102
            lv("vga", "base-900-disk-0", 10 * GiB, "Vri---tz-k"),     # template base
            lv("vga", "vm-103-disk-0", 10 * GiB, "Vwi-a-tz--")]       # linked clone of the base
    surveys = {"a": thin_node("vga", 10 * TiB, 5, extra_lvs=vols),
               "b": thin_node("vgb", 10 * TiB, 5), "c": thin_node("vgc", 10 * TiB, 5)}
    guests = [guest(100, "b", "lvmb:vm-100-disk-0", 100 * GiB), guest(102, "a", "lvma:vm-102-disk-0", 100 * GiB),
              guest(900, "a", "lvma:base-900-disk-0", 10 * GiB, template=True),
              guest(103, "a", "lvma:base-900-disk-0/vm-103-disk-0", 10 * GiB)]
    s = kinds(hazfs.suggest(facts(surveys, guests)))
    removals = [k for k in s if k.startswith("remove_volume")]
    assert removals == ["remove_volume:a:vga/vm-100-disk-0"]
    assert s[removals[0]]["impact"] == "destructive" and "now runs on b" in s[removals[0]]["detail"]


def test_guest_too_big_for_any_second_node_is_a_note():
    surveys = {"a": thin_node("vga", 50 * TiB, 1, extra_lvs=[lv("vga", "vm-108-disk-0", 30 * TiB, pool="vga", data=2)]),
               "b": thin_node("vgb", 10 * TiB, 5), "c": thin_node("vgc", 10 * TiB, 5)}
    cfg = {"lvma": {"type": "lvmthin", "vgname": "vga"}}
    r = hazfs.suggest(facts(surveys, [guest(108, "a", "lvma:vm-108-disk-0", 30 * TiB)], storage_cfg=cfg))
    assert any("VM 108" in n["text"] and "does not fit" in n["text"] for n in r["notes"])


def test_fingerprint_changes_with_the_action():
    surveys = {n: thin_node(f"vg{n}", 3 * TiB, 60) for n in "abc"}
    a = kinds(hazfs.suggest(facts(surveys)))["quota:a"]["fingerprint"]
    surveys["a"] = thin_node("vga", 3 * TiB, 40)
    b = kinds(hazfs.suggest(facts(surveys)))["quota:a"]["fingerprint"]
    assert a != b


# ── apply ───────────────────────────────────────────────────────────────────────

class FakePve:
    def __init__(self, configs=None):
        self.calls = []
        self.configs = configs or {}

    def __getattr__(self, name):
        return _Path(self, [name])


class _Path:
    def __init__(self, root, parts):
        self.root, self.parts = root, parts

    def __getattr__(self, name):
        return _Path(self.root, self.parts + [name])

    def __call__(self, *args):
        return _Path(self.root, self.parts + [str(a) for a in args])

    def get(self, **kw):
        if self.parts[:2] == ["cluster", "resources"]:
            return [{"vmid": v, "node": n, "type": "qemu"} for (n, v) in self.root.configs]
        if self.parts[-1] == "config":
            return self.root.configs[(self.parts[1], int(self.parts[3]))]
        return []

    def put(self, **kw):
        self.root.calls.append(("put", "/".join(self.parts), kw))

    def post(self, **kw):
        self.root.calls.append(("post", "/".join(self.parts), kw))


def run_apply(monkeypatch, chosen, responses, pve=None):
    ran = []

    def fake(ip, command, stdin=None, timeout=120, jump=None):
        ran.append(command)
        for prefix, out in responses.items():
            if command.startswith(prefix):
                return out
        return ""
    monkeypatch.setattr(hazfs, "run_on_node", fake)
    f = facts({"a": {}, "b": {}, "c": {}})
    hazfs.apply(pve or FakePve(), f, chosen, lambda t: None)
    return ran


def sug(kind, node, **action):
    return {"title": kind, "node": node, "action": dict(action, kind=kind, node=node)}


def test_apply_grow_extends_volume_then_pool(monkeypatch):
    ran = run_apply(monkeypatch, [sug("grow", "a", vg="vga", size=4 * TiB, thin=True)], {
        "lvs --noheadings": f"  {2 * TiB}\n",
        "zpool list -vHP": "hazfs\t2T\n\t/dev/vga/ha-zfs\t2T\n",
        "zpool list -Hp -o size": f"{4 * TiB - GiB}\n",
    })
    assert f"lvextend -L {4 * TiB}b vga/ha-zfs" in ran
    assert "zpool online -e hazfs /dev/vga/ha-zfs" in ran


def test_apply_quota_arc_dropin(monkeypatch):
    ran = run_apply(monkeypatch, [sug("quota", "a", quota=5 * TiB), sug("dropin", "a", vg="vga"),
                                  sug("arc", "a", arc_max=8 * GiB)], {})
    assert f"zfs set quota={5 * TiB} hazfs" in ran
    assert any(c.startswith("mkdir -p /etc/systemd/system/zfs-import-cache.service.d") for c in ran)
    assert any(c.startswith(f"python3 - /etc/modprobe.d/zfs.conf {8 * GiB}") for c in ran)
    assert "update-initramfs -u -k all" in ran


def test_apply_setup_refuses_when_pool_exists(monkeypatch):
    import pytest
    with pytest.raises(RuntimeError, match="already has"):
        run_apply(monkeypatch, [sug("setup", "a", vg="vga", thin_pool="vga", size=TiB)], {"zpool list -H": "hazfs\n"})


def test_apply_setup_thin(monkeypatch):
    pve = FakePve()
    ran = run_apply(monkeypatch, [sug("setup", "c", vg="vgc", thin_pool="vgc", size=TiB)], {}, pve)
    assert f"lvcreate -V {TiB}b -T vgc/vgc -n ha-zfs" in ran
    assert any("zpool create" in c and "/dev/vgc/ha-zfs" in c for c in ran)
    # storage already lists a, b, c: nothing to add
    assert pve.calls == []


def test_apply_remove_volume_checks_it_is_unused(monkeypatch):
    import pytest
    pve = FakePve({("a", 102): {"scsi0": "lvma:vm-100-disk-0,size=10G"}})
    with pytest.raises(RuntimeError, match="uses vm-100-disk-0"):
        run_apply(monkeypatch, [sug("remove_volume", "a", vg="vga", lv="vm-100-disk-0", vmid=100)],
                  {"lvs --noheadings": "  -wi-a-----\n"}, pve)
    with pytest.raises(RuntimeError, match="open"):
        run_apply(monkeypatch, [sug("remove_volume", "a", vg="vga", lv="vm-100-disk-0", vmid=100)],
                  {"lvs --noheadings": "  -wi-ao----\n"}, FakePve())
    ran = run_apply(monkeypatch, [sug("remove_volume", "a", vg="vga", lv="vm-100-disk-0", vmid=100)],
                    {"lvs --noheadings": "  -wi-a-----\n"},
                    FakePve({("a", 102): {"scsi0": "lvma:vm-100-disk-01,size=10G"}}))
    assert "lvremove -y vga/vm-100-disk-0" in ran
