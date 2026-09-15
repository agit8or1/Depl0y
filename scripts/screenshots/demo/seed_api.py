"""Populate the demo instance through Depl0y's own REST API.

Runs after the demo backend is up: registers the three synthetic datacenters,
polls them (which creates the node records from the mock Proxmox API), attaches
BMC credentials to every node and kicks off a BMC poll against mock Redfish.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as F  # noqa: E402

BASE = os.environ.get("DEMO_API", "http://127.0.0.1:8010/api/v1")
PW = os.environ["DEMO_ADMIN_PASSWORD"]
TOKEN = None


def call(method, path, body=None, form=None, quiet=False):
    url = BASE + path
    data, headers = None, {}
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        if not quiet:
            print(f"  !! {method} {path} -> {e.code} {detail}")
        raise


import urllib.parse  # noqa: E402

# ---- wait for backend -----------------------------------------------------
for _ in range(90):
    try:
        urllib.request.urlopen(BASE.replace("/api/v1", "/") , timeout=3).read()
        break
    except Exception:
        time.sleep(1)
else:
    sys.exit("backend never came up")

# ---- login ----------------------------------------------------------------
tok = call("POST", "/auth/login", {"username": "admin", "password": PW})
TOKEN = tok["access_token"]
print("logged in")

# ---- register datacenters -------------------------------------------------
existing = {h["name"]: h for h in call("GET", "/proxmox/")}
host_ids = {}
for dc in F.DATACENTERS:
    if dc["name"] in existing:
        host_ids[dc["key"]] = existing[dc["name"]]["id"]
        continue
    created = call("POST", "/proxmox/", {
        "name": dc["name"],
        "hostname": dc["hostname"],
        "port": 8006,
        "username": "depl0y@pve",
        "api_token_id": "depl0y@pve!panel",
        "api_token_secret": "00000000-0000-4000-8000-000000000000",
        "verify_ssl": False,
    })
    host_ids[dc["key"]] = created["id"]
    print(f"registered {dc['name']} -> host {created['id']}")

# ---- poll so node rows get created ---------------------------------------
for key, hid in host_ids.items():
    call("POST", f"/proxmox/{hid}/poll")
time.sleep(12)

# ---- attach BMC credentials to each node ---------------------------------
for key, hid in host_ids.items():
    nodes = call("GET", f"/proxmox/{hid}/nodes")
    for nd in nodes:
        spec = F.NODES.get(nd["node_name"])
        if not spec:
            continue
        call("PATCH", f"/proxmox/nodes/{nd['id']}/idrac", {
            "idrac_hostname": spec["bmc_ip"],
            "idrac_port": 443,
            "idrac_username": "demo",
            "idrac_password": "demo",
            "idrac_type": spec["bmc"],
            "idrac_use_ssh": False,
        })
        print(f"  bmc attached: {nd['node_name']} -> {spec['bmc_ip']} ({spec['bmc']})")

# ---- poll the BMCs --------------------------------------------------------
call("POST", "/idrac/poll")
for _ in range(40):
    time.sleep(2)
    cache = call("GET", "/idrac/status") or {}
    ready = [k for k, v in cache.items() if v.get("model")]
    print(f"  bmc cache: {len(ready)}/{len(F.NODES)} resolved")
    if len(ready) >= len(F.NODES):
        break

print(json.dumps(call("GET", "/dashboard/summary"), indent=2))
