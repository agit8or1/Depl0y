"""Node maintenance: preview where every guest on a node would go, then carry out that plan.

`gather_facts()` reads what the decision needs from the Proxmox API, using GET calls only.
`build_preview()` is a pure function of those facts. `run_evacuation()` carries out a reviewed
plan one guest at a time and checks each placement again before moving the guest.

It builds on the HA wizard's readiness checks (app.services.ha_failover): the same cluster facts
(`gather_cluster`), the same reading of a guest config (`guest_volumes`) and the same storage
rules (`_usable`).

Classes in the preview:

- ``online``    moves without interrupting it: a live migration of a running VM, or an offline
                migration of a stopped guest.
- ``downtime``  moves only with a stop: a running container (restart migration) or a running VM
                with mapped PCI/USB devices (shut down, migrate, start). Run only when the operator
                names the guest in ``allow_downtime``.
- ``blocked``   cannot move: node-bound hardware, a local ISO, a bind mount, a lock, HA placement,
                no destination storage, or not enough capacity once earlier moves are counted.
- ``unknown``   Depl0y could not read enough to decide (guest or config unreadable).

Placement is greedy, biggest memory first. RAM and destination disk space are reserved as each
guest is placed, so the last guests see what the earlier moves leave behind. Each target keeps
MEM_RESERVE_FRACTION of its memory free.

Execution never chooses a new target. Before each move it re-reads the cluster and checks the
reviewed target again on its own. If the method, destination storage or guest configuration
changed, or the target can no longer take the guest, the guest is skipped. A move counts only
when its Proxmox task ended OK *and* the guest is seen on the target in the expected state. An HA
migration task ends as soon as the request is queued, so for HA guests only the location counts.

Host power actions are not part of this module.
"""
import logging
import re
import threading
import time
import uuid
from datetime import datetime, timezone

from app.services import ha_failover as hf
from app.services.hazfs import STORAGE as HAZFS_STORAGE

logger = logging.getLogger(__name__)

MEM_RESERVE_FRACTION = 0.10      # keep 10% of a target's RAM free
MIGRATE_TIMEOUT = 6 * 3600       # a live migration with large local disks can take hours
SHUTDOWN_TIMEOUT = 300           # seconds a cold move waits for a clean guest shutdown
CT_RESTART_TIMEOUT = 180         # seconds a container restart migration waits for shutdown
VERIFY_TIMEOUT = 120             # seconds to see the guest on its target after the task ended OK
HA_PICKUP_GRACE = 90             # seconds HA may take to act on a migrate request
POLL_INTERVAL = 3
PLAN_TTL = 2 * 3600
JOB_TTL = 24 * 3600

CLASSES = ("online", "downtime", "blocked", "unknown")

# Indirections so tests can run the executor on a fake clock.
_sleep = time.sleep
_now = time.time

GiB = 1 << 30


def _gib(n: int) -> str:
    return f"{n / GiB:.1f} GiB"


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - an optional read must not abort the preview
        logger.debug("node_evacuation: optional call failed: %s", exc)
        return default


def _try(fn):
    """(value, None) or (None, error text)."""
    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _guest_api(pve, node, vmtype, vmid):
    return pve.nodes(node).lxc(vmid) if vmtype == "lxc" else pve.nodes(node).qemu(vmid)


# ── Permissions ─────────────────────────────────────────────────────────────────

PREVIEW_PRIVS = [
    ("Sys.Audit", "/nodes", "read nodes, HA state and tasks"),
    ("VM.Audit", "/vms", "read guest configurations"),
    ("Datastore.Audit", "/storage", "read storage capacity"),
]


def has_priv(perms: dict, priv: str, path: str) -> bool:
    """`perms` is GET /access/permissions. Privileges set on a parent path are inherited."""
    parts = [p for p in path.split("/") if p]
    for i in range(len(parts), -1, -1):
        p = "/" + "/".join(parts[:i])
        if perms.get(p, {}).get(priv):
            return True
    return False


def required_privileges(entries: list) -> list:
    """The Proxmox privileges carrying out these plan entries needs, one row per guest and need."""
    need = []
    for e in entries:
        path = f"/vms/{e['vmid']}"
        need.append(("VM.Migrate", path, f"migrate {e['sid']}"))
        if e.get("method") == "cold":
            need.append(("VM.PowerMgmt", path, f"shut down and start {e['sid']}"))
        for src, dst in (e.get("storage_map") or {}).items():
            need.append(("Datastore.AllocateSpace", f"/storage/{dst}", f"copy {e['sid']}'s {src} disks to {dst}"))
        for m in e.get("mappings") or []:
            need.append(("Mapping.Use", f"/mapping/{m['kind']}/{m['id']}", f"use mapped device {m['id']}"))
    return need


def check_permissions(perms, entries: list) -> dict:
    """Which privileges are missing for the preview and for executing `entries`."""
    if perms is None:
        return {"checked": False, "preview": {"ok": None, "missing": []},
                "execute": {"ok": None, "missing": []},
                "note": "Could not read the token's permissions (GET /access/permissions); "
                        "Proxmox will still refuse anything the token may not do."}
    def missing(rows):
        return [{"privilege": p, "path": path, "why": why} for p, path, why in rows if not has_priv(perms, p, path)]
    pm, em = missing(PREVIEW_PRIVS), missing(required_privileges(entries))
    return {"checked": True, "preview": {"ok": not pm, "missing": pm}, "execute": {"ok": not em, "missing": em}}


# ── Facts ───────────────────────────────────────────────────────────────────────

def _mapping_nodes(entries) -> dict:
    """/cluster/mapping/{pci,usb} -> {id: {node, ...}, live: bool}."""
    out = {}
    for m in entries or []:
        nodes = set()
        for line in m.get("map") or []:
            hit = re.search(r"(?:^|,)node=([^,]+)", str(line))
            if hit:
                nodes.add(hit.group(1))
        out[m.get("id")] = {"nodes": nodes, "live": bool(m.get("live-migration-capable"))}
    return out


def _ha_node_status(pve) -> dict:
    ms = _safe(lambda: pve.cluster.ha.status.manager_status.get(), {}) or {}
    return (ms.get("manager_status") or {}).get("node_status") or {}


def gather_guest(pve, node: str, res: dict) -> dict:
    """One guest's facts. `res` is its /cluster/resources entry."""
    vmtype = "lxc" if res.get("type") == "lxc" else "qemu"
    vmid = int(res["vmid"])
    api = _guest_api(pve, node, vmtype, vmid)
    g = {
        "vmtype": vmtype, "vmid": vmid, "sid": hf.sid(vmtype, vmid), "name": res.get("name") or "",
        "status": res.get("status") or "unknown", "running": res.get("status") == "running",
        "maxmem": int(res.get("maxmem") or 0), "maxcpu": int(res.get("maxcpu") or 0),
        "template": bool(res.get("template")), "hastate": res.get("hastate"),
        "config": None, "config_error": None, "precondition": None, "precondition_error": None,
    }
    g["config"], g["config_error"] = _try(lambda: api.config.get())
    if vmtype == "qemu" and g["config"] is not None:
        # Proxmox's own migration check (local resources, mapped devices per node). It needs
        # VM.Migrate, so a read-only token gets 403 here and the preview falls back to the config.
        g["precondition"], g["precondition_error"] = _try(lambda: api.migrate.get())
    return g


def gather_facts(pve, node: str, only_vmid: int = None) -> dict:
    """Everything build_preview() needs. GET calls only."""
    cluster = hf.gather_cluster(pve)
    resources = [r for r in pve.cluster.resources.get(type="vm")]
    located = {hf.sid("lxc" if r.get("type") == "lxc" else "qemu", int(r["vmid"])): r.get("node")
               for r in resources}
    on_node = sorted((r for r in resources if r.get("node") == node), key=lambda r: int(r["vmid"]))
    if only_vmid is not None:
        on_node = [r for r in on_node if int(r["vmid"]) == int(only_vmid)]
    source_online = cluster["nodes"].get(node, {}).get("online", False)
    guests = []
    for r in on_node:
        if not source_online or r.get("status") == "unknown":
            vmtype = "lxc" if r.get("type") == "lxc" else "qemu"
            guests.append({"vmtype": vmtype, "vmid": int(r["vmid"]), "sid": hf.sid(vmtype, int(r["vmid"])),
                           "name": r.get("name") or "", "status": "unknown", "running": False,
                           "maxmem": int(r.get("maxmem") or 0), "maxcpu": int(r.get("maxcpu") or 0),
                           "template": bool(r.get("template")), "hastate": r.get("hastate"),
                           "config": None, "config_error": "the node or guest is not reporting status",
                           "precondition": None, "precondition_error": None})
            continue
        guests.append(gather_guest(pve, node, r))
    return {
        "node": node,
        "cluster": cluster,
        "guests": guests,
        "located": located,
        "ha_node_status": _ha_node_status(pve),
        "mappings": {"pci": _mapping_nodes(_safe(lambda: pve.cluster.mapping.pci.get(), [])),
                     "usb": _mapping_nodes(_safe(lambda: pve.cluster.mapping.usb.get(), []))},
        "permissions": _safe(lambda: pve.access.permissions.get(), None),
        "gathered_at": _now(),
    }


# ── Guest analysis (target independent) ─────────────────────────────────────────

def _parse_affinity(nodes_text: str) -> dict:
    """'pve1:2,pve2:1' -> {'pve1': 2, 'pve2': 1}; a node without a priority gets 0."""
    out = {}
    for part in str(nodes_text or "").split(","):
        part = part.strip()
        if not part:
            continue
        name, _, prio = part.partition(":")
        try:
            out[name] = int(prio) if prio else 0
        except ValueError:
            out[name] = 0
    return out


def _ha_info(g, facts):
    """HA resource, node preference and resource-affinity rules for one guest."""
    c = facts["cluster"]
    res = next((r for r in c["ha_resources"] if r.get("sid") == g["sid"]), None)
    if not res and not g.get("hastate"):
        return None
    res = res or {"sid": g["sid"], "state": g.get("hastate")}
    info = {"resource": res, "state": res.get("state"), "prefer": {}, "strict": False, "failback": True,
            "rule": None, "negative": [], "positive": []}
    if str(res.get("state")) in ("ignored", "disabled"):
        info["unmanaged"] = True
    for rule in c.get("ha_rules") or []:
        members = [s for s in str(rule.get("resources", "")).split(",") if s]
        if g["sid"] not in members or rule.get("disable"):
            continue
        if rule.get("type") == "node-affinity":
            info["prefer"] = _parse_affinity(rule.get("nodes"))
            info["strict"] = bool(int(rule.get("strict") or 0))
            info["rule"] = rule.get("rule")
        elif rule.get("type") == "resource-affinity":
            others = [s for s in members if s != g["sid"]]
            (info["negative"] if rule.get("affinity") == "negative" else info["positive"]).append(
                {"rule": rule.get("rule"), "members": others})
    if "failback" in res:
        info["failback"] = bool(int(res.get("failback") or 0))
    group = res.get("group")
    if group and not info["rule"]:   # Proxmox VE 8: HA groups
        grp = next((x for x in c.get("ha_groups") or [] if x.get("group") == group), None)
        if grp:
            info["prefer"] = _parse_affinity(grp.get("nodes"))
            info["strict"] = bool(int(grp.get("restricted") or 0))
            info["failback"] = not bool(int(grp.get("nofailback") or 0))
            info["rule"] = f"group {group}"
    return info


def _devices(g):
    """Node-bound and mapped devices from the config."""
    raw, mapped, binds = [], [], []
    for key, value in (g["config"] or {}).items():
        if not isinstance(value, str):
            continue
        if g["vmtype"] == "qemu" and re.match(r"^hostpci\d+$", key):
            m = re.search(r"(?:^|,)mapping=([^,]+)", value)
            if m:
                mapped.append({"key": key, "kind": "pci", "id": m.group(1)})
            else:
                raw.append(f"{key} passes through PCI device {value.split(',')[0]}")
        elif g["vmtype"] == "qemu" and re.match(r"^usb\d+$", key):
            m = re.search(r"(?:^|,)mapping=([^,]+)", value)
            if m:
                mapped.append({"key": key, "kind": "usb", "id": m.group(1)})
            elif re.search(r"(?:^|,)host=", value):
                raw.append(f"{key} passes through a USB device plugged into this node")
        elif g["vmtype"] == "lxc" and re.match(r"^dev\d+$", key):
            raw.append(f"{key} passes through device {value.split(',')[0]}")
        elif g["vmtype"] == "lxc" and re.match(r"^mp\d+$", key) and value.split(",")[0].startswith("/"):
            path = value.split(",")[0]
            if re.search(r"(?:^|,)shared=1", value):
                binds.append(path)
            else:
                raw.append(f"{key} is a bind mount of {path} from this node")
    return raw, mapped, binds


def analyze_guest(g: dict, facts: dict) -> dict:
    """Everything about a guest that does not depend on the target node."""
    node = facts["node"]
    here = facts["cluster"]["nodes"].get(node, {}).get("storages", {})
    a = {"blockers": [], "warnings": [], "unknown": None, "method": None, "ha": None,
         "disks": [], "isos": [], "mappings": [], "mem": 0, "cpu": g.get("maxcpu") or 0,
         "replication_targets": [], "content": "rootdir" if g["vmtype"] == "lxc" else "images"}
    if g["config"] is None:
        a["unknown"] = f"Could not read the configuration: {g.get('config_error') or 'unknown error'}"
        return a
    cfg = g["config"]
    if cfg.get("lock"):
        a["blockers"].append(f"Locked ({cfg['lock']}): another operation (backup, migration, snapshot) is running "
                             "on this guest. Wait for it to finish and preview again.")
    vols = hf.guest_volumes(g["vmtype"], cfg)
    raw, mapped, binds = _devices(g)
    for item in raw:
        a["blockers"].append(f"{item}: it only exists on {node}, so the guest cannot run anywhere else.")
    for item in vols["passthrough"]:
        if " uses /" in item:     # a QEMU disk on a raw device path
            a["blockers"].append(f"{item}: a host device path that only exists on {node}.")
    for path in binds:
        a["warnings"].append(f"Bind mount {path} is marked shared; it must exist on the target too.")
    a["mappings"] = mapped
    for iso in vols["isos"]:
        st = here.get(iso["storage"], {})
        if st.get("shared"):
            a["isos"].append(iso)
        else:
            a["blockers"].append(f"{iso['key']} has {iso['volume']} attached, on storage only {node} has. "
                                 "Eject it (Hardware → CD/DVD → Do not use any media) and preview again.")
    snippet_stores = set(re.findall(r"=([^:,=]+):snippets/", str(cfg.get("cicustom", ""))))
    if any(not here.get(s, {}).get("shared") for s in snippet_stores):
        a["warnings"].append("cicustom points at a cloud-init snippet on node-local storage; copy the snippet "
                             "to the target before the guest's next reboot, or cloud-init cannot regenerate it.")
    if g["vmtype"] == "qemu" and str(cfg.get("cpu", "")).split(",")[0] == "host":
        a["warnings"].append("CPU type 'host': a live migration can fail if the target's CPU differs.")

    rep = [j for j in facts["cluster"]["replication"] if str(j.get("guest")) == str(g["vmid"])]
    a["replication_targets"] = [j.get("target") for j in rep]
    cloudinit = [dict(c, size=4 << 20, cloudinit=True) for c in vols.get("cloudinit", [])]
    for d in vols["disks"] + cloudinit + [dict(u, size=0) for u in vols["unused"]]:
        st = here.get(d["storage"], {})
        kind = "shared" if st.get("shared") else "local"
        a["disks"].append({**d, "kind": kind, "storage_type": st.get("type", "unknown")})
        if d["key"].startswith("unused") and kind == "local":
            a["warnings"].append(f"{d['key']} ({d['volume']}) is an unused disk on local storage; "
                                 "Proxmox copies it too (its size is not counted).")

    pre = g.get("precondition")
    if pre:
        for item in pre.get("local_resources") or []:
            if not any(item.startswith(m["key"]) for m in mapped) and not any(item in b for b in a["blockers"]):
                a["blockers"].append(f"Proxmox reports local resource {item}, which cannot move.")
    elif g["vmtype"] == "qemu" and g.get("precondition_error"):
        a["warnings"].append("Proxmox's own migration check was not available "
                             f"({g['precondition_error']}); the preview uses the configuration only.")

    a["ha"] = _ha_info(g, facts)
    if g["template"]:
        a["method"] = "offline"
        clones = [x["sid"] for x in facts["guests"] if x is not g and x.get("config")
                  and any(f"base-{g['vmid']}-" in str(v) for v in x["config"].values())]
        if clones and any(d["kind"] == "local" for d in a["disks"]):
            a["blockers"].append(f"Linked clones ({', '.join(clones)}) use this template's disks on local storage; "
                                 "it can only move with them, so move or full-clone them first.")
    elif not g["running"]:
        a["method"] = "offline"
    elif g["vmtype"] == "lxc":
        a["method"] = "restart"
    elif mapped and not all(facts["mappings"][m["kind"]].get(m["id"], {}).get("live") for m in mapped):
        a["method"] = "cold"
    else:
        a["method"] = "live"
    a["mem"] = g["maxmem"] if (g["running"] and not g["template"]) else 0

    ha = a["ha"]
    if ha and not ha.get("unmanaged") and a["method"] == "cold":
        a["blockers"].append("HA manages this VM and it needs a shutdown to move (mapped devices). "
                             "Stop it through HA or take it out of HA first; Depl0y does not cold-move HA guests.")
    if ha:
        # Proxmox sends every guest listed as an HA resource (even 'ignored'/'disabled') through
        # ha-manager, which neither copies local disks nor maps storages.
        for d in a["disks"]:
            if d["kind"] != "local" or d.get("cloudinit"):
                continue
            if d["storage_type"] != "zfspool":
                a["blockers"].append(f"{d['key']} is on node-local {d['storage']} and this guest is an HA resource; "
                                     "HA migrations do not copy local disks. Move it to shared storage first.")
            elif not a["replication_targets"]:
                a["blockers"].append(f"{d['key']} is on local ZFS {d['storage']} with no replication job, and this "
                                     "guest is an HA resource; HA migrations do not copy local disks. Set up "
                                     "replication (failover wizard) or move it to shared storage first.")
    return a


# ── Placement ───────────────────────────────────────────────────────────────────

def _reserve_bytes(info):
    return int(info.get("maxmem", 0) * MEM_RESERVE_FRACTION)


def _mem_left(t, facts, res):
    info = facts["cluster"]["nodes"][t]
    return info.get("mem_free", 0) - _reserve_bytes(info) - res["mem"].get(t, 0)


def _storage_left(t, storage, facts, res):
    st = facts["cluster"]["nodes"][t].get("storages", {}).get(storage, {})
    return int(st.get("avail", 0)) - res["disk"].get((t, storage), 0)


def _storage_plan(g, a, t, facts, res):
    """Map the guest's storages for target t. Returns (storage_map, copy_bytes_by_dest, problems)."""
    tnode = facts["cluster"]["nodes"][t]
    problems, smap, copy = [], {}, {}
    content = a["content"]
    by_src = {}
    for d in a["disks"]:
        if d["kind"] == "shared":
            if not hf._usable(tnode, d["storage"], content):
                problems.append(f"shared storage {d['storage']} is not available on {t}")
            continue
        by_src.setdefault(d["storage"], []).append(d)
    replicated_to_t = t in a["replication_targets"]
    for src, disks in by_src.items():
        need = 0 if (replicated_to_t and disks[0]["storage_type"] == "zfspool") else sum(x["size"] for x in disks)
        if a["replication_targets"]:
            # Replicated guests may only go to a replication target, on the same storage.
            if not replicated_to_t:
                problems.append(f"it replicates to {', '.join(a['replication_targets'])}; Proxmox only migrates "
                                "a replicated guest to its replication target")
                continue
            if not hf._usable(tnode, src, content):
                problems.append(f"{src} is not available on {t}")
                continue
            smap[src] = src
            continue
        candidates = []
        if hf._usable(tnode, src, content):
            candidates.append(src)          # the same storage ID first: no mapping needed
        if not a["ha"]:
            # Otherwise a local storage on t: the same type first, the HA-ZFS wizard's pool (kept for HA
            # replicas) last, then the most room.
            src_type = disks[0]["storage_type"]
            tst = tnode.get("storages", {})
            candidates += sorted(
                (s for s, st in tst.items() if s != src and not st.get("shared") and hf._usable(tnode, s, content)),
                key=lambda s: (s == HAZFS_STORAGE, tst[s].get("type") != src_type, -_storage_left(t, s, facts, res), s))
        fits = [s for s in candidates if _storage_left(t, s, facts, res) - copy.get(s, 0) >= need]
        if not candidates:
            problems.append(f"no storage on {t} accepts {'container volumes' if content == 'rootdir' else 'VM disks'}"
                            f" for the disks on {src}")
        elif not fits:
            best = candidates[0]
            problems.append(f"capacity: {', '.join(candidates)} on {t} lack room for {_gib(need)} from {src} "
                            f"({_gib(max(0, _storage_left(t, best, facts, res)))} left on {best} after earlier moves)")
        else:
            smap[src] = fits[0]
            copy[fits[0]] = copy.get(fits[0], 0) + need
    for iso in a["isos"]:
        if not hf._usable(tnode, iso["storage"], "iso"):
            problems.append(f"ISO storage {iso['storage']} is not available on {t}")
    return smap, copy, problems


def _target_problems(g, a, t, facts, res, planned):
    """Why target t cannot take the guest (empty list = it can). Capacity problems start with 'capacity'."""
    node = facts["node"]
    info = facts["cluster"]["nodes"].get(t, {})
    p = []
    if not info.get("online"):
        return [f"{t} is offline"], {}, {}
    if facts["ha_node_status"].get(t) == "maintenance":
        return [f"{t} is in HA maintenance mode"], {}, {}
    ha = a["ha"] if a["ha"] and not a["ha"].get("unmanaged") else None
    if ha:
        if not info.get("lrm"):
            p.append(f"HA (pve-ha-lrm) is not running on {t}")
        if ha["strict"] and ha["prefer"] and t not in ha["prefer"]:
            p.append(f"HA {ha['rule']} only allows {', '.join(sorted(ha['prefer']))}")
        src_prio = ha["prefer"].get(node)
        if (ha["prefer"] and ha["failback"] and src_prio is not None and src_prio > ha["prefer"].get(t, -1)
                and facts["ha_node_status"].get(node) != "maintenance"):
            p.append(f"HA {ha['rule']} prefers {node} (priority {src_prio}) and failback is on, so HA would move "
                     f"the guest straight back; put {node} into HA maintenance mode "
                     f"(ha-manager crm-command node-maintenance enable {node}) or change the rule")
        for rule in ha["negative"]:
            clash = [s for s in rule["members"] if facts["located"].get(s) == t or planned.get(s) == t]
            if clash:
                p.append(f"HA rule {rule['rule']} keeps it apart from {', '.join(clash)}, which is on {t}")
        for rule in ha["positive"]:
            for s in rule["members"]:
                where = planned.get(s) or (facts["located"].get(s) if facts["located"].get(s) != node else None)
                if where and where != t:
                    p.append(f"HA rule {rule['rule']} keeps it with {s}, which is (or will be) on {where}")
    if a["cpu"] and info.get("maxcpu") and a["cpu"] > info["maxcpu"]:
        p.append(f"it has {a['cpu']} vCPUs; {t} has {info['maxcpu']} CPUs")
    for m in a["mappings"]:
        if t not in facts["mappings"][m["kind"]].get(m["id"], {}).get("nodes", set()):
            p.append(f"mapped {m['kind'].upper()} device {m['id']} has no device on {t}")
    pre = g.get("precondition") or {}
    bad = (pre.get("not_allowed_nodes") or {}).get(t) or {}
    unavailable = bad.get("unavailable-resources") or bad.get("unavailable_resources")
    if unavailable:
        p.append(f"Proxmox reports {', '.join(map(str, unavailable))} unavailable on {t}")
    smap, copy, sp = _storage_plan(g, a, t, facts, res)
    p += sp
    if a["mem"]:
        left = _mem_left(t, facts, res)
        if left < a["mem"]:
            p.append(f"capacity: needs {_gib(a['mem'])} RAM; {t} has {_gib(max(0, left))} left "
                     f"(after earlier moves and a {int(MEM_RESERVE_FRACTION * 100)}% reserve)")
    return p, smap, copy


_METHOD_TEXT = {
    "live": "Live migration",
    "offline": "Offline migration (the guest is stopped)",
    "restart": "Restart migration: the container stops, moves and starts again",
    "cold": "Cold move: shut down, migrate, start on the target",
}


def place_guest(g, a, facts, res, planned, only_target=None):
    """Pick a target for one analysed guest and reserve its RAM and disk there."""
    node = facts["node"]
    entry = {
        "sid": g["sid"], "vmid": g["vmid"], "vmtype": g["vmtype"], "name": g["name"], "status": g["status"],
        "running": g["running"], "template": g["template"], "maxmem": g["maxmem"], "mem_needed": a.get("mem", 0),
        "ha": bool(a.get("ha")),
        "method": a.get("method"), "target": None, "storage_map": {}, "copy_bytes": 0, "mappings": a.get("mappings", []),
        "digest": (g.get("config") or {}).get("digest"), "class": None, "reason": "",
        "warnings": list(a.get("warnings", [])), "blockers": list(a.get("blockers", [])), "targets": {},
    }
    if a.get("unknown"):
        entry.update({"class": "unknown", "reason": a["unknown"]})
        return entry
    if entry["blockers"]:
        entry.update({"class": "blocked", "reason": entry["blockers"][0]})
        return entry
    names = [only_target] if only_target else sorted(n for n in facts["cluster"]["nodes"] if n != node)
    feasible, capacity_only = [], []
    for t in names:
        if t not in facts["cluster"]["nodes"]:
            entry["targets"][t] = [f"{t} is no longer in the cluster"]
            continue
        problems, smap, copy = _target_problems(g, a, t, facts, res, planned)
        entry["targets"][t] = problems
        if not problems:
            feasible.append((t, smap, copy))
        elif all(x.startswith("capacity") for x in problems):
            capacity_only.append(t)
    if not feasible:
        if capacity_only:
            entry["class"] = "blocked"
            entry["capacity"] = True
            entry["reason"] = ("Not enough capacity left once the earlier moves are counted: "
                               + "; ".join(f"{t}: {entry['targets'][t][0][len('capacity: '):]}" for t in capacity_only))
        else:
            entry["class"] = "blocked"
            entry["reason"] = "No node can take it: " + "; ".join(
                f"{t}: {', '.join(v)}" for t, v in entry["targets"].items()) if entry["targets"] else \
                "There is no other node in the cluster."
        return entry
    # Most RAM left after the move wins; a stopped guest goes where the most RAM is left too, so a later
    # start has room.
    feasible.sort(key=lambda x: (-(_mem_left(x[0], facts, res) - a["mem"]), x[0]))
    t, smap, copy = feasible[0]
    res["mem"][t] = res["mem"].get(t, 0) + a["mem"]
    for s, b in copy.items():
        res["disk"][(t, s)] = res["disk"].get((t, s), 0) + b
    planned[g["sid"]] = t
    entry["target"] = t
    entry["storage_map"] = smap
    entry["copy_bytes"] = sum(copy.values())
    entry["class"] = "downtime" if a["method"] in ("restart", "cold") else "online"
    parts = [f"{_METHOD_TEXT[a['method']]} to {t}"]
    if entry["copy_bytes"]:
        moves = ", ".join(f"{s} → {d}" if s != d else s for s, d in smap.items())
        parts.append(f"copies {_gib(entry['copy_bytes'])} of local disk ({moves})")
    elif smap:
        parts.append("disks already replicated there")
    elif any(d["kind"] == "shared" for d in a["disks"]):
        parts.append("disks on shared storage")
    if a["mem"]:
        parts.append(f"{t} keeps {_gib(_mem_left(t, facts, res))} RAM free after it")
    if entry["ha"]:
        parts.append("requested through HA")
    entry["reason"] = "; ".join(parts) + "."
    return entry


def _cluster_checks(facts):
    c, node = facts["cluster"], facts["node"]
    checks = []

    def add(status, title, detail=""):
        checks.append({"status": status, "title": title, "detail": detail})

    if not c["clustered"]:
        add("fail", "Not a cluster", "A standalone node has nowhere to move its guests.")
    if not c["nodes"].get(node, {}).get("online"):
        add("fail", f"{node} is offline", "An offline node cannot be evacuated; HA recovers HA guests by itself.")
    if c["quorate"]:
        add("ok", "Cluster is quorate")
    else:
        add("fail", "Cluster is not quorate", "Proxmox refuses migrations without quorum.")
    votes = len(c["nodes"]) + (1 if c["qdevice"] else 0)
    online_after = sum(1 for n, i in c["nodes"].items() if i.get("online") and n != node) + (1 if c["qdevice"] else 0)
    needed = votes // 2 + 1
    if c["clustered"]:
        if online_after < needed:
            add("warn", f"Taking {node} down loses quorum",
                f"{online_after} of {votes} votes would remain; quorum needs {needed}. Evacuating is safe, but do "
                f"not shut down or reboot {node} until another node is back.")
        else:
            add("ok", "Quorum holds without this node", f"{online_after} of {votes} votes remain; {needed} needed.")
    others = [n for n, i in c["nodes"].items() if n != node and i.get("online")]
    if c["clustered"] and not others:
        add("fail", "No other node is online")
    if facts["ha_node_status"].get(node) == "maintenance":
        add("info", f"{node} is in HA maintenance mode", "HA is already moving HA guests off this node.")
    for n, st in facts["ha_node_status"].items():
        if n != node and st == "maintenance":
            add("info", f"{n} is in HA maintenance mode", "It is not used as a target.")
    return checks


def build_preview(facts: dict) -> dict:
    """Pure: a plan entry for every guest on the node, with capacity after all proposed moves."""
    node = facts["node"]
    checks = _cluster_checks(facts)
    analysed = [(g, analyze_guest(g, facts)) for g in facts["guests"]]
    # Biggest memory first, stable by vmid. Positive-affinity partners follow whoever is placed first.
    order = sorted(analysed, key=lambda x: (-(x[1].get("mem") or 0), x[0]["vmid"]))
    res, planned = {"mem": {}, "disk": {}}, {}
    entries = {}
    cluster_blocked = any(c["status"] == "fail" for c in checks)
    for g, a in order:
        if cluster_blocked and not a.get("unknown"):
            a = {**a, "blockers": a["blockers"] + ["The cluster cannot evacuate right now (see the cluster checks)."]}
        entries[g["sid"]] = place_guest(g, a, facts, res, planned)
    ordered = [entries[g["sid"]] for g in facts["guests"]]
    summary = {k: sum(1 for e in ordered if e["class"] == k) for k in CLASSES}
    nodes = facts["cluster"]["nodes"]
    targets = {}
    for t, info in sorted(nodes.items()):
        if t == node or not info.get("online"):
            continue
        targets[t] = {
            "mem_free": info.get("mem_free", 0), "mem_reserve": _reserve_bytes(info),
            "mem_planned": res["mem"].get(t, 0), "mem_left": _mem_left(t, facts, res),
            "guests": [e["sid"] for e in ordered if e["target"] == t],
            "storage": {s: {"avail": int(info["storages"].get(s, {}).get("avail", 0)), "planned": b}
                        for (n2, s), b in res["disk"].items() if n2 == t},
        }
    need_mem = sum(e["mem_needed"] for e in ordered)
    have_mem = sum(max(0, info.get("mem_free", 0) - _reserve_bytes(info))
                   for n, info in nodes.items() if n != node and info.get("online"))
    summary.update({
        "guests": len(ordered), "running_mem": need_mem, "target_mem_available": have_mem,
        "aggregate_ok": need_mem <= have_mem,
        "capacity_blocked": sum(1 for e in ordered if e.get("capacity")),
        "empty_after": all(e["class"] in ("online", "downtime") for e in ordered),
    })
    if not summary["aggregate_ok"]:
        checks.append({"status": "fail", "title": "Not enough RAM on the other nodes",
                       "detail": f"Running guests need {_gib(need_mem)}; the other online nodes have {_gib(have_mem)} "
                                 f"free after the {int(MEM_RESERVE_FRACTION * 100)}% reserve."})
    elif summary["capacity_blocked"]:
        checks.append({"status": "warn", "title": "Some guests do not fit",
                       "detail": "Enough RAM in total, but not on any single node once the other moves are placed."})
    perms = check_permissions(facts.get("permissions"),
                              [e for e in ordered if e["class"] in ("online", "downtime")])
    if perms["checked"] and not perms["preview"]["ok"]:
        checks.append({"status": "warn", "title": "The Proxmox token cannot read everything",
                       "detail": ", ".join(f"{m['privilege']} on {m['path']}" for m in perms["preview"]["missing"])})
    if perms["checked"] and not perms["execute"]["ok"]:
        checks.append({"status": "warn", "title": "The Proxmox token cannot carry out this plan",
                       "detail": "Missing: " + ", ".join(sorted({f"{m['privilege']} on {m['path']}"
                                                                for m in perms["execute"]["missing"]}))})
    return {"node": node, "checks": checks, "guests": ordered, "summary": summary, "targets": targets,
            "permissions": perms, "executable": not cluster_blocked,
            "power_note": f"Evacuation never shuts down, reboots or powers off {node}. Do that separately, "
                          "after the job has finished and the node is empty."}


# ── Plans and jobs (in memory) ──────────────────────────────────────────────────

_plans: dict = {}
_jobs: dict = {}
_active: dict = {}          # host_id -> job_id while an evacuation runs
_lock = threading.Lock()


def store_plan(host_id: int, preview: dict, user_id) -> dict:
    now = _now()
    with _lock:
        for pid in [p for p, v in _plans.items() if now - v["created"] > PLAN_TTL]:
            del _plans[pid]
        plan_id = uuid.uuid4().hex
        _plans[plan_id] = {"id": plan_id, "host_id": host_id, "node": preview["node"], "user_id": user_id,
                           "created": now, "preview": preview}
    return {**preview, "plan_id": plan_id, "expires_in": PLAN_TTL}


def get_plan(plan_id: str):
    with _lock:
        p = _plans.get(plan_id)
        if p and _now() - p["created"] > PLAN_TTL:
            del _plans[plan_id]
            return None
        return p


class Job:
    def __init__(self, host_id, node, plan_id, user_id, entries):
        self.id = uuid.uuid4().hex
        self.host_id, self.node, self.plan_id, self.user_id = host_id, node, plan_id, user_id
        self.created = _now()
        self.status = "running"
        self.error = None
        self.steps = []
        self.order = [e["sid"] for e in entries]
        self.results = {e["sid"]: {"sid": e["sid"], "vmid": e["vmid"], "name": e["name"], "target": e["target"],
                                   "method": e["method"], "status": "pending", "detail": "", "upid": None,
                                   "location": None} for e in entries}
        self.remaining = None
        self.cancel = threading.Event()
        self._lk = threading.Lock()

    def log(self, text):
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        with self._lk:
            self.steps.append({"time": stamp, "text": text})
        logger.info("evacuation %s (%s): %s", self.id[:8], self.node, text)

    def set(self, sid, **kw):
        with self._lk:
            self.results[sid].update(kw)

    def snapshot(self):
        with self._lk:
            counts = {}
            for r in self.results.values():
                counts[r["status"]] = counts.get(r["status"], 0) + 1
            return {"id": self.id, "host_id": self.host_id, "node": self.node, "plan_id": self.plan_id,
                    "status": self.status, "error": self.error, "created": self.created,
                    "steps": list(self.steps), "guests": [dict(self.results[s]) for s in self.order],
                    "counts": counts, "remaining_on_node": self.remaining,
                    "cancel_requested": self.cancel.is_set()}


def start_job(host_id, node, plan_id, user_id, entries, pve, target=None) -> Job:
    """Register and start an evacuation; raises RuntimeError if one already runs on this host."""
    now = _now()
    with _lock:
        for jid in [j for j, v in _jobs.items() if v.status != "running" and now - v.created > JOB_TTL]:
            del _jobs[jid]
        if host_id in _active and _jobs.get(_active[host_id]) and _jobs[_active[host_id]].status == "running":
            raise RuntimeError(f"evacuation {_active[host_id]} is still running on this cluster")
        job = Job(host_id, node, plan_id, user_id, entries)
        _jobs[job.id] = job
        _active[host_id] = job.id

    def run():
        try:
            (target or run_evacuation)(pve, job, entries)
        except Exception as exc:  # noqa: BLE001 - keep the job record truthful
            logger.exception("evacuation %s crashed", job.id)
            job.error = str(exc)
            job.status = "failed"
        finally:
            with _lock:
                if _active.get(host_id) == job.id:
                    del _active[host_id]

    threading.Thread(target=run, daemon=True, name=f"evacuate-{job.id[:8]}").start()
    return job


def get_job(job_id):
    with _lock:
        return _jobs.get(job_id)


def list_jobs(host_id):
    with _lock:
        jobs = list(_jobs.values())
    return sorted((j for j in jobs if j.host_id == host_id), key=lambda j: -j.created)


# ── Execution ───────────────────────────────────────────────────────────────────

def _upid_node(upid, default):
    m = re.match(r"^UPID:([^:]+):", str(upid or ""))
    return m.group(1) if m else default


def wait_task(pve, upid, node, timeout, vmid=None):
    """Follow a Proxmox task to its end. Returns (ok, exitstatus or error, log tail).

    If the task's node stops answering, keep waiting while the guest still carries a lock
    (the migration is still going); give up only when it is unlocked or the deadline passes.
    """
    tnode = _upid_node(upid, node)
    deadline = _now() + timeout
    misses = 0
    while _now() < deadline:
        try:
            st = pve.nodes(tnode).tasks(upid).status.get()
            misses = 0
        except Exception as exc:  # noqa: BLE001 - a node can drop out for a moment
            misses += 1
            if misses >= 10:
                cur = _safe(lambda: locate(pve, vmid), None) if vmid is not None else None
                if not (cur and cur.get("lock")):
                    return False, f"lost track of the task: {exc}", []
            _sleep(POLL_INTERVAL)
            continue
        if st.get("status") == "stopped":
            exit_status = st.get("exitstatus") or "unknown"
            if exit_status == "OK" or exit_status.startswith("WARNINGS"):
                return True, exit_status, []
            lines = _safe(lambda: pve.nodes(tnode).tasks(upid).log.get(limit=5000), []) or []
            tail = [str(x.get("t", "")) for x in lines[-6:]]
            return False, exit_status, tail
        _sleep(POLL_INTERVAL)
    return False, f"still running after {timeout // 60} minutes", []


def locate(pve, vmid):
    """The guest's current /cluster/resources entry, or None."""
    for r in pve.cluster.resources.get(type="vm"):
        if int(r.get("vmid", -1)) == int(vmid):
            return r
    return None


def _ha_service(pve, sid):
    for item in _safe(lambda: pve.cluster.ha.status.current.get(), []) or []:
        if item.get("type") == "service" and item.get("sid") == sid:
            return item
    return None


def verify_location(pve, entry, expect_running, ha, timeout):
    """Wait until the guest is on its target in the expected state. Returns (ok, detail, resource)."""
    deadline = _now() + timeout
    started = _now()
    last = None
    while True:
        last = _safe(lambda: locate(pve, entry["vmid"]), last)
        if last and last.get("node") == entry["target"] and not last.get("lock") and (
                not expect_running or last.get("status") == "running"):
            return True, f"on {entry['target']} ({last.get('status')})", last
        if ha:
            svc = _ha_service(pve, entry["sid"])
            state = (svc or {}).get("state")
            if state == "error":
                return False, f"HA put {entry['sid']} into the error state", last
            settled = state not in ("migrate", "relocate", "request_start", "starting")
            if (last and last.get("node") == entry["target"] and expect_running and settled
                    and last.get("status") != "running" and _now() - started > HA_PICKUP_GRACE):
                return False, f"HA moved it to {entry['target']} but it is {last.get('status')} (state {state})", last
            if last and last.get("node") not in (None, entry["target"]) and state not in (
                    "migrate", "relocate", "request_start", "starting") and _now() - started > HA_PICKUP_GRACE:
                if last.get("node") != entry.get("source"):
                    return True, f"HA placed it on {last.get('node')} instead of {entry['target']}", last
                return False, f"HA left it on {last.get('node')} (state {state or 'unknown'})", last
        if _now() >= deadline:
            where = f"{last.get('node')} ({last.get('status')})" if last else "not found"
            return False, f"not on {entry['target']} as expected within {timeout // 60 or 1} min; now {where}", last
        _sleep(POLL_INTERVAL)


def _migrate_params(entry, live):
    p = {"target": entry["target"]}
    mapped = {s: d for s, d in (entry.get("storage_map") or {}).items() if s != d}
    if entry["vmtype"] == "qemu":
        if live:
            p["online"] = 1
            if entry.get("storage_map"):
                p["with-local-disks"] = 1
        if mapped:
            p["targetstorage"] = ",".join(f"{s}:{d}" for s, d in sorted((entry.get("storage_map") or {}).items()))
    else:
        if entry["method"] == "restart":
            p["restart"] = 1
            p["timeout"] = CT_RESTART_TIMEOUT
        if mapped:
            p["target-storage"] = ",".join(f"{s}:{d}" for s, d in sorted((entry.get("storage_map") or {}).items()))
    return p


def recheck(pve, source, entry):
    """Re-read the cluster and check the reviewed placement on its own.

    Returns ("go", fresh_entry), ("done", detail), ("elsewhere", detail) or ("skip", reason).
    """
    current = locate(pve, entry["vmid"])
    if current is None:
        return "skip", "the guest no longer exists"
    if current.get("node") == entry["target"]:
        want_running = entry["running"]
        if not want_running or current.get("status") == "running":
            return "done", f"already on {entry['target']} ({current.get('status')})"
        return "skip", f"already on {entry['target']} but {current.get('status')}; start it there"
    if current.get("node") != source:
        return "elsewhere", (f"already off {source}: now on {current.get('node')} ({current.get('status')}), "
                             f"not the planned {entry['target']}" + (" — HA placed it" if entry.get("ha") else ""))
    facts = gather_facts(pve, source, only_vmid=entry["vmid"])
    for c in _cluster_checks(facts):
        if c["status"] == "fail":
            return "skip", f"cluster check failed: {c['title']}"
    g = next((x for x in facts["guests"] if x["sid"] == entry["sid"]), None)
    if g is None:
        return "skip", f"the guest is no longer on {source}"
    if (g.get("config") or {}).get("digest") != entry.get("digest"):
        return "skip", "the configuration changed since the plan was reviewed; preview again"
    a = analyze_guest(g, facts)
    fresh = place_guest(g, a, facts, {"mem": {}, "disk": {}}, {}, only_target=entry["target"])
    if fresh["class"] not in ("online", "downtime"):
        return "skip", f"{entry['target']} can no longer take it: {fresh['reason']}"
    if fresh["method"] != entry["method"]:
        return "skip", (f"it now needs a {fresh['method']} move instead of the reviewed {entry['method']} move "
                        f"(was it started or stopped?); preview again")
    if fresh["storage_map"] != entry["storage_map"]:
        return "skip", "the destination storage would differ from the reviewed plan; preview again"
    return "go", fresh


def _move(pve, job, source, e):
    """Carry out one reviewed entry after recheck. Returns the final result status."""
    sid = e["sid"]
    api = _guest_api(pve, source, e["vmtype"], e["vmid"])
    if e["method"] == "cold":
        job.set(sid, status="stopping", detail=f"shutting down on {source}")
        job.log(f"{sid}: shutting down for a cold move")
        ok, why, tail = wait_task(pve, api.status.shutdown.post(timeout=SHUTDOWN_TIMEOUT), source, SHUTDOWN_TIMEOUT + 60)
        cur = _safe(lambda: locate(pve, e["vmid"]), None)
        if not ok or (cur and cur.get("status") != "stopped"):
            job.set(sid, status="failed", detail=f"shutdown did not finish ({why}); the guest was not moved and "
                                                 f"is {cur.get('status') if cur else 'unknown'} on {source}",
                    location=source)
            return "failed"
    live = e["method"] == "live"
    params = _migrate_params(e, live)
    job.set(sid, status="migrating", detail=f"{_METHOD_TEXT[e['method']]} to {e['target']}")
    job.log(f"{sid}: migrating to {e['target']} ({', '.join(f'{k}={v}' for k, v in params.items())})")
    try:
        upid = api.migrate.post(**params)
    except Exception as exc:  # noqa: BLE001
        job.set(sid, status="failed", detail=f"Proxmox refused the migration: {exc}", location=source)
        if e["method"] == "cold":
            _restart_after_failed_cold(pve, job, e, source)
        return "failed"
    job.set(sid, upid=upid)
    ha_task = bool(re.search(r":ha(migrate|relocate):", str(upid))) or e.get("ha")
    ok, why, tail = wait_task(pve, upid, source, MIGRATE_TIMEOUT, vmid=e["vmid"])
    if not ok:
        cur = _safe(lambda: locate(pve, e["vmid"]), None)
        where = cur.get("node") if cur else None
        detail = f"migration task ended with: {why}" + (f" — {' | '.join(t for t in tail if t)}" if tail else "")
        detail += f"; the guest is on {where} ({cur.get('status')})" if cur else "; its location is unknown"
        if e["method"] == "cold" and where != source:
            detail += " — it was shut down for this cold move; check where it is and start it by hand"
        job.set(sid, status="failed", detail=detail, location=where)
        if e["method"] == "cold" and where == source:
            _restart_after_failed_cold(pve, job, e, source)
        return "failed"
    if e["method"] == "cold":
        job.set(sid, status="starting", detail=f"starting on {e['target']}")
        tapi = _guest_api(pve, e["target"], e["vmtype"], e["vmid"])
        try:
            sok, swhy, _ = wait_task(pve, tapi.status.start.post(), e["target"], 600)
        except Exception as exc:  # noqa: BLE001
            sok, swhy = False, str(exc)
        if not sok:
            job.set(sid, status="failed", location=e["target"],
                    detail=f"moved to {e['target']} but it did not start ({swhy}); start it there by hand")
            return "failed"
    job.set(sid, status="verifying", detail=f"waiting to see it on {e['target']}")
    expect_running = e["running"] and not e["template"]
    vok, vdetail, cur = verify_location(pve, {**e, "source": source}, expect_running, ha_task,
                                        MIGRATE_TIMEOUT if ha_task else VERIFY_TIMEOUT)
    where = cur.get("node") if cur else None
    if vok and where == e["target"]:
        job.set(sid, status="moved", detail=f"verified {vdetail}", location=where)
        return "moved"
    if vok:
        job.set(sid, status="moved_elsewhere", detail=vdetail, location=where)
        return "moved_elsewhere"
    job.set(sid, status="failed", detail=f"the task ended OK but {vdetail}", location=where)
    return "failed"


def _restart_after_failed_cold(pve, job, e, source):
    """A cold move stopped the guest and could not move it: start it again where it is."""
    job.log(f"{e['sid']}: starting it again on {source} after the failed cold move")
    api = _guest_api(pve, source, e["vmtype"], e["vmid"])
    try:
        ok, why, _ = wait_task(pve, api.status.start.post(), source, 600)
    except Exception as exc:  # noqa: BLE001
        ok, why = False, str(exc)
    r = job.results[e["sid"]]
    job.set(e["sid"], detail=r["detail"] + (f"; started again on {source}" if ok
                                             else f"; could not start it again on {source} ({why}): start it by hand"))


def run_evacuation(pve, job: Job, entries: list):
    """Move each reviewed entry in order. Never picks a new target."""
    source = job.node
    job.log(f"Evacuating {len(entries)} guest(s) from {source}")
    for e in entries:
        sid = e["sid"]
        if job.cancel.is_set():
            job.set(sid, status="cancelled", detail="cancelled before it started")
            continue
        job.set(sid, status="rechecking", detail=f"checking {e['target']} again")
        try:
            verdict, info = recheck(pve, source, e)
        except Exception as exc:  # noqa: BLE001 - a recheck that cannot read the cluster must not move
            verdict, info = "skip", f"could not re-check the placement: {exc}"
        if verdict == "done":
            job.set(sid, status="already_moved", detail=info, location=e["target"])
            job.log(f"{sid}: {info}")
            continue
        if verdict == "elsewhere":
            location = _safe(lambda: locate(pve, e["vmid"]).get("node"), None)
            job.set(sid, status="moved_elsewhere", detail=info, location=location)
            job.log(f"{sid}: {info}")
            continue
        if verdict == "skip":
            job.set(sid, status="skipped", detail=info, location=source)
            job.log(f"{sid}: skipped: {info}")
            continue
        try:
            outcome = _move(pve, job, source, e)
        except Exception as exc:  # noqa: BLE001
            job.set(sid, status="failed", detail=f"unexpected error: {exc}")
            outcome = "failed"
        job.log(f"{sid}: {job.results[sid]['status']}: {job.results[sid]['detail']}")
    remaining = _safe(lambda: [f"{'ct' if r.get('type') == 'lxc' else 'vm'}:{r['vmid']}"
                               for r in pve.cluster.resources.get(type="vm") if r.get("node") == source], None)
    job.remaining = remaining
    statuses = [r["status"] for r in job.results.values()]
    good = {"moved", "already_moved", "moved_elsewhere"}
    if job.cancel.is_set() and "cancelled" in statuses:
        job.status = "cancelled"
    elif all(s in ("moved", "already_moved") for s in statuses):
        job.status = "done"
    elif all(s in good for s in statuses):
        job.status = "deviated"     # all off the node, but not all where the plan put them
    elif any(s in good for s in statuses):
        job.status = "partial"
    else:
        job.status = "failed"
    if remaining == []:
        job.log(f"{source} has no guests left. Shutting it down or rebooting it is a separate step.")
    elif remaining:
        job.log(f"Still on {source}: {', '.join(remaining)}")
    job.log(f"Finished: {job.status}")
