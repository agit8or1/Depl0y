"""Read-only mock of the Proxmox VE API for the Depl0y screenshot demo.

Serves synthetic inventory from fixtures.py. Dispatches to a datacenter by the
Host header so a single process can stand in for several PVE endpoints.

Safety properties:
  * binds to loopback only, inside a private network namespace
  * every mutating verb (POST/PUT/DELETE) is refused with HTTP 403
"""
import logging
import re
import sys
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

sys.path.insert(0, __import__("os").path.dirname(__file__))
import fixtures as F  # noqa: E402

logging.basicConfig(level=logging.INFO, format="mock-pve %(levelname)s %(message)s")
log = logging.getLogger("mock-pve")
UNMATCHED = set()

app = FastAPI(docs_url=None, redoc_url=None)


def dc_for(request: Request):
    host = (request.headers.get("host") or "").split(":")[0]
    dc = F.DC_BY_HOST.get(host)
    if dc:
        return dc
    for d in F.DATACENTERS:
        if d["loopback"] == host:
            return d
    return F.DATACENTERS[0]


def ok(data):
    return JSONResponse({"data": data})


# ---------------------------------------------------------------- handlers


def h_version(dc, m, q):
    return {"version": dc["pve_version"], "release": dc["pve_version"].rsplit(".", 1)[0],
            "repoid": "2bc3f2a1", "console": "xtermjs"}


def h_nodes(dc, m, q):
    out = []
    for name in dc["nodes"]:
        n = F.NODES[name]
        out.append({
            "node": name, "status": "online", "type": "node",
            "id": f"node/{name}",
            "cpu": round(n["cpu_pct"], 4), "maxcpu": n["cores"],
            "mem": int(n["mem_gb"] * F.GiB * n["mem_pct"]), "maxmem": n["mem_gb"] * F.GiB,
            "disk": int(n["root_gb"] * F.GiB * n["root_pct"]), "maxdisk": n["root_gb"] * F.GiB,
            "uptime": n["uptime"], "level": "", "ssl_fingerprint": "AA:BB:CC:DD",
        })
    return out


def h_cluster_status(dc, m, q):
    out = []
    if dc["cluster"]:
        out.append({"type": "cluster", "id": "cluster", "name": dc["cluster"],
                    "version": len(dc["nodes"]), "nodes": len(dc["nodes"]), "quorate": 1})
    for i, name in enumerate(dc["nodes"], start=1):
        n = F.NODES[name]
        out.append({"type": "node", "id": f"node/{name}", "name": name, "nodeid": i,
                    "ip": n["ip"], "online": 1, "local": 1 if i == 1 else 0, "level": ""})
    return out


def h_cluster_resources(dc, m, q):
    kind = q.get("type")
    out = []
    if kind in (None, "vm"):
        for name in dc["nodes"]:
            for g in F.guests_of(name):
                out.append({
                    "id": f"qemu/{g['vmid']}", "type": "qemu", "vmid": g["vmid"],
                    "name": g["name"], "node": name, "status": g["status"],
                    "maxcpu": g["maxcpu"], "cpu": g["cpu"], "maxmem": g["maxmem"],
                    "mem": g["mem"], "maxdisk": g["maxdisk"], "disk": g["disk"],
                    "uptime": g["uptime"], "template": g["template"], "tags": g["tags"],
                    "netin": g["netin"], "netout": g["netout"],
                    "diskread": g["diskread"], "diskwrite": g["diskwrite"],
                })
            for c in F.containers_of(name):
                out.append({
                    "id": f"lxc/{c['vmid']}", "type": "lxc", "vmid": c["vmid"],
                    "name": c["name"], "node": name, "status": c["status"],
                    "maxcpu": c["maxcpu"], "cpu": c["cpu"], "maxmem": c["maxmem"],
                    "mem": c["mem"], "maxdisk": c["maxdisk"], "disk": c["disk"],
                    "uptime": c["uptime"], "template": 0,
                })
    if kind in (None, "node"):
        out += [dict(r, type="node") for r in h_nodes(dc, m, q)]
    if kind in (None, "storage"):
        for name in dc["nodes"]:
            for s in h_node_storage(dc, {"node": name}, q):
                out.append({"id": f"storage/{name}/{s['storage']}", "type": "storage",
                            "node": name, "storage": s["storage"], "status": "available",
                            "total": s["total"], "used": s["used"], "avail": s["avail"],
                            "shared": s["shared"], "plugintype": s["type"],
                            "content": s["content"]})
    return out


def h_node_status(dc, m, q):
    n = F.NODES[m["node"]]
    total = n["mem_gb"] * F.GiB
    used = int(total * n["mem_pct"])
    rtotal = n["root_gb"] * F.GiB
    rused = int(rtotal * n["root_pct"])
    return {
        "uptime": n["uptime"],
        "cpu": round(n["cpu_pct"], 4),
        "wait": 0.0042,
        "loadavg": [f"{n['cores'] * n['cpu_pct']:.2f}",
                    f"{n['cores'] * n['cpu_pct'] * 0.94:.2f}",
                    f"{n['cores'] * n['cpu_pct'] * 0.88:.2f}"],
        "cpuinfo": {"cpus": n["cores"], "sockets": n["sockets"], "cores": n["cores"] // n["sockets"],
                    "model": n["cpu_model"], "mhz": n["mhz"], "hvm": "1", "user_hz": 100,
                    "flags": "vmx"},
        "memory": {"total": total, "used": used, "free": total - used},
        "ksm": {"shared": 0},
        "swap": {"total": 8 * F.GiB, "used": 0, "free": 8 * F.GiB},
        "rootfs": {"total": rtotal, "used": rused, "avail": rtotal - rused, "free": rtotal - rused},
        "pveversion": f"pve-manager/{dc['pve_version']}/2bc3f2a1",
        "kversion": f"Linux {dc['kversion']} #1 SMP PREEMPT_DYNAMIC PVE",
        "idle": 0, "current-kernel": {"release": dc["kversion"], "sysname": "Linux"},
        "boot-info": {"mode": "efi", "secureboot": 0},
    }


def h_node_qemu(dc, m, q):
    out = []
    for g in F.guests_of(m["node"]):
        out.append({
            "vmid": g["vmid"], "name": g["name"], "status": g["status"],
            "cpus": g["maxcpu"], "cpu": g["cpu"], "maxmem": g["maxmem"], "mem": g["mem"],
            "maxdisk": g["maxdisk"], "disk": g["disk"], "uptime": g["uptime"],
            "template": g["template"], "tags": g["tags"], "pid": 2000 + g["vmid"],
            "netin": g["netin"], "netout": g["netout"],
            "diskread": g["diskread"], "diskwrite": g["diskwrite"],
        })
    return out


def h_node_lxc(dc, m, q):
    return F.containers_of(m["node"])


def h_node_storage(dc, m, q):
    out = []
    for sname, stype, content, total, pct, shared in dc["storages"]:
        total = int(total)
        used = int(total * pct)
        out.append({"storage": sname, "type": stype, "content": content,
                    "active": 1, "enabled": 1, "shared": shared,
                    "total": total, "used": used, "avail": total - used,
                    "used_fraction": round(pct, 4)})
    return out


_ISOS = [
    ("ubuntu-24.04.1-live-server-amd64.iso", 2_663_383_040),
    ("debian-12.7.0-amd64-netinst.iso", 659_030_016),
    ("Rocky-9.4-x86_64-minimal.iso", 1_694_498_816),
    ("virtio-win-0.1.262.iso", 707_397_632),
]


def h_storage_content(dc, m, q):
    storage = m["storage"]
    node = m["node"]
    ctype = q.get("content")
    out = []
    if storage == "local" and ctype in (None, "iso"):
        for name, size in _ISOS:
            out.append({"volid": f"local:iso/{name}", "content": "iso", "format": "iso",
                        "size": size, "ctime": int(time.time()) - 86400 * 30})
    if ctype in (None, "images"):
        for g in F.guests_of(node):
            out.append({"volid": f"{storage}:vm-{g['vmid']}-disk-0", "content": "images",
                        "format": "raw", "size": g["maxdisk"], "vmid": g["vmid"]})
    if ctype in (None, "vztmpl") and storage == "local":
        out.append({"volid": "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst",
                    "content": "vztmpl", "format": "tzst", "size": 128_974_848})
    return out


def h_node_network(dc, m, q):
    n = F.NODES[m["node"]]
    net = n["ip"].rsplit(".", 1)[0]
    return [
        {"iface": "vmbr0", "type": "bridge", "active": 1, "autostart": 1, "method": "static",
         "address": n["ip"], "netmask": "255.255.255.0", "cidr": f"{n['ip']}/24",
         "gateway": f"{net}.1", "bridge_ports": "bond0", "bridge_stp": "off",
         "bridge_fd": "0", "bridge_vlan_aware": 1, "priority": 5},
        {"iface": "vmbr1", "type": "bridge", "active": 1, "autostart": 1, "method": "manual",
         "bridge_ports": "bond1", "bridge_stp": "off", "bridge_fd": "0",
         "bridge_vlan_aware": 1, "comments": "storage / migration", "priority": 6},
        {"iface": "bond0", "type": "bond", "active": 1, "autostart": 1, "method": "manual",
         "slaves": "eno1 eno2", "bond_mode": "802.3ad", "bond_xmit_hash_policy": "layer3+4",
         "priority": 4},
        {"iface": "bond1", "type": "bond", "active": 1, "autostart": 1, "method": "manual",
         "slaves": "ens3f0 ens3f1", "bond_mode": "802.3ad", "priority": 4},
        {"iface": "eno1", "type": "eth", "active": 1, "method": "manual", "priority": 1},
        {"iface": "eno2", "type": "eth", "active": 1, "method": "manual", "priority": 2},
    ]


_TASK_TYPES = [
    ("vzdump", "Backup", "OK"), ("qmstart", "Start VM", "OK"),
    ("qmigrate", "Migrate VM", "OK"), ("qmsnapshot", "Snapshot", "OK"),
    ("aptupdate", "Update package database", "OK"), ("qmclone", "Clone VM", "OK"),
]


def h_node_tasks(dc, m, q):
    if q.get("source") == "active":
        return []          # nothing is running on the demo fixture
    node = m["node"]
    guests = [g for g in F.guests_of(node) if not g["template"]]
    now = int(time.time())
    out = []
    for i in range(min(int(q.get("limit", 20) or 20), 20)):
        ttype, _label, status = _TASK_TYPES[i % len(_TASK_TYPES)]
        g = guests[i % len(guests)] if guests else None
        start = now - 900 * (i + 1)
        out.append({
            "upid": f"UPID:{node}:0000{1000+i:04X}:0{i:07X}:{start:08X}:{ttype}:{g['vmid'] if g else ''}:root@pam:",
            "node": node, "pid": 1000 + i, "pstart": start, "starttime": start,
            "endtime": start + 40 + i * 3, "type": ttype,
            "id": str(g["vmid"]) if g else node, "user": "root@pam", "status": status,
        })
    return out


def _rrd(q, keys_base, *key):
    tf = (q.get("timeframe") or "hour")
    step = {"hour": 60, "day": 1800, "week": 10800, "month": 43200, "year": 518400}.get(tf, 60)
    points = 70
    cols = {}
    for name, (base, spread) in keys_base.items():
        cols[name] = F.series(points, step, base, spread, name, *key)
    times = [t for t, _ in next(iter(cols.values()))]
    out = []
    for i, t in enumerate(times):
        row = {"time": t}
        for name in cols:
            row[name] = round(cols[name][i][1], 6)
        out.append(row)
    return out


def h_node_rrd(dc, m, q):
    n = F.NODES[m["node"]]
    total = n["mem_gb"] * F.GiB
    rows = _rrd(q, {
        "cpu": (n["cpu_pct"], n["cpu_pct"] * 0.45),
        "iowait": (0.01, 0.008),
        "loadavg": (n["cores"] * n["cpu_pct"], n["cores"] * n["cpu_pct"] * 0.3),
        "memused": (total * n["mem_pct"], total * 0.04),
        "netin": (7.4e7, 5.2e7), "netout": (5.1e7, 3.9e7),
        "rootused": (n["root_gb"] * F.GiB * n["root_pct"], 2e8),
    }, m["node"])
    for r in rows:
        r["maxcpu"] = n["cores"]
        r["memtotal"] = total
        r["roottotal"] = n["root_gb"] * F.GiB
        r["swaptotal"] = 8 * F.GiB
        r["swapused"] = 0
    return rows


def h_vm_rrd(dc, m, q):
    g = F.find_guest(m["node"], m["vmid"])
    if not g:
        return []
    running = g["status"] == "running"
    rows = _rrd(q, {
        "cpu": (g["cpu"] if running else 0, (g["cpu"] * 0.55) if running else 0),
        "mem": (g["mem"], g["maxmem"] * 0.05 if running else 0),
        "netin": (3.9e6, 3.1e6), "netout": (2.6e6, 2.0e6),
        "diskread": (1.4e6, 1.3e6), "diskwrite": (2.2e6, 1.9e6),
    }, m["node"], m["vmid"])
    for r in rows:
        r["maxcpu"] = g["maxcpu"]
        r["maxmem"] = g["maxmem"]
        r["maxdisk"] = g["maxdisk"]
        r["disk"] = 0
    return rows


def h_vm_status(dc, m, q):
    g = F.find_guest(m["node"], m["vmid"])
    if not g:
        return {}
    running = g["status"] == "running"
    return {
        "vmid": g["vmid"], "name": g["name"], "status": g["status"],
        "qmpstatus": "running" if running else "stopped",
        "cpus": g["maxcpu"], "cpu": g["cpu"],
        "maxmem": g["maxmem"], "mem": g["mem"], "balloon": g["maxmem"],
        "freemem": g["maxmem"] - g["mem"] if running else 0,
        "maxdisk": g["maxdisk"], "disk": 0, "uptime": g["uptime"],
        "netin": g["netin"], "netout": g["netout"],
        "diskread": g["diskread"], "diskwrite": g["diskwrite"],
        "pid": 2000 + g["vmid"] if running else None,
        "agent": 1, "template": g["template"],
        "ha": {"managed": 1 if dc["cluster"] else 0,
               "state": "started" if running else "stopped",
               "group": f"{dc['cluster']}-ha" if dc["cluster"] else ""},
        "running-machine": "pc-q35-9.0+pve0" if running else None,
        "running-qemu": "9.0.2" if running else None,
        "tags": g["tags"],
    }


def h_vm_config(dc, m, q):
    g = F.find_guest(m["node"], m["vmid"])
    if not g:
        return {}
    win = g["ostype"].startswith("win")
    store = "ceph-nvme" if dc["key"] == "east" else ("nfs-west" if dc["key"] == "west" else "local-zfs")
    disk_gb = g["maxdisk"] // F.GiB
    cfg = {
        "name": g["name"],
        "cores": g["maxcpu"] // g["sockets"],
        "sockets": g["sockets"],
        "cpu": "host",
        "numa": 1 if g["maxcpu"] >= 16 else 0,
        "memory": g["maxmem"] // F.MiB,
        "balloon": 0,
        "ostype": g["ostype"],
        "scsihw": "virtio-scsi-single",
        "scsi0": f"{store}:vm-{g['vmid']}-disk-0,size={disk_gb}G,iothread=1,discard=on,ssd=1",
        "net0": f"virtio={F.mac(g['vmid'])},bridge=vmbr0,firewall=1,tag={110 if dc['key'] == 'east' else 120}",
        "boot": "order=scsi0;ide2;net0",
        "agent": "enabled=1,fstrim_cloned_disks=1",
        "bios": "ovmf" if win else "seabios",
        "machine": "pc-q35-9.0",
        "onboot": 1,
        "tags": g["tags"],
        "vmgenid": "3f2b1c44-9e10-4b2f-9a5d-0c71e2d8ab10",
        "smbios1": "uuid=8c2f1a90-9d51-4c7e-b0d2-5a3f8e1c4b77",
        "description": f"Managed by Depl0y · {g['tags'].replace(';', ', ')}",
        "digest": "9f8d2c1b4a6e7f30",
    }
    if win:
        cfg["efidisk0"] = f"{store}:vm-{g['vmid']}-disk-1,efitype=4m,pre-enrolled-keys=1,size=4M"
        cfg["tpmstate0"] = f"{store}:vm-{g['vmid']}-disk-2,size=4M,version=v2.0"
    if g["maxdisk"] > 900 * F.GiB:
        cfg["scsi1"] = f"{store}:vm-{g['vmid']}-disk-3,size=1024G,iothread=1,backup=0"
    if not win:
        cfg["ide2"] = f"local:iso/{_ISOS[0][0]},media=cdrom"
    return cfg


def h_vm_snapshots(dc, m, q):
    g = F.find_guest(m["node"], m["vmid"])
    if not g:
        return []
    now = int(time.time())
    out = []
    if g["status"] == "running":
        out.append({"name": "pre-patch-2026-09", "description": "Before September patch window",
                    "snaptime": now - 86400 * 9, "vmstate": 0, "parent": None})
        out.append({"name": "pre-schema-migration", "description": "Before v14 schema migration",
                    "snaptime": now - 86400 * 2, "vmstate": 1, "parent": "pre-patch-2026-09"})
    out.append({"name": "current", "description": "You are here!",
                "digest": "9f8d2c1b4a6e7f30", "running": 1 if g["status"] == "running" else 0,
                "parent": out[-1]["name"] if out else None})
    return out


def h_vm_agent_ifaces(dc, m, q):
    g = F.find_guest(m["node"], m["vmid"])
    if not g or not g["ip"]:
        return {"result": []}
    return {"result": [
        {"name": "lo", "hardware-address": "00:00:00:00:00:00",
         "ip-addresses": [{"ip-address": "127.0.0.1", "ip-address-type": "ipv4", "prefix": 8}],
         "statistics": {"rx-bytes": 1024, "tx-bytes": 1024}},
        {"name": "ens18", "hardware-address": F.mac(g["vmid"]).lower(),
         "ip-addresses": [{"ip-address": g["ip"], "ip-address-type": "ipv4", "prefix": 24}],
         "statistics": {"rx-bytes": g["netin"], "tx-bytes": g["netout"]}},
    ]}


def h_vm_firewall_rules(dc, m, q):
    return [
        {"pos": 0, "type": "in", "action": "ACCEPT", "enable": 1, "proto": "tcp",
         "dport": "22", "source": "203.0.113.0/24", "comment": "SSH from management net"},
        {"pos": 1, "type": "in", "action": "ACCEPT", "enable": 1, "proto": "tcp",
         "dport": "443", "comment": "HTTPS"},
        {"pos": 2, "type": "in", "action": "DROP", "enable": 1, "comment": "default deny"},
    ]


def h_vm_firewall_options(dc, m, q):
    return {"enable": 1, "policy_in": "DROP", "policy_out": "ACCEPT",
            "dhcp": 0, "macfilter": 1, "ndp": 1, "log_level_in": "info"}


def h_ha_groups(dc, m, q):
    if not dc["cluster"]:
        return []
    return [{"group": f"{dc['cluster']}-ha", "type": "group", "nodes": ",".join(dc["nodes"]),
             "restricted": 0, "nofailback": 0, "comment": "Production workloads"}]


def h_ha_resources(dc, m, q):
    if not dc["cluster"]:
        return []
    out = []
    for name in dc["nodes"]:
        for g in F.guests_of(name):
            if g["template"] or "production" not in g["tags"]:
                continue
            out.append({"sid": f"vm:{g['vmid']}", "type": "vm", "state": "started",
                        "group": f"{dc['cluster']}-ha", "max_restart": 1, "max_relocate": 1,
                        "digest": "a1b2c3"})
    return out


def h_ha_status(dc, m, q):
    if not dc["cluster"]:
        return []
    out = [{"id": "quorum", "type": "quorum", "node": dc["nodes"][0], "quorate": 1,
            "status": "OK"}]
    for i, name in enumerate(dc["nodes"]):
        out.append({"id": f"node/{name}", "type": "lrm", "node": name,
                    "status": "active" if i else "active (master)",
                    "timestamp": int(time.time())})
    return out


def h_pools(dc, m, q):
    return [{"poolid": "production", "comment": "Production workloads"},
            {"poolid": "staging", "comment": "Pre-production"}]


def h_access_users(dc, m, q):
    return [{"userid": "root@pam", "enable": 1, "comment": "Superuser"},
            {"userid": "depl0y@pve", "enable": 1, "comment": "Depl0y service account"}]


def h_access_roles(dc, m, q):
    return [{"roleid": "Administrator", "privs": "VM.Allocate,VM.Config.CPU", "special": 1},
            {"roleid": "PVEVMAdmin", "privs": "VM.Allocate", "special": 1},
            {"roleid": "PVEAuditor", "privs": "Datastore.Audit,VM.Audit", "special": 1}]


def h_cluster_nextid(dc, m, q):
    used = set()
    for name in dc["nodes"]:
        used |= {g["vmid"] for g in F.guests_of(name)}
        used |= {c["vmid"] for c in F.containers_of(name)}
    i = 100
    while i in used:
        i += 1
    return str(i)


def h_cluster_backup(dc, m, q):
    return [{"id": "backup-nightly", "enabled": 1, "schedule": "02:15", "storage": "pbs-east"
             if dc["key"] == "east" else "local", "mode": "snapshot", "all": 1,
             "compress": "zstd", "mailnotification": "failure", "comment": "Nightly full"}]


def h_cluster_options(dc, m, q):
    return {"keyboard": "en-us", "migration": {"type": "secure", "network":
            "203.0.113.0/24" if dc["key"] == "east" else "198.51.100.0/24"}}


def h_node_subscription(dc, m, q):
    return {"status": "notfound", "level": "", "productname": "Proxmox VE",
            "message": "There is no subscription key"}


def h_node_version(dc, m, q):
    return {"version": dc["pve_version"], "release": dc["pve_version"].rsplit(".", 1)[0],
            "repoid": "2bc3f2a1"}


def h_node_dns(dc, m, q):
    return {"search": "example.net", "dns1": "203.0.113.2", "dns2": "198.51.100.2"}


def h_node_time(dc, m, q):
    return {"time": int(time.time()), "localtime": int(time.time()), "timezone": "UTC"}


def h_replication(dc, m, q):
    if dc["key"] != "west":
        return []
    return [{"id": "202-0", "type": "local", "source": "west-01", "target": "west-02",
             "guest": 202, "schedule": "*/15", "rate": None, "disable": 0,
             "last_sync": int(time.time()) - 540, "duration": 18.4, "fail_count": 0,
             "next_sync": int(time.time()) + 360, "jobnum": "0"}]



_OSINFO = {
    "l26": {"id": "ubuntu", "name": "Ubuntu", "pretty-name": "Ubuntu 24.04.1 LTS",
            "version": "24.04", "version-id": "24.04",
            "kernel-release": "6.8.0-45-generic", "kernel-version": "#45-Ubuntu SMP",
            "machine": "x86_64"},
    "win11": {"id": "mswindows", "name": "Microsoft Windows",
              "pretty-name": "Windows Server 2022 Standard", "version": "10 (2022)",
              "version-id": "2022", "kernel-release": "20348",
              "kernel-version": "10.0", "machine": "x86_64"},
}


def h_agent_osinfo(dc, m, q):
    g = F.find_guest(m["node"], m["vmid"])
    if not g or g["status"] != "running":
        return {}
    return {"result": _OSINFO.get(g["ostype"], _OSINFO["l26"])}


def h_agent_hostname(dc, m, q):
    g = F.find_guest(m["node"], m["vmid"])
    if not g or g["status"] != "running":
        return {}
    return {"result": {"host-name": g["name"]}}


def h_agent_timezone(dc, m, q):
    return {"result": {"zone": "Etc/UTC", "offset": 0}}


def h_agent_users(dc, m, q):
    g = F.find_guest(m["node"], m["vmid"])
    if not g or g["status"] != "running":
        return {}
    user = "Administrator" if g["ostype"].startswith("win") else "ubuntu"
    return {"result": [{"user": user, "login-time": time.time() - 86400 * 3}]}


def h_agent_fsinfo(dc, m, q):
    g = F.find_guest(m["node"], m["vmid"])
    if not g or g["status"] != "running":
        return {}
    total = g["maxdisk"]
    used = int(total * F.wobble(0.46, 0.2, g["name"], "fs"))
    if g["ostype"].startswith("win"):
        return {"result": [{"name": "C:", "mountpoint": "C:\\", "type": "NTFS",
                            "total-bytes": total, "used-bytes": used, "disk": []}]}
    return {"result": [{"name": "sda2", "mountpoint": "/", "type": "ext4",
                        "total-bytes": total, "used-bytes": used, "disk": []}]}


def h_agent_info(dc, m, q):
    g = F.find_guest(m["node"], m["vmid"])
    if not g or g["status"] != "running":
        return {}
    return {"result": {"version": "9.0.2", "supported_commands": [
        {"name": n, "enabled": True, "success-response": True} for n in
        ("guest-info", "guest-get-osinfo", "guest-get-host-name",
         "guest-network-get-interfaces", "guest-get-fsinfo", "guest-get-users",
         "guest-get-timezone", "guest-ping", "guest-exec")]}}


ROUTES = [
    (r"^version$", h_version),
    (r"^nodes$", h_nodes),
    (r"^cluster/status$", h_cluster_status),
    (r"^cluster/resources$", h_cluster_resources),
    (r"^cluster/nextid$", h_cluster_nextid),
    (r"^cluster/options$", h_cluster_options),
    (r"^cluster/backup$", h_cluster_backup),
    (r"^cluster/ha/groups$", h_ha_groups),
    (r"^cluster/ha/resources$", h_ha_resources),
    (r"^cluster/ha/status/current$", h_ha_status),
    (r"^cluster/replication$", h_replication),
    (r"^pools$", h_pools),
    (r"^access/users$", h_access_users),
    (r"^access/roles$", h_access_roles),
    (r"^nodes/(?P<node>[^/]+)/status$", h_node_status),
    (r"^nodes/(?P<node>[^/]+)/version$", h_node_version),
    (r"^nodes/(?P<node>[^/]+)/subscription$", h_node_subscription),
    (r"^nodes/(?P<node>[^/]+)/dns$", h_node_dns),
    (r"^nodes/(?P<node>[^/]+)/time$", h_node_time),
    (r"^nodes/(?P<node>[^/]+)/qemu$", h_node_qemu),
    (r"^nodes/(?P<node>[^/]+)/lxc$", h_node_lxc),
    (r"^nodes/(?P<node>[^/]+)/storage$", h_node_storage),
    (r"^nodes/(?P<node>[^/]+)/storage/(?P<storage>[^/]+)/content$", h_storage_content),
    (r"^nodes/(?P<node>[^/]+)/network$", h_node_network),
    (r"^nodes/(?P<node>[^/]+)/tasks$", h_node_tasks),
    (r"^nodes/(?P<node>[^/]+)/rrddata$", h_node_rrd),
    (r"^nodes/(?P<node>[^/]+)/qemu/(?P<vmid>\d+)/status/current$", h_vm_status),
    (r"^nodes/(?P<node>[^/]+)/qemu/(?P<vmid>\d+)/config$", h_vm_config),
    (r"^nodes/(?P<node>[^/]+)/qemu/(?P<vmid>\d+)/pending$", lambda dc, m, q: []),
    (r"^nodes/(?P<node>[^/]+)/qemu/(?P<vmid>\d+)/rrddata$", h_vm_rrd),
    (r"^nodes/(?P<node>[^/]+)/qemu/(?P<vmid>\d+)/snapshot$", h_vm_snapshots),
    (r"^nodes/(?P<node>[^/]+)/qemu/(?P<vmid>\d+)/agent/network-get-interfaces$", h_vm_agent_ifaces),
    (r"^nodes/(?P<node>[^/]+)/qemu/(?P<vmid>\d+)/firewall/rules$", h_vm_firewall_rules),
    (r"^nodes/(?P<node>[^/]+)/qemu/(?P<vmid>\d+)/firewall/options$", h_vm_firewall_options),
]
COMPILED = [(re.compile(p), h) for p, h in ROUTES]


@app.get("/api2/json/{path:path}")
def api(path: str, request: Request):
    dc = dc_for(request)
    q = dict(request.query_params)
    path = path.rstrip("/")
    for rx, handler in COMPILED:
        mo = rx.match(path)
        if mo:
            return ok(handler(dc, mo.groupdict(), q))
    if path not in UNMATCHED:
        UNMATCHED.add(path)
        log.info("unmatched GET %s", path)
    return ok([])


@app.api_route("/api2/json/{path:path}", methods=["POST", "PUT", "DELETE", "PATCH"])
def refuse(path: str, request: Request):
    """The demo instance is strictly read-only."""
    log.warning("refused %s %s", request.method, path)
    return JSONResponse({"errors": {"demo": "read-only demo fixture"}}, status_code=403)


@app.get("/")
def root():
    return {"mock": "proxmox-ve", "readonly": True}
