"""
Synthetic inventory for the Depl0y screenshot demo.

Everything here is fictitious:
  * host names use the reserved example.net domain (RFC 2606)
  * IP addresses come from the documentation ranges of RFC 5737
      203.0.113.0/24  -> DC-East
      198.51.100.0/24 -> DC-West
      192.0.2.0/24    -> Lab
  * serial numbers / service tags / MACs are made up

The mock servers that serve this data bind only to 127.0.0.0/8 and are run
inside a private network namespace, so nothing here can reach real hardware.
"""
import hashlib
import math
import time

_T0 = int(time.time())

GiB = 1024 ** 3
MiB = 1024 ** 2

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _seed(*parts) -> int:
    return int(hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()[:8], 16)


def wobble(base: float, spread: float, *key) -> float:
    """Deterministic pseudo-random value around `base`."""
    s = _seed(*key)
    return base + spread * ((s % 2000) / 1000.0 - 1.0)


def mac(vmid: int, idx: int = 0) -> str:
    s = _seed("mac", vmid, idx)
    return "BC:24:11:%02X:%02X:%02X" % ((s >> 16) & 0xFF, (s >> 8) & 0xFF, s & 0xFF)


def series(points: int, step: int, base: float, spread: float, *key):
    """Deterministic wavy time series ending at 'now'."""
    now = int(time.time()) // step * step
    out = []
    s = _seed(*key)
    for i in range(points):
        t = now - (points - 1 - i) * step
        phase = (s % 360) * math.pi / 180.0
        v = base + spread * (
            0.6 * math.sin(i / 7.0 + phase)
            + 0.3 * math.sin(i / 3.0 + phase * 2)
            + 0.1 * math.sin(i / 17.0)
        )
        out.append((t, max(0.0, v)))
    return out


# --------------------------------------------------------------------------
# guests
# --------------------------------------------------------------------------
# (vmid, name, cores, mem_gb, disk_gb, status, ostype, tags, ip, note)

_EAST_01 = [
    (101, "web-prod-01",      4,  8,  120, "running", "l26",  "production;web",       "203.0.113.41"),
    (102, "web-prod-02",      4,  8,  120, "running", "l26",  "production;web",       "203.0.113.42"),
    (103, "db-prod-01",      16, 64,  900, "running", "l26",  "production;database",  "203.0.113.50"),
    (104, "cache-redis-01",   4, 16,   60, "running", "l26",  "production;cache",     "203.0.113.55"),
    (105, "k8s-cp-01",        8, 16,  100, "running", "l26",  "kubernetes;control",   "203.0.113.61"),
    (106, "k8s-worker-01",   16, 64,  400, "running", "l26",  "kubernetes;worker",    "203.0.113.71"),
    (107, "mail-relay-01",    2,  4,   40, "running", "l26",  "production;mail",      "203.0.113.80"),
    (108, "jenkins-01",       8, 32,  300, "running", "l26",  "ci",                   "203.0.113.85"),
    (110, "fileserver-01",    8, 32,  2048, "running", "win11", "production;windows", "203.0.113.90"),
]
_EAST_02 = [
    (111, "web-prod-03",      4,  8,  120, "running", "l26",  "production;web",       "203.0.113.43"),
    (112, "db-prod-02",      16, 64,  900, "running", "l26",  "production;database",  "203.0.113.51"),
    (113, "k8s-cp-02",        8, 16,  100, "running", "l26",  "kubernetes;control",   "203.0.113.62"),
    (114, "k8s-worker-02",   16, 64,  400, "running", "l26",  "kubernetes;worker",    "203.0.113.72"),
    (115, "k8s-worker-03",   16, 64,  400, "running", "l26",  "kubernetes;worker",    "203.0.113.73"),
    (116, "monitoring-01",    8, 32,  500, "running", "l26",  "observability",        "203.0.113.95"),
    (117, "elastic-01",      12, 48,  800, "running", "l26",  "observability",        "203.0.113.96"),
    (118, "backup-proxy-01",  4, 16,  200, "stopped", "l26",  "backup",               None),
    (119, "gitlab-01",        8, 32,  600, "running", "l26",  "ci",                   "203.0.113.86"),
]
_EAST_03 = [
    (121, "k8s-cp-03",        8, 16,  100, "running", "l26",  "kubernetes;control",   "203.0.113.63"),
    (122, "k8s-worker-04",   16, 64,  400, "running", "l26",  "kubernetes;worker",    "203.0.113.74"),
    (123, "nfs-gateway-01",   4, 16,  120, "running", "l26",  "storage",              "203.0.113.100"),
    (124, "vpn-gw-01",        2,  4,   40, "running", "l26",  "network;edge",         "203.0.113.101"),
    (126, "staging-web-01",   4,  8,  120, "running", "l26",  "staging",              "203.0.113.120"),
    (127, "staging-db-01",    8, 32,  400, "running", "l26",  "staging;database",     "203.0.113.121"),
    (128, "dev-sandbox-02",   4, 16,  200, "stopped", "l26",  "dev",                  None),
    (9000, "ubuntu-24.04-cloud-image", 2, 2, 20, "stopped", "l26", "template", None),
    (9001, "debian-12-cloud-image",    2, 2, 20, "stopped", "l26", "template", None),
]
_WEST_01 = [
    (201, "web-dr-01",        4,  8,  120, "running", "l26",  "dr;web",               "198.51.100.41"),
    (202, "db-dr-01",        16, 64,  900, "running", "l26",  "dr;database",          "198.51.100.50"),
    (203, "ad-dc-02",         4, 16,  120, "running", "win11", "production;windows",  "198.51.100.10"),
    (204, "rds-broker-01",    8, 32,  300, "running", "win11", "production;windows",  "198.51.100.11"),
    (205, "veeam-proxy-01",   8, 16,  400, "running", "win11", "backup;windows",      "198.51.100.20"),
    (206, "build-agent-01",   8, 16,  200, "running", "l26",  "ci",                   "198.51.100.61"),
    (207, "build-agent-02",   8, 16,  200, "stopped", "l26",  "ci",                   None),
]
_WEST_02 = [
    (211, "web-dr-02",        4,  8,  120, "running", "l26",  "dr;web",               "198.51.100.42"),
    (212, "fileserver-dr-01", 8, 32, 2048, "running", "win11", "dr;windows",          "198.51.100.90"),
    (213, "sql-report-01",    8, 48,  600, "running", "win11", "production;database", "198.51.100.51"),
    (214, "obs-collector-01", 4, 16,  300, "running", "l26",  "observability",        "198.51.100.95"),
    (215, "test-harness-01",  4,  8,  120, "stopped", "l26",  "dev",                  None),
    (9002, "rocky-9-cloud-image", 2, 2, 20, "stopped", "l26", "template", None),
]
_LAB_01 = [
    (301, "lab-ubuntu-01",    4,  8,   80, "running", "l26",  "lab",                  "192.0.2.41"),
    (302, "lab-rocky-01",     4,  8,   80, "running", "l26",  "lab",                  "192.0.2.42"),
    (303, "llm-inference-01", 8, 48,  400, "running", "l26",  "lab;llm",              "192.0.2.50"),
    (304, "lab-win11-01",     4, 16,  160, "stopped", "win11", "lab;windows",         None),
    (305, "imported-esxi-01", 4, 12,  240, "stopped", "l26",  "lab;imported",         None),
]

# LXC containers: (vmid, name, cores, mem_gb, disk_gb, status)
_CT = {
    "east-01": [(150, "ct-dns-01", 1, 1, 8, "running"), (151, "ct-haproxy-01", 2, 2, 8, "running")],
    "east-02": [(152, "ct-dns-02", 1, 1, 8, "running")],
    "east-03": [(153, "ct-registry-01", 2, 4, 120, "running"), (154, "ct-syslog-01", 1, 2, 60, "running")],
    "west-01": [(250, "ct-dns-03", 1, 1, 8, "running")],
    "west-02": [(251, "ct-haproxy-02", 2, 2, 8, "running")],
    "lab-01": [(350, "ct-lab-tools", 2, 2, 16, "running")],
}


def _counter(base, spread, rate, rate_spread, *key):
    """A byte counter that actually advances, so rate widgets show throughput."""
    elapsed = int(time.time()) - _T0
    return int(wobble(base, spread, *key) + wobble(rate, rate_spread, *key, "rate") * elapsed)


def _guest(rec, node):
    vmid, name, cores, mem_gb, disk_gb, status, ostype, tags, ip = rec
    template = 1 if "template" in tags else 0
    running = status == "running"
    maxmem = mem_gb * GiB
    return {
        "vmid": vmid,
        "name": name,
        "node": node,
        "cores": cores,
        "sockets": 2 if cores >= 16 else 1,
        "maxmem": maxmem,
        "mem": int(maxmem * wobble(0.58, 0.22, name, "mem")) if running else 0,
        "maxdisk": disk_gb * GiB,
        "disk": 0,
        "maxcpu": cores,
        "cpu": round(wobble(0.18, 0.16, name, "cpu"), 4) if running else 0,
        "status": status,
        "template": template,
        "ostype": ostype,
        "tags": tags,
        "ip": ip,
        "uptime": int(wobble(1_100_000, 900_000, name, "up")) if running else 0,
        "netin": _counter(4.2e10, 3.8e10, 2.4e6, 2.0e6, name, "netin") if running else 0,
        "netout": _counter(3.1e10, 2.7e10, 1.7e6, 1.4e6, name, "netout") if running else 0,
        "diskread": _counter(9.5e10, 8e10, 1.1e6, 0.9e6, name, "dr") if running else 0,
        "diskwrite": _counter(6.5e10, 5e10, 1.9e6, 1.6e6, name, "dw") if running else 0,
    }


# --------------------------------------------------------------------------
# nodes / datacenters
# --------------------------------------------------------------------------

NODES = {
    "east-01": dict(
        ip="203.0.113.11", cores=64, sockets=2, mhz="2000",
        cpu_model="Intel(R) Xeon(R) Gold 6338 CPU @ 2.00GHz",
        mem_gb=512, mem_pct=0.61, cpu_pct=0.34, root_gb=440, root_pct=0.38,
        uptime=4_912_800, guests=_EAST_01,
        model="Dell PowerEdge R750", bmc="idrac", bmc_ip="203.0.113.21",
        service_tag="7KJ4X29", bios="2.13.3", bmc_fw="7.10.30.00", gen="14G Monolithic",
        health="OK", watts=418, temp=27.0, dimms=16, dimm_gb=32,
        drives=[("SSD", 1_920_383_410_176, "Dell Ent NVMe P5600 MU", 6)],
    ),
    "east-02": dict(
        ip="203.0.113.12", cores=64, sockets=2, mhz="2000",
        cpu_model="Intel(R) Xeon(R) Gold 6338 CPU @ 2.00GHz",
        mem_gb=512, mem_pct=0.72, cpu_pct=0.47, root_gb=440, root_pct=0.87,
        uptime=4_912_200, guests=_EAST_02,
        model="Dell PowerEdge R750", bmc="idrac", bmc_ip="203.0.113.22",
        service_tag="7KJ4X31", bios="2.13.3", bmc_fw="7.10.30.00", gen="14G Monolithic",
        health="OK", watts=463, temp=29.0, dimms=16, dimm_gb=32,
        drives=[("SSD", 1_920_383_410_176, "Dell Ent NVMe P5600 MU", 6)],
    ),
    "east-03": dict(
        ip="203.0.113.13", cores=48, sockets=2, mhz="2100",
        cpu_model="Intel(R) Xeon(R) Gold 6230R CPU @ 2.10GHz",
        mem_gb=384, mem_pct=0.41, cpu_pct=0.23, root_gb=440, root_pct=0.31,
        uptime=1_604_000, guests=_EAST_03,
        model="Dell PowerEdge R740xd", bmc="idrac", bmc_ip="203.0.113.23",
        service_tag="6BQ2M14", bios="2.19.1", bmc_fw="6.10.80.00", gen="14G Monolithic",
        # one DIMM flagged -> gives the hardware view a real, readable warning state
        health="Warning", warn_dimm="DIMM.Socket.B3", watts=352, temp=31.0,
        dimms=12, dimm_gb=32,
        drives=[("SSD", 960_197_124_096, "Dell Ent SSD SAS MU", 8)],
    ),
    "west-01": dict(
        ip="198.51.100.11", cores=40, sockets=2, mhz="2200",
        cpu_model="Intel(R) Xeon(R) Gold 5218R CPU @ 2.10GHz",
        mem_gb=256, mem_pct=0.66, cpu_pct=0.58, root_gb=220, root_pct=0.46,
        uptime=2_784_000, guests=_WEST_01,
        model="Dell PowerEdge R640", bmc="idrac", bmc_ip="198.51.100.21",
        service_tag="5FTL903", bios="2.21.2", bmc_fw="6.10.80.00", gen="14G Monolithic",
        health="OK", watts=311, temp=24.0, dimms=12, dimm_gb=16,
        drives=[("SSD", 960_197_124_096, "Dell Ent SSD SAS MU", 6)],
    ),
    "west-02": dict(
        ip="198.51.100.12", cores=40, sockets=2, mhz="2200",
        cpu_model="Intel(R) Xeon(R) Gold 5218R CPU @ 2.10GHz",
        mem_gb=256, mem_pct=0.44, cpu_pct=0.29, root_gb=220, root_pct=0.33,
        uptime=2_783_400, guests=_WEST_02,
        model="Dell PowerEdge R640", bmc="idrac", bmc_ip="198.51.100.22",
        service_tag="5FTL911", bios="2.21.2", bmc_fw="6.10.80.00", gen="14G Monolithic",
        health="OK", watts=268, temp=23.0, dimms=12, dimm_gb=16,
        drives=[("SSD", 960_197_124_096, "Dell Ent SSD SAS MU", 6)],
    ),
    "lab-01": dict(
        ip="192.0.2.11", cores=32, sockets=2, mhz="2300",
        cpu_model="Intel(R) Xeon(R) Gold 5218 CPU @ 2.30GHz",
        mem_gb=192, mem_pct=0.29, cpu_pct=0.13, root_gb=220, root_pct=0.22,
        uptime=903_600, guests=_LAB_01,
        model="HPE ProLiant DL380 Gen10", bmc="ilo", bmc_ip="192.0.2.21",
        service_tag="CZJ0240XYZ", bios="U30 v2.90", bmc_fw="2.81 Jul 20 2024", gen="iLO 5",
        health="OK", watts=196, temp=22.0, dimms=8, dimm_gb=32,
        drives=[("HDD", 1_200_243_695_616, "HPE EG001200JWJNQ", 8)],
    ),
}

DATACENTERS = [
    dict(
        key="east", name="DC-East · Ashburn", hostname="pve-east.example.net",
        loopback="127.0.0.11", cluster="east-prod", nodes=["east-01", "east-02", "east-03"],
        pve_version="8.4.1", kversion="6.8.12-9-pve",
        storages=[
            ("local", "dir", "iso,vztmpl,backup", 440 * GiB, 0.38, 0),
            ("local-lvm", "lvmthin", "images,rootdir", 1600 * GiB, 0.52, 0),
            ("ceph-nvme", "rbd", "images,rootdir", 46.0 * 1024 * GiB, 0.47, 1),
            ("pbs-east", "pbs", "backup", 96.0 * 1024 * GiB, 0.61, 1),
        ],
    ),
    dict(
        key="west", name="DC-West · Reno", hostname="pve-west.example.net",
        loopback="127.0.0.12", cluster="west-prod", nodes=["west-01", "west-02"],
        pve_version="8.4.1", kversion="6.8.12-9-pve",
        storages=[
            ("local", "dir", "iso,vztmpl,backup", 220 * GiB, 0.46, 0),
            ("local-lvm", "lvmthin", "images,rootdir", 880 * GiB, 0.58, 0),
            ("nfs-west", "nfs", "images,iso,backup", 18.0 * 1024 * GiB, 0.54, 1),
        ],
    ),
    dict(
        key="lab", name="Lab · Bristol", hostname="pve-lab.example.net",
        loopback="127.0.0.13", cluster=None, nodes=["lab-01"],
        pve_version="8.3.5", kversion="6.8.12-8-pve",
        storages=[
            ("local", "dir", "iso,vztmpl,backup", 220 * GiB, 0.22, 0),
            ("local-zfs", "zfspool", "images,rootdir", 3.6 * 1024 * GiB, 0.34, 0),
        ],
    ),
]

DC_BY_KEY = {d["key"]: d for d in DATACENTERS}
DC_BY_HOST = {d["hostname"]: d for d in DATACENTERS}
NODE_TO_DC = {n: d for d in DATACENTERS for n in d["nodes"]}
BMC_BY_IP = {n["bmc_ip"]: (name, n) for name, n in NODES.items()}


def guests_of(node_name):
    return [_guest(r, node_name) for r in NODES[node_name]["guests"]]


def containers_of(node_name):
    out = []
    for vmid, name, cores, mem_gb, disk_gb, status in _CT.get(node_name, []):
        maxmem = mem_gb * GiB
        out.append({
            "vmid": vmid, "name": name, "node": node_name, "type": "lxc",
            "status": status, "cpus": cores, "maxcpu": cores,
            "cpu": round(wobble(0.06, 0.05, name, "cpu"), 4),
            "maxmem": maxmem, "mem": int(maxmem * wobble(0.45, 0.2, name, "mem")),
            "maxdisk": disk_gb * GiB, "disk": int(disk_gb * GiB * wobble(0.4, 0.2, name, "d")),
            "uptime": int(wobble(1_200_000, 600_000, name, "up")), "template": 0,
        })
    return out


def find_guest(node_name, vmid):
    for g in guests_of(node_name):
        if g["vmid"] == int(vmid):
            return g
    return None
