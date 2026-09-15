# Screenshot gallery

27 views of Depl0y — 13 dark, 14 light — captured at 1440×1000 at 2× from the running application.

[← Back to the README](../README.md) · [▶ Watch the walkthrough](https://github.com/agit8or1/Depl0y/releases/download/v2.2.74/depl0y-walkthrough.mp4)

> **Demo data.** Every screenshot comes from an isolated demo instance whose Proxmox and Redfish responses are synthetic fixtures served on loopback inside a private network namespace. Host names use the reserved `example.net` domain and addresses come from the RFC 5737 documentation ranges (`203.0.113.0/24`, `198.51.100.0/24`, `192.0.2.0/24`). No real infrastructure was reachable during capture, and nothing was started, stopped, migrated or deleted to stage a picture. Regenerate them with [`scripts/screenshots/`](../scripts/screenshots/README.md).

## Contents

- [Overview and dashboards](#overview-and-dashboards)
- [Visual insights and monitoring](#visual-insights-and-monitoring)
- [Everyday workflows](#everyday-workflows)
- [Management and configuration](#management-and-configuration)
- [Access and administration](#access-and-administration)

---

## Overview and dashboards

### Infrastructure dashboard

**🌙 Dark** · `/`

[![Depl0y dashboard in dark theme showing 50 VMs, 44 running, 8 containers, 288 CPU cores, 2.1 TB RAM and 909 GB storage across three sites, with a storage warning, per-node status cards, network traffic sparklines and a recent task feed.](images/github/infrastructure-dashboard-dark.png)](images/github/infrastructure-dashboard-dark.png)

See every registered Proxmox site in one place — guest counts, capacity, live throughput and the alerts that need attention. · [Full size](images/github/infrastructure-dashboard-dark.png)

### Infrastructure dashboard (light)

**☀️ Light** · `/`

[![The same Depl0y dashboard rendered in light theme, with identical totals, alert banner, node status cards and task feed.](images/github/infrastructure-dashboard-light.png)](images/github/infrastructure-dashboard-light.png)

The same dashboard in light theme — Depl0y ships Light, Dark and System appearance options. · [Full size](images/github/infrastructure-dashboard-light.png)

### Datacenters and hosts

**🌙 Dark** · `/proxmox`

[![Datacenters page in dark theme with three cards — east-prod with three nodes, west-prod with two nodes and a standalone Bristol lab host — each showing PVE version, server model, guest counts and CPU, RAM and disk bars.](images/github/datacenters-dark.png)](images/github/datacenters-dark.png)

Compare clusters and standalone hosts side by side, each with its own credentials, detected server model and live utilisation. · [Full size](images/github/datacenters-dark.png)

### Cluster status

**☀️ Light** · `/cluster`

[![Cluster status page in light theme listing cluster nodes with quorum state, node membership and high-availability information.](images/github/cluster-status-light.png)](images/github/cluster-status-light.png)

Check quorum, node membership and HA state for a cluster at a glance. · [Full size](images/github/cluster-status-light.png)


---

## Visual insights and monitoring

### VM metrics and history

**🌙 Dark** · `/proxmox/1/nodes/east-01/vms/103`

[![VM detail page for db-prod-01 in dark theme: running 20 days, CPU gauge at 21 percent, memory 55 percent of 64 GB, network and disk I/O sparklines with throughput in MB/s, and CPU and memory line charts over the last hour.](images/github/vm-metrics-dark.png)](images/github/vm-metrics-dark.png)

Watch a guest's CPU, memory and I/O live, with an hour of history behind it. · [Full size](images/github/vm-metrics-dark.png)

### Node metrics

**☀️ Light** · `/proxmox/1/nodes/east-01`

[![Node detail page for east-01 in light theme showing CPU, memory, network and disk utilisation charts alongside the node's guest list.](images/github/node-metrics-light.png)](images/github/node-metrics-light.png)

Track a hypervisor's CPU, memory, network and disk trends from the node's own RRD data. · [Full size](images/github/node-metrics-light.png)

### iDRAC / iLO hardware health

**🌙 Dark** · `/idrac`

[![iDRAC and iLO management page in dark theme with tiles reading 6 total, 6 online, 5 healthy, 1 warning and 2008 W total draw, health and power donut charts, a temperature bar chart per server, and a six-row server table.](images/github/hardware-health-dark.png)](images/github/hardware-health-dark.png)

Read health, power draw and inlet temperature for every BMC-equipped server without leaving the panel. · [Full size](images/github/hardware-health-dark.png)

### Per-server hardware inventory

**☀️ Light** · `/idrac`

[![Expanded hardware detail for east-01 in light theme showing manufacturer Dell, model PowerEdge R750, service tag, BIOS version, 512 GB memory and dual Xeon Gold CPUs, plus temperature bars, a fan speed chart and a power usage donut reading 418 W of 1100 W.](images/github/hardware-inventory-light.png)](images/github/hardware-inventory-light.png)

Drill into one machine for its service tag, firmware, temperatures, fan speeds and current power draw. · [Full size](images/github/hardware-inventory-light.png)

### Infrastructure topology

**🌙 Dark** · `/topology`

[![Topology view in dark theme drawing registered sites, their nodes and the guests attached to each node as a connected graph.](images/github/topology-dark.png)](images/github/topology-dark.png)

Follow the relationships between sites, nodes and the guests running on them. · [Full size](images/github/topology-dark.png)

### Task history

**🌙 Dark** · `/tasks`

[![Task list in dark theme showing Proxmox tasks with type, target guest, node, start time, duration and status.](images/github/task-history-dark.png)](images/github/task-history-dark.png)

Review what ran across every cluster, when it ran and whether it succeeded. · [Full size](images/github/task-history-dark.png)

### Audit timeline

**☀️ Light** · `/audit-log`

[![Audit log in light theme listing user actions with timestamp, user, action type, affected resource and result.](images/github/audit-timeline-light.png)](images/github/audit-timeline-light.png)

Trace every action back to the account that performed it. · [Full size](images/github/audit-timeline-light.png)


---

## Everyday workflows

### Virtual machine inventory

**☀️ Light** · `/vms`

[![Virtual machines list in light theme showing 45 guests with VMID, name, node, allocated resources, guest-agent IP address, status and Details, Stop, Restart and Console actions.](images/github/vm-inventory-light.png)](images/github/vm-inventory-light.png)

Find any guest across every site, with its live guest-agent IP and one-click actions. · [Full size](images/github/vm-inventory-light.png)

### LXC containers

**🌙 Dark** · `/containers`

[![Containers list in dark theme showing LXC guests with ID, name, node, resource allocation, status and lifecycle actions.](images/github/containers-dark.png)](images/github/containers-dark.png)

Manage containers next to virtual machines, with the same lifecycle controls. · [Full size](images/github/containers-dark.png)

### Create a virtual machine

**☀️ Light** · `/vms/create`

[![Create Virtual Machine wizard in light theme on the General step, with DC-East selected, node cards for east-01 to east-03 showing core counts and live CPU load, and the VM identity fields filled in.](images/github/create-vm-light.png)](images/github/create-vm-light.png)

Place a new guest deliberately — choose the site, then the node, with its current load in front of you. · [Full size](images/github/create-vm-light.png)

### Sizing disks and storage

**🌙 Dark** · `/vms/create`

[![Create Virtual Machine wizard in dark theme on the Storage step, offering storage pool selection, disk size and disk options for the new guest.](images/github/create-vm-storage-dark.png)](images/github/create-vm-storage-dark.png)

Pick the backing pool and disk layout for the new guest from the storage actually available on that cluster. · [Full size](images/github/create-vm-storage-dark.png)

### Deploy an inference VM

**☀️ Light** · `/llm-deploy`

[![LLM deployment wizard in light theme presenting inference engine choices and deployment modes.](images/github/deploy-llm-light.png)](images/github/deploy-llm-light.png)

Stand up an Ollama, llama.cpp, vLLM or LocalAI guest from a guided wizard, with optional GPU passthrough. · [Full size](images/github/deploy-llm-light.png)

### Import an existing VM

**🌙 Dark** · `/import-vm`

[![VM import page in dark theme offering file upload for OVA, OVF, VMDK, VHD, VHDX, QCOW2 and RAW images alongside a direct VMware connection option.](images/github/import-vm-dark.png)](images/github/import-vm-dark.png)

Bring in an OVA, OVF, VMDK, VHD or QCOW2 image, or pull a VM straight from ESXi or vCenter. · [Full size](images/github/import-vm-dark.png)


---

## Management and configuration

### Storage pools

**☀️ Light** · `/storage-management`

[![Storage management page in light theme with DC-East selected, listing four pools — local (dir), local-lvm (lvmthin), ceph-nvme (rbd) and pbs-east (pbs) — with the nodes each is available on, content-type chips, and shared and enabled status.](images/github/storage-pools-light.png)](images/github/storage-pools-light.png)

Review every pool defined on a datacenter — type, which nodes see it, what content it accepts and whether it is shared. · [Full size](images/github/storage-pools-light.png)

### High availability

**🌙 Dark** · `/ha-management`

[![High availability management page in dark theme listing HA groups and the guests assigned to them with their current state.](images/github/ha-management-dark.png)](images/github/ha-management-dark.png)

Manage HA groups and the resources assigned to them, with quorum in view. · [Full size](images/github/ha-management-dark.png)

### Networking

**☀️ Light** · `/network`

[![Network management page in light theme with a host and node selected, listing bridges, bonds and physical interfaces with addresses, ports and active state.](images/github/networking-light.png)](images/github/networking-light.png)

Inspect the bridges, bonds and VLANs on a node, with pending changes surfaced before they apply. · [Full size](images/github/networking-light.png)

### Backups

**☀️ Light** · `/backup`

[![Backup page in light theme with a host selected, showing backup schedules with target storage, mode and retention alongside manual run controls.](images/github/backups-light.png)](images/github/backups-light.png)

Review backup schedules for a datacenter and trigger a run without switching tools. · [Full size](images/github/backups-light.png)

### Cloud images

**🌙 Dark** · `/cloud-images`

[![Cloud images page in dark theme listing Ubuntu, Debian and Rocky Linux cloud image templates with version and availability.](images/github/cloud-images-dark.png)](images/github/cloud-images-dark.png)

Keep Ubuntu, Debian and Rocky cloud-init templates ready for thirty-second deployments. · [Full size](images/github/cloud-images-dark.png)

### ISO library

**☀️ Light** · `/iso-images`

[![ISO images page in light theme listing uploaded installation ISOs with size, storage location and actions.](images/github/iso-images-light.png)](images/github/iso-images-light.png)

Upload and manage installation media on the storage that will serve it. · [Full size](images/github/iso-images-light.png)

### Appearance settings

**☀️ Light** · `/settings`

[![Settings page in light theme showing the Appearance section with Light, Dark and System theme cards and the Light option selected.](images/github/settings-appearance-light.png)](images/github/settings-appearance-light.png)

Switch the panel between Light, Dark and System themes and set the accent colour. · [Full size](images/github/settings-appearance-light.png)


---

## Access and administration

### Users and roles

**🌙 Dark** · `/users`

[![User management page in dark theme listing accounts with username, email, role, two-factor status and active state.](images/github/user-management-dark.png)](images/github/user-management-dark.png)

Give operators their own login with an Admin, Operator or Viewer role instead of sharing Proxmox credentials. · [Full size](images/github/user-management-dark.png)

### Security controls

**☀️ Light** · `/security`

[![Security page in light theme showing login activity, failed attempt handling and access control settings.](images/github/security-light.png)](images/github/security-light.png)

Review sign-in activity, lockouts and the access rules protecting the panel. · [Full size](images/github/security-light.png)

### API explorer

**🌙 Dark** · `/api-explorer`

[![API explorer in dark theme listing Depl0y REST endpoints grouped by area with methods and paths, ready to execute.](images/github/api-explorer-dark.png)](images/github/api-explorer-dark.png)

Browse and exercise the REST API that every screen in Depl0y is built on. · [Full size](images/github/api-explorer-dark.png)

---

## More tools from MSPReboot

Depl0y is built and maintained alongside other operations tooling at [mspreboot.com](https://mspreboot.com).

[← Back to the README](../README.md)
