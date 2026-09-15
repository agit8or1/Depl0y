# Feature reference

The complete catalogue of what Depl0y does. The [README](../README.md) covers the
short version; this page is the detail.

---

## Proxmox VE management

**Virtual machines**
Start / stop / reboot / suspend / resume, configuration editing (CPU, RAM, disks,
NICs), snapshots, clone, migrate, convert to template, per-VM firewall rules,
noVNC console and a QEMU serial terminal. (The console page loads the noVNC
client from `cdn.jsdelivr.net`, so the browser needs outbound access to it.)

**LXC containers**
Lifecycle, configuration editing, snapshots, and an xterm.js terminal.

**Nodes**
RRD metric charts, VM and LXC listings, storage browser, network configuration,
task log, node terminal, and OS-level shutdown / reboot through `pvesh`.

**Cluster**
Status, node list, HA groups and resources, quorum monitoring. Nodes can be
joined to a cluster (the fingerprint is fetched automatically) or removed.

**Replication**
Job create / edit / delete, force-sync, and log viewer.

**Node evacuation**
Migrate every VM off a node onto the remaining online nodes.

**Firewall**
Cluster-, node- and VM-level rules, security groups and IPsets.

**Backup**
Schedule CRUD, manual triggers, and Proxmox Backup Server datastore browsing.

**Storage**
Pool management, content browsing, ISO and cloud-image management.

**Networking**
Bridge / bond / VLAN configuration with apply-pending support, plus SDN/VNet views.

**Offline tolerance**
Host and node endpoints (`status`, `vms`, `lxc`, `tasks`) return clean empty
payloads when a node is powered off, so a dead node does not take the dashboard
down with it.

---

## Multi-environment view

- **Multiple Proxmox endpoints** in one installation, each with its own
  credentials (API token or username/password) and TLS verification setting.
- **Aggregate summary** — VM, node and storage totals computed across every
  registered endpoint.
- **Federated dashboard** — cross-site VM and node overview in a single view.
- **Map view** — registered sites plotted on an OpenStreetMap/Leaflet map, marked
  online or offline. (Requires outbound access to the tile server from the
  browser.)

---

## Out-of-band hardware (iDRAC / iLO)

- **Redfish dashboard** — health, power state, temperature and wattage for every
  BMC-equipped server in one table, backed by a background poller.
- **Two-section power menu** on host cards, node cards and the iDRAC page. The
  top section acts through the Proxmox OS (graceful shutdown / reboot via
  `pvesh`); the bottom section acts through the BMC (Power On, Force Off,
  Graceful Off, Reset, Power Cycle, PXE). The BMC path is the only one that can
  power on a machine that is fully off.
- **Server model detection** — Redfish `Model`, then Dell `SystemPID`, then Dell
  `SystemID`, then a PCI subsystem lookup, then the manager generation tag. This
  resolves PowerEdge model names even on 13G boxes where the standard `Model`
  field is blank.
- **Manual model override** — editable model chip on the host/node card,
  persisted in `system_settings`. Needed for older iDRAC 7 BMCs that expose no
  model metadata at all.
- **Configurable poll interval** — 1 / 2 / 5 / 10 minutes, stored globally; the
  backend reschedules the job and queues an immediate poll when it changes.
- **Continuous post-poll refresh** — "Refresh All" / "Poll Now" re-reads the
  cache every 1.5 s for about 20 s, so each server appears as soon as its own BMC
  answers rather than after the slowest one.
- **Hardware inventory** — CPUs, DIMMs, storage controllers and drives, firmware
  versions, BMC NICs, and the system event log.
- **Daily firmware check (Dell only)** — Dell's public catalog XML is parsed daily
  and compared against installed BIOS / iDRAC versions, with direct support
  links. HPE firmware is inventoried but not version-checked.
- **Vendors** — Dell iDRAC (7 / 8 / 9) and HPE iLO over Redfish v1, plus
  SSH-based hardware reporting for hosts whose BMC does not answer Redfish.
  A legacy TLS adapter is mounted so iDRAC 7 boxes negotiate successfully.

---

## Dashboard

- Drag-and-drop widget grid with a masonry layout.
- Widgets for CPU, RAM, storage, network traffic, disk I/O, VM status, alerts,
  activity feed, node status grid, recent tasks and quick actions.
- Every tile links through to the management view behind it.
- Each widget refreshes on its own schedule.

---

## Deployment and import

**Cloud images**
Built-in catalogue of Ubuntu 20.04 / 22.04 / 24.04 LTS, Debian 11 / 12 and
Rocky Linux 8 / 9 generic cloud images, with cloud-init injection — hostname,
user, SSH key, static IP, DNS and package lists.

**VM import**
Upload OVA, OVF, VMDK, VHD, VHDX, QCOW2 or RAW images, or connect to an ESXi
host or vCenter and pull VMs over the network (pyVmomi). OVF descriptors are
parsed for name, CPU, RAM, disk and OS type; VMDK/VHD/VHDX disks are converted
to qcow2 with `qemu-img`.

**LLM deployment**
Runs an open-source LLM as a self-hosted VM. Start from the model catalogue —
open-weight models such as Llama 3.2 (1B/3B/8B), Qwen 2.5 (0.5B–7B, including
the Coder variants), Gemma 2 and Phi-3.5 Mini — each listed with its parameter
count, download size, context length and VRAM requirement, filterable by
category (chat, code, vision, reasoning, embedding) and by size. Depl0y then
builds the guest and installs the serving stack around the chosen model.

Engines: Ollama, llama.cpp (GGUF), vLLM (OpenAI-compatible) and LocalAI, plus
Stable Diffusion (ComfyUI). Optional NVIDIA (CUDA) or AMD (ROCm) GPU passthrough
with driver installation, and add-ons such as Open WebUI. Simple mode asks four
questions; advanced mode exposes the full engine / model / GPU / OS / storage
matrix. Deployed instances are tracked on their own tab.

---

## Access control and auditing

- **Roles** — Admin, Operator and Viewer, enforced at the route level.
- **2FA** — TOTP with QR-code enrolment and backup codes.
- **Encryption at rest** — Proxmox passwords, API token secrets and BMC
  passwords are stored Fernet-encrypted using the key in
  `/etc/depl0y/config.env`.
- **Audit log** — every user action and system change, with filtering.
- **Rate limiting** and standard security headers on the API.
- **Per-host permissions** — users can be scoped to specific Proxmox endpoints.

---

## Operations

- **VM update management** — check and install OS updates on managed Linux VMs
  over SSH, with live streaming output and a configurable automatic check
  interval.
- **Alerts** — rule-based alerting with an event history.
- **Notifications** — in-app notification centre and webhook dispatch.
- **Bulk operations** — act on many guests at once.
- **Tasks** — running and historical Proxmox task views.
- **API explorer** — browse and exercise the Depl0y REST API from inside the panel.
- **Time sync audit** — compare and remediate clock drift across nodes.
- **Topology view** — a graph of registered sites, nodes and guests.

---

## API

- Swagger UI: `/api/v1/docs`
- ReDoc: `/api/v1/redoc`
- In-app: sidebar → **API Explorer**
