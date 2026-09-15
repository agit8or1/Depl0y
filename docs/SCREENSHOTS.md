# Screenshot tour

Captured from a running Depl0y build at 1600×900 in the dark theme.

> **About this data.** Every screenshot on this page comes from an isolated demo
> instance whose Proxmox and Redfish responses are synthetic fixtures served on
> loopback inside a private network namespace. Host names use the reserved
> `example.net` domain and addresses come from the RFC 5737 documentation ranges
> (`203.0.113.0/24`, `198.51.100.0/24`, `192.0.2.0/24`). No real infrastructure
> was contacted and nothing was started, stopped or migrated to take these
> pictures.

---

## Infrastructure overview

[![Depl0y dashboard showing 50 VMs, 44 running, 8 containers, 288 CPU cores, 2.1 TB RAM and 909 GB storage in use across three registered Proxmox sites, with a storage warning on east-02, per-node CPU and RAM cards, live network throughput per node, and a feed of recent Proxmox tasks.](images/github/01-infrastructure-overview.png)](images/github/01-infrastructure-overview.png)

Totals across every registered endpoint, a draggable widget grid, and alerts
raised from the polled node data. Each tile links through to the view behind it.

---

## Datacenters and hosts

[![Datacenters page with three cards: east-prod with 3 nodes, west-prod with 2 nodes, and a standalone Bristol lab host, each showing PVE version, detected server model, guest counts and CPU, RAM and disk usage bars.](images/github/02-datacenters.png)](images/github/02-datacenters.png)

Two clusters and one standalone host, each registered with its own credentials.
The model chip is resolved from the BMC and can be overridden by hand; the
lightning menu on each card carries both the Proxmox-side and BMC-side power
actions.

---

## iDRAC / iLO overview

[![iDRAC and iLO management page: tiles reading 6 total, 6 online, 5 healthy, 1 warning and 2008 W total draw, health and power donuts, a temperature bar chart per server, and a table of six servers with power, health, temperature, watts and model.](images/github/03-hardware-redfish.png)](images/github/03-hardware-redfish.png)

Six machines across three sites in one table — Dell PowerEdge over iDRAC and an
HPE ProLiant over iLO. east-03 is flagged Warning because its BMC is reporting a
correctable memory error on a DIMM.

---

## Per-server hardware detail

[![Expanded hardware detail for east-01: manufacturer Dell, model PowerEdge R750, service tag, BIOS version, hostname, 512 GB memory, dual Xeon Gold 6338, BMC address, plus temperature bars, fan speed chart and a power usage donut reading 418 W of 1100 W.](images/github/07-hardware-detail.png)](images/github/07-hardware-detail.png)

System information straight from Redfish, with temperatures, fan speeds and
current draw against the chassis capacity. The tabs above hold the CPU, DIMM,
drive, NIC, firmware and system-event-log inventories.

---

## Virtual machine inventory

[![Virtual machines list showing 45 VMs with columns for VMID, name, node, resources, guest-agent IP address, status and per-row Details, Stop, Restart and Console actions.](images/github/06-vm-inventory.png)](images/github/06-vm-inventory.png)

Every guest across every registered endpoint, with the live IP reported by the
QEMU guest agent, filters by status and node, and per-row actions.

---

## VM detail

[![VM detail page for db-prod-01: running for 20 days, CPU gauge at 21.6 percent, memory at 55 percent of 64 GB, network I/O at 11.2 MB/s in and 3.2 MB/s out, and CPU and memory charts over the last hour.](images/github/04-vm-detail.png)](images/github/04-vm-detail.png)

Overview tab with live gauges and an hour of RRD history. The other tabs cover
config, hardware, disks, network, snapshots, backup, replication, firewall,
power schedule, console and per-VM access.

---

## Creating a VM

[![Create Virtual Machine wizard on the General step, with a datacenter selected, node cards showing core counts and live CPU load, and the VM name and hostname filled in.](images/github/05-deploy-vm.png)](images/github/05-deploy-vm.png)

Six steps — General, Hardware, Storage, Network, Cloud-Init, Confirm. Node
selection shows current load so you can place the guest deliberately.

---

The `screenshots/` directory at the repository root holds captures from much
older releases (v1.x, light theme). They no longer reflect the interface and
some of them still show real host names, so they are not linked here.
