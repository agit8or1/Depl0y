# Node maintenance: preview and verified evacuation

Use this before patching, rebooting or repairing a Proxmox node. Depl0y first shows a read-only
plan for every VM and container on the node. You can then move the guests you pick, one at a
time. Each move is checked again before it starts and confirmed on its target after it ends.
Depl0y never shuts down, reboots or powers off the node. That stays a separate step.

## Walkthrough

### 1. Open the preview

**Cluster Overview → Nodes → Maintenance** on the node. Depl0y marks the node as under maintenance
in the page and opens the **Maintenance** panel. Opening the preview changes nothing in Proxmox:
it only makes GET calls. Any user with access to the host can open it (viewer, operator, admin).

### 2. Read the cluster checks

| Check | Meaning |
|---|---|
| ✓ Cluster is quorate | Required. Proxmox refuses migrations without quorum. |
| ✓ / ⚠ Quorum holds without this node | ⚠ means shutting the node down would cost quorum. Evacuating is still fine; do not power the node off until another node is back. |
| ✕ Not enough RAM on the other nodes | Running guests need more RAM than the other online nodes have free (after a 10% reserve on each). |
| ⚠ Some guests do not fit | There is enough RAM in total, but no single node can take a guest once the earlier moves are placed. |
| ℹ node is in HA maintenance mode | HA is already moving HA guests away; that node is never used as a target. |
| ⚠ The Proxmox token cannot carry out this plan | Names each missing privilege (see *Permissions*). |

If any check marked ✕ is about the cluster itself (not a cluster, source node offline, no
quorum, no other node online), the plan cannot be carried out at all.

### 3. Read each guest's row

Every guest gets a **class**, a **destination** (node, plus a storage mapping when its disks land on a
storage with a different ID), and a **reason**.

| Class | What it means | What happens if you run it |
|---|---|---|
| **Movable online** | A running VM that can live-migrate, or a stopped guest (offline migration, nothing to interrupt). | Selected by default. |
| **Downtime required** | A running container (restart migration: stop, move, start) or a running VM with mapped PCI/USB devices (cold move: shut down, migrate, start on the target). | Never selected by default. You tick it **and** confirm the downtime. |
| **Blocked** | It cannot move. The reason says why and what to do. | Cannot be selected. |
| **Unknown** | Depl0y could not read the guest or its configuration. | Cannot be selected. Fix the cause and preview again. |

Placement is greedy, biggest memory first. RAM and destination disk space are reserved as each
guest is placed, so the last guests see what the earlier moves leave. Stopped guests need no RAM on
the target. Disk space counts each disk's provisioned size, so thin disks are over-counted (the
safe direction). For a **Blocked** guest, *Why not other nodes* lists every node and the reason it
was rejected.

What is evaluated, and what blocks a guest:

- **Local disks**: copied during the migration (live for running VMs). They go to the same storage
  ID on the target if it has room. Otherwise they go to a local storage of the same type, then any
  other local storage, with the `ha-zfs` HA pool last. ZFS disks already replicated to the target
  copy nothing. A guest with replication jobs can only go to a replication target.
- **Shared storage**: the target must have the storage active.
- **Bind mounts (containers)**: blocked unless the mount point is marked `shared=1` (then a warning
  that the path must exist on the target).
- **Attached ISOs**: an ISO on node-local storage blocks the move (Proxmox refuses it). Eject it and
  preview again. An ISO on shared storage needs that storage on the target. Cloud-init drives are
  not ISOs; Proxmox regenerates them.
- **PCI/USB passthrough**: raw `hostpciN` and `usbN: host=` devices and container `devN` entries
  block the move: they only exist on this node. Resource-mapped devices (`mapping=`) need a cold
  move to a node where the mapping has a device. SPICE USB redirection is fine.
- **HA placement**: HA guests go only to nodes running `pve-ha-lrm`. A strict node-affinity rule
  (or a restricted group on Proxmox VE 8) limits the targets. Negative resource-affinity rules keep
  guests apart and positive ones keep them together. If a rule prefers the node you are evacuating and
  failback is on, HA would move the guest straight back. That guest is blocked until you enable HA
  maintenance on the node (`ha-manager crm-command node-maintenance enable <node>`) or change the
  rule. Guests listed as HA resources (even `ignored` or `disabled` ones), with disks on node-local
  LVM/directory storage, or on local ZFS without a replication job, are blocked, because HA
  migrations do not copy local disks. HA VMs that would need a cold move are blocked as well.
- **Capacity**: vCPUs (a guest with more vCPUs than the target has CPUs), RAM, and destination
  disk space. All of these are counted cumulatively.
- **Locks**: a guest locked by a backup, snapshot or migration is blocked until the lock clears.
- **Templates**: they move offline. A template whose linked clones share its local disks is blocked.
- **Warnings** (not blockers): CPU type `host` (live migration can fail between different CPUs);
  cloud-init snippets (`cicustom`) on node-local storage, which must be copied to the target
  before the guest's next boot. Also shown when Proxmox's own migration check was not available
  (read-only token), in which case the preview relies on the guest configuration alone.

### 4. Run the plan (admins)

Pick the guests and click **Move N guests**. For guests that need downtime, also tick *I accept
downtime for …*. The plan is valid for two hours and only the admin who opened it can run it.
Preview again if it expired or the cluster changed.

The job then works through the guests **one at a time**:

1. **Recheck.** It reads the cluster again and checks the reviewed target on its own. The guest is
   **skipped**, never sent elsewhere, if any of these is true:
   - the target is offline or in HA maintenance,
   - the target is short on RAM or storage,
   - the guest's configuration changed since review (Proxmox config digest),
   - it was started or stopped (so it now needs a different kind of move),
   - its storage mapping would differ,
   - a cluster check fails.
2. **Move.**
   - Live: `migrate online=1`, plus `with-local-disks` and `targetstorage` when needed.
   - Offline: `migrate`.
   - Restart (containers): `migrate restart=1`.
   - Cold: `shutdown`, then `migrate`, then `start` on the target.
3. **Follow the task.** Depl0y polls the Proxmox task until it ends, for up to 6 hours, since copies
   of large local disks take time. A task that is only queued or running is not a move. A task that
   ends with `WARNINGS` still has to pass the location check. If the task's node stops answering,
   Depl0y keeps waiting while the guest stays locked by the migration. On failure it records the
   exit status and the last lines of the task log.
4. **Verify.** The guest must appear on the planned target in the expected state (running if it was
   running) before it counts as **moved**. For HA guests, Proxmox's `hamigrate` task ends as soon as
   the request is queued, so only the observed location counts. If HA never acts, or puts the guest
   into the error state, the move is **failed**. If HA placed the guest on a different node, it is
   **moved elsewhere** and the node it landed on is shown.

**Stop after current move** finishes the migration that is running (it is not interrupted) and
marks the rest **cancelled**.

### 5. Read the result

Each guest ends as one of:

| Status | Meaning |
|---|---|
| `moved` | The task ended OK and the guest was seen on its planned target. |
| `already_moved` | It was already on its target (a retry). |
| `moved_elsewhere` | Off the node, but on a different node than planned (for example HA chose it). |
| `skipped` | The recheck failed. The reason is shown and nothing was changed. |
| `failed` | The task failed, could not be followed, or the guest did not appear on the target. The guest's current location is shown. A failed cold move starts the guest again where it is. |
| `cancelled` | Stopped before it started. |

The job ends as one of:

| Job status | Meaning |
|---|---|
| `done` | Every selected guest is on its planned target. |
| `deviated` | Every selected guest is off the node, but at least one is not where the plan put it. Check that node's capacity. |
| `partial` | Some succeeded. |
| `failed` | None succeeded. |
| `cancelled` | Stopped before every guest had its turn. |

The job also lists anything still on the node.

**Retry** is safe. **Select N to retry** opens a fresh preview and selects the guests that failed,
were skipped or were cancelled. Guests that already moved are off the node and no longer listed.
Running the same plan again also works: guests already on their target are recorded as
`already_moved` and are not migrated twice. Only one evacuation runs per cluster at a time. If the
Depl0y backend restarts mid-job, the Proxmox task carries on. The guest stays locked
(`migrate`) and shows as blocked until the task ends. Then preview again.

### 6. Power the node down (separately)

Once the job reports that the node has no guests left, shut down or reboot it from the node page,
the BMC panel or Proxmox. Check the quorum line from step 2 first. Afterwards, click **Exit Maint.**
and, if you enabled it, turn HA maintenance off:
`ha-manager crm-command node-maintenance disable <node>`. Guests do not move back on their own,
except HA guests whose rules prefer the node.

## Permissions

**Depl0y roles.** Anyone with access to the host can open the preview and follow a job. Only admins
can run or stop an evacuation. Operators cannot.

**Proxmox API token.** The preview reads the token's privileges (`GET /access/permissions`) and
lists what is missing. The run is refused up front (HTTP 403) if the token lacks a privilege the
selected moves need. Privileges set on a parent path count, which approximates Proxmox's
propagation.

| Needed for | Privilege | Path |
|---|---|---|
| Preview (read-only) | `Sys.Audit` | `/nodes` (or `/`) |
| | `VM.Audit` | `/vms` |
| | `Datastore.Audit` | `/storage` |
| | `Mapping.Audit` (only with mapped devices) | `/mapping` |
| Proxmox's own migration precheck (optional) | `VM.Migrate` | `/vms/<vmid>` |
| Every move | `VM.Migrate` | `/vms/<vmid>` |
| Cold moves | `VM.PowerMgmt` | `/vms/<vmid>` |
| Disk copies | `Datastore.AllocateSpace` | `/storage/<destination>` |
| Mapped devices | `Mapping.Use` | `/mapping/<pci or usb>/<id>` |

A read-only profile (for example the built-in `PVEAuditor` role) can open the full preview. Without
`VM.Migrate`, Proxmox's precheck is skipped and the preview says so, then falls back to the guest
configuration. Running the plan is refused, with the missing privileges listed. These are the
minimum privileges for this feature only. The rest of Depl0y uses the same token and needs more.

```bash
pveum role add Depl0yMaintPreview --privs "Sys.Audit VM.Audit Datastore.Audit Mapping.Audit"
pveum role add Depl0yEvacuate --privs "Sys.Audit VM.Audit Datastore.Audit Mapping.Audit VM.Migrate VM.PowerMgmt Datastore.AllocateSpace Mapping.Use"
```

## API

```
GET  /api/v1/cluster/{host_id}/nodes/{node}/maintenance/preview      -> plan (plan_id, checks, guests, summary, targets, permissions)
POST /api/v1/cluster/{host_id}/nodes/{node}/evacuate                  admin
     {"plan_id": "...", "guests": ["vm:100", "ct:200"], "allow_downtime": ["ct:200"]}
     guests omitted = every "online" guest in the plan; a downtime guest must be in allow_downtime
GET  /api/v1/cluster/{host_id}/evacuations                            recent jobs (kept in memory for a day)
GET  /api/v1/cluster/{host_id}/evacuations/{job_id}                   per-guest status, steps, what is left on the node
POST /api/v1/cluster/{host_id}/evacuations/{job_id}/cancel            admin; stops after the current move
```

`POST .../evacuate` without a `plan_id` is refused (HTTP 422). Before 2.2.115 it queued a
round-robin migration of every VM with no checks.

## Limits

- Plans and jobs are kept in memory. A backend restart forgets them, but the Proxmox tasks are
  not affected.
- Proxmox VE 9 node-affinity and resource-affinity rules, and Proxmox VE 8 HA groups, are
  understood. Proxmox's own HA maintenance mode is detected, not switched on.
- Destination disk space is checked against what Proxmox reports as available on the storage.
  ZFS/LVM-thin over-provisioning is not modelled beyond provisioned sizes.
