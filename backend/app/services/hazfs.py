"""HA-ZFS wizard: check the replicated ZFS storage on every node and suggest fixes.

Failover without shared storage uses one ZFS storage (ID `ha-zfs`, pool `hazfs`) on several
nodes; Proxmox replicates guest disks between them. On these clusters the pool sits on an
LVM volume `ha-zfs` in each node's data volume group (never the OS volume group).

`survey_node()` reads a node over SSH, `gather()` adds the cluster view from the Proxmox API,
and `suggest()` is a pure function of both, so the advice can be tested without a cluster.
`apply()` carries out the suggestions the user picked.

What the wizard checks and suggests:
- set up the pool on a node that has room in its data volume group but no pool yet;
- add a node's pool to the `ha-zfs` storage (or create the storage);
- grow a pool that is too small for the guests it would hold: the node's own guests plus
  the replicas the failover wizard would send it (it picks the node with the most free
  memory that has room);
- on a thin-provisioned volume, a ZFS quota so the pool can never fill the thin pool
  (a full thin pool breaks every volume in it), and autotrim so freed space goes back;
- the boot drop-in that activates the LVM volume before ZFS imports pools;
- a cap on the ZFS ARC so the cache does not take memory the guests need.
It also reports, without changing anything: unhealthy pools, thin pools that are nearly full,
and old guest volumes that no guest uses any more.
"""
import hashlib
import json
import logging
import re
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor

from app.services import ha_failover

logger = logging.getLogger(__name__)

POOL = "hazfs"
STORAGE = "ha-zfs"
LV = "ha-zfs"
GiB = 1 << 30
TiB = 1 << 40
MIN_POOL = TiB                 # smallest pool worth setting up
MIN_SETUP_ROOM = 500 * GiB     # a node needs this much room in its data VG for a pool
SIZE_STEP = 256 * GiB          # suggested sizes are rounded up to this
OVERHEAD = 1.2                 # ZFS metadata and replication snapshots on top of guest data
DROPIN = "/etc/systemd/system/zfs-import-cache.service.d/lvm-before-zfs.conf"
ARC_CONF = "/etc/modprobe.d/zfs.conf"

# Runs on the node (python3 ships with Proxmox VE) and prints one JSON document.
SURVEY_SCRIPT = r'''
import json, os, subprocess

def run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout
    except Exception:
        return 1, ""

def lvm(cmd, key):
    rc, out = run(cmd + ["--reportformat", "json", "--units", "b", "--nosuffix"])
    try:
        return json.loads(out)["report"][0][key] if rc == 0 else []
    except Exception:
        return []

def read(path):
    try:
        with open(path) as fh:
            return fh.read()
    except Exception:
        return None

out = {"hostname": os.uname().nodename}
for line in (read("/proc/meminfo") or "").splitlines():
    if line.startswith("MemTotal:"):
        out["mem_total"] = int(line.split()[1]) * 1024
root = run(["findmnt", "-no", "SOURCE", "/"])[1].strip()
out["root_vg"] = run(["lvs", "--noheadings", "-o", "vg_name", root])[1].strip() if root.startswith("/dev/") else ""
out["vgs"] = lvm(["vgs", "-o", "vg_name,vg_size,vg_free"], "vg")
out["lvs"] = lvm(["lvs", "-o", "vg_name,lv_name,lv_size,lv_attr,pool_lv,data_percent,metadata_percent"], "lv")
pools = []
rc, txt = run(["zpool", "list", "-Hp", "-o", "name,size,alloc,free,health,autotrim"])
for line in txt.splitlines():
    f = line.split("\t")
    if len(f) == 6:
        pools.append({"name": f[0], "size": int(f[1]), "alloc": int(f[2]), "free": int(f[3]),
                      "health": f[4], "autotrim": f[5]})
out["zpools"] = pools
if any(p["name"] == "%(pool)s" for p in pools):
    props = {}
    for line in run(["zfs", "get", "-Hp", "-o", "property,value", "quota,available,used,mountpoint", "%(pool)s"])[1].splitlines():
        k, _, v = line.partition("\t")
        props[k] = v
    out["pool_props"] = props
    vdevs = [l.split() for l in run(["zpool", "list", "-vHP", "%(pool)s"])[1].splitlines()[1:]]
    out["pool_vdevs"] = [v[0] for v in vdevs if v and v[0].startswith("/")]
    zvols = []
    for line in run(["zfs", "list", "-Hp", "-t", "volume", "-o", "name,volsize,used", "-r", "%(pool)s"])[1].splitlines():
        f = line.split("\t")
        if len(f) == 3:
            zvols.append({"name": f[0], "volsize": int(f[1]), "used": int(f[2])})
    out["zvols"] = zvols
def num(path):
    v = read(path)
    return int(v) if v and v.strip().isdigit() else None
out["arc_max"] = num("/sys/module/zfs/parameters/zfs_arc_max")
out["arc_min"] = num("/sys/module/zfs/parameters/zfs_arc_min")
out["arc_conf"] = read("%(arc_conf)s")
out["dropin"] = read("%(dropin)s")
print(json.dumps(out))
''' % {"pool": POOL, "arc_conf": ARC_CONF, "dropin": DROPIN}


# ── SSH ─────────────────────────────────────────────────────────────────────────

def run_on_node(ip: str, command: str, stdin: str = None, timeout: int = 120, jump: str = None) -> str:
    """Run `command` as root on a node with Depl0y's SSH key; raise with stderr if it fails.

    If the node cannot be reached directly, retry through `jump` (the node serving the API).
    """
    base = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new"]
    attempts = [base + [f"root@{ip}", command]]
    if jump and jump != ip:
        attempts.append(base + ["-o", f"ProxyJump=root@{jump}", f"root@{ip}", command])
    for i, argv in enumerate(attempts):
        p = subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=timeout)
        if p.returncode == 255 and i + 1 < len(attempts):
            continue   # ssh itself failed (unreachable): try the jump host
        if p.returncode != 0:
            raise RuntimeError((p.stderr or p.stdout or f"exit {p.returncode}").strip()[-500:])
        return p.stdout
    raise RuntimeError("unreachable")


def survey_node(ip: str, jump: str = None) -> dict:
    return json.loads(run_on_node(ip, "python3 -", stdin=SURVEY_SCRIPT, timeout=90, jump=jump))


# ── Facts ───────────────────────────────────────────────────────────────────────

def gather(pve, jump: str = None) -> dict:
    """Everything suggest() needs: the cluster from the API, each online node over SSH."""
    cluster = ha_failover.gather_cluster(pve)
    ips = {x["name"]: x.get("ip") for x in pve.cluster.status.get() if x.get("type") == "node"}
    storage_cfg = {s["storage"]: s for s in pve.storage.get()}
    guests = []
    for r in pve.cluster.resources.get(type="vm"):
        if r.get("status") == "unknown" or not cluster["nodes"].get(r["node"], {}).get("online"):
            continue
        api = pve.nodes(r["node"]).lxc(r["vmid"]) if r["type"] == "lxc" else pve.nodes(r["node"]).qemu(r["vmid"])
        try:
            config = api.config.get()
        except Exception as exc:  # noqa: BLE001 - a guest that vanished mid-survey is skipped
            logger.debug("hazfs: config of %s failed: %s", r["vmid"], exc)
            continue
        guests.append({"vmid": int(r["vmid"]), "name": r.get("name") or "", "node": r["node"],
                       "vmtype": r["type"], "template": bool(r.get("template")),
                       "maxmem": int(r.get("maxmem") or 0), "config": config})

    def one(name):
        if not cluster["nodes"][name].get("online") or not ips.get(name):
            return name, {"error": "node is offline"}
        try:
            return name, survey_node(ips[name], jump)
        except Exception as exc:  # noqa: BLE001 - report per node, keep the rest
            return name, {"error": f"could not read the node over SSH: {exc}"}

    with ThreadPoolExecutor(max_workers=8) as pool:
        surveys = dict(pool.map(one, list(cluster["nodes"])))
    return {"cluster": cluster, "ips": ips, "storage_cfg": storage_cfg, "guests": guests, "surveys": surveys}


# ── Analysis ────────────────────────────────────────────────────────────────────

def _round_up(n: int, step: int = SIZE_STEP) -> int:
    return -(-int(n) // step) * step


def _gib(n) -> str:
    n = int(n or 0)
    if n >= TiB:
        return f"{n / TiB:.1f} TiB"
    return f"{n / GiB:.0f} GiB" if n >= GiB else f"{n >> 20} MiB"


def _fingerprint(action: dict) -> str:
    return hashlib.sha1(json.dumps(action, sort_keys=True).encode()).hexdigest()[:12]


def arc_target(mem_total: int) -> int:
    """ARC cap the wizard suggests: 1/16 of RAM, at least 1 GiB, at most 16 GiB."""
    return max(1, min(16, (mem_total // 16) // GiB)) * GiB


def _node_storage(s: dict) -> dict:
    """The node's view of LVM and the hazfs pool, from survey_node()."""
    lvs = {(lv["vg_name"], lv["lv_name"]): lv for lv in s.get("lvs", [])}
    vgs = {vg["vg_name"]: vg for vg in s.get("vgs", [])}
    pool = next((p for p in s.get("zpools", []) if p["name"] == POOL), None)
    ha_lv = next((lv for (vg, name), lv in lvs.items() if name == LV), None)
    thin_pools = [lv for lv in lvs.values() if lv.get("lv_attr", "").startswith("t")]
    data_vgs = [vg for name, vg in vgs.items() if name != s.get("root_vg")]
    info = {"lvs": lvs, "vgs": vgs, "pool": pool, "ha_lv": ha_lv, "thin": None, "thick_vg": None}
    if pool and not ha_lv:
        return info   # the pool is not on our LVM volume: leave its layout alone
    if ha_lv:
        info["vg"] = ha_lv["vg_name"]
        if ha_lv.get("pool_lv"):
            info["thin"] = lvs.get((ha_lv["vg_name"], ha_lv["pool_lv"]))
        else:
            info["thick_vg"] = vgs.get(ha_lv["vg_name"])
    else:
        # Where a new pool would go: the biggest thin pool in a data VG, else the data VG with most free space.
        data_names = {vg["vg_name"] for vg in data_vgs}
        thins = [t for t in thin_pools if t["vg_name"] in data_names]
        if thins:
            best = max(thins, key=lambda t: _thin_free(t))
            info.update(vg=best["vg_name"], thin=best)
        elif data_vgs:
            best = max(data_vgs, key=lambda vg: int(vg["vg_free"]))
            info.update(vg=best["vg_name"], thick_vg=best)
    return info


def _thin_free(thin: dict) -> int:
    size = int(thin["lv_size"])
    return int(size * (1 - float(thin.get("data_percent") or 0) / 100))


def _thin_reserve(thin_backing: dict) -> int:
    """Space always kept free in a thin pool that holds a ZFS pool: 5%, at least 100 GiB."""
    return max(int(thin_backing["size"] * 0.05), 100 * GiB)


def _written(lv: dict) -> int:
    """Bytes an LVM volume really holds (thin volumes only hold what was written)."""
    size = int(lv["lv_size"])
    if lv.get("lv_attr", "").startswith("V") and lv.get("data_percent") not in (None, ""):
        return int(size * float(lv["data_percent"]) / 100)
    return size


def _guest_usage(g: dict, facts: dict) -> dict:
    """Allocated and written bytes of a guest's disks, and where they live."""
    node = g["node"]
    survey = facts["surveys"].get(node, {})
    node_st = facts["cluster"]["nodes"].get(node, {}).get("storages", {})
    lvs = {(lv["vg_name"], lv["lv_name"]): lv for lv in survey.get("lvs", [])}
    zvols = {z["name"]: z for z in survey.get("zvols", [])}
    vols = ha_failover.guest_volumes(g["vmtype"], g["config"])
    alloc = written = 0
    biggest = 0
    kinds = set()
    local_by_vg = {}
    for d in vols["disks"]:
        st = node_st.get(d["storage"], {})
        cfg = facts["storage_cfg"].get(d["storage"], {})
        name = d["volume"].split(":", 1)[1].split("/")[-1]
        size = d["size"]
        used = size
        if d["storage"] == STORAGE:
            kinds.add("hazfs")
            z = zvols.get(f"{POOL}/{name}")
            used = z["used"] if z else size
        elif st.get("shared"):
            kinds.add("shared")
        else:
            kinds.add("local")
            lv = lvs.get((cfg.get("vgname"), name)) if cfg.get("type") in ("lvm", "lvmthin") else None
            if lv:
                used = _written(lv)
                size = size or int(lv["lv_size"])
                local_by_vg[lv["vg_name"]] = local_by_vg.get(lv["vg_name"], 0) + used
        alloc += size
        written += used
        biggest = max(biggest, size)
    return {"alloc": alloc, "written": written, "biggest": biggest, "kinds": kinds,
            "local_by_vg": local_by_vg, "passthrough": bool(vols["passthrough"])}


def suggest(facts: dict) -> dict:
    """Per-node status, suggested changes and notes. Pure function of gather()."""
    cluster, surveys = facts["cluster"], facts["surveys"]
    nodes_info = cluster["nodes"]
    storage = facts["storage_cfg"].get(STORAGE)
    storage_nodes = set(filter(None, str((storage or {}).get("nodes", "")).split(","))) if storage else set()
    if storage and not storage.get("nodes"):
        storage_nodes = set(nodes_info)   # no node list: every node
    suggestions, notes, nodes = [], [], {}

    # 1. Each node: what it has and how much room the pool can get.
    for name in sorted(nodes_info):
        s = surveys.get(name, {})
        entry = {"node": name, "online": nodes_info[name].get("online"), "lrm": nodes_info[name].get("lrm"),
                 "error": s.get("error"), "in_storage": name in storage_nodes, "mem_total": s.get("mem_total"),
                 "arc_max": s.get("arc_max"), "pool": None, "backing": None}
        nodes[name] = entry
        if s.get("error"):
            continue
        st = _node_storage(s)
        entry["_st"] = st
        pool = st["pool"]
        if pool:
            props = s.get("pool_props", {})
            entry["pool"] = {"size": pool["size"], "alloc": pool["alloc"], "free": pool["free"],
                             "health": pool["health"], "autotrim": pool["autotrim"],
                             "quota": int(props.get("quota") or 0), "used": int(props.get("used") or 0),
                             "available": int(props.get("available") or 0)}
        if st["thin"]:
            t = st["thin"]
            entry["backing"] = {"kind": "thin", "vg": t["vg_name"], "thin_pool": t["lv_name"],
                                "size": int(t["lv_size"]), "free": _thin_free(t),
                                "data_percent": float(t.get("data_percent") or 0),
                                "metadata_percent": float(t.get("metadata_percent") or 0)}
        elif st["thick_vg"]:
            vg = st["thick_vg"]
            entry["backing"] = {"kind": "thick", "vg": vg["vg_name"], "size": int(vg["vg_size"]),
                                "free": int(vg["vg_free"])}
        if st["ha_lv"]:
            entry["lv_size"] = int(st["ha_lv"]["lv_size"])

    def hazfs_node(name, planned=True):
        e = nodes[name]
        if not e["online"] or not e["lrm"] or e["error"]:
            return False
        if e["pool"]:
            return True
        return planned and e.get("backing") is not None and _setup_room(e) >= MIN_SETUP_ROOM

    def _setup_room(e):
        b = e.get("backing")
        if not b or e["pool"] or e.get("lv_size"):
            return 0
        return b["free"]

    # 2. Per node with a pool (or room for one):
    #    limit    - the most free space Proxmox can report for the pool now (thin: what the thin
    #               pool can really back, keeping a reserve; thick: the volume plus free VG space).
    #               The failover wizard needs a guest's full allocated size free on both nodes.
    #    capacity - data the pool could eventually hold: the limit plus the node's own guest
    #               disks in the same VG, which are freed as they move into the pool.
    guests = [dict(g, **_guest_usage(g, facts)) for g in facts["guests"]]
    limit, capacity = {}, {}
    for name, e in nodes.items():
        if not hazfs_node(name):
            continue
        b = e["backing"]
        used = e["pool"]["used"] if e["pool"] else 0
        if not b:   # a pool on its own disks: it holds what it has room for
            limit[name] = capacity[name] = int(e["pool"]["size"] * 0.9)
            continue
        if b["kind"] == "thin":
            limit[name] = max(0, used + b["free"] - _thin_reserve(b))
        else:
            limit[name] = max(0, (e.get("lv_size") or 0) + b["free"] - 4 * GiB)
        own_local = sum(g["local_by_vg"].get(b["vg"], 0) for g in guests
                        if g["node"] == name and not g["template"])
        capacity[name] = limit[name] + own_local

    # 3. Where every failover-capable guest would live: first each guest on its own node, then a
    #    replica on the node with the most free memory that has room (as the failover wizard picks).
    remaining = dict(capacity)
    demand = {n: {"written": 0, "biggest": 0, "own": [], "replicas": []} for n in capacity}
    jobs = {str(j.get("guest")): j.get("target") for j in cluster.get("replication", [])}
    too_big = []
    candidates = [g for g in guests if not g["template"] and not g["passthrough"] and g["alloc"]
                  and g["kinds"] <= {"local", "hazfs"} and g["node"] in capacity]
    placed = []
    for g in sorted(candidates, key=lambda g: g["written"], reverse=True):
        g["need"] = int(g["written"] * OVERHEAD)
        if g["alloc"] <= limit[g["node"]] and g["need"] <= remaining[g["node"]]:
            remaining[g["node"]] -= g["need"]
            placed.append(g)
        else:
            too_big.append(g)
    for g in placed:
        fits = [n for n in remaining if n != g["node"] and g["alloc"] <= limit[n] and g["need"] <= remaining[n]]
        target = jobs.get(str(g["vmid"]))
        if target not in fits:
            fits.sort(key=lambda n: nodes_info[n].get("mem_free", 0), reverse=True)
            target = fits[0] if fits else None
        if not target:
            remaining[g["node"]] += g["need"]
            too_big.append(g)
            continue
        remaining[target] -= g["need"]
        for n, role in ((g["node"], "own"), (target, "replicas")):
            demand[n]["written"] += g["need"]
            demand[n]["biggest"] = max(demand[n]["biggest"], g["alloc"])
            demand[n][role].append(g["vmid"])

    for name, d in demand.items():
        nodes[name]["plan"] = {"guests": len(d["own"]), "replicas": len(d["replicas"]),
                               "needed": d["written"], "capacity": capacity[name], "limit": limit[name]}

    def size_for(name):
        """Pool size that holds the planned data with room for the biggest guest to arrive."""
        d = demand[name]
        size = max(MIN_POOL, _round_up(d["written"] + d["biggest"]))
        b = nodes[name]["backing"]
        if b["kind"] == "thin":
            return min(size, _round_up(b["size"]))
        current = nodes[name].get("lv_size", 0)
        return max(current, min(size, current + b["free"] - 4 * GiB))

    def add(kind, node, title, detail, action, impact="normal", key=None):
        action = dict(action, kind=kind, node=node)
        sid = f"{kind}:{node or 'cluster'}" + (f":{key}" if key else "")
        suggestions.append({"id": sid, "kind": kind, "node": node, "title": title,
                            "detail": detail, "impact": impact, "action": action,
                            "fingerprint": _fingerprint(action)})

    # 4. Suggestions per node.
    pool_nodes = sorted(n for n, e in nodes.items() if e["pool"])
    for name, e in sorted(nodes.items()):
        s, b, pool = surveys.get(name, {}), e.get("backing"), e["pool"]
        if e["error"]:
            notes.append({"level": "warn", "node": name, "text": f"{name}: {e['error']}"})
            continue
        if not pool:
            if not e["online"]:
                continue
            if not e["lrm"]:
                notes.append({"level": "info", "node": name,
                              "text": f"{name}: the HA service (pve-ha-lrm) is not running, so it cannot take part in failover."})
            elif e.get("lv_size"):
                notes.append({"level": "warn", "node": name,
                              "text": f"{name} has an LVM volume {LV} but no {POOL} pool on it. Create the pool "
                                      f"by hand or remove the volume; the wizard will not touch it."})
            elif name in capacity:
                size = size_for(name)
                where = (f"a thin volume in {b['vg']}/{b['thin_pool']} ({_gib(b['free'])} free)" if b["kind"] == "thin"
                         else f"{b['vg']} ({_gib(b['free'])} free)")
                add("setup", name, f"Set up the {POOL} pool on {name}",
                    f"Create a {_gib(size)} LVM volume {LV} on {where}, the {POOL} ZFS pool on it "
                    f"(compression lz4, autotrim on), the boot drop-in that activates the volume before ZFS "
                    f"imports pools, and add {name} to the {STORAGE} storage. Guests on {name} can then fail over "
                    f"with replication, and other nodes can replicate to it. Nothing existing is changed.",
                    {"vg": b["vg"], "thin_pool": b.get("thin_pool"), "size": size})
            else:
                room = b["free"] if b else 0
                notes.append({"level": "info", "node": name,
                              "text": f"{name} has no room for a {POOL} pool outside its OS volume group "
                                      f"({_gib(room)} free in its data storage; at least {_gib(MIN_SETUP_ROOM)} is needed). "
                                      f"Its guests can only fail over by moving to another node first or with shared storage."})
            continue

        # Pool health and thin pool fill.
        if pool["health"] != "ONLINE":
            notes.append({"level": "warn", "node": name,
                          "text": f"{POOL} on {name} is {pool['health']}: check `zpool status {POOL}` on the node."})
        if b and b["kind"] == "thin" and (b["data_percent"] >= 80 or b["metadata_percent"] >= 80):
            notes.append({"level": "warn", "node": name,
                          "text": f"Thin pool {b['vg']}/{b['thin_pool']} on {name} is {b['data_percent']:.0f}% full "
                                  f"(metadata {b['metadata_percent']:.0f}%). A full thin pool stops every volume in it."})

        if storage and name not in storage_nodes:
            add("storage_node", name, f"Add {name} to the {STORAGE} storage",
                f"{name} has the {POOL} pool but the {STORAGE} storage is not enabled for it, so the failover "
                f"wizard cannot move disks or replicate there.", {"nodes": sorted(storage_nodes | {name})})

        if not b:
            continue   # not on an LVM volume: nothing below applies
        current = e.get("lv_size") or pool["size"]
        new_size = current
        if name in demand:
            size = size_for(name)
            if size > current * 1.1 and size - current >= SIZE_STEP:
                new_size = size
                plan = nodes[name]["plan"]
                if b["kind"] == "thin":
                    how = "The volume is thin, so growing it uses no space until data is written. "
                else:
                    how = f"This takes {_gib(size - current)} of the {_gib(b['free'])} free in {b['vg']}. "
                    if size + SIZE_STEP < _round_up(plan["needed"] + demand[name]["biggest"]):
                        how += ("That is all the room there is now; after guests' disks have moved into the pool "
                                "(or unused volumes are deleted) run the wizard again to grow it further. ")
                add("grow", name, f"Grow {POOL} on {name} from {_gib(current)} to {_gib(size)}",
                    f"{name} would hold its own {plan['guests']} failover-capable guest(s) and replicas of "
                    f"{plan['replicas']} guest(s) from other nodes: about {_gib(plan['needed'])} of data. "
                    f"The failover wizard only offers a pool with room for a guest's full disk size. "
                    + how + "Growing happens online; guests keep running.",
                    {"vg": e["_st"]["vg"], "size": size, "thin": b["kind"] == "thin"})

        if b["kind"] == "thin":
            reserve = _thin_reserve(b)
            safe = pool["used"] + b["free"] - reserve
            quota = max(_round_up(pool["used"] + 50 * GiB, 64 * GiB), (safe // (64 * GiB)) * 64 * GiB)
            current_q = pool["quota"]
            if safe < new_size * 0.98 and (not current_q or abs(quota - current_q) > max(current_q * 0.1, 100 * GiB)):
                verb = "Set" if not current_q else ("Lower" if quota < current_q else "Raise")
                add("quota", name, f"{verb} the {POOL} quota on {name} to {_gib(quota)}",
                    f"The pool{' (after growing)' if new_size != current else ''} is {_gib(new_size)} on a thin "
                    f"volume, but the thin pool {b['vg']}/{b['thin_pool']} only has {_gib(b['free'])} really free. "
                    f"If ZFS wrote more than that, the thin pool would fill and every volume in it would stop. "
                    f"A quota of {_gib(quota)} keeps {_gib(reserve)} spare in the thin pool"
                    + (f" (the quota is {_gib(current_q)} now)." if current_q else " (there is no quota now).")
                    + " Proxmox reports the quota as the pool's free space, so the failover wizard sees the real "
                      "limit. Run the wizard again after moving guests; the space they free can raise it.",
                    {"quota": quota})
            if pool["autotrim"] != "on":
                add("autotrim", name, f"Turn on autotrim for {POOL} on {name}",
                    "The pool is on a thin volume; with autotrim, space ZFS frees is handed back to the thin pool.",
                    {})

        vg = e["_st"]["vg"]
        dropin = s.get("dropin") or ""
        if f"lvchange -ay {vg}/{LV}" not in dropin:
            add("dropin", name, f"Activate the {LV} volume before ZFS imports pools at boot on {name}",
                f"Without this, {name} can boot before LVM has activated {vg}/{LV}; the {POOL} pool is then "
                f"missing and every guest on it fails to start. Adds {DROPIN}.", {"vg": vg})

        mem, arc = s.get("mem_total") or 0, s.get("arc_max") or 0
        if mem and (arc == 0 or arc > mem // 4):
            target = arc_target(mem)
            add("arc", name, f"Cap the ZFS cache on {name} at {_gib(target)}",
                f"ZFS keeps a read cache (ARC) in RAM; {'with no cap it can grow to half the RAM' if arc == 0 else f'the cap is {_gib(arc)}'} "
                f"of {_gib(mem)}. Guests need that memory, and on an LVM-backed pool the cache adds little. "
                f"Takes effect now and after reboots.", {"arc_max": target})

    if not storage and len(pool_nodes) >= 2:
        add("storage_create", None, f"Create the {STORAGE} storage for {', '.join(pool_nodes)}",
            f"These nodes have the {POOL} pool. One ZFS storage with the same ID on all of them lets the "
            f"failover wizard move guest disks there and replicate them between nodes.",
            {"nodes": pool_nodes})

    for g in sorted(too_big, key=lambda g: (g["node"], g["vmid"])):
        notes.append({"level": "info", "node": g["node"],
                      "text": f"{'CT' if g['vmtype'] == 'lxc' else 'VM'} {g['vmid']} ({g['name']}) on {g['node']} "
                              f"({_gib(g['alloc'])} of disks, {_gib(g['written'])} in use) does not fit in the {POOL} "
                              f"pools as they could be now: its node and a second node both need room for it. "
                              f"Free space (see unused volumes), or use shared storage for its failover."})

    for v in _stale_volumes(facts):
        add("remove_volume", v["node"], f"Delete unused volume {v['vg']}/{v['lv']} on {v['node']} ({_gib(v['size'])})",
            f"{v['why'].capitalize()}, and nothing has the volume open. It looks like a leftover from a "
            f"migration or restore. Deleting it frees {_gib(v['size'])} in {v['vg']}. This cannot be undone.",
            {"vg": v["vg"], "lv": v["lv"], "vmid": v["vmid"]}, impact="destructive", key=f"{v['vg']}/{v['lv']}")

    order = ["setup", "storage_create", "storage_node", "remove_volume", "grow", "quota", "autotrim", "dropin", "arc"]
    suggestions.sort(key=lambda x: (order.index(x["kind"]), x["node"] or ""))
    for e in nodes.values():
        e.pop("_st", None)
    return {"nodes": [nodes[n] for n in sorted(nodes)], "suggestions": suggestions, "notes": notes,
            "storage": {"exists": bool(storage), "nodes": sorted(storage_nodes)}}


_GUEST_VOL = re.compile(r"^(vm|base)-(\d+)-(disk-\d+|cloudinit|state-.+)$")


def _stale_volumes(facts: dict) -> list:
    """LVM guest volumes on a node that no guest on that node uses."""
    found = []
    shared_vgs = {c.get("vgname") for c in facts["storage_cfg"].values()
                  if c.get("type") == "lvm" and c.get("shared")}
    for node, s in facts["surveys"].items():
        if s.get("error"):
            continue
        referenced = set()
        for g in facts["guests"]:
            if g["node"] != node:
                continue
            for value in g["config"].values():
                for m in re.finditer(r"[\w.-]+:([\w./-]+)", str(value)):
                    referenced.update(m.group(1).split("/"))
        here = {g["vmid"]: g for g in facts["guests"] if g["node"] == node}
        elsewhere = {g["vmid"]: g["node"] for g in facts["guests"] if g["node"] != node}
        for lv in s.get("lvs", []):
            if lv["vg_name"] in shared_vgs:
                continue   # shared LVM: the guest using it may run on another node
            m = _GUEST_VOL.match(lv["lv_name"])
            if not m or lv["lv_name"] in referenced:
                continue
            if len(lv.get("lv_attr", "")) > 5 and lv["lv_attr"][5] == "o":
                continue   # open: something is using it
            vmid = int(m.group(2))
            if vmid in here:
                why = f"guest {vmid} is on {node} but its config does not use it"
            elif vmid in elsewhere:
                why = f"guest {vmid} now runs on {elsewhere[vmid]}"
            else:
                why = f"there is no guest {vmid}"
            found.append({"node": node, "vg": lv["vg_name"], "lv": lv["lv_name"], "vmid": vmid,
                          "size": _written(lv), "why": why})
    return found


# ── Apply ───────────────────────────────────────────────────────────────────────

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")


def _q(name: str) -> str:
    if not _NAME.match(str(name)):
        raise RuntimeError(f"unexpected name {name!r}")
    return shlex.quote(str(name))


def _dropin_text(vg: str) -> str:
    return ("[Unit]\nAfter=lvm2-monitor.service\n\n[Service]\n"
            f"# {POOL} lives on an LVM volume: make sure it is active before ZFS imports pools\n"
            f"ExecStartPre=-/sbin/lvchange -ay {vg}/{LV}\n")


ARC_SCRIPT = r'''
import re, sys
path, arc_max = sys.argv[1], int(sys.argv[2])
try:
    text = open(path).read()
except FileNotFoundError:
    text = ""
opts = {}
for line in text.splitlines():
    if line.strip().startswith("options zfs "):
        for kv in line.split()[2:]:
            k, _, v = kv.partition("=")
            opts[k] = v
opts["zfs_arc_max"] = str(arc_max)
if int(opts.get("zfs_arc_min", "0") or 0) >= arc_max:
    opts["zfs_arc_min"] = str(arc_max // 2)
others = [l for l in text.splitlines() if not l.strip().startswith("options zfs ")]
line = "options zfs " + " ".join(f"{k}={v}" for k, v in opts.items())
open(path, "w").write("\n".join(others + [line]) + "\n")
p = "/sys/module/zfs/parameters/"
cur_min = int(open(p + "zfs_arc_min").read())
if cur_min >= arc_max:
    open(p + "zfs_arc_min", "w").write(opts["zfs_arc_min"])
open(p + "zfs_arc_max", "w").write(str(arc_max))
'''


def apply(pve, facts: dict, chosen: list, progress, jump: str = None):
    """Carry out the chosen suggestions (dicts from suggest()), in their listed order."""
    ips = facts["ips"]

    def node_run(node, command, **kw):
        return run_on_node(ips[node], command, jump=jump, **kw)

    for sug in chosen:
        a, node = sug["action"], sug["node"]
        progress(sug["title"])
        kind = a["kind"]
        if kind == "setup":
            vg = _q(a["vg"])
            out = node_run(node, f"zpool list -H -o name {POOL} 2>/dev/null; lvs --noheadings -o lv_name {vg}/{LV} 2>/dev/null; true")
            if out.strip():
                raise RuntimeError(f"{node} already has a {POOL} pool or an {LV} volume; run the wizard again")
            if a.get("thin_pool"):
                node_run(node, f"lvcreate -V {int(a['size'])}b -T {vg}/{_q(a['thin_pool'])} -n {LV}")
            else:
                node_run(node, f"lvcreate -y -L {int(a['size'])}b -n {LV} {vg}")
            dev = f"/dev/{a['vg']}/{LV}"
            progress(f"Creating the {POOL} pool on {dev}")
            node_run(node, f"wipefs -a {shlex.quote(dev)} && zpool create -o ashift=12 -o autotrim=on "
                           f"-O compression=lz4 -O atime=off -O xattr=sa -O mountpoint=/{POOL} {POOL} {shlex.quote(dev)}")
            progress("Adding the boot drop-in")
            _write_dropin(node_run, node, a["vg"])
            storage = facts["storage_cfg"].get(STORAGE)
            if storage:
                nodes = set(filter(None, str(storage.get("nodes", "")).split(",")))
                if nodes and node not in nodes:
                    progress(f"Adding {node} to the {STORAGE} storage")
                    pve.storage(STORAGE).put(nodes=",".join(sorted(nodes | {node})))
            progress(f"{POOL} on {node} is ready")
        elif kind == "storage_node":
            pve.storage(STORAGE).put(nodes=",".join(a["nodes"]))
        elif kind == "storage_create":
            pve.storage.post(storage=STORAGE, type="zfspool", pool=POOL, content="images,rootdir",
                             sparse=1, nodes=",".join(a["nodes"]))
        elif kind == "grow":
            vg, size = _q(a["vg"]), int(a["size"])
            current = int(node_run(node, f"lvs --noheadings --units b --nosuffix -o lv_size {vg}/{LV}").strip())
            if current < size:
                node_run(node, f"lvextend -L {size}b {vg}/{LV}")
            vdevs = [v.split() for v in node_run(node, f"zpool list -vHP {POOL}").splitlines()[1:]]
            for vdev in [v[0] for v in vdevs if v and v[0].startswith("/")]:
                node_run(node, f"zpool online -e {POOL} {shlex.quote(vdev)}")
            new = int(node_run(node, f"zpool list -Hp -o size {POOL}").strip())
            progress(f"{POOL} on {node} is now {_gib(new)}")
            if new < size * 0.9:
                raise RuntimeError(f"the pool only grew to {_gib(new)}")
        elif kind == "remove_volume":
            vg, lv = _q(a["vg"]), _q(a["lv"])
            attr = node_run(node, f"lvs --noheadings -o lv_attr {vg}/{lv}").strip()
            if len(attr) > 5 and attr[5] == "o":
                raise RuntimeError(f"{a['vg']}/{a['lv']} is open now; not deleting it")
            for r in pve.cluster.resources.get(type="vm"):
                if r.get("node") != node:
                    continue
                api = pve.nodes(node).lxc(r["vmid"]) if r["type"] == "lxc" else pve.nodes(node).qemu(r["vmid"])
                if re.search(rf"[:/]{re.escape(a['lv'])}(?![\w.-])", json.dumps(api.config.get())):
                    raise RuntimeError(f"guest {r['vmid']} on {node} uses {a['lv']} now; not deleting it")
            node_run(node, f"lvremove -y {vg}/{lv}")
        elif kind == "quota":
            node_run(node, f"zfs set quota={int(a['quota'])} {POOL}")
        elif kind == "autotrim":
            node_run(node, f"zpool set autotrim=on {POOL}")
        elif kind == "dropin":
            _write_dropin(node_run, node, a["vg"])
        elif kind == "arc":
            node_run(node, f"python3 - {shlex.quote(ARC_CONF)} {int(a['arc_max'])}", stdin=ARC_SCRIPT)
            progress(f"Cache capped now; rebuilding the initramfs on {node} so the cap also applies at boot")
            node_run(node, "update-initramfs -u -k all", timeout=900)
        else:
            raise RuntimeError(f"unknown change {kind}")
    progress("Done")


def _write_dropin(node_run, node, vg):
    _q(vg)
    node_run(node, f"mkdir -p {shlex.quote(DROPIN.rsplit('/', 1)[0])} && cat > {shlex.quote(DROPIN)} "
                   "&& systemctl daemon-reload", stdin=_dropin_text(vg))
