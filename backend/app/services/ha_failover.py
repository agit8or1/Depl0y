"""Failover planning for the HA wizard.

`gather_facts()` reads everything the decision needs from the Proxmox API. `build_plan()`
is a pure function of those facts, so the decision logic can be tested without a cluster.
`apply_plan()` carries a plan out step by step.

The wizard has no knobs: these are the settings it always uses.

- Failover only uses Proxmox's own HA manager, which keeps working when Depl0y is down.
  Proxmox detects a dead node, fences it, and starts the guest elsewhere.
- Guest disks must be reachable from the failover node:
    * shared storage (NFS, Ceph, iSCSI, ...): mode "shared", no data loss;
    * ZFS on both nodes: mode "replication", a replication job every REPLICATION_SCHEDULE,
      so at most that much is lost.
  Anything else (local LVM, directory storage) cannot fail over. The plan says so and, if
  the guest's node has a suitable storage, offers to move the disks there first.
- HA resource: state follows the guest (started if running), max_restart=1,
  max_relocate=1, failback on.
- A node-affinity rule keeps the guest on its current node (priority 2) and names one
  failover node (priority 1): the online node with the most free memory that can reach
  the guest's storage. With replication the rule is strict, because only those two nodes
  have the disks; with shared storage it is not, so Proxmox may use any node if both are down.
  Proxmox VE 8 has no HA rules; there the same placement is an HA group of the same name
  (restricted instead of strict, failback through nofailback=0).
- Cluster option `ha: shutdown_policy=migrate` (if unset), so HA guests move away when
  their node is shut down or rebooted instead of stopping.
"""
import logging
import re
import time

logger = logging.getLogger(__name__)

REPLICATION_SCHEDULE = "*/2"   # every 2 minutes: at most ~2 minutes of data lost on failover
MANAGED_COMMENT = "Managed by Depl0y failover wizard"
FIRST_SYNC_TIMEOUT = 3600      # seconds to wait for the first replication run

_QEMU_DISK = re.compile(r"^(scsi|virtio|sata|ide)\d+$|^efidisk0$|^tpmstate0$")
_LXC_DISK = re.compile(r"^rootfs$|^mp\d+$")
_UNUSED = re.compile(r"^unused\d+$")


def rule_id(vmtype: str, vmid: int) -> str:
    return f"depl0y-{'ct' if vmtype == 'lxc' else 'vm'}-{vmid}"


def sid(vmtype: str, vmid: int) -> str:
    return f"{'ct' if vmtype == 'lxc' else 'vm'}:{vmid}"


def _parse_size(text: str) -> int:
    """'32G' / '512M' / '1T' -> bytes (0 if unknown)."""
    m = re.match(r"^(\d+(?:\.\d+)?)([KMGT]?)$", text or "")
    if not m:
        return 0
    mult = {"": 1, "K": 1 << 10, "M": 1 << 20, "G": 1 << 30, "T": 1 << 40}[m.group(2)]
    return int(float(m.group(1)) * mult)


def guest_volumes(vmtype: str, config: dict) -> dict:
    """Split a guest config into disks, attached ISOs, unused volumes and blockers."""
    disks, isos, unused, passthrough = [], [], [], []
    for key, value in config.items():
        if not isinstance(value, str):
            continue
        if vmtype == "qemu" and _QEMU_DISK.match(key):
            volume = value.split(",")[0]
            if "media=cdrom" in value:
                if volume not in ("none", "cdrom") and ":" in volume:
                    isos.append({"key": key, "volume": volume, "storage": volume.split(":")[0]})
                continue
            if ":" not in volume:      # e.g. a raw /dev path
                passthrough.append(f"{key} uses {volume} directly")
                continue
            size = re.search(r"size=([0-9.]+[KMGT]?)", value)
            disks.append({"key": key, "volume": volume, "storage": volume.split(":")[0],
                          "size": _parse_size(size.group(1)) if size else 0})
        elif vmtype == "lxc" and _LXC_DISK.match(key):
            volume = value.split(",")[0]
            if volume.startswith("/"):
                passthrough.append(f"{key} is a bind mount of {volume}")
                continue
            size = re.search(r"size=([0-9.]+[KMGT]?)", value)
            disks.append({"key": key, "volume": volume, "storage": volume.split(":")[0],
                          "size": _parse_size(size.group(1)) if size else 0})
        elif _UNUSED.match(key):
            unused.append({"key": key, "volume": value, "storage": value.split(":")[0]})
        elif vmtype == "qemu" and re.match(r"^hostpci\d+$", key):
            passthrough.append(f"{key} passes through PCI device {value.split(',')[0]}")
        elif vmtype == "qemu" and re.match(r"^usb\d+$", key) and "host=" in value:
            passthrough.append(f"{key} passes through a USB device on this node")
        elif vmtype == "lxc" and re.match(r"^dev\d+$", key):
            passthrough.append(f"{key} passes through device {value.split(',')[0]}")
    return {"disks": disks, "isos": isos, "unused": unused, "passthrough": passthrough}


# ── Facts ───────────────────────────────────────────────────────────────────────

def _safe(fn, default=None):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a missing optional endpoint must not abort planning
        logger.debug("ha_failover: optional call failed: %s", exc)
        return default


def gather_cluster(pve) -> dict:
    """Cluster-wide facts, shared by every guest's plan."""
    status = pve.cluster.status.get()
    nodes = {}
    for res in pve.cluster.resources.get(type="node"):
        nodes[res["node"]] = {
            "online": res.get("status") == "online",
            "mem_free": max(0, int(res.get("maxmem", 0)) - int(res.get("mem", 0))),
        }
    for name, info in nodes.items():
        if not info["online"]:
            info.update(lrm=False, storages={})
            continue
        lrm = _safe(lambda n=name: pve.nodes(n).services("pve-ha-lrm").state.get(), {}) or {}
        info["lrm"] = lrm.get("state") == "running"
        info["storages"] = {
            s["storage"]: {
                "type": s.get("type"),
                "shared": bool(s.get("shared")),
                "active": bool(s.get("active")) and bool(s.get("enabled", 1)),
                "enabled": bool(s.get("enabled", 1)),
                "avail": int(s.get("avail") or 0),
                "content": s.get("content", ""),
            }
            for s in _safe(lambda n=name: pve.nodes(n).storage.get(), []) or []
        }
    qdevice = _safe(lambda: pve.cluster.config.qdevice.get(), {}) or {}
    version = str((_safe(lambda: pve.version.get(), {}) or {}).get("version", "9"))
    return {
        "pve_major": int(re.match(r"\d+", version).group()) if re.match(r"\d+", version) else 9,
        "quorate": any(x.get("type") == "cluster" and x.get("quorate") for x in status),
        "clustered": any(x.get("type") == "cluster" for x in status),
        "qdevice": bool(qdevice),
        "nodes": nodes,
        "ha_resources": _safe(lambda: pve.cluster.ha.resources.get(), []) or [],
        "ha_rules": _safe(lambda: pve.cluster.ha.rules.get(), []) or [],
        "ha_groups": _safe(lambda: pve.cluster.ha.groups.get(), []) or [],
        "replication": _safe(lambda: pve.cluster.replication.get(), []) or [],
        "cluster_options": _safe(lambda: pve.cluster.options.get(), {}) or {},
    }


def gather_facts(pve, node: str, vmtype: str, vmid: int, cluster: dict = None, resource: dict = None) -> dict:
    """Read everything build_plan() needs for one guest. `pve` is a proxmoxer ProxmoxAPI.

    `cluster` (from gather_cluster) and `resource` (the guest's /cluster/resources entry)
    can be passed in to avoid re-reading them when planning many guests.
    """
    vmtype = "lxc" if vmtype in ("lxc", "ct") else "qemu"
    guest_api = pve.nodes(node).lxc(vmid) if vmtype == "lxc" else pve.nodes(node).qemu(vmid)
    if cluster is None:
        cluster = gather_cluster(pve)
    if resource is None:
        resource = guest_api.status.current.get()
    return {
        **cluster,
        "vmtype": vmtype,
        "vmid": int(vmid),
        "node": node,
        "name": resource.get("name") or "",
        "running": resource.get("status") == "running",
        "maxmem": int(resource.get("maxmem") or 0),
        "config": guest_api.config.get(),
    }


# ── Plan ────────────────────────────────────────────────────────────────────────

def _check(checks, status, title, detail=""):
    checks.append({"status": status, "title": title, "detail": detail})


def _usable(node_info, storage, content):
    st = node_info.get("storages", {}).get(storage)
    return bool(st and st["active"] and content in st["content"].split(","))


def build_plan(f: dict) -> dict:
    """Decide whether and how the guest can fail over. Pure function of gather_facts()."""
    checks = []
    vmtype, vmid, node = f["vmtype"], f["vmid"], f["node"]
    content = "rootdir" if vmtype == "lxc" else "images"
    the_sid = sid(vmtype, vmid)
    vols = guest_volumes(vmtype, f["config"])
    plan = {
        "sid": the_sid, "vmid": vmid, "vmtype": vmtype, "node": node, "name": f["name"],
        "running": f["running"], "mode": None, "target": None, "eligible": False,
        "already_protected": False, "checks": checks, "actions": [], "disks": vols["disks"],
        "move_options": [], "settings": {},
    }

    existing = next((r for r in f["ha_resources"] if r.get("sid") == the_sid), None)
    if existing:
        plan["already_protected"] = True
        plan["existing"] = {
            "resource": existing,
            "rules": [r for r in f["ha_rules"] if the_sid in str(r.get("resources", "")).split(",")],
            "group": next((g for g in f.get("ha_groups", []) if existing.get("group")
                           and g.get("group") == existing.get("group")), None),
            "replication": [j for j in f["replication"] if str(j.get("guest")) == str(vmid)],
        }
        _check(checks, "ok", "Already protected by HA", f"{the_sid} is an HA resource ({existing.get('state')}).")
        return plan

    # Cluster health
    votes = len(f["nodes"]) + (1 if f["qdevice"] else 0)
    if not f["clustered"]:
        _check(checks, "fail", "Not a cluster", "Failover needs at least two nodes in a Proxmox cluster.")
    elif votes < 3:
        _check(checks, "fail", "Not enough votes for safe HA",
               f"{len(f['nodes'])} node(s){' + QDevice' if f['qdevice'] else ''}: HA needs at least 3 votes "
               "(3 nodes, or 2 nodes and a QDevice) so a node can be fenced safely.")
    else:
        _check(checks, "ok", "Cluster votes", f"{len(f['nodes'])} nodes{' + QDevice' if f['qdevice'] else ''}.")
    if f["quorate"]:
        _check(checks, "ok", "Cluster is quorate")
    else:
        _check(checks, "fail", "Cluster is not quorate", "HA changes are refused without quorum.")
    if not f["nodes"].get(node, {}).get("lrm"):
        _check(checks, "fail", "HA service not running on this node",
               f"pve-ha-lrm is not running on {node}; start it before enabling HA.")

    # Things that cannot move between nodes at all
    for item in vols["passthrough"]:
        _check(checks, "fail", "Passthrough device", f"{item}: it only exists on {node}, so the guest cannot start elsewhere.")

    # Storage classification
    here = f["nodes"].get(node, {}).get("storages", {})
    local_disks, zfs_disks, shared_disks = [], [], []
    for d in vols["disks"]:
        st = here.get(d["storage"], {})
        d["storage_type"] = st.get("type", "unknown")
        if st.get("shared"):
            d["kind"] = "shared"; shared_disks.append(d)
        elif st.get("type") == "zfspool":
            d["kind"] = "zfs"; zfs_disks.append(d)
        else:
            d["kind"] = "local"; local_disks.append(d)
    for iso in vols["isos"]:
        if not here.get(iso["storage"], {}).get("shared"):
            plan["actions"].append({"type": "eject_iso", "key": iso["key"], "volume": iso["volume"],
                                    "label": f"Eject {iso['volume']} from {iso['key']} (ISO on node-local storage)"})
            _check(checks, "warn", "Local ISO attached",
                   f"{iso['key']} has {iso['volume']}, which other nodes cannot see; the wizard will eject it.")
    for u in vols["unused"]:
        st = here.get(u["storage"], {})
        if not st.get("shared") and st.get("type") != "zfspool":
            _check(checks, "fail", "Unused disk on local storage",
                   f"{u['key']} ({u['volume']}) is on node-local storage and blocks migration and replication. "
                   "Delete it or move it to shared storage first.")

    # Candidate failover nodes
    needed = {d["storage"] for d in vols["disks"]}
    candidates = []
    for name, info in f["nodes"].items():
        if name == node or not info.get("online") or not info.get("lrm"):
            continue
        if all(_usable(info, s, content) for s in needed):
            candidates.append(name)
    candidates.sort(key=lambda n: f["nodes"][n]["mem_free"], reverse=True)

    if local_disks:
        names = ", ".join(f"{d['key']} on {d['storage']} ({d['storage_type']})" for d in local_disks)
        _check(checks, "fail", "Disks are on node-local storage",
               f"{names}. If {node} fails these disks are unreachable, so no other node can start the guest. "
               "The guest can still fail over once its disks are on shared storage (NFS, Ceph, iSCSI: no data "
               "loss) or on a ZFS pool, which Proxmox replicates to a second node every 2 minutes without any "
               "shared storage.")
        plan["move_options"] = _move_options(f, vols["disks"], content)
        if not plan["move_options"] and vmtype == "lxc" and f["running"]:
            _check(checks, "info", "Stop the container to move its disks",
                   "Proxmox can only move container volumes while the container is stopped.")
        elif not plan["move_options"]:
            _check(checks, "info", "No suitable storage to move to", _no_move_reason(f, vols["disks"], content))
    elif not vols["disks"]:
        plan["mode"] = "shared"
    elif zfs_disks:
        plan["mode"] = "replication"
    else:
        plan["mode"] = "shared"

    if plan["mode"]:
        _check(checks, "ok", "Storage supports failover",
               "Shared storage: no data loss." if plan["mode"] == "shared" else
               f"ZFS: replicated every 2 minutes, so up to ~2 minutes of changes can be lost.")
        if not candidates:
            _check(checks, "fail", "No failover node",
                   "No other online node with the HA service running can use all of this guest's storage.")
        else:
            target = candidates[0]
            plan["target"] = target
            if f["nodes"][target]["mem_free"] < f["maxmem"]:
                _check(checks, "warn", "Failover node is short on memory",
                       f"{target} has {f['nodes'][target]['mem_free'] >> 20} MiB free; the guest needs up to "
                       f"{f['maxmem'] >> 20} MiB.")
            if plan["mode"] == "replication":
                tgt_st = f["nodes"][target]["storages"]
                for d in zfs_disks:
                    if tgt_st[d["storage"]]["avail"] < d["size"]:
                        _check(checks, "fail", "Not enough space for the replica",
                               f"{d['storage']} on {target} has {tgt_st[d['storage']]['avail'] >> 30} GiB free; "
                               f"{d['key']} is {d['size'] >> 30} GiB.")
                _check(checks, "ok", "Failover node", f"{target}: has the same ZFS storage and the most free memory.")
            else:
                _check(checks, "ok", "Failover node", f"{target}: can reach the shared storage and has the most free memory.")

    if not f["running"]:
        _check(checks, "warn", "Guest is stopped",
               "It will be added to HA in the 'stopped' state; start it from Depl0y or Proxmox to protect it.")

    plan["eligible"] = bool(plan["mode"] and plan["target"]) and not any(c["status"] == "fail" for c in checks)
    if plan["eligible"]:
        plan["settings"] = _settings(f, plan)
        plan["actions"] += _actions(f, plan)
    return plan


def _move_options(f, disks, content):
    """Storages on the guest's node that would make it failover-capable, best first."""
    node = f["node"]
    total = sum(d["size"] for d in disks)
    options = []
    if f["vmtype"] == "lxc" and f["running"]:
        return []   # Proxmox only moves container volumes while the container is stopped
    for name, st in f["nodes"].get(node, {}).get("storages", {}).items():
        if not st["active"] or content not in st["content"].split(","):
            continue
        if not (st["shared"] or st["type"] == "zfspool"):
            continue
        others = [n for n, info in f["nodes"].items()
                  if n != node and info.get("online") and info.get("lrm") and _usable(info, name, content)]
        if not others or st["avail"] < total:
            continue
        options.append({"storage": name, "type": st["type"], "shared": st["shared"],
                        "avail": st["avail"], "needed": total, "other_nodes": others})
    options.sort(key=lambda o: (not o["shared"], -o["avail"]))
    return options


def _no_move_reason(f, disks, content):
    """Explain why _move_options() found nothing, naming the specific ZFS/shared problem."""
    node = f["node"]
    total = sum(d["size"] for d in disks)
    howto = ("For replication, create a ZFS pool on {node} and on at least one other node, and add it as one "
             "ZFS storage (same storage ID) for those nodes under Datacenter → Storage. The wizard will then "
             "move the disks onto it and set up replication.").format(node=node)
    problems = []
    for name, st in f["nodes"].get(node, {}).get("storages", {}).items():
        if not (st["shared"] or st["type"] == "zfspool") or content not in st["content"].split(","):
            continue   # e.g. a backup-only PBS store is not a candidate at all
        what = "Shared storage" if st["shared"] else "ZFS storage"
        if not st.get("enabled", True):
            problems.append(f"{what} {name} is not set up for {node}"
                            + ("" if st["shared"] else f": {node} needs the same ZFS pool as the other nodes,")
                            + f" and {node} added to {name}'s nodes under Datacenter → Storage.")
            continue
        if not st["active"]:
            problems.append(f"{what} {name} is inactive on {node}.")
        elif not any(n != node and info.get("online") and info.get("lrm") and _usable(info, name, content)
                     for n, info in f["nodes"].items()):
            problems.append(f"{what} {name} is not available on any other online node with HA running"
                            + ("; replication needs a ZFS storage with the same ID on the failover node."
                               if not st["shared"] else "."))
        elif st["avail"] < total:
            problems.append(f"{what} {name} has {st['avail'] >> 30} GiB free; the disks need {total >> 30} GiB.")
    if any("is not set up for" in p for p in problems):
        return " ".join(problems)
    if problems:
        return " ".join(problems) + " " + howto
    return f"{node} has no shared storage and no ZFS pool. " + howto


def _settings(f, plan):
    vmtype, vmid, node, target = plan["vmtype"], plan["vmid"], plan["node"], plan["target"]
    strict = 1 if plan["mode"] == "replication" else 0
    resource = {"sid": plan["sid"], "state": "started" if f["running"] else "stopped",
                "max_restart": 1, "max_relocate": 1, "comment": MANAGED_COMMENT}
    if f.get("pve_major", 9) >= 9:
        s = {
            "ha_resource": {**resource, "failback": 1},
            "rule": {"rule": rule_id(vmtype, vmid), "type": "node-affinity", "resources": plan["sid"],
                     "nodes": f"{node}:2,{target}:1", "strict": strict, "comment": MANAGED_COMMENT},
        }
    else:   # Proxmox VE 8: HA groups instead of rules
        s = {
            "ha_resource": {**resource, "group": rule_id(vmtype, vmid)},
            "group": {"group": rule_id(vmtype, vmid), "type": "group", "nodes": f"{node}:2,{target}:1",
                      "restricted": strict, "nofailback": 0, "comment": MANAGED_COMMENT},
        }
    if plan["mode"] == "replication":
        used = {int(str(j.get("id", "")).split("-")[1]) for j in f["replication"]
                if str(j.get("id", "")).startswith(f"{vmid}-")}
        s["replication"] = {"id": f"{vmid}-{min(set(range(len(used) + 1)) - used)}", "target": target,
                            "type": "local", "schedule": REPLICATION_SCHEDULE, "comment": MANAGED_COMMENT}
    ha_opt = str(f["cluster_options"].get("ha", ""))
    if "shutdown_policy" not in ha_opt:
        s["cluster_ha_option"] = "shutdown_policy=migrate"
    return s


def _actions(f, plan):
    s, acts = plan["settings"], []
    if "replication" in s:
        r = s["replication"]
        acts.append({"type": "replication", "label": f"Replicate disks to {r['target']} every 2 minutes "
                     f"(job {r['id']}) and wait for the first copy"})
    if "cluster_ha_option" in s:
        acts.append({"type": "cluster_option", "label": "Set cluster HA shutdown policy to 'migrate' "
                     "(HA guests move away when their node is shut down or rebooted)"})
    acts.append({"type": "ha_resource", "label": f"Add {plan['sid']} to HA (restart once, then relocate once; "
                 "failback on)"})
    strict = s["rule"]["strict"] if "rule" in s else s["group"]["restricted"]
    acts.append({"type": "rule" if "rule" in s else "group",
                 "label": f"Prefer {plan['node']}, fail over to {plan['target']}"
                 + (", and never run anywhere else (only these two nodes have the disks)" if strict else "")
                 + ("" if "rule" in s else f": HA group {s['group']['group']}")})
    return acts


# ── Apply ───────────────────────────────────────────────────────────────────────

def wait_task(pve, node: str, upid: str, timeout: int = 7200):
    """Wait for a Proxmox task; raise if it fails."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = pve.nodes(node).tasks(upid).status.get()
        if st.get("status") == "stopped":
            if st.get("exitstatus") != "OK":
                raise RuntimeError(f"task failed: {st.get('exitstatus')}")
            return
        time.sleep(3)
    raise RuntimeError("task timed out")


def move_disks(pve, plan: dict, storage: str, progress):
    """Move every disk of the guest to `storage`, deleting the source copy afterwards."""
    node, vmid, vmtype = plan["node"], plan["vmid"], plan["vmtype"]
    for d in plan["disks"]:
        if d["storage"] == storage:
            continue
        progress(f"Moving {d['key']} ({d['size'] >> 30} GiB) from {d['storage']} to {storage}")
        if vmtype == "lxc":
            upid = pve.nodes(node).lxc(vmid).move_volume.post(volume=d["key"], storage=storage, delete=1)
        else:
            upid = pve.nodes(node).qemu(vmid).move_disk.post(disk=d["key"], storage=storage, delete=1)
        wait_task(pve, node, upid)


def apply_plan(pve, plan: dict, progress):
    """Carry out an eligible plan. `progress(text)` reports each step."""
    s = plan["settings"]
    node, vmid = plan["node"], plan["vmid"]
    guest_api = pve.nodes(node).lxc(vmid) if plan["vmtype"] == "lxc" else pve.nodes(node).qemu(vmid)

    for a in plan["actions"]:
        if a["type"] == "eject_iso":
            progress(a["label"])
            guest_api.config.put(**{a["key"]: "none,media=cdrom"})

    if "replication" in s:
        r = s["replication"]
        progress(f"Creating replication job {r['id']} to {r['target']}")
        pve.cluster.replication.post(**r)
        progress("Running the first replication (copies the full disks; later runs only send changes)")
        pve.nodes(node).replication(r["id"]).schedule_now.post()
        deadline = time.time() + FIRST_SYNC_TIMEOUT
        while True:
            st = _safe(lambda: pve.nodes(node).replication(r["id"]).status.get(), {}) or {}
            if st.get("error"):
                raise RuntimeError(f"replication failed: {st['error']}")
            if st.get("last_sync"):
                break
            if time.time() > deadline:
                raise RuntimeError("the first replication did not finish within an hour")
            time.sleep(5)
        progress("First replication finished")

    if "cluster_ha_option" in s:
        progress("Setting cluster HA shutdown policy to 'migrate'")
        pve.cluster.options.put(ha=s["cluster_ha_option"])

    if "group" in s:
        # Proxmox VE 8: the resource names its group, so the group has to exist first.
        progress(f"Creating HA group {s['group']['group']}")
        pve.cluster.ha.groups.post(**s["group"])
        try:
            progress(f"Adding {plan['sid']} to HA")
            pve.cluster.ha.resources.post(**s["ha_resource"])
        except Exception:
            _safe(lambda: pve.cluster.ha.groups(s["group"]["group"]).delete())
            raise
    else:
        progress(f"Adding {plan['sid']} to HA")
        pve.cluster.ha.resources.post(**s["ha_resource"])
        try:
            progress(f"Adding node-affinity rule {s['rule']['rule']}")
            pve.cluster.ha.rules.post(**s["rule"])
        except Exception:
            # Without the rule a replicated guest could be started on a node without its disks.
            _safe(lambda: pve.cluster.ha.resources(plan["sid"]).delete())
            raise
    progress("Done: Proxmox will now restart this guest on the failover node if its node fails")


def remove_protection(pve, plan: dict, progress):
    """Undo what the wizard set up for this guest (HA resource, its rules, its replication jobs)."""
    existing = plan.get("existing") or {}
    for rule in existing.get("rules", []):
        resources = [r for r in str(rule.get("resources", "")).split(",") if r and r != plan["sid"]]
        if resources:
            progress(f"Removing {plan['sid']} from rule {rule['rule']}")
            pve.cluster.ha.rules(rule["rule"]).put(type=rule["type"], resources=",".join(resources))
        else:
            progress(f"Deleting rule {rule['rule']}")
            pve.cluster.ha.rules(rule["rule"]).delete()
    progress(f"Removing {plan['sid']} from HA (the guest keeps running)")
    pve.cluster.ha.resources(plan["sid"]).delete()
    group = existing.get("group")
    if group and MANAGED_COMMENT in str(group.get("comment", "")):
        progress(f"Deleting HA group {group['group']}")
        pve.cluster.ha.groups(group["group"]).delete()
    for job in existing.get("replication", []):
        if MANAGED_COMMENT in str(job.get("comment", "")):
            progress(f"Removing replication job {job['id']} (and its replica on {job.get('target')})")
            pve.cluster.replication(job["id"]).delete()
    progress("Done")
