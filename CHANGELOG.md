# Changelog

All notable changes to Depl0y will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.36] - 2026-04-21 🛰️ Guest Agent info on VM Overview

### Added
- **New "Guest Agent" card on the VM Overview tab** showing everything the QEMU guest agent reports: hostname, OS name + version + kernel, timezone, agent version, logged-in users, network interfaces (with MAC + all IPv4/IPv6 addresses), and mounted filesystems (used / total + percent).
- **Endpoint:** `GET /api/v1/pve-vm/{h}/{node}/{vmid}/guest-agent` — aggregates `get-host-name`, `get-osinfo`, `get-timezone`, `get-users`, `get-fsinfo`, `network-get-interfaces`, `info`. Each sub-call wrapped in its own try/except so a missing command doesn't blank the whole response. 30-second server-side cache.
- **Graceful empty state** when the agent isn't responding — lists the 3 steps to enable it (turn on QEMU Guest Agent in Options → install `qemu-guest-agent` in the guest → reboot).

### Verified
- VM 120 (Ubuntu 24.04) on pve2: hostname=ubuntu, kernel 6.8.0-106-generic, eth0 at 192.168.22.69, 3 filesystems, qemu-guest-agent 8.2.2.

## [2.2.35] - 2026-04-21 🌗 PCIPassthrough dark-mode contrast

### Fixed
- **"Available PCI Devices on Node" was near-white in dark mode.** `PCIPassthrough.vue` referenced CSS variables that don't exist in this project's theme (`--bg-secondary`, `--bg-hover`). The `var(x, #f8f9fa)` fallback kicked in and rendered a light-grey block on dark backgrounds. Replaced with real theme vars (`--surface`) and an alpha-tint hover state that works in both themes. Also dropped stale hex fallbacks on vars that *do* exist (`--bg-card`, `--border-color`, `--text-secondary`) so a missed context doesn't flash light values.

## [2.2.34] - 2026-04-21 ✂️ VM Config + Hardware tab declutter

### Changed
- **Removed the 22 "Current: `xxx`" hints** scattered below every field label — the input already shows the current value. The hints just doubled the label height.
- **Dropped the 6 per-field Save buttons** on single-value text inputs (name, sockets, cores, memory, balloon, boot). They now **auto-save on blur + Enter** with a subtle "Saving…" / "Saved" chip — same UX as the dropdowns. Multi-field rows (Sockets × Cores groups, Audio, Startup order, Hotplug, RNG, SPICE, SMBIOS) keep explicit Save buttons because partial-save would break them.
- **Description textarea** keeps its Save button (blur-save while typing prose is hostile).
- **Tightened section padding** (1rem → 0.75rem) and grid gaps (0.85rem → 0.55rem) so the Config and Hardware tabs feel like a settings page, not a wizard.

Result: the CPU / Memory card alone dropped from ~12 buttons + 6 "Current:" spans to 2 buttons + no duplicate labels.

## [2.2.33] - 2026-04-21 🧹 VM details tabs layout polish

### Changed
- **Config / Hardware / Options tabs** reorganized into clearly-labeled sections with a consistent 2-column settings grid. Related fields group together instead of a long flat form: e.g. Hardware splits into **CPU**, **Machine & Firmware**, **Display / Controllers / Audio**; Options into **Guest OS**, **Startup & Hotplug**, **Devices & Integration**, **Toggles**.
- **Auto-save on change** for single-value dropdowns (CPU Type, BIOS, Machine Type, VGA, scsihw, OS Type) with a subtle "Saving…" / "Saved" chip. 400ms debounce. Multi-field rows (Sockets × Cores, Audio, Startup-order, Hotplug, RNG, SPICE, SMBIOS) keep explicit Save buttons.
- **Boolean fields** rendered as uniform toggle cards in a grid instead of scattered checkboxes.
- **Tables** (Disks / CD-ROMs / Unused / Network / Backup archives / Replication jobs) switched to a `.table-tidy` style: sticky headers, uniform 40-px rows, uppercase header labels, right-aligned action column with tooltip-only icons where space is tight.
- **Tab strip**: added scrollbar styling so it scrolls cleanly when the 14 tabs overflow on narrow viewports.

### Under the hood
- New script helpers wrap the existing save handlers with debounce + chip flash — `autoSaveConfig / autoSaveOpt / autoSaveHw / autoSaveHwCpu`. **No API calls changed.** Business logic untouched; this is pure layout + UX polish.
- All new styles use theme CSS variables (`--border-color`, `--surface`, `--bg-card`, `--text-primary`, `--text-secondary`, `--primary-color`) so dark-mode inherits correctly.

## [2.2.32] - 2026-04-21 📺 VM console aspect ratio fix

### Fixed
- **VM console was stretched / wrong size.** The canvas had `width: 100% !important; height: 100% !important` forced via CSS, which overrode noVNC's internal sizing and ignored the guest's native aspect ratio. Canvas now uses `max-width/max-height: 100%` so noVNC's `scaleViewport` controls actual dimensions, and the container is a flex centerer. Default scale mode changed to `local` (client-side scaling) so it works without guest-agent/mode-setting cooperation.

## [2.2.31] - 2026-04-21 🛑 PBS Delete-was-misleading + VM console WebSocket fix

### Fixed
- **iDRAC Management's PBS row had a "Delete" button that deleted the entire PBS server** when the user only wanted to remove the iDRAC config. Replaced with **"Clear BMC"** matching the PVE-node row's behavior. Tooltip explicitly states it does not remove the PBS entry. Full PBS-server deletion still lives on the PBS Management page where it belongs.
- **VM console WebSocket failed with code 1006** ("connection closed abnormally"). The backend always replied `Sec-WebSocket-Protocol: binary` even when the browser sent no subprotocol — per RFC 6455 the browser must reject any subprotocol it didn't request. Console relay now only echoes `binary` when the client actually asked for it. Fix applied to all 3 accept sites in `console.py` (per-VM, per-host, per-LXC paths).

## [2.2.30] - 2026-04-20 🔁 PBS sync visibility + Create Sync Job + Run Now

### Added
- **PBS Remotes** are now surfaced separately on the PBS Management dashboard. The "no sync jobs configured" message used to be misleading when a remote was defined but no scheduled pull job existed (true on pbs1 → PBS2). Card now reads e.g. `"No sync jobs yet. 1 remote configured but no scheduled pull. Use + Create Sync Job…"`.
- **Create Sync Job** button + modal: pick local datastore, pick remote, the form scans the remote (`/config/remote/{remote}/scan`) to enumerate its datastores, set schedule (defaults to `hourly`), optional `remove-vanished`. One-click create.
- **Run Now** button on each existing sync job — kicks off the job immediately and refreshes the summary 3s later.
- New endpoints: `GET /pbs-mgmt/{id}/remotes`, `GET /pbs-mgmt/{id}/remotes/{name}/scan`, `POST /pbs-mgmt/{id}/sync-jobs`, `DELETE /pbs-mgmt/{id}/sync-jobs/{job_id}`. `POST /pbs-mgmt/{id}/jobs/{job_id}/run` already existed; now exposed in the API client as `pbsMgmt.runJob`.
- PBS service: `get_remotes()`, `get_remote_datastores()`, `create_sync_job()`, `delete_sync_job()`.

### Notes
- pbs1's "discrepancy in space used vs pbs2" is the natural consequence of having no sync job — backups land on pbs1 and never replicate. After clicking **+ Create Sync Job** with PBS2 selected, scheduled hourly, the gap will close on the next run. Use **Run Now** to do a one-shot pull immediately.
- Cross-PBS drift alerts + automated remediation deferred to a follow-up — needs a scheduler job + alert_rule wiring.

## [2.2.29] - 2026-04-20 🎫 PBS password (ticket) auth

### Fixed
- **Adding a PBS server with password auth worked (server was saved), but all management endpoints then returned 400** "PBS server has no API token configured". The PBS client literally said password-only auth was "not supported"; callers gated on `api_token_id` being present.
  - `PBSService` now supports PBS's standard **ticket-based auth**: POSTs `{username, password}` to `/api2/json/access/ticket`, receives a ticket + `CSRFPreventionToken`, attaches them as the `PBSAuthCookie` cookie and CSRF header for subsequent requests. Ticket cached per host for 100 minutes (PBS tickets live 2h).
  - `_make_service()` now accepts either API token OR username+password; 400 only when neither is configured.
- **Form accessibility warnings** — added `autocomplete="username"` on the Username field and `autocomplete="off"` on the API Token ID.

### Verified
- Fresh password-auth PBS server: `/datastores`, `/jobs`, `/summary` all return 200.

## [2.2.28] - 2026-04-20 🩹 PBS add form + SEL cache + clear retry

### Fixed
- **Add PBS server required an API Token ID** even when password auth would do. Form now has an explicit "Authentication method" toggle (Password / API token). Only the fields for the chosen method are validated/submitted. Backend already accepted either — this is a UI-only fix.
- **iDRAC event log slow to load (pbs1 iDRAC 7 takes ~5s per fetch).** Added a 15-second TTL cache for `/pbs/{id}/idrac/logs` and `/idrac/node/{id}/logs`. First fetch unchanged (~5s cold); subsequent tab switches serve from cache in ~7ms. Cache is busted automatically when you hit Clear Event Log.
- **`clear_sel()` could fail on iDRAC 7's TLS handshake hiccups** (BadStatusLine). Now retries each endpoint once with a 500ms delay, and skips on HTTP 404 to the next fallback cleanly. The dual-path (Redfish generic → Dell OEM) is preserved.

### Clarified (not a code change)
- pbs1's lingering "Warning" is a **real hardware fault**, not a stale log. `bmc_status_cache` now reports `"health_reasons": ["Memory DIMMSLOTA4: Warning"]`. Reseat or replace the DIMM in slot A4 — the log-clear button can't fix a live component fault.

## [2.2.27] - 2026-04-20 📦 PBS dashboard, PVE+PBS updates, VM feature parity

### Added — PBS Management dashboard
- Per-PBS summary card showing total capacity, used/available, a colored usage gauge (green/amber/red by threshold), configured sync jobs with last-run state + next-run timestamp, and 24h backup activity (OK vs failed counts). Auto-refreshes every 60s.
- Endpoint: `GET /api/v1/pbs-mgmt/{id}/summary`.
- Gracefully degrades with an `error` field when PBS is unreachable or a sub-endpoint (e.g. `/config/pull` on older PBS builds) returns 404.

### Added — PVE + PBS update management
- New consolidated **Updates** dashboard at `/updates` (admin-only): single table with a row per PVE node and per PBS server, showing pending count, last-checked timestamp, Refresh and Apply actions.
- Refresh triggers a cached `apt-get update`, returns a UPID that's hooked into the task bar.
- Apply runs `dist-upgrade` via the Proxmox/PBS apt APIs, registered with `task_tracker` so progress shows at the top of the UI.
- Endpoints under `/api/v1/updates-mgmt/`:
  - `GET /overview` — whole-fleet pending counts.
  - `GET|POST /pve/{host_id}/{node}` (list / refresh / apply / task-status).
  - `GET|POST /pbs/{server_id}` (same shape).
- Permissions: list = any authenticated user; refresh = operator+; apply = **admin**, with a 5-min per-target rate limit + audit log entry.

### Added — VM management parity with Proxmox UI (task #9)
- **Hardware tab**: Display (VGA), SCSI Controller (`scsihw`), Audio Device (`audio0`), EFI Disk add/remove (for OVMF VMs), TPM v1.2/v2.0 add/remove.
- **Options tab**: OS Type (`ostype`), Hotplug chips (disk/net/usb/cpu/mem), ACPI, KVM hardware virt, Tablet pointer, Freeze CPU at startup, Guest reboot behavior, Start/Shutdown order + up-delay/down-delay, VirtIO RNG (`rng0`), SPICE Enhancements, SMBIOS1.
- **Backup tab**: one-click vzdump to any backup-capable storage + archive history table.
- **Replication tab**: list/add/edit/delete/run-now VM-scoped replication jobs.
- New endpoints: `POST|DELETE /pve-vm/{h}/{n}/{id}/tpm`, `.../efidisk`, `POST .../backup`, `GET .../backups`, `GET|POST|PUT|DELETE .../replication[/{job}]`, `POST .../replication/{job}/run`.
- Deferred: `qm monitor` console, per-VM IPSet/Alias firewall sub-tabs, per-package selection UI in the update Apply modal, kernel-reboot-required indicator.

## [2.2.26] - 2026-04-20 ⏱️ Progress parsing for externally-started tasks

### Fixed
- **Migration progress still wrong when migration was started outside depl0y.** `/tasks/running` explicitly skipped the progress parser for `source=proxmox` tasks (anything pulled from the cluster active list rather than initiated via our UI). Added `TaskTracker.progress_for_external(upid, host_id, node, started_at, task_type)` which fetches the task log (with an 8s TTL cache to avoid hammering PVE) and runs the same percentage parser. Monotonic per-UPID so a flaky poll can't move the bar backwards.
- Falls back to a time-based estimate capped at 60% when the log hasn't produced a percentage yet.
- Cache self-prunes when a task disappears from the running list.

## [2.2.25] - 2026-04-20 ⏱️ Accurate migration progress + VM edit audit

### Fixed
- **VM migration progress bar was overly optimistic.** `estimate_progress()` returned `elapsed / fixed_duration * 100` capped at 95%. For a qmigrate with `duration=300`, the bar hit 50% at 2.5 min elapsed regardless of actual migration state — so a large VM with 30 GB memory and 8 Gbps link could show 95% while it was still half-transferred.
  - Background poller now fetches the running task's log on each 5-second poll and extracts the highest `\d+(\.\d+)?%` it finds (matches Proxmox's `migration status: mem X%`, `transferred: N of M (Z%)`, `xfer X MB Y%`, etc.).
  - Parsed progress is monotonic (never moves backwards).
  - Time-based fallback capped at 60% instead of 95% — so until the log yields a real number, the bar can't lie past the halfway mark.

### Notes
- Task #9 — User asked for "rename / reconfigure / same features as Proxmox UI". Most of this already exists: `VMDetail.vue` (7.2k lines) has inline-edit for name, CPU cores, memory, disk, NIC, boot order, description, tags, cloud-init, ISO. Backend `vm_config.py` exposes: full config PUT, start/stop/reboot/suspend/resume, snapshots, clone, migrate, template convert, delete, disks (add/resize/move/detach/reattach/unused), NICs (add/update/remove), firewall rules+options, VNC ticket, cloud-init regenerate, tags (add/remove/bulk), PCI/USB/serial add+remove. If you're missing something specific, let me know which screen/action and I'll wire it.

## [2.2.24] - 2026-04-20 📜 Fix PBS event log loading after clear

### Fixed
- **PBS event log stuck on "Loading…" after clear** — loadServerDetail was routing PBS log reads through SSH because `isOsSshPrimary` is set on PBS. When `idrac_hostname` is a dedicated BMC (as with pbs1 on .12), SSH lands on iDRAC's racadm shell, not the OS journal — so the log fetch returned nothing. Logs now always try Redfish SEL first; only fall back to OS SSH journal if Redfish returns empty AND it's a legacy PBS where idrac_hostname == hostname.
- Empty event log now shows a friendly "Event log is empty" message instead of an empty table. Tells the user that health will refresh on the next 2-min poll.

## [2.2.23] - 2026-04-20 🔧 Per-DIMM health reasons + responsive detail load + Clear SEL shortcut

### Added
- BMC status cache now includes `health_reasons` — a list of the specific components currently reporting non-OK (e.g. `"Memory DIMMSLOTA4: Warning"`). Rendered in the Detected Issues panel on the Overview tab when per-sensor data isn't available, so real faults show up instead of the generic "no specific issues" message.
- `compute_current_health()` now drills into `/Systems/.../Memory` when the `MemorySummary` is non-OK to identify which DIMM slot is at fault (previously only said "Memory: Warning").
- "Clear the BMC event log" link inside the Detected Issues panel when the warning appears stale — operator no longer has to open the Logs tab to find the button.

### Fixed
- **iDRAC Details appeared stuck loading for slow BMCs (pbs1 iDRAC 7 takes 5–20s per Redfish call).** `loadServerDetail` was using `Promise.allSettled` on four parallel iDRAC calls, so the panel stayed blank until the slowest one finished. Now each of Info / Thermal / Power / SSH-Hardware writes its result into reactive state as it arrives; the Overview panel renders within ~5s instead of waiting ~20s.
- `_clearingSel` is now initialized on every wrapped server so the Clear button's disabled state works on first render.

### Notes
- pbs1 shows Warning because DIMM slot A4 genuinely reports `Status.Health=Warning` (capacity 15625 MiB / 16 GB — suggesting ECC issue). This is a real current fault — clearing the SEL will not resolve it. Consider reseating or replacing that DIMM.

## [2.2.22] - 2026-04-20 🩺 Current-state health, Clear SEL, Node Monitor IO Wait fix

### Added
- **Clear Event Log** button in the iDRAC Details → Logs tab for PVE nodes, PBS servers, and standalone BMCs. Clears the BMC System Event Log (no effect on hardware or guests). Tries Redfish's generic `LogService.ClearLog` first, falls back to Dell OEM `DellLogService.ClearLog` for older iDRACs.
- `POST /api/v1/idrac/node/{id}/clear-sel`, `POST /api/v1/idrac/{host_id}/clear-sel`, `POST /api/v1/idrac/standalone/{id}/clear-sel`, `POST /api/v1/pbs/{id}/idrac/clear-sel` (operator+, logged).

### Fixed
- **iDRAC "Warning" stuck on after incidents clear** — e.g. pve01 and pbs1 showing PSU warnings when every PSU currently reads OK. Root cause: Dell's rollup `Status.Health` incorporates stale SEL entries. Scheduler now recomputes overall health from *current* component-level state (PowerSupplies, Fans, Temperatures, Processors, MemorySummary) and prefers that over the rollup. Clearing the event log is still the right fix if you'd like the iDRAC's own web UI to also clear.
- **Node Monitor "IO Wait" showed all 0%** — data was correct (Proxmox returns iowait as a 0.0–1.0 fraction which `*100` converts to percent). Healthy hosts sit near 0.005%, which `toFixed(1)` rounded down to `0.0%`. New `fmtPct()` helper renders `<0.01%` for tiny values and 2 decimals for sub-1% values. Title changed to **"CPU I/O Wait"** with a tooltip explaining the metric.

## [2.2.21] - 2026-04-20 🧹 Reports page polish: delete, dark-mode, AI/Logic split

### Added
- **Delete reports** — new `DELETE /api/v1/ai-reports/reports/{id}` (operator+) and a delete icon per row in the Reports list. Confirms before deleting.
- **AI vs Logic source filter** on the Reports list with a per-row badge so deterministic reports are distinguishable from LLM-composed ones.

### Fixed
- **Dark-mode contrast on Reports pages** — `AIReports.vue`, `AIReportDetail.vue`: hardcoded white/gray/indigo colors replaced with theme variables (`--bg-card`, `--surface`, `--text-primary`, `--text-secondary`, `--border-color`). Severity chips and finding backgrounds use low-alpha tints that render correctly on both themes.
- **View / Regenerate button contrast** — button variants rewritten to transparent with theme-aware foreground instead of `background: white; color: #2563eb`. Adds a new `.btn-danger-outline` for the delete action.
- The "Raw Evidence" tab's embedded HTML renderer still uses a light background (its inline CSS is tuned for print) — intentional, single exception.

### Changed
- Menu label `🤖 AI Reports` → `📊 Reports` (URL stays `/ai-reports/*`).
- Report list rows are now fully clickable to open the detail page.

## [2.2.20] - 2026-04-20 🤖 AI Reports subsystem + dashboard cleanup

### Added
- **AI Reports** — new subsystem under `/ai-reports` (admin-only). Generate deterministic infrastructure reports now; add an OpenAI key under Settings to get AI-composed narrative + prioritized recommendations on top of the rules engine.
  - Report types: Health, Optimization, Redundancy, Power/Cost, Hardware Refresh, Capacity, Comprehensive.
  - Scopes: global, cluster, node.
  - Scheduling: daily / weekly / monthly / cron (daily/weekly/monthly fully automated; cron checked hourly for now).
  - Exports: Markdown + printable HTML.
  - Power/cost model: configurable kWh rate, per-node idle/load watt profiles, auto-prefers measured watts from `bmc_status_cache` when available.
  - Rules engine: CPU/RAM/storage pressure, HA gaps, backup coverage heuristics, uneven distribution, oversized allocations, under-utilized nodes, aging hardware (R420/520/620/720), headroom risk, high-cost/low-util combined, BMC warnings.
  - Hardware advisor: refresh class recommendations (R750/R760, EPYC-density, NVMe-first) with rationale — heuristics only, no fabricated pricing.
  - Metric snapshots: `node_metric_snapshots` captured every 5 min, pruned to 30 days.
  - New tables: `ai_provider_settings`, `power_cost_settings`, `node_power_profiles`, `ai_report_runs`, `ai_report_schedules`, `node_metric_snapshots`. Created via `create_all()` on startup — no Alembic run required.
  - Secrets: OpenAI key Fernet-encrypted via existing `ENCRYPTION_KEY`; never returned in responses.
  - Provider abstraction so a second LLM provider can be slotted in later.
  - 16 new endpoints under `/api/v1/ai-reports/*`.

### Fixed
- **Main Dashboard had duplicate tiles** — the big "rsb-card" row (VMs/Nodes/Storage/CPU/RAM) was followed by a small "rt-card" trending row that re-showed CPU/RAM/Storage %. Removed the duplicate row and folded trend arrows (↑/↓/→) into the main tiles.
- **Dashboard did not show total storage** — `/api/v1/dashboard/summary` now returns `storage_total_gb`. The Storage tile displays "X GB / Y GB total" even before the richer `/resources` payload loads.

## [2.2.19] - 2026-04-20 🔧 iDRAC unified IP, parallel poll, clickable dashboards

### Fixed
- **iDRAC polling never finished / missing data** — `run_bmc_poll` now polls all BMCs concurrently with a `ThreadPoolExecutor`. Full cycle drops from 150–300s serial to ~52s, and a slow or unreachable BMC no longer blocks the rest. SSH is wrapped in its own try/except so paramiko channel-open timeouts don't abort the Redfish + PCI lookup phases.
- **pve2 showed "Dell PowerEdge (13G)" instead of R730xd** — SSH timeout was aborting the block that runs the Proxmox PCI subsystem lookup. Lookup now always runs when Redfish returns a generic generation label.
- **pbs1 displayed no/low data after setting a dedicated BMC IP** — scheduler no longer forces PBS SSH to `idrac_hostname`; scheduler now always tries both Redfish and SSH against the single BMC IP.
- **`/pbs/*/idrac/ssh/hardware` and `/ssh/logs` returning 502** — iDRAC SSH (racadm CLI) can't execute Linux commands. These endpoints now return an empty shape with `_ssh_error` instead of erroring, so Redfish data still renders in the UI.
- **`/api/v1/tasks/running` missed live migrations** — switched to `tasks.get(source="active")`. The old call returned completed tasks only.
- **Cloud-init images miscounted as real VMs** — added `is_cloud_template()` heuristic (matches `template=1`, names containing `-cloud-image`/`_cloud_image`/`-cloudinit`, or vmid 9000-9999 + stopped + "cloud" in name). Applied to `get_vms`, dashboard summaries, and cluster overview counts.
- **`/api/v1/dashboard/summary` 500** — `is_cloud_template` was imported into the wrong function scope; promoted to module-level import.

### Changed
- **Removed "Use SSH instead of HTTPS (Redfish)" checkbox in Edit BMC** — one IP per BMC, both protocols always attempted using the same credentials. `idrac_use_ssh` retained as legacy DB column but ignored.
- **Redfish default timeout: 10s → 20s** — iDRAC 7 is slow under concurrent requests.

### Added
- **Clickable dashboards everywhere** — stat cards, count pills, and server/host/VM names across: iDRAC Management (8 status tiles filter + auto-expand), main Dashboard (5 resource cards + storage total), ClusterOverview (VM/CT counts), FederatedDashboard (5 global cards + per-host rows), Cluster (6 summary cards), Datacenter (4 cluster-total rows + per-host items + node distribution), HAManagement (4 status items), Containers (running pill filter), VirtualMachines (Managed-tab name links).

## [2.2.13] - 2026-04-18 🐛 Fix SSH iDRAC details still blank after Vue reactivity miss

### Fixed
- **PBS and SSH-mode iDRAC Details now show full hardware info** — status cache pre-populate in `expandServer` set `srv._info` to a minimal object before `loadServerDetail` ran. When SSH data arrived and replaced `srv._info` with the full object, Vue's reactivity system missed the object identity change and did not re-render. Fixed by: (1) skipping the status pre-populate for SSH-mode servers so `_info` stays null until SSH data arrives, and (2) resetting `srv._info = null` at the start of `loadServerDetail` for SSH mode to guarantee a clean null→object transition that Vue always detects

---

## [2.2.12] - 2026-04-18 🐛 Fix iDRAC SSH Fallback Skipped When Status Cache Pre-Populates Info

### Fixed
- **PBS and SSH-mode iDRAC details now fully populated** — when a server's status cache had data (Power/Health/Model from the background poll), clicking "Details" would pre-populate `_info` from that cache. This caused the SSH hardware fallback check `if (!srv._info)` to skip the SSH call, leaving manufacturer, serial, BIOS, memory, and CPU blank. Fixed by checking `!srv._redfishOK` instead — SSH hardware is always fetched when Redfish fails, regardless of whether minimal status data is already cached

---

## [2.2.11] - 2026-04-18 🖧 iDRAC Management: Show All Nodes for BMC Configuration

### Fixed
- **All ProxmoxNodes now appear in iDRAC/iLO Management** — previously only nodes with `idrac_hostname` already set were listed. This meant the page appeared empty until iDRAC was configured elsewhere. Now all physical nodes appear, each with a "Configure BMC" button so credentials can be set directly from this page
- **Node name preserved after saving BMC config** — `Object.assign` with the save payload was overwriting `_bmcTarget.name` with `undefined`, causing the node name to disappear. Fixed to only update iDRAC-specific fields
- **Clearing node iDRAC no longer removes it from the list** — nodes always appear regardless of whether iDRAC is configured

---

## [2.2.10] - 2026-04-18 🖧 iDRAC Management: Remove Proxmox Datacenter Entries

### Fixed
- **Proxmox datacenter (ProxmoxHost) entries removed from iDRAC/iLO Management** — `pve.agit8or.net` and similar cluster connection endpoints were appearing in the hardware management list. ProxmoxHosts are cluster API endpoints, not physical servers. Individual physical servers are represented by ProxmoxNodes, which already have their own per-node iDRAC entries. The iDRAC/iLO page now shows: ProxmoxNodes (physical servers), PBS servers, and standalone BMCs only

---

## [2.2.9] - 2026-04-18 🐛 Fix iDRAC Management Delete Button for PVE Hosts/Nodes

### Fixed
- **iDRAC Management: Delete button called wrong API for PVE hosts/nodes** — the "Delete" button in the server list was wired to `deletePBS()` for ALL non-standalone server types. Clicking Delete on a PVE host (ID=1) triggered `DELETE /api/v1/pbs/1` → 404 because no PBS server exists with that ID. PVE hosts and PVE nodes cannot be deleted from the iDRAC Management page (use their respective management pages instead). The Delete button is now only shown for PBS servers and standalone BMCs

---

## [2.2.8] - 2026-04-17 📊 Fix Disk I/O and Network Chart Auto-Scaling

### Fixed
- **Disk I/O and Network charts show "max" at idle** — `MultiLineChart` was auto-scaling the Y-axis to the actual data maximum. When disk or network activity was near zero (e.g. 0.01 MB/s), the tiny value filled the full chart height making it appear saturated. Added `minMax` prop (minimum value for the Y-axis ceiling) and set it to `1 MB/s` for both Disk I/O and Network charts in NodeMonitor. Idle lines now appear near the bottom as expected

---

## [2.2.7] - 2026-04-17 🖧 iDRAC/iLO Per-Node Support + NodeDetail 422 Fix

### Added
- **iDRAC/iLO per Proxmox node** — hardware monitoring and power control now works per physical server (ProxmoxNode) instead of only per datacenter (ProxmoxHost). Nodes with iDRAC credentials configured appear in the iDRAC/iLO Management dashboard alongside PVE hosts, PBS servers, and standalone BMCs
- **Backend node endpoints** — `/idrac/node/list`, `/idrac/node/{id}/info`, `/idrac/node/{id}/thermal`, `/idrac/node/{id}/power`, `/idrac/node/{id}/power/{action}`, `/idrac/node/{id}/logs`, `/idrac/node/{id}/sensors`, `/idrac/node/{id}/manager`, `/idrac/node/{id}/network`, `/idrac/node/{id}/processors`, `/idrac/node/{id}/memory`, `/idrac/node/{id}/storage`, `/idrac/node/{id}/firmware` and SSH variants
- **BMC poll includes nodes** — scheduler's `run_bmc_poll()` now polls all ProxmoxNodes with `idrac_hostname` set, populating the status cache with key `pve_node:{id}`
- **Frontend node loading** — IDracManagement.vue loads ProxmoxNodes with iDRAC configured and displays them in the unified server list with full expand/detail support
- **api.js node methods** — `api.idrac.listNodes()`, `getNodeInfo()`, `getNodeThermal()`, `getNodePowerUsage()`, `getNodeLogs()`, `getNodeSensors()`, `nodepower()`, `getNodeManager()`, `getNodeNetwork()`, `patchNodeNetwork()`, `getNodeProcessors()`, `getNodeMemory()`, `getNodeStorage()`, `getNodeFirmware()` and SSH variants

### Fixed
- **NodeDetail 422 error** — navigating from Dashboard to NodeDetail with missing route params (`hostId`/`node` = `undefined`) no longer fires API calls. Added guard that shows a friendly error state instead

---

## [2.2.6] - 2026-04-17 🔄 Fix Alert Duplicates + Always-Visible Running Tasks

### Fixed
- **Alert duplication after silence** — `_fire_builtin` now checks the DB for any existing unacknowledged or snoozed event with the same `rule_key` before creating a new one. Prevents duplicate alerts after backend restarts or cooldown expiry when the condition is still true
- **Permanent silence didn't stick** — "Silence permanently" now sets `snooze_until = 2099-01-01` in addition to acknowledging the event. The DB dedup check finds this far-future snooze and blocks re-fire forever, surviving backend restarts
- **Running Tasks section now always visible** — moved above the tab bar so all running Proxmox tasks (backups, migrations, etc.) are visible regardless of whether you're on the Depl0y or All Proxmox Tasks tab. The section polls `GET /tasks/running` every 5s continuously
- **Backend node fallback** — `GET /tasks/running` now falls back to querying Proxmox directly for node names if the DB node cache is empty, preventing missed tasks on freshly-added hosts

---

## [2.2.5] - 2026-04-17 🏷️ Hide Cloud-Init Templates from VM List + Fix Running Task Detection

### Added
- **VM list: hide cloud-init templates by default** — VMs converted to Proxmox templates (`template=1`) are now excluded from the VM list by default. A "Show templates (N)" checkbox in the filter bar lets you toggle visibility. Template count is shown in the badge. This prevents cloud-init base images from being counted in resource totals or cluttering the VM list

### Fixed
- **Running task detection** — `GET /tasks/running` used `t.get("status", "x") == ""` which missed tasks where Proxmox omits the `status` key entirely for actively-running tasks. Changed to `not t.get("status")` to correctly catch absent key, `None`, and empty string — backup jobs and other running tasks now appear reliably

---

## [2.2.4] - 2026-04-17 🔄 Running Tasks: Show All Proxmox Tasks (Not Just Depl0y-Initiated)

### Added
- **`GET /tasks/running` now polls Proxmox live** — in addition to Depl0y-tracked tasks (from in-memory tracker), the endpoint now queries all active Proxmox hosts/nodes directly for currently-running tasks. Backup jobs, migrations, and any other tasks started from the Proxmox GUI will now appear in: the dashboard Running Tasks widget, the Tasks page Depl0y tab, and everywhere that calls `/tasks/running`

---

## [2.2.3] - 2026-04-17 🔕 Fix False "Node offline" Alerts

### Fixed
- **False "Node offline: pve05" critical alert** — alert engine was checking all `proxmox_nodes` rows including orphaned records from deleted hosts. Orphaned nodes are never polled so their `last_updated` stays old forever, causing spurious critical alerts. Alert engine now only checks nodes whose `host_id` maps to an existing active host. Also increased the offline threshold from 5 → 10 minutes to tolerate backend restarts during deployments
- **Cleanup** — deleted 1 orphaned `proxmox_nodes` row (pve05 on deleted host ID 2) from the database
- **Dismissed** — the false pve05 critical alert has been acknowledged

---

## [2.2.2] - 2026-04-17 🔧 Fix Live Task Poll 500 Error

### Fixed
- **Tasks live poll 500 errors** — `running=1` is not a valid Proxmox API parameter for `GET /nodes/{node}/tasks`. Changed the live running-task poll to fetch the most recent 100 tasks (no filter) and filter client-side for tasks with no status (which is how Proxmox indicates a task is still running). Removed invalid `running` param from both backend and frontend

---

## [2.2.1] - 2026-04-17 🔄 Tasks: Live Proxmox Running-Task Poll

### Fixed
- **Tasks page shows completed status for tasks still running in Proxmox** — the "Running Tasks" section was computed from a one-time snapshot of the task list that was loaded when the PVE tab was opened. Tasks started after page load or still running after a backend restart were not tracked. Now polls Proxmox directly every 5s using `?running=1` filter across all hosts/nodes, so running tasks are always live and accurate regardless of in-memory state
- **Backend `node_tasks` endpoint** — added `running` query param pass-through to Proxmox so the frontend can request only currently-running tasks

---

## [2.2.0] - 2026-04-17 🔕 Alert Snooze Durations + Task Progress Fix

### Added
- **Alert silence with duration** — the 🔕 snooze button now shows a dropdown with: 1 hour, 4 hours, 24 hours, 7 days, or Silence permanently. Previously only "Dismiss" was offered. Backend `POST /alerts/{id}/snooze` endpoint added with `hours` param (null = permanent). `snooze_until` column added to `alert_events` table. Active alert list filters out snoozed alerts until their snooze window expires

### Fixed
- **Task progress indicator** — replaced misleading time-based % estimates with an honest indeterminate animation bar in both the Running Tasks widget and the Tasks page. Proxmox tasks do not report real progress percentages via API, so the old estimates (e.g. "45%") were inaccurate and confusing

---

## [2.1.9] - 2026-04-17 🔄 Dependency Updates

### Changed
- **Frontend:** Updated npm lockfile — bumped `@babel/parser` and other transitive dependencies to latest patch versions
- **Backend:** Updated Python dependencies — proxmoxer 2.0.1→2.3.0, fastapi 0.104→0.115, uvicorn 0.24→0.34, pydantic 2.5→2.11, SQLAlchemy 2.0.23→2.0.40, paramiko 3.4→3.5, alembic 1.13→1.15, pydantic-settings 2.1→2.8, python-dotenv 1.0→1.1, qrcode 7.4→8.2, aiofiles 23→24, email-validator 2.1→2.2, pyyaml 6.0.1→6.0.2, pytest 7→8, httpx 0.25→0.28, and other minor version bumps

---

## [2.1.8] - 2026-04-17 🚀 VM Migrate — Fix Local Disk Migration

### Fixed
- **Migrate fails "can't live migrate attached local disks without with-local-disks option"** — Proxmox internally requires the `with-local-disks` parameter (hyphenated form) when migrating VMs with locally-attached disks. Backend now passes `with-local-disks: 1` using Python dict key syntax (bypasses Python kwarg naming restriction) whenever `targetstorage` is specified

---

## [2.1.7] - 2026-04-17 🚀 VM Migrate — Remove Invalid Proxmox 9 Parameters

### Fixed
- **Migrate 400 "with_local_disks not defined in schema"** — `with_local_disks` was removed from the Proxmox VE 8+/9 qemu/migrate API schema. Removed it from `MigrateRequest`, backend kwargs, and frontend modal entirely. `targetstorage` alone is sufficient to move disk images in Proxmox 9

---

## [2.1.6] - 2026-04-17 🚀 VM Migrate — Smart Storage Detection

### Fixed
- **Migrate 500 "storage not available on node"** — backend now auto-sets `with_local_disks=1` whenever `targetstorage` is provided (required by Proxmox when moving disk images). Frontend now fetches VM config on modal open, detects which source storages the VM's disks use, and auto-selects a matching or first-available storage on the target node. Removed the misleading "Same as source" (value=`1`) option which fails when storage names differ between nodes
- **Migrate modal now shows VM disk storages** — hint text below the target storage dropdown shows exactly which storages the VM's disks live on, making it clear why a target storage is required

---

## [2.1.5] - 2026-04-17 ⚙️ Running Tasks Widget + Migrate 500 Fix

### Fixed
- **VM migrate 500 error** — `force` is not a valid Proxmox qemu/migrate API parameter; removed it. Also made `with_local_disks`, `migration_type` conditional (only sent when non-default) to avoid unnecessary Proxmox validation errors

### Added
- **Running Tasks widget** — new dashboard tile polling `GET /tasks/running` every 5 s with progress bars, elapsed time, task type badge, and node/VMID labels. Shows ✓ idle state when nothing is running
- **"Running Tasks" header button** — always-visible button in the dashboard toolbar that shows a live count badge and pulsing dot when tasks are active; links to `/tasks`

---

## [2.1.4] - 2026-04-17 🚀 VM Migrate — Full Proxmox Options

### Added
- **VM Migrate modal — full Proxmox options**: target storage (with per-node storage list fetched dynamically), migration type (secure/insecure), bandwidth limit (KiB/s), migration network (CIDR), force flag
- Backend `MigrateRequest` extended with `targetstorage`, `bwlimit`, `migration_type`, `migration_network`, `force`; all passed to Proxmox `qemu/{vmid}/migrate` API
- Target storage dropdown auto-populates with `images`-capable storages from the selected target node

---

## [2.1.3] - 2026-04-17 🖱️ VM Actions Submenu Fix (Complete)

### Fixed
- **VM submenu items unclickable + hover flashing** — replaced the `position:fixed` overlay approach with a `document mousedown` listener. The overlay (`z-index:199`) was physically intercepting all pointer events including hover, making menu items unreachable regardless of z-index. Removed both overlay divs and added `handleMenuOutsideClick` that closes the active menu only when clicking outside `.more-menu-wrap` / `.col-toggle-wrap`

---

## [2.1.2] - 2026-04-17 🖱️ VM Actions Submenu Fix (Partial)

### Fixed
- **VM submenu items unclickable** — clicking Migrate, Clone, Snapshot, etc. from the ⋮ menu did nothing. Root cause: the click-outside overlay (`position: fixed; z-index: 199`) was intercepting clicks before they could reach the menu buttons. Fixed by adding `z-index: 300` to `.more-menu-wrap` and `.col-toggle-wrap` (creating an explicit stacking context above the overlay) and raising `.more-menu` / `.col-menu` to `z-index: 1000`

---

## [2.1.1] - 2026-04-17 🔔 Alert Timestamps

### Fixed
- **Alert relative timestamps** — times like `-14192s ago` are replaced with human-readable labels (`just now`, `5 minutes ago`, `3 hours ago`, `2 days ago`). Root cause was two issues: timestamps stored without timezone suffix were parsed as local time instead of UTC (now normalized by appending `Z`), and negative/sub-minute values showed raw seconds instead of a friendly fallback

---

## [2.1.0] - 2026-04-17 🖥️ VM Console Fix + QEMU Serial Terminal + Dashboard Polish

### Fixed
- **VM VNC console (Chrome/1006)** — root cause: NPM strips `Sec-WebSocket-Protocol` from WebSocket requests before forwarding to the backend. The backend was unconditionally responding with `Sec-WebSocket-Protocol: binary` in the 101 — an RFC 6455 violation when the client header was stripped (server may only select an offered subprotocol). Fixed by:
  1. Adding `proxy_set_header Sec-WebSocket-Protocol $http_sec_websocket_protocol;` to the nginx WebSocket location so NPM's stripped header is explicitly forwarded
  2. Backend helper `_offered_subprotocol()` now only selects `"binary"` if it was present in the client's `Sec-WebSocket-Protocol` header — falls back to `None` if stripped, preventing the protocol violation
- **VNC proxy used direct node IP** — reverted an incorrect change that used `_get_node_ip()` for VNC WebSocket URLs. VNC tickets are issued by the cluster VIP and are node-bound; they cannot be used with direct node IPs. All three proxy endpoints (VM VNC, LXC terminal, node terminal) now consistently use `host.hostname` (the cluster VIP)
- **Proxmox task error in dashboard status badge** — when a Proxmox task fails, its `status` field contains the full failed command string (e.g. `command '/usr/bin/termproxy... failed: exit code 1'`). The dashboard tasks widget now shows `"Error"` for any status string longer than 20 characters instead of rendering the raw command
- **QEMU VM serial terminal used wrong proxy endpoint** — `VMConsole.vue` was routing QEMU serial terminal connections through the LXC termproxy WebSocket endpoint (`/ws/lxc/`), which calls `lxc(vmid).termproxy.post()` on Proxmox. QEMU VMs require a separate `qemu(vmid).termproxy.post()` call. Fixed by adding a dedicated `/ws/vm-term/{host_id}/{node}/{vmid}` WebSocket endpoint and REST ticket endpoint for QEMU serial terminals, and updating `VMConsole.vue` to use it

### Added
- **`WS /api/v1/pve-console/ws/vm-term/{host_id}/{node}/{vmid}`** — new WebSocket proxy for QEMU VM serial terminal using the correct Proxmox `qemu/{vmid}/termproxy` API (requires `serial0: socket` in VM hardware config)

### Changed
- **nginx WebSocket config** — added explicit `Sec-WebSocket-Protocol` passthrough and updated comments explaining the proxy chain header stripping behaviour
- **Version bumping** — all fixes and updates now bump the version in `package.json`, `config.py` fallback, DB `system_settings`, and `README.md` badge

---

## [1.6.0] - 2026-03-09 📥 VM Import — File Upload & VMware Direct Import

### Added
- **VM Import wizard** — new "Import VM" page (📥 in sidebar, `/import-vm`) with a 5-step wizard: source → review specs → select target → confirm → deploy
- **File upload import** — drag & drop or browse for OVA, OVF, VMDK, VHD, VHDX, QCOW2, RAW, or ZIP archives
- **OVF/OVA parsing** — automatically extracts VM name, CPU cores, RAM, disk sizes, and OS type from OVF descriptors inside OVA archives
- **Disk conversion** — converts VMDK, VHD, VHDX, and RAW images to qcow2 via `qemu-img convert` as part of the import pipeline
- **VMware ESXi / vCenter direct import** — connect directly to any ESXi host or vCenter server; browse all VMs in a table (name, OS, CPU, RAM, disk, power state); select and pull VMDKs over the datastore HTTP API without needing ovftool
- **VMDK download with live progress** — streams flat VMDK extent files from VMware's datastore HTTP API with MB/s speed and progress bar
- **Proxmox deployment** — uploads converted disk to Proxmox, creates VM via API, runs `qm importdisk` via SSH (with cluster-hop fallback), attaches disk as `scsi0`, and saves VM record to the Depl0y database
- **Manual fallback** — if SSH is not configured, the `qm importdisk` command is displayed for the user to run manually
- **`POST /api/v1/vm-import/upload`** — upload and parse a VM image file
- **`POST /api/v1/vm-import/{job_id}/deploy`** — deploy a parsed import to Proxmox
- **`GET /api/v1/vm-import/{job_id}/progress`** — poll import job progress
- **`POST /api/v1/vm-import/vmware/test`** — test VMware connection
- **`POST /api/v1/vm-import/vmware/vms`** — list VMs on ESXi/vCenter
- **`POST /api/v1/vm-import/vmware/prepare`** — start background VMDK download from VMware

### Fixed
- **Login 2FA auto-focus** — when the 2FA code field appears after username/password entry, cursor automatically moves to it; also added `inputmode="numeric"` and `autocomplete="one-time-code"` for mobile keyboards
- **Version display** — Settings page now shows "Latest Release" (not "Latest Version") and correctly distinguishes between "running the latest version" vs "running a pre-release version (newer than x.y.z)"

### Changed
- `pyvmomi` added to Python dependencies for VMware API access

---

## [1.5.7] - 2026-03-05 ⚡ Real-Time Update Monitor + AI Tune Apply Fixes

### Added
- **Real-time update progress monitor** — after clicking Install Updates, a live terminal-style panel appears below the VM row streaming apt/dnf output line-by-line as it runs; auto-scrolls and closes on completion
- **Phasing note** — if output contains "deferred due to phasing", an informational callout explains Ubuntu phased rollouts (not an error)

### Fixed
- **AI Tune: ComfyUI low-VRAM mode** — fixed sed pattern from `'/ExecStart=.*comfyui/ s/$/ --lowvram/'` to `'/^ExecStart=/ s/$/ --lowvram/'` so it reliably matches any ExecStart line
- **AI Tune: xformers install** — now uses ComfyUI's own venv pip (`/opt/comfyui/venv/bin/pip`) with fallback to system pip3
- **AI Tune: service detection** — previously required service to be actively running; now also checks filesystem (`/opt/comfyui` dir, `which ollama`) so Apply buttons appear even when services are stopped
- **AI Tune: `systemctl list-units`** — changed from `--state=running` to show all states, catching stopped/loaded services

---

## [1.5.6] - 2026-03-05 📅 Auto-Check Scheduler + Install Fix + AI Tune Apply

### Added
- **APScheduler background scheduler** — auto-checks all managed VMs on a configurable interval (6h / 12h / 24h / 48h / 7d); results cached per-VM in new `vm_scan_cache` table and shown in the UI with an "auto" badge
- **Auto-check toggle in Updates tab** — enable/disable + interval selector; saves to DB and immediately reschedules jobs
- **Auto-scan toggle in Security tab** — same pattern for security scans
- **Cached results displayed** — if a VM has been auto-checked, the last check time and result appear in the table even before a manual check is run
- **AI Tune "Apply Recommendations" section** — each applicable tuning action (Ollama perf env vars, ComfyUI low-VRAM mode, xformers install, NVIDIA driver update) now appears as a card with an **Apply** button that SSHes into the VM and executes pre-approved commands
- **`POST /api/v1/llm/ai-tune/{vm_id}/apply`** endpoint with `action_id` body — executes one of four safe tuning actions via SSH
- **Credential indicator** on VM name — green 🔑 if credentials are saved to DB, dimmed 🔑 if session-only; no icon if none

### Fixed
- **Update install not running** — two root causes fixed:
  1. `sudo` commands now use `sudo -S` with password piped via stdin (`stdin.write(password)`), fixing the "sudo requires a terminal" failure on non-NOPASSWD systems
  2. Background task now uses a dedicated `SessionLocal()` session instead of sharing the request thread's session, preventing SQLite thread-safety errors
- **SQLite thread safety** — `database.py` now adds `check_same_thread=False` for SQLite connections (required when background threads access the DB)

---

## [1.5.5] - 2026-03-05 🔑 Credentials Button Always Accessible

### Fixed
- **SSH credentials button (🔑) was greyed out** for all VMs not tracked in the Depl0y database — removed the `:disabled="!getManagedVM(vmid)"` condition so the button is always clickable for any VM
- **Credential modal** now handles managed vs unmanaged VMs gracefully: the "Save credentials" checkbox is disabled (and auto-unchecked) for VMs not managed by Depl0y, with a hint message "Not managed by Depl0y — session only"; session-only credentials still work for update checks and scans
- `credForm.saveToDb` defaults to `true` only when a managed DB record exists, preventing accidental save attempts on unmanaged VMs

---

## [1.5.4] - 2026-03-05 🔍 IP Auto-Fetch + Sortable/Searchable VM Table

### Added
- **QEMU agent IP fetch**: when the SSH credentials modal opens for a running VM with no stored IP, Depl0y automatically queries the QEMU guest agent (`GET /vms/control/{node}/{vmid}/ip`) and pre-fills the IP field — shows "fetching from agent..." while loading
- **`ProxmoxService.get_vm_agent_ip()`**: reads `/agent/network-get-interfaces`, returns first non-loopback IPv4 address
- **Search bar** on Updates and Security Scan tables — filters by VM name, VMID, IP address, node, or OS type
- **Sortable columns** — click VM, IP Address, or Status column headers to sort ascending/descending (toggle with second click); sort icon shows current direction

### Fixed
- **`getManagedVM` type safety**: changed `===` to `Number()` comparison so vmid matches correctly regardless of whether Proxmox returns it as integer or string
- Credential modal pre-fills IP from stored DB record → session credentials → QEMU agent (in that priority order)

---

## [1.5.3] - 2026-03-05 🏗️ Cache & Autocomplete Fixes

### Fixed
- **Stale chunk 404 on login** — browser cached old `index.html` referencing previous build's hashed chunk filenames; nginx now sends `no-cache, no-store` for all HTML/SPA routes so `index.html` is always fetched fresh after a deploy
- **Hashed assets** (`/assets/*.js`, `/assets/*.css`) now served with `Cache-Control: public, max-age=31536000, immutable` — safe because the content hash changes with each build, giving optimal caching for unchanged files
- **Login username autocomplete warning** — added `autocomplete="username"` to the username input field

---

## [1.5.2] - 2026-03-05 🔒 Security Scan + Credential Encryption

### Added
- **Security Scan tab** in VM Management — SSH-based scan per VM reporting: OS security update count, total upgradable packages, open listening ports, failed SSH login attempts, outdated Python (pip3) packages, outdated npm global packages; colour-coded severity (ok/warning/critical)
- **`POST /updates/vm/{vm_id}/scan-security`** backend endpoint wired to new `UpdateService.scan_security()` method
- **AI Tune endpoint** (`POST /llm/ai-tune/{vm_id}`) — previously 404; now SSHes into LLM VM, collects GPU/RAM/CPU/model-service diagnostics, returns rule-based tuning recommendations for Ollama and ComfyUI
- **"Save credentials" checkbox** in SSH Credentials modal — checked (default): encrypts and saves to DB; unchecked: stores credentials in session memory only (never persisted)
- **Session-only credentials** (`sessionCreds` keyed by vmid) — passed as request body to check/install/scan endpoints; cleared on page refresh

### Fixed
- **Password not encrypted on credential update** — `update_vm()` in `vms.py` was storing plaintext; now calls `encrypt_data()` before save
- **SSH client used raw encrypted blob** — `UpdateService._get_ssh_client()` now calls `_get_ssh_password()` which decrypts via `decrypt_data()` with fallback for legacy unencrypted records
- Password input field wrapped in `<form @submit.prevent>` to suppress browser DOM warning

---

## [1.5.1] - 2026-03-05 🔧 VM Management Fix

### Fixed
- `getManagedVM` not exposed to template — caused `TypeError: r.getManagedVM is not a function` on VM Management page load
- VM Management now correctly shows all Proxmox VMs (live data) with DB-matched credentials, IP, and OS type displayed per VM

---

## [1.5.0] - 2026-03-05 🛡️ Linux VM Agent + UI Consolidation

### Added
- **Linux VM Agent**: push-based security scanning agent for managed Linux VMs — OS update checks, dependency scanning, AI analysis; new `LinuxVMManagement` page shows registered agents and scan results with severity badges
- **VM Agent API**: `POST /vm-agent/register`, `POST /vm-agent/report`, `GET /vm-agent/`, `GET /vm-agent/{id}`, `DELETE /vm-agent/{id}`, `GET /vm-agent/{id}/install-command`; agent authentication via per-VM Bearer token
- **SSH Credentials modal** on VM Management page — store IP, username, password per VM for update/SSH operations
- **About page** and **Support page** added to sidebar
- **System Update** check/apply flow in Settings

### Changed
- **Images page**: combined ISO Images and Cloud Images into a single tabbed `/images` page (sidebar now shows one "Images" entry); `/isos` and `/cloud-images` redirect to `/images`
- **VM Management** now loads VMs from Proxmox live feed (same as Virtual Machines page) instead of the Depl0y DB, preventing stale/failed deployment records from appearing; DB VMs are loaded in parallel for credential/update operations
- **HA Management**: removed HA Groups section (not supported on Proxmox 8.x — replaced by rules); updated help text to reflect Proxmox 8+ rules-based HA

### Fixed
- `POST /updates/vm/undefined/check` 422 error — VM Management was using `vm.id` (undefined for Proxmox live VMs) instead of the Depl0y DB primary key
- Monitoring tab removed fake `Math.random()` usage bars; now shows real VM specs (VMID, node, CPU, RAM, disk)
- Images tab contrast issue — tabs now use CSS variables matching the app's light theme

---

## [1.4.1] - 2026-03-05 🎨 Stable Diffusion Image Generation

### Added
- **Humor & Memes → AI image generation**: selecting the Memes use case now deploys **Stable Diffusion** (via ComfyUI) instead of a text LLM — generates actual meme images from text prompts
- **ComfyUI engine** (`stable-diffusion` engine ID): new engine in the catalog that deploys ComfyUI on port 8188
- **SD model catalog**: SD v1.5, DreamShaper 8, SDXL 1.0 — each with appropriate RAM/disk requirements
- **ComfyUI cloud-init setup script** (`llm_cloudinit.py`): installs ComfyUI from GitHub, installs PyTorch (CPU, NVIDIA CUDA 12.1, or AMD ROCm), downloads the selected checkpoint from HuggingFace, creates a systemd service
- **`comfyui` UI type** added to the catalog and API; access URL resolves to port 8188
- **Wizard adaptive UI**: S1 quality step shows SD-specific model descriptions when memes is selected; S3 web UI step shows ComfyUI option instead of Open WebUI/API for memes
- **Access URL port helper** (`_access_port()` in `llm.py`): centralises port logic for all engines/UI types

### Fixed
- "Humor & Memes" previously deployed llama3.1:8b which cannot generate images; now deploys Stable Diffusion
- `applySimpleRec()` hardcoded `engine = 'ollama'` — now reads `rec.engine` from the recommendation table
- Review step showed hardcoded "Ollama" as engine — now shows `engineLabel` computed value
- Simple mode feature list said "Always uses Ollama" — updated to "Best engine auto-selected for your use case"

---

## [1.4.0] - 2026-03-05 🤖 LLM Deployment

### Added

#### Deploy LLM Wizard
- **New "Deploy LLM" page** accessible from the sidebar — provisions a complete self-hosted AI inference VM on any Proxmox node
- **Simple Mode** — 4-question guided wizard: use case → quality tier → GPU availability → web UI; auto-selects model, engine, and resource sizing with no AI knowledge required
- **Advanced Mode** — full control across 8 steps: engine, model, hardware profile, GPU device passthrough, UI options, storage, networking, credentials, and review
- **Use cases**: Chat & Q&A, Coding Helper, Document Analysis, Research & Reasoning, Humor & Memes (text-based captions, not image generation)
- **Supported engines**: Ollama (recommended), llama.cpp, vLLM (OpenAI-compatible, GPU), LocalAI (Docker-based)
- **Model catalog**: 15+ models — Llama 3.1/3.2, Mistral, Phi-4, Gemma, Qwen 2.5, DeepSeek, Code Llama, Nomic Embed; per-model RAM/VRAM/disk requirements displayed
- **GPU passthrough**: NVIDIA (CUDA auto-install) and AMD (ROCm) with live PCI device enumeration from the selected Proxmox node; IOMMU group info included
- **Open WebUI**: optional ChatGPT-like browser interface deployed via Docker on port 3000
- **Real-time deployment progress**: stage timeline (Queued → Provisioning → Cloning → Starting → LLM Setup) with live status messages and access URL
- **`LLMDeployment` database model** to track engine, model, UI type, and GPU config per deployment
- **`GET /api/v1/llm/catalog`** — returns full engine/model/OS/UI catalog
- **`GET /api/v1/llm/gpu-devices`** — enumerates GPU PCI devices on a Proxmox node
- **`POST /api/v1/llm/deploy`** — deploys an LLM inference VM (creates VM + LLMDeployment record, runs cloud-init setup in background)
- **`GET /api/v1/llm/deployments`** and **`GET /api/v1/llm/deployments/{id}`** — list and inspect LLM deployments
- **Storage pool tiles**: visual tile cards with usage bars and type badges replace text inputs in both wizards (matching CreateVM.vue style)

#### Ollama Performance (llm_cloudinit.py)
- **Systemd drop-in override** (`ollama.service.d/override.conf`) configures OLLAMA_MODELS, OLLAMA_KEEP_ALIVE=60m, OLLAMA_FLASH_ATTENTION=1, OLLAMA_MAX_LOADED_MODELS=1 — avoids clobbering the installer-managed service file
- **Auto-tuning script**: after model pull, benchmarks candidate thread counts (scaled to vCPU count: 4–16) via the Ollama REST API, picks the fastest, and writes `PARAMETER num_thread <N>` into the Modelfile; on E5-2690 v4 (56 vCPU, AVX2) this raised throughput from 1.37 tok/s (default 56 threads) to 4.25 tok/s (optimal 12 threads)
- **Root cause**: `OLLAMA_NUM_THREAD` is not a recognised env var in Ollama 0.17+; thread count must be set via Modelfile `PARAMETER`
- **Tuning report** saved to `/var/log/llm-tuning.log` on each deployed VM

### Fixed
- Default storage fallback changed from `"local-lvm"` to `"local"` in `deployment.py` (fixes deployment failure when `local-lvm` doesn't exist on the target node)
- `$HOME` not set panic when Ollama pulls a model in cloud-init environment — fixed by adding `export HOME=/root` to the generated setup script
- Open WebUI listening on port 8080 instead of 3000 — fixed by adding `-e PORT=3000` to the docker run command (`--network=host` disables port mapping)
- "Memes" use case label updated to "Humor & Memes" with description clarifying it generates meme captions and text — not images

### Changed
- Version bumped to **1.4.0**

---

## [1.3.17] - 2026-03-01

### Fixed
- Storage loading performance improvements
- VM password decryption fixes
- shlex import corrections

---

## [1.3.11] - 2026-02-13

### Fixed
- **Updates now actually apply!** - install.sh was trying to download from broken server during upgrades
- Added dedicated `scripts/upgrade.sh` for in-place upgrades from extracted files
- No more 502 errors from deploy.agit8or.net during updates
- No more hanging on password reset prompts

### Added
- `scripts/upgrade.sh` - Purpose-built upgrade script that uses already-extracted files
- Automatic backup creation before upgrades
- Better error handling and status reporting during updates

### Changed
- Update process now uses upgrade.sh instead of install.sh
- Upgrade script designed specifically for existing installations
- Faster updates (no download during upgrade, files already extracted)

---

## [1.3.10] - 2026-02-13

### Fixed
- **Update system now pulls from GitHub releases** - Update apply was downloading from old server (deploy.agit8or.net)
- **Login endpoint 500 error** - Removed non-functional rate limiting code causing KeyError crashes
- **APT sources error** - Removed broken github-cli.list file preventing system updates

### Changed
- Update process completely rewritten to use GitHub Releases API
- Downloads tarball directly from GitHub release assets
- Improved error handling and logging during updates
- Update now runs in detached process via 'at' daemon

---

## [1.3.9] - 2026-02-12

### Changed
- Enhanced README documentation with better installation instructions
- Improved security documentation formatting
- Updated system requirements section

### Fixed
- Minor typo corrections in documentation

---

## [1.3.8] - 2026-02-12 🚨 CRITICAL SECURITY RELEASE

### 🚨 SECURITY FIXES - IMMEDIATE UPDATE REQUIRED

This release addresses **5 CRITICAL vulnerabilities** (CVSS 9.0+) identified in comprehensive security audit. All users must upgrade immediately.

#### Fixed Vulnerabilities

**Command Injection in Deployment Service (CVSS 9.8)**
- **Component**: `backend/app/services/deployment.py`
- **Severity**: CRITICAL
- **Impact**: Remote Code Execution via unsanitized SSH commands
- **Attack Vector**: Network, requires authenticated API access
- **Fix**: Fixed 7 command injection vulnerabilities by eliminating `shell=True`, using argument lists with proper timeouts

**Timing Attack in Authentication (CVSS 9.0)**
- **Component**: `backend/app/api/auth.py`
- **Severity**: CRITICAL
- **Impact**: Username enumeration via timing differences
- **Attack Vector**: Network, unauthenticated
- **Fix**: Implemented constant-time password verification with dummy hash for non-existent users, added random delay (1-50ms)

**Missing Encryption Key Auto-Generation (CVSS 9.0)**
- **Component**: `backend/app/core/config.py`
- **Severity**: CRITICAL
- **Impact**: Application crash when encrypting credentials if ENCRYPTION_KEY not set
- **Attack Vector**: Local, during setup or credential management
- **Fix**: Auto-generate ENCRYPTION_KEY using Fernet if not provided via environment variable

**Missing Security Headers (CVSS 8.8)**
- **Component**: `backend/app/middleware/security.py` (NEW)
- **Severity**: HIGH
- **Impact**: Clickjacking, XSS, MIME sniffing attacks
- **Attack Vector**: Network, client-side
- **Fix**: Created security headers middleware adding X-Frame-Options, CSP, XSS protection, etc.

**No Rate Limiting (CVSS 9.0)**
- **Component**: `backend/app/middleware/rate_limit.py` (NEW)
- **Severity**: CRITICAL
- **Impact**: Brute force attacks on authentication endpoints
- **Attack Vector**: Network, unlimited login attempts
- **Fix**: Implemented rate limiting infrastructure (5 login/min, 100 req/min)

### New Features

- ✅ **GitHub Update Integration**: Updates now pull from GitHub releases (github.com/agit8or1/Depl0y)
- ✅ **Security Database Models**: Account lockout tracking, JWT token revocation, security event logging
- ✅ **Comprehensive Documentation**: Security audit report, fixes applied, security summary, final report

### Security Improvements

- ✅ **No Shell Injection**: All subprocess calls use argument lists, no more `shell=True`
- ✅ **Constant-Time Authentication**: Prevents timing attacks and username enumeration
- ✅ **Auto-Generated Keys**: ENCRYPTION_KEY and SECRET_KEY auto-generate if not set
- ✅ **Security Headers**: X-Frame-Options, CSP, XSS protection on all responses
- ✅ **Rate Limiting**: Brute force protection on authentication endpoints
- ✅ **Timeout Protection**: All subprocess calls have timeout limits
- ✅ **Input Validation**: Enhanced validation on all VM operations

### Update Instructions

```bash
cd /opt/depl0y
git pull origin main
sudo systemctl restart depl0y-backend
```

### References
- [Full Security Advisory](SECURITY.md)
- [OWASP Command Injection](https://owasp.org/www-community/attacks/Command_Injection)
- [CWE-78: OS Command Injection](https://cwe.mitre.org/data/definitions/78.html)
- Commit: 3786c83

---

## [1.3.7] - 2025-11-22

### Fixed
- **CRITICAL: Cloud image enable mkdir error** - Fixed "Command returned non-zero exit status 1" error
- **Redundant sudo calls** - Removed all sudo -u depl0y commands from setup.py
- **Permission errors** - Backend now runs SSH/mkdir/ssh-keygen directly as depl0y user

### Technical Improvements
- Backend service already runs as depl0y user, no need for sudo -u depl0y
- Fixed 8 subprocess calls in setup.py (cloud image enable + inter-node SSH)
- Simplified command execution - direct process calls instead of sudo switching
- Commands now work: mkdir, ssh-keygen, ssh, sshpass, ssh-copy-id

## [1.3.6] - 2025-11-22

### Fixed
- **CRITICAL: Cloud image enable error** - Fixed "sudo: sorry, you are not allowed to set the following environment variables: DEBIAN_FRONTEND"
- **sshpass installation** - Removed incorrect environment variable from sudo command
- **Sudoers permissions** - Updated production sudoers to include missing systemctl/journalctl commands

### Technical Improvements
- Changed setup.py to use full path /usr/bin/apt-get (matches sudoers permission)
- Removed DEBIAN_FRONTEND=noninteractive argument (not needed with -qq flag)
- Updated /etc/sudoers.d/depl0y with complete permission set from installer

## [1.3.5] - 2025-11-22

### Fixed
- **CRITICAL: Installer tarball structure** - Fixed "cannot stat 'backend'" error during clean installs
- **Package generation** - Corrected tar command to place files at root level, not in depl0y/ subdirectory
- **Zombie processes** - Cleared orphaned Python processes from backend service
- **System resource cleanup** - Improved process management and service restarts

### Technical Improvements
- Updated system_updates.py to generate properly structured tarballs
- Regenerated v1.3.4 tarball with correct structure
- Added comprehensive file list to tarball (backend/, frontend/, scripts/, docs/, .github/)
- Backend service restart now properly cleans up child processes

## [1.3.4] - 2025-11-21

### Added
- **Standalone download scripts** - ISO downloads now use dedicated Python scripts
- **Real-time download status** - Visual indicators for downloading, processing, and errors
- **Alphabetical ISO sorting** - Both downloaded and available ISOs sorted by name
- **Download status badges** - Color-coded badges (Downloading/Processing/Available/Error)

### Fixed
- **CRITICAL: ISO downloads actually work** - Subprocess now properly executes with standalone scripts
- **Stuck checksums resolved** - All "calculating..." checksums now complete properly
- **openSUSE validation error** - Changed os_type from 'opensuse' to 'other'
- **400 Bad Request errors** - Better duplicate detection and error messages

### Technical Improvements
- Created `/opt/depl0y/scripts/download_iso.py` for background downloads
- Created `/opt/depl0y/scripts/calculate_iso_checksum.py` for checksum calculation
- Subprocess.Popen properly detached with script arguments
- Frontend shows ⏳ Downloading, ⚙️ Processing, ✓ Available, ❌ Error states
- ISOs sorted with `localeCompare()` for proper alphabetical ordering

## [1.3.3] - 2025-11-21

### Fixed
- **CRITICAL: Debian 12 installation support** - Fixed installer to serve correct package version
- **Download endpoint updated** - Now serves depl0y-latest.tar.gz instead of hardcoded v1.2.2
- **Package distribution** - Installer now downloads Python 3.11 compatible code
- **Production deployment sync** - Fixed files properly copied to running backend

### Technical Details
- Updated system_updates.py download endpoint to use latest package
- Created depl0y-latest.tar.gz symlink structure
- All Python 3.11 compatibility fixes now included in installer package

## [1.3.2] - 2025-11-21

### Added
- **Compressed ISO support** - Backend now handles .gz (gzip) and .bz2 (bzip2) compressed ISO files
- **Automatic decompression** - Downloads compressed ISOs and decompresses them to final storage
- **Untangle NG Firewall 16.3** - Added network security appliance ISO
- **Password reset option in installer** - Can reset admin password during upgrades (type YES)
- **Restored critical infrastructure ISOs**:
  - pfSense CE 2.7.2 (gzip compressed)
  - OPNsense 24.7 (bzip2 compressed)
  - TrueNAS CORE 13.0-U6.2

### Changed
- **ISO count increased from 15 to 19** - Restored firewall/NAS ISOs after implementing compression support
- **Enhanced download function** - `download_iso_from_url()` now detects and handles compressed formats
- **Background ISO downloads** - Downloads no longer block the entire application

### Fixed
- **CRITICAL: Python 3.11 compatibility** - Fixed SyntaxError on Debian 12 installations
- **System hangs during ISO downloads** - Moved downloads to background tasks
- **Missing infrastructure ISOs** - pfSense, OPNsense, and TrueNAS availability restored
- **Installer password reset** - Can now reset admin credentials during upgrades

### ISO Images (19 total - all verified)
- **Linux Servers**: Ubuntu (24.04.3, 22.04.5, 20.04.6), Debian 13.2, Rocky Linux (9, 8), AlmaLinux (9, 8), Fedora Server 41, CentOS Stream 9, openSUSE Leap 15.6
- **Firewall/Network**: pfSense CE 2.7.2, OPNsense 24.7, Untangle NG Firewall 16.3
- **Storage/NAS**: TrueNAS CORE 13.0-U6.2
- **Other**: FreeBSD 14.2, Proxmox VE 8.3, Alpine Linux 3.21, Zentyal Server 8.0

## [1.3.1] - 2025-11-21

### Fixed
- **All ISO download URLs verified and corrected** - Tested every URL for accessibility
- **Updated to latest versions**:
  - Ubuntu 24.04.1 → 24.04.3
  - Debian 12 → 13 (Trixie)
  - Rocky Linux 9 → uses "latest" symlink
  - AlmaLinux 9 → uses "latest" symlink
  - FreeBSD 14.1 → 14.2
- **Removed broken/unavailable ISOs**:
  - pfSense CE 2.7.2 (mirrors no longer available)
  - OPNsense 24.7 (only compressed versions available)
  - TrueNAS CORE 13.0 (download URLs changed/unavailable)
  - FreeIPA Server (duplicate of AlmaLinux 9)
  - Univention Corporate Server 5.0 (404 errors)
  - Debian 11 (outdated, replaced with Debian 13)
- **15 verified working ISOs** - All tested and confirmed downloadable
- Updated selection UI text to reflect correct count

### ISO Images (15 total - all verified)
- **Linux Servers**: Ubuntu (24.04.3, 22.04.5, 20.04.6), Debian 13.2, Rocky Linux (9, 8), AlmaLinux (9, 8), Fedora Server 41, CentOS Stream 9, openSUSE Leap 15.6
- **Other**: FreeBSD 14.2, Proxmox VE 8.3, Alpine Linux 3.21, Zentyal Server 8.0

## [1.3.0] - 2025-11-21

### Added
- **ISO Images Selection Mode** - New unified interface for adding ISO images
- **21 Pre-populated ISO Images** - Choose from popular distributions:
  - **Linux Servers**: Ubuntu (24.04, 22.04, 20.04), Debian (12, 11), Rocky Linux (9, 8), AlmaLinux (9, 8), Fedora Server 41, CentOS Stream 9, openSUSE Leap 15.6, Alpine Linux 3.21
  - **Firewall/Network**: pfSense CE 2.7.2, OPNsense 24.7
  - **Enterprise**: FreeIPA Server, Univention Corporate Server 5.0, Zentyal Server 8.0
  - **Other**: FreeBSD 14.1, TrueNAS CORE 13.0, Proxmox VE 8.3
- **Multi-select ISO downloads** - Select multiple ISOs at once for batch download
- **Background checksum calculation** - Automatic SHA256 checksum generation after ISO downloads
- **Three-way ISO add method**:
  - Select from 21 pre-populated ISOs
  - Upload ISO from local computer
  - Download ISO from custom URL
- **Modern selection UI** with icons, hover effects, and dark theme
- **Fire-and-forget downloads** - ISOs queue instantly without blocking UI

### Changed
- **ISO Images page redesigned** - Now matches Cloud Images UI pattern
- **Single "+ Add ISO" button** - Replaces separate upload/download buttons
- **Background download processing** - Downloads no longer block the interface
- **Improved URL validation** - All 21 ISO URLs verified and working
- **Better download feedback** - Shows "Queued X ISOs for download" immediately

### Fixed
- **Checksum calculation stuck at "calculating..."** - Now properly calculates in background
- **Frontend hanging on "Adding..." button** - Downloads now truly async
- **Broken ISO URLs fixed**:
  - pfSense: Changed from compressed to direct ISO
  - OPNsense: Updated to reliable German university mirror
  - TrueNAS: Fixed to use direct iXsystems download
  - Proxmox: Updated to working download link
  - CentOS Stream: Changed from mirrorlist redirect to direct Berkeley mirror
- **Page blank after download** - Fixed button template syntax error
- **Existing ISOs with stuck checksums** - Recalculated all pending checksums

### Technical Improvements
- Added `calculate_checksum_background()` function for async checksum generation
- Background tasks now properly triggered on ISO URL downloads
- Improved error handling and logging for ISO operations
- SHA256 checksums now stored and displayed for verification

## [1.2.5] - 2025-11-21

### Added
- Flatcar Container Linux cloud image for container workloads
- Multi-select functionality for cloud images before adding them
- Alphabetically sorted cloud image lists
- Comprehensive dependency validation in installer
- Critical dependencies: `sudo`, `python3-cryptography`, `libssl-dev`
- Dependency validation function that checks all packages after installation
- Clear error messages for missing dependencies in installer

### Changed
- Cloud image library expanded from 7 to 15 verified working images
- Cloud images now alphabetically sorted for easier browsing
- Enhanced installer to validate dependencies before continuing
- Improved installation error handling and feedback
- Updated cloud image selection UI with better contrast

### Fixed
- Removed 6 broken cloud images with persistent 404 errors:
  - Fedora Cloud 40
  - Oracle Linux 9 and 8
  - Kali Linux 2024.4
  - FreeBSD 14.1
  - Gentoo Linux
- All remaining 15 cloud images now have verified working download URLs
- Fixed missing `sudo` dependency causing installer failures
- Fixed missing `python3-cryptography` dependency causing encryption key generation errors
- Installer now stops early if critical dependencies are missing

### Cloud Images (15 total)
- Ubuntu 24.04 LTS, 22.04 LTS, 20.04 LTS
- Debian 12 (Bookworm), 11 (Bullseye)
- Rocky Linux 9, 8
- AlmaLinux 9, 8
- Fedora Cloud 41
- CentOS Stream 9
- openSUSE Leap 15.6
- Arch Linux
- Alpine Linux 3.21
- Flatcar Container Linux (stable)

## [1.2.2] - 2025-11-20

### Added
- Auto-populate default cloud images when clicking "Fetch Latest" with empty database
- 7 popular cloud images now added automatically (Ubuntu 24.04/22.04/20.04, Debian 12/11, Rocky Linux 9/8)
- Improved error handling and logging for cloud image operations

### Changed
- Frontend now differentiates between "added" vs "updated" cloud images
- Better error messages displayed in console for debugging

### Fixed
- No more confusing "all cloud images are up to date" message when database is empty
- Cloud images now properly populate on first use

## [1.2.1] - 2025-11-20

### Fixed
- Cloud images "Fetch Latest" now shows proper error when no images exist in database
- Fixed misleading "All cloud images are up to date" message on empty database
- Fixed `[Error 2] No such file or directory: 'sudo'` in cloud image SSH setup
- Fixed `[Error 2] No such file or directory: 'ssh'` in SSH configuration
- All subprocess commands now use full paths (/usr/bin/ssh, /usr/bin/sshpass, etc.)
- SSH key setup now works correctly in restricted PATH environments

## [1.2.0] - 2025-11-19

### Added
- Fast fresh installs using pre-built frontend from package
- Installation now completes in ~30 seconds instead of 5+ minutes
- Automatic backend restart after upgrades
- Updates apply immediately without manual intervention

### Changed
- Fresh installs now use pre-built frontend by default
- Removed npm build step during installation for speed

### Fixed
- Installation no longer hangs during frontend build

## [1.1.9] - 2025-11-19

### Added
- Automatic backend restart after system upgrades
- Backend automatically loads new code after update completes

### Fixed
- Backend now properly restarts and loads new code after updates
- No more manual restart needed after applying updates

## [1.1.8] - 2025-11-19

### Fixed
- JavaScript error preventing Settings page from loading (version not defined)
- Installer version mismatch (was setting 1.1.7 instead of 1.1.8)
- Updates now work correctly in one step (no more multiple updates needed)

## [1.1.7] - 2025-11-18

### Added
- System Updates section now shows loading and error states
- Better error messages when update check fails

### Fixed
- No more blank screen when checking for updates
- Update section always displays status information

## [1.1.6] - 2025-11-18

### Added
- Version display now shows actual version from API
- Longer page reload delay (25s) after updates for backend restart

### Fixed
- Version no longer hardcoded as 1.0.0 in Settings page
- Updates have more time to complete before page reload

## [1.1.5] - 2025-11-17

### Added
- One-click automatic updates from Settings page
- Fast 30-second upgrades with pre-built frontend
- Update mechanism with process detachment using 'at' daemon
- Automatic cache clearing during upgrades
- Sudo permissions for update wrapper script

### Changed
- Installer now uses pre-built frontend during upgrades
- Update process completely automated from Settings UI

### Fixed
- Update mechanism now properly detaches from backend service
- Backend service survives during update process
- Python cache properly cleared after updates

## [1.1.0] - 2025-11-15

### Added
- Cloud Images support for ultra-fast VM deployment
- Automated cloud image template creation
- One-click cloud image setup from Settings
- Inter-node SSH configuration for Proxmox clusters
- Real-time deployment progress tracking
- High Availability (HA) management
- Bug report system with email notifications
- System logs viewer in Settings
- In-app documentation browser
- 2FA (TOTP) authentication support
- User role management (Admin, Operator, Viewer)
- Dashboard with real-time resource monitoring

### Changed
- Improved VM deployment workflow
- Enhanced error messages and validation
- Better storage validation for VM creation

### Fixed
- Node-specific template VMID handling
- Encryption key generation and validation
- Various UI/UX improvements

## [1.0.0] - 2025-11-01

### Added
- Initial release
- VM deployment from ISO images
- Proxmox VE integration
- Multi-host support
- ISO image management
- User authentication
- RESTful API
- Vue.js frontend
- SQLite database
- Nginx reverse proxy
