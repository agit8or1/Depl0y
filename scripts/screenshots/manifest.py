"""Screenshot manifest — the source of truth for the documentation gallery.

Each entry records everything needed to reproduce one capture:

    slug     output filename stem (also the gallery anchor)
    route    SPA path
    theme    "light" or "dark" — applied through Settings -> Appearance
    dwell    seconds to wait after navigation for data/charts to settle
    section  gallery section it belongs to
    title    gallery heading
    caption  one line describing what the operator can accomplish
    alt      descriptive alt text
    action   optional name of an interaction helper in capture.py

Viewport for every capture: 1440x1000 at deviceScaleFactor 2.
Demo data: the isolated fixture stack under scripts/screenshots/demo/
(three synthetic Proxmox endpoints, six BMCs, 45 guests, 8 containers).
"""

VIEWPORT = {"width": 1440, "height": 1000}
DEVICE_SCALE_FACTOR = 2

OVERVIEW = "Overview and dashboards"
INSIGHTS = "Visual insights and monitoring"
WORKFLOWS = "Everyday workflows"
MANAGEMENT = "Management and configuration"
ACCESS = "Access and administration"

SHOTS = [
    # ── Overview and dashboards ───────────────────────────────────────────
    dict(slug="infrastructure-dashboard-dark", route="/", theme="dark", dwell=8,
         section=OVERVIEW, title="Infrastructure dashboard",
         caption="See every registered Proxmox site in one place — guest counts, "
                 "capacity, live throughput and the alerts that need attention.",
         alt="Depl0y dashboard in dark theme showing 50 VMs, 44 running, 8 containers, "
             "288 CPU cores, 2.1 TB RAM and 909 GB storage across three sites, with a "
             "storage warning, per-node status cards, network traffic sparklines and a "
             "recent task feed."),
    dict(slug="infrastructure-dashboard-light", route="/", theme="light", dwell=8,
         section=OVERVIEW, title="Infrastructure dashboard (light)",
         caption="The same dashboard in light theme — Depl0y ships Light, Dark and "
                 "System appearance options.",
         alt="The same Depl0y dashboard rendered in light theme, with identical "
             "totals, alert banner, node status cards and task feed."),
    dict(slug="datacenters-dark", route="/proxmox", theme="dark", dwell=11,
         section=OVERVIEW, title="Datacenters and hosts",
         caption="Compare clusters and standalone hosts side by side, each with its "
                 "own credentials, detected server model and live utilisation.",
         alt="Datacenters page in dark theme with three cards — east-prod with three "
             "nodes, west-prod with two nodes and a standalone Bristol lab host — each "
             "showing PVE version, server model, guest counts and CPU, RAM and disk bars."),
    dict(slug="cluster-status-light", route="/cluster", theme="light", dwell=9,
         action="select_first_host",
         section=OVERVIEW, title="Cluster status",
         caption="Check quorum, node membership and HA state for a cluster at a glance.",
         alt="Cluster status page in light theme listing cluster nodes with quorum "
             "state, node membership and high-availability information."),

    # ── Visual insights and monitoring ────────────────────────────────────
    dict(slug="vm-metrics-dark", route="/proxmox/1/nodes/east-01/vms/103",
         theme="dark", dwell=30, action="wait_for_io",
         section=INSIGHTS, title="VM metrics and history",
         caption="Watch a guest's CPU, memory and I/O live, with an hour of history "
                 "behind it.",
         alt="VM detail page for db-prod-01 in dark theme: running 20 days, CPU gauge at "
             "21 percent, memory 55 percent of 64 GB, network and disk I/O sparklines "
             "with throughput in MB/s, and CPU and memory line charts over the last hour."),
    dict(slug="node-metrics-light", route="/proxmox/1/nodes/east-01", theme="light",
         dwell=12, section=INSIGHTS, title="Node metrics",
         caption="Track a hypervisor's CPU, memory, network and disk trends from the "
                 "node's own RRD data.",
         alt="Node detail page for east-01 in light theme showing CPU, memory, network "
             "and disk utilisation charts alongside the node's guest list."),
    dict(slug="hardware-health-dark", route="/idrac", theme="dark", dwell=12,
         section=INSIGHTS, title="iDRAC / iLO hardware health",
         caption="Read health, power draw and inlet temperature for every BMC-equipped "
                 "server without leaving the panel.",
         alt="iDRAC and iLO management page in dark theme with tiles reading 6 total, 6 "
             "online, 5 healthy, 1 warning and 2008 W total draw, health and power donut "
             "charts, a temperature bar chart per server, and a six-row server table."),
    dict(slug="hardware-inventory-light", route="/idrac", theme="light", dwell=12,
         action="expand_bmc",
         section=INSIGHTS, title="Per-server hardware inventory",
         caption="Drill into one machine for its service tag, firmware, temperatures, "
                 "fan speeds and current power draw.",
         alt="Expanded hardware detail for east-01 in light theme showing manufacturer "
             "Dell, model PowerEdge R750, service tag, BIOS version, 512 GB memory and "
             "dual Xeon Gold CPUs, plus temperature bars, a fan speed chart and a power "
             "usage donut reading 418 W of 1100 W."),
    dict(slug="topology-dark", route="/topology", theme="dark", dwell=11,
         section=INSIGHTS, title="Infrastructure topology",
         caption="Follow the relationships between sites, nodes and the guests running "
                 "on them.",
         alt="Topology view in dark theme drawing registered sites, their nodes and the "
             "guests attached to each node as a connected graph."),
    dict(slug="storage-pools-light", route="/storage-management", theme="light",
         dwell=8, action="select_first_host",
         section=MANAGEMENT, title="Storage pools",
         caption="Review every pool defined on a datacenter — type, which nodes see "
                 "it, what content it accepts and whether it is shared.",
         alt="Storage management page in light theme with DC-East selected, listing "
             "four pools — local (dir), local-lvm (lvmthin), ceph-nvme (rbd) and "
             "pbs-east (pbs) — with the nodes each is available on, content-type "
             "chips, and shared and enabled status."),
    dict(slug="task-history-dark", route="/tasks", theme="dark", dwell=9,
         action="all_proxmox_tasks",
         section=INSIGHTS, title="Task history",
         caption="Review what ran across every cluster, when it ran and whether it "
                 "succeeded.",
         alt="Task list in dark theme showing Proxmox tasks with type, target guest, "
             "node, start time, duration and status."),
    dict(slug="audit-timeline-light", route="/audit-log", theme="light", dwell=8,
         section=INSIGHTS, title="Audit timeline",
         caption="Trace every action back to the account that performed it.",
         alt="Audit log in light theme listing user actions with timestamp, user, action "
             "type, affected resource and result."),

    # ── Everyday workflows ────────────────────────────────────────────────
    dict(slug="vm-inventory-light", route="/vms", theme="light", dwell=16,
         section=WORKFLOWS, title="Virtual machine inventory",
         caption="Find any guest across every site, with its live guest-agent IP and "
                 "one-click actions.",
         alt="Virtual machines list in light theme showing 45 guests with VMID, name, "
             "node, allocated resources, guest-agent IP address, status and Details, "
             "Stop, Restart and Console actions."),
    dict(slug="containers-dark", route="/containers", theme="dark", dwell=14,
         section=WORKFLOWS, title="LXC containers",
         caption="Manage containers next to virtual machines, with the same lifecycle "
                 "controls.",
         alt="Containers list in dark theme showing LXC guests with ID, name, node, "
             "resource allocation, status and lifecycle actions."),
    dict(slug="create-vm-light", route="/vms/create", theme="light", dwell=6,
         action="create_vm_walkthrough",
         section=WORKFLOWS, title="Create a virtual machine",
         caption="Place a new guest deliberately — choose the site, then the node, with "
                 "its current load in front of you.",
         alt="Create Virtual Machine wizard in light theme on the General step, with "
             "DC-East selected, node cards for east-01 to east-03 showing core counts "
             "and live CPU load, and the VM identity fields filled in."),
    dict(slug="create-vm-storage-dark", route="/vms/create", theme="dark", dwell=6,
         action="create_vm_storage_step",
         section=WORKFLOWS, title="Sizing disks and storage",
         caption="Pick the backing pool and disk layout for the new guest from the "
                 "storage actually available on that cluster.",
         alt="Create Virtual Machine wizard in dark theme on the Storage step, offering "
             "storage pool selection, disk size and disk options for the new guest."),
    dict(slug="deploy-llm-light", route="/llm-deploy", theme="light", dwell=9,
         section=WORKFLOWS, title="Deploy an inference VM",
         caption="Stand up an Ollama, llama.cpp, vLLM or LocalAI guest from a guided "
                 "wizard, with optional GPU passthrough.",
         alt="LLM deployment wizard in light theme presenting inference engine choices "
             "and deployment modes."),
    dict(slug="import-vm-dark", route="/import-vm", theme="dark", dwell=8,
         section=WORKFLOWS, title="Import an existing VM",
         caption="Bring in an OVA, OVF, VMDK, VHD or QCOW2 image, or pull a VM straight "
                 "from ESXi or vCenter.",
         alt="VM import page in dark theme offering file upload for OVA, OVF, VMDK, VHD, "
             "VHDX, QCOW2 and RAW images alongside a direct VMware connection option."),
    dict(slug="ha-management-dark", route="/ha-management", theme="dark", dwell=9,
         action="select_first_host",
         section=MANAGEMENT, title="High availability",
         caption="Manage HA groups and the resources assigned to them, with quorum in "
                 "view.",
         alt="High availability management page in dark theme listing HA groups and the "
             "guests assigned to them with their current state."),
    dict(slug="networking-light", route="/network", theme="light", dwell=8,
         action="select_first_host",
         section=MANAGEMENT, title="Networking",
         caption="Inspect the bridges, bonds and VLANs on a node, with pending changes "
                 "surfaced before they apply.",
         alt="Network management page in light theme with a host and node selected, "
             "listing bridges, bonds and physical interfaces with addresses, ports and "
             "active state."),
    dict(slug="backups-light", route="/backup", theme="light", dwell=8,
         action="backup_schedules",
         section=MANAGEMENT, title="Backups",
         caption="Review backup schedules for a datacenter and trigger a run without "
                 "switching tools.",
         alt="Backup page in light theme with a host selected, showing backup schedules "
             "with target storage, mode and retention alongside manual run controls."),
    dict(slug="cloud-images-dark", route="/cloud-images", theme="dark", dwell=8,
         section=MANAGEMENT, title="Cloud images",
         caption="Keep Ubuntu, Debian and Rocky cloud-init templates ready for "
                 "thirty-second deployments.",
         alt="Cloud images page in dark theme listing Ubuntu, Debian and Rocky Linux "
             "cloud image templates with version and availability."),
    dict(slug="iso-images-light", route="/iso-images", theme="light", dwell=8,
         section=MANAGEMENT, title="ISO library",
         caption="Upload and manage installation media on the storage that will serve it.",
         alt="ISO images page in light theme listing uploaded installation ISOs with "
             "size, storage location and actions."),
    dict(slug="settings-appearance-light", route="/settings", theme="light", dwell=8,
         action="open_appearance",
         section=MANAGEMENT, title="Appearance settings",
         caption="Switch the panel between Light, Dark and System themes and set the "
                 "accent colour.",
         alt="Settings page in light theme showing the Appearance section with Light, "
             "Dark and System theme cards and the Light option selected."),

    # ── Access and administration ─────────────────────────────────────────
    dict(slug="user-management-dark", route="/users", theme="dark", dwell=8,
         section=ACCESS, title="Users and roles",
         caption="Give operators their own login with an Admin, Operator or Viewer role "
                 "instead of sharing Proxmox credentials.",
         alt="User management page in dark theme listing accounts with username, email, "
             "role, two-factor status and active state."),
    dict(slug="security-light", route="/security", theme="light", dwell=9,
         section=ACCESS, title="Security controls",
         caption="Review sign-in activity, lockouts and the access rules protecting the "
                 "panel.",
         alt="Security page in light theme showing login activity, failed attempt "
             "handling and access control settings."),
    dict(slug="api-explorer-dark", route="/api-explorer", theme="dark", dwell=9,
         section=ACCESS, title="API explorer",
         caption="Browse and exercise the REST API that every screen in Depl0y is built "
                 "on.",
         alt="API explorer in dark theme listing Depl0y REST endpoints grouped by area "
             "with methods and paths, ready to execute."),
]


def by_section():
    out = {}
    for s in SHOTS:
        out.setdefault(s["section"], []).append(s)
    return out


SECTION_ORDER = [OVERVIEW, INSIGHTS, WORKFLOWS, MANAGEMENT, ACCESS]
