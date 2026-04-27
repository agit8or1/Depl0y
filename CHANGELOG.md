# Changelog

All notable changes to Depl0y will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.63] - 2026-04-27 🔗 Top-level Add Node button

### Added
- **`+ Add Node` button alongside `+ Add Datacenter` in the page header.** From the top level: pick the target cluster from a dropdown, pick a standalone host from a dropdown, root password — done. Disabled with a clear tooltip when there are no eligible standalones or no multi-node clusters yet.
- The same modal is reused from the per-cluster `+ Add Node` button on each cluster card; the cluster picker is hidden when the cluster is already known.

## [2.2.62] - 2026-04-27 🔗 Streamlined cluster join + remove

### Added
- **`＋ Add Node` and `－ Remove Node` buttons** sit directly on every cluster's info row (next to the node count) — no longer buried in the More menu.
- **Add Node Wizard**: from a cluster card, pick a standalone host from a dropdown of *available* standalones, enter root password, click Join. Fingerprint + cluster node address are auto-fetched and tucked under "Advanced" (only override if the join fails). Success polls cluster status until the new node appears, then auto-deletes the standalone host entry.

### Changed
- **Remove Node modal** now loads the live cluster node list from `/cluster/{id}/status` and presents a dropdown — no more typing the exact node name. Cluster master is auto-disabled in the picker (you can't remove the box you're running the unjoin from).
- **Join Cluster modal** stripped of instructional copy and form hints. Required fields collapse to *Cluster + Root password*; fingerprint/addr live under an "Advanced" disclosure that's only shown after a cluster is selected.

## [2.2.61] - 2026-04-27 🧹 Host card actions: zoom-tolerant layout

### Fixed
- **Action row still overflowed at higher browser zoom** even after the previous consolidation. Restructured into two rows: `Open Cluster` as a full-width primary CTA on its own line, and a compact **icon-only** secondary row (PVE UI · Details · ⚡ Power · ⋮ More) that fits at any zoom level. Power state is now a colored dot (green/red/amber) instead of a text badge — same info, no chance of wrapping. All actions keep tooltips with full text labels.

## [2.2.60] - 2026-04-27 🧹 Host card action row cleanup

### Fixed
- **Host-card action row was 10 buttons wide and overflowed**, with the Power-button label wrapping ("⚡ Power" / "Mixed" stacked on two lines). Reduced to four primary buttons in the row — `Open Cluster`, `PVE UI`, `Details`, `⚡ Power` — with `Edit` / `Test` / `Poll Now` / `Join Cluster` / `Unjoin Node` / `Delete` consolidated into a single `⋮ More` dropdown. Power-button label and state badge now `nowrap` so they always sit on one line.

## [2.2.59] - 2026-04-27 ⚡ iDRAC page power menu + PBS polling fixes

### Added
- **Power dropdown on the iDRAC/iLO Management page**, in the always-visible status row of every server card. Same six actions as the host/node cards (On / Graceful Off / Force Off / Graceful Restart / Force Reset / Power Cycle), routed to the right backend per server type (`pve` / `pve_node` / `pbs` / `standalone`). Teleported with auto flip-up.

### Fixed
- **PBS servers without iDRAC (e.g. `pbs2`, a VM) were being added to the BMC poll cycle** because `idrac_hostname.isnot(None)` only excludes SQL NULL — the empty-string column slipped through. Filter now excludes both NULL and `""`. Also drops cache entries that no longer correspond to a configured BMC, so old polls of cleared rows stop showing stale "error" entries.
- **`pbs1` Redfish reads were timing out** at the new 8s per-call cap (its iDRAC takes ~5–6s for the first response on cold connections, plus thermal/power calls that can each push past 8s individually). Bumped the per-call timeout back up to 15s — still well below the original 20s, but enough headroom for slower BMCs.
- **Dashboard alerts overflow** when a backup audit log entry includes a long termproxy command. Title truncates to one line with ellipsis; detail clamps to 2 lines; full text accessible via hover tooltip.

## [2.2.58] - 2026-04-27 ✎ Manual model override for older iDRAC + offline-node task tolerance

### Fixed
- **All per-node Proxmox endpoints now tolerate an offline target node** instead of bubbling 500s into the dashboard console. Extracted `_is_offline_error()` helper in `node.py` matching `no route to host` / `connection refused` / `timed out` / `name or service not known` / `unreachable` / `network is unreachable`, and applied it to `/nodes/{node}/status`, `/vms`, `/lxc`, and `/tasks`. Offline shape: status returns `{status: "offline", error: ...}`, vms returns `{vms: [], containers: [], offline: true}`, lxc/tasks return `[]`. Other failure modes still 500.

### Background
- Confirmed against pve2 (iDRAC 7, R730xd): the BMC literally does not expose `Model`, `SystemPID`, `SystemID`, or any Dell OEM model field via Redfish — every endpoint returns blank or whitespace. iDRAC 7 firmware predates the Dell Redfish OEM extension that newer boxes use. Auto-detection isn't fixable for these — there's no field to read.

### Added
- **Manual model override** (admin only) via the new `🖥 ✎` pencil button on every host and node card. Sets `system_settings.model_override:<cache_key>` and instantly applies to the live BMC cache so the chip updates without waiting for the next poll. Auto-detected value is preserved as `auto_model` so we can restore it by clearing the override. New `PUT /api/v1/idrac/model-override/{cache_key}` endpoint backs it.
- Pre-seeded `model_override:pve_node:1` = `Dell PowerEdge R730xd` so pve2 reads correctly out of the gate.

## [2.2.57] - 2026-04-27 ⚡ Faster BMC refresh + SystemID-based model lookup

### Fixed
- **pve2 (and other 13G hosts) still showed `Dell PowerEdge (13G)` after a fresh poll** because the OEM `SystemPID` field is empty on iDRAC 8 too. The poll already retrieves Dell's `SystemID` (e.g. 1575 → `0x0627`) — same key the PCI lookup table is indexed by — but it was only stored, never used for model resolution. Now `get_system_info()` runs `lookup_dell_model_from_pci(SystemID)` before falling back to the generation label, so 13G boxes resolve to their actual PowerEdge model directly from Redfish — no Proxmox PCI query, works even when the host OS is offline.

### Improved
- **Redfish per-call timeout reduced from 20s → 8s**, so an unreachable BMC fails fast instead of stalling the whole poll cycle. Combined with the existing 10-worker thread pool, a slow/dead BMC now caps at ~8s rather than 20s.
- **"Refresh All" / "Poll" / changing the poll interval all now drive a continuous cache re-fetch** (every 1.5s for up to 20s) instead of two fixed checkpoints, so the UI updates as soon as each individual BMC poll finishes rather than waiting for the slowest one.

## [2.2.56] - 2026-04-27 ⚙️ Configurable BMC poll + Dell OEM model fallback

### Added
- **BMC poll interval is now user-configurable.** New `BMC poll: [1/2/5/10 min]` selector in the Cluster Nodes header (admin only); default stays at 2 min. Persisted in `system_settings.bmc_poll_interval_minutes`. Backend exposes `reschedule_bmc_poll()` which `PATCH /api/v1/system/settings` calls live, so the new cadence takes effect without a backend restart and a fresh poll is queued immediately.

### Fixed
- **Server model showing `Dell PowerEdge (13G)` instead of the actual model on iDRAC 8 / 13G boxes (e.g. pve2).** Redfish returns blank `Model` on those boxes; we now read `Oem.Dell.DellSystem.SystemPID` from the System resource (the human-readable PowerEdge name iDRAC emits as an OEM extension) before falling back to the manager-generation label. Also extended the PCI lookup to cover host-level (`pve:`) entries, not just `pve_node:` ones, and log unknown Dell subsystem IDs at info-level so the lookup table can be extended for any model that's still missing.

## [2.2.55] - 2026-04-27 ⚡ PVE OS shutdown/reboot + layout cleanup

### Added
- **Two-section power menu on every host + node card.** Top section runs through the **Proxmox OS** (`/api/v1/pve-node/{host}/nodes/{node}/status/{shutdown|reboot}` → `pvesh /nodes/{n}/status` `command=shutdown|reboot`) — works while the OS is alive but cannot turn a fully-off machine back on. Bottom section runs through the **iDRAC/BMC** (existing `/idrac/.../power/{action}`) — the only path that can power on a dead box, plus force-off / reset / power-cycle when the OS is unresponsive. When the host has no iDRAC configured, the bottom section is replaced with a hint pointing at Edit.
- New backend endpoint `POST /api/v1/pve-node/{host_id}/nodes/{node}/status/{command}` (admin-only, accepts `shutdown` or `reboot`).

### Fixed
- **Proxmox Hosts page layout overflow.** Action button row now wraps cleanly on narrow cards; long version/model chips truncate with ellipsis instead of pushing content outside the card; node header wraps the model chip below the node name when there's no horizontal room.

## [2.2.54] - 2026-04-27 ⚡ Power controls on host + node cards

### Added
- **Power dropdown on each Proxmox host card** (when host iDRAC is configured): Power On / Graceful Shutdown / Force Power Off / Graceful Restart / Force Reset / Power Cycle. Current power state shown as a badge on the trigger button.
- **Same dropdown on each node card** in the Cluster Nodes section, when that node has its own iDRAC configured (uses `POST /idrac/node/{id}/power/{action}`).
- Destructive actions (everything except Power On) prompt before executing. After any action, the BMC poll is kicked and the cache re-read so the state badge updates without needing another click.
- Menu uses `<Teleport>` + auto flip-up so it isn't clipped by the card or container — same pattern as the VM more-actions fix.

## [2.2.53] - 2026-04-27 🛠️ Poll Now triggers BMC refresh

### Fixed
- **"Poll" / "Refresh All" on Proxmox Hosts didn't pick up missing iDRAC-sourced data quickly.** Both buttons fetched the Proxmox node list but didn't kick the BMC poller, so server model / health / firmware fields stayed stale until the next scheduled BMC pass. Both now fire `POST /api/v1/idrac/poll` in parallel and re-read the cache at +2s and +8s (covers fast and slow iDRACs).

## [2.2.52] - 2026-04-27 🛠️ VM dropdown clip fix + task progress/ETA polish

### Fixed
- **Virtual Machines page — "More actions" dropdown was clipped when the list was filtered.** `.table-container` has `overflow-x: auto`, which (per CSS spec) forces `overflow-y` to behave as `auto` too — so the absolutely-positioned `.more-menu` got cut off below the shrunken container. The three menu instances now render via `<Teleport to="body">` with fixed positioning computed from the trigger button's bounding rect, with auto flip-up when there isn't room below. Closes on scroll/resize.
- **Floating task detail modal — "Started 1/21/1970" timestamp.** PVE/PBS-sourced tasks emit `started_at` as Unix seconds while depl0y-tracked tasks emit ISO strings; `new Date(seconds)` interpreted the number as milliseconds. New `toDate()` helper detects numeric epochs (< 1e12 → seconds, ≥ 1e12 → ms) and converts correctly. Same fix applied to `Tasks.vue`.
- **Task progress jitter — bar moved backwards between polls.** `progress_for_external` fell back to a time-based estimate whenever the log parser returned `None`, so a transient parse miss could drop progress below the previously-cached value. Now keeps the last-known parsed value when a poll fails to produce a percentage.
- **Interactive tasks no longer show a fake progress bar.** `vncshell` / `vncproxy` / `spiceshell` / `spiceproxy` / `termproxy` return `progress: null`; the bar hides instead of pretending to track an interactive session.
- **Stale console sessions no longer linger in the floating task bar.** PVE leaves `vncshell` / `vncproxy` / `spiceshell` / `spiceproxy` / `termproxy` UPIDs in "running" state long after the user closes the console tab; `/api/v1/tasks/running` now filters those types out so they don't accumulate in the running list.

### Added
- **ETA + Elapsed in the floating task detail modal**, computed from progress rate. Durations now format as `Xd Yh Zm` / `Xh Ym` / `Xm Ys` / `Xs` everywhere (running list, detail KV, Tasks page).
- **Server model chip on each Proxmox host card** (e.g. `🖥 Dell PowerEdge R730xd`) — visible without expanding the node list. Sourced from the BMC poll cache; falls back to the host-level entry, summarises as `Mixed (N models)` for clusters with non-identical hardware, and is hidden when no model has been collected yet.
- **Per-node server model chip in the Cluster Nodes section** of the Proxmox Hosts page — same data source, on every node card next to the node name.

## [2.2.51] - 2026-04-27 🛠️ Floating tasks PBS-task fix + Proxmox Hosts shows server model

### Fixed
- **Floating tasks panel was firing `GET /api/v1/tasks/null/localhost/.../log` for PBS tasks** and getting 422s in a tight loop. PBS-sourced tasks have `host_id: null` (correctly — they aren't on a Proxmox host) and a `server_id`, but `GlobalTaskBar.vue` was still routing them through the PVE `/tasks/{host_id}/...` path. Now routes by `task.source`: PBS tasks go through `/pbs-mgmt/{server_id}/tasks/{upid}/log` (which returns a flat `string[]`), PVE tasks keep the existing `{lines: [...]}` shape — handler normalises both.
- The Stop button is hidden on PBS tasks in the floating panel and the detail modal (PBS doesn't expose a stop endpoint via depl0y; the button would have failed the same way the log fetch did).

### Added
- **Proxmox Hosts → server model column.** Each node row now shows the server model (e.g. `Dell PowerEdge R730xd`) next to the node name, sourced from the BMC poll cache (`pve_node:{id}` entries from `/api/v1/idrac/status`). Empty when the BMC poll hasn't run yet or the node has no iDRAC configured.

## [2.2.50] - 2026-04-22 🔐 Security hardening pass

Comprehensive CVE + static-analysis scan across the codebase; everything critical or high-severity fixed in this release. No functional regressions expected — if something breaks, the most likely cause is a tighter input validator rejecting data the old code silently accepted.

### Dependency CVEs patched
- **python-jose 3.3.0 → 3.4.0** — `PYSEC-2024-232` (algorithm confusion) and `PYSEC-2024-233` (JWT-bomb DoS). Would have let a single crafted token hang a worker or bypass signature checks.
- **starlette 0.46.2 → 0.49.1** — `CVE-2025-54121` (event-loop block on large multipart) and `CVE-2025-62727` (`Range`-header quadratic-time ReDoS, unauth CPU exhaustion). Required bumping **fastapi 0.115.12 → 0.121.3** (starlette is a transitive dep).
- **weasyprint 66.0 → 68.0** — `CVE-2025-68616` SSRF-bypass via HTTP redirect; the PDF export path could have been steered at `169.254.169.254` metadata.
- **python-dotenv 1.1.0 → 1.2.2** — `CVE-2026-28684` symlink-follow arbitrary-file overwrite in `set_key`.
- **defusedxml 0.7.1** added (OVF parsing; see below).

### Command-injection fixes — `services/deployment.py::_create_cloud_template_automated`
- All shell-interpolated values (`host.hostname`, `node.node_name`, `storage`, `cloud_image.filename`, `node_ip`) now pass through strict regex validators at function entry; a malformed value raises `ValueError` instead of reaching the shell.
- `scp` upload converted from `subprocess.run(shell=True)` + f-string to an argv list.
- Boundary validation added to `CloudImageCreate` / `CloudImageUpdate` (`api/cloud_images.py`) — filename must match `[A-Za-z0-9._-]{1,255}`, `download_url` must be `http(s)://`. These are the fields that fed the shell in the first place.

### OVA/OVF import hardening — `services/vm_import_service.py`
- **ZipSlip / TarSlip** fixed. `extract_ova()` no longer calls `tarfile.extractall()` / `zipfile.extractall()` blindly. New `_safe_tar_members()` / `_safe_zip_members()` iterators drop any entry whose resolved path escapes the extract dir, plus symlinks / hardlinks / device files / absolute paths. A malicious OVA can no longer overwrite `/etc/passwd` or drop files under `/opt`.
- **XXE** fixed. OVF XML is now parsed via `defusedxml.ElementTree.parse` (external-entity / DTD attacks disabled). Stdlib `ET` is kept only for type hints.

### Authentication / authorisation
- `GET /api/v1/system/info` now requires authentication (was unauth; leaked app version + name).
- `POST /api/v1/setup/cloud-images/enable` and `POST /api/v1/setup/proxmox-cluster-ssh/enable` now require `require_admin` (were `get_current_user`; any signed-in viewer could trigger package installs + SSH-key exchange on Proxmox hosts).

### CORS is now configurable
- `BACKEND_CORS_ORIGINS` reads from a new `CORS_ORIGINS` env var (comma-separated). Set it in `/etc/depl0y/config.env`:
  ```
  CORS_ORIGINS=https://deploy.example.com,https://panel.example.com
  ```
  Localhost dev entries remain in place so `npm run dev` keeps working. The old wildcard `allow_methods=["*"]` / `allow_headers=["*"]` with `allow_credentials=True` — an invalid spec combination — is replaced by an explicit allowlist.

### Frontend XSS
- `AIReportDetail.vue` sanitises `report.rendered_html` through **DOMPurify** before `v-html`. LLM-produced markup can no longer smuggle `<script>` / inline event handlers / `javascript:` URLs into an admin session.

### Ancillary fix discovered during smoke tests
- `RequestValidationError` handler now stringifies the raw `ValueError` in `ctx.error`; pydantic-v2 includes the exception object, which broke `JSONResponse` serialisation (422 turned into 500 when a validator fired). Affected any endpoint using pydantic `field_validator` — now fully visible.

### Still open (deferred — cost/benefit or bigger change)
- JWT tokens remain in `localStorage`. Moving to an HTTP-only cookie flow is a bigger refactor; flagged, not shipped.
- `/vm_import_service.py` upload dir is still `/tmp/depl0y-imports` — hardcoded, low-risk on a single-tenant host.
- `paramiko.AutoAddPolicy()` still in use in `ssh_hw.py` + `updates.py` — acceptable for a first-contact panel that owns the inventory, flagged as known-accepted.
- 6 npm moderate advisories (vite / esbuild / vis-network / uuid) — all dev-time or low-impact; tracked.

## [2.2.49] - 2026-04-22 🛠️ Floating tasks show PBS jobs + HA status fixes

### Fixed
- **Floating Running Tasks now shows PBS jobs.** `/tasks/running` only polled PVE clusters; PBS-fired sync / verify / GC / prune / backup jobs returned a UPID but never appeared in the floating panel. Now polls every active PBS server via `/nodes/localhost/tasks?running=1` and merges results with PVE + tracker entries.
- **PBS task progress** — time-based estimate (capped at 50 %) for sync / verify / GC which can run for hours, so the bar never lies.
- **HA Manager Status no longer shows "No Master / 0 ⁄ 0".** `/pve-node/{host}/cluster/ha/status` was returning PVE's wrapper with `manager_status` nested, but the UI reads `master_node` / `node_status` at the top level. Flattened the response and added `quorate`, `nodes_online`, `nodes_total`.
- **`/api/v1/ha/status`** — replaced the SSH + `pvesh` path with proxmoxer, and now surfaces `master_node`, `nodes_online`, `nodes_total`, `node_status` alongside `enabled` / `protected_vms` / `quorum`.

## [2.2.48] - 2026-04-22 🕰️ Time Sync audit + remediation

### Added
- **New admin page `/time-sync`** — single-pane audit of clock + NTP state across every PVE node, PBS server, and iDRAC/BMC in the fleet.
  - Summary tiles: Total · OK · Drifting · Unreachable · NTP-enabled · NTP-disabled · NTP-unknown.
  - Matrix table: Target · Kind · Address · Local Time · Drift (colored by magnitude) · NTP state · NTP servers · Actions.
  - Per-row **Fix** button and a top-right **Fix All Drifting** batch action (admin only, with confirm).
  - Settings modal: configurable default NTP server + drift threshold (stored in `system_settings`).
- **Probe strategy per target kind:**
  - **PVE nodes** — `pve.nodes(x).time.get()` + SSH `chronyc tracking` / `timedatectl status`.
  - **PBS** — SSH into `PBSServer.hostname` using stored OS creds; parses `chronyc sources` / `timedatectl`.
  - **iDRAC / BMC** — Redfish Manager `DateTime` + `NTPConfigGroup.*` attributes.
- **Remediation:**
  - **PVE / PBS** — SSH: `timedatectl set-ntp true`, restart `chrony` / `systemd-timesyncd`, `chronyc makestep` to force immediate step.
  - **iDRAC** — PATCH `/Managers/iDRAC.Embedded.1/Attributes` with `NTPConfigGroup.1.NTPEnable=Enabled` + `NTPConfigGroup.1.NTP1=<server>`.
- **Scheduled drift check** — new apscheduler job `run_time_sync_drift_check` runs hourly. Fires alert (rule_key `time_sync:<kind>:<id>`) when drift > threshold or NTP disabled; auto-acks when drift clears.
- 30-second in-memory cache on `/status` so opening the page is instant after the first load.
- Endpoints: `GET /time-sync/status`, `POST /fix`, `POST /fix-all`, `GET|PUT /settings`.

### Changed
- **PBS Servers / Storage Servers labels restored** — v2.2.47 shortened them to "PBS" and "Storage"; that was too ambiguous next to the overview pages. Back to explicit labels.

### Live state (for reference)
- 13 targets detected: 5 PVE nodes + 2 PBS + 5 node iDRACs + 1 PBS iDRAC.
- 6 OK / 6 drifting / 1 unreachable.

### Known limitations
- API-token-only PBS entries can't be SSH'd from depl0y; NTP state shows unknown. Add username+password to the PBS record to enable.
- HPE iLO remediation not implemented (attribute path is Dell-specific). Dell iDRAC fully supported.
- First probe is slow (~60s) when BMCs are unreachable — bounded by TLS timeouts; 30s cache covers subsequent visits.

## [2.2.47] - 2026-04-22 🧹 Condensed sidebar menu

### Changed — sidebar cleanup
The menu had grown to **46 items**. Trimmed and reorganized:

- **Overview** (5 → 5): moved Federation behind admin-only (rarely used by daily operators).
- **Compute** (6 → 5): removed `VM Management` from the sidebar (route still exists, but it duplicated the `/vms` list; users get the same via the VM detail row). Renamed `VM Groups` → `Groups`.
- **Infrastructure** (9 → 9 but re-ordered): grouped by frequency of use: Proxmox Hosts / Nodes / Topology / iDRAC at the top; HA / Replication / Network / SDN / Firewall below. `Node Monitor` → `Nodes`. `HA Management` → `HA`.
- **Storage** (7 → 7): re-ordered to put aggregated views (Storage, PBS) first, then operations (Backup, Snapshots, Images). `PBS Management` → `PBS`. `Storage Management` → `Storage`.
- **Admin** (14 → 7 top-level + 7 behind "More ›"): surfaced the ones operators actually click daily (Alerts, Reports, Updates, Security, Linux Security, Users, Health). Moved rarely-used items into a collapsible **More** subsection (Audit Log, System Logs, Notifications, PVE Users, Integrations, API Explorer, Analysis).
- Dropped `Alert Rules` i18n key in favor of just `Alerts`, `Analysis` kept under More (Reports is the primary place now).

Net: **46 items → 25 visible + 7 behind More**. Section structure and persistence of collapsed state unchanged.

## [2.2.46] - 2026-04-22 🏃 PBS Run Now — correct /admin/ path

### Fixed
- **Run Now on any PBS job returned 502.** Backend was POSTing to `/config/sync/{id}/run` — which PBS 4.x returns 404 for. Run actions live under `/admin/<type>/{id}/run`. Same story for verify and prune jobs: `/config/verify/{id}/run` 404s, `/admin/verify/{id}/run` works.
- `PBSService.run_sync_job` no longer passes a `sync-direction` query param — PBS's admin endpoint rejects it with `schema does not allow additional properties` and infers the direction from the stored config.
- `POST /api/v1/pbs-mgmt/{id}/jobs/{job_id}/run` for sync / verify / prune all route through `/admin/...`.

### Verified
- POST against pbs1's push job `s-cd228a39-4d1d` now returns 200 with a fresh UPID: `UPID:pbs1:...:syncjob:PBS2...:root@pam!depl0y:`.

## [2.2.45] - 2026-04-22 📤 PBS push-sync jobs finally visible

### Fixed
- **Push-direction PBS sync jobs were invisible.** PBS 4.x split sync config by direction: `GET /config/sync` returns only **pull** jobs by default; push jobs require `?sync-direction=push` (or `all`). pbs1's hourly `backup → PBS2:PBS2` push job (`s-cd228a39-4d1d`, last state OK) was therefore never returned to depl0y.
- `PBSService.get_sync_jobs()` now fetches with `?sync-direction=all` first (falls back to both explicit pulls for older PBS), deduplicates by `id`, and exposes each job's `sync-direction` field to callers so the UI/alert engine can branch.
- `run_sync_job(job_id, direction)` passes the direction through to the PBS run endpoint — push-direction jobs were previously rejected by the run call.
- API `POST /pbs-mgmt/{id}/jobs/{job_id}/run` introspects the job's direction before triggering so a Run-Now on a push job works.

### Added
- **Create Sync Job modal** now has a **Direction** selector (Pull / Push). Labels on datastore fields flip accordingly (Local = destination for pull, source for push). Push requires PBS ≥ 3.3 on both ends.

### Verified
- Live response on pbs1 now includes the push job: `{"id":"s-cd228a39-4d1d", "sync-direction":"push", "store":"backup", "remote":"PBS2", "remote-store":"PBS2", "schedule":"hourly", "last-run-state":"OK"}`.

## [2.2.44] - 2026-04-22 🏷️ Topology custom labels + sync diagnosis

### Added
- **Right-click any node on the Topology graph to set a custom label.** Prompts for the new label; blank input restores the auto-generated one. Stored client-side in `localStorage` under `depl0y.topology.labels` — survives reloads. A small hint lives under the View toggle.

### Clarified (not code)
- **PBS sync jobs from pbs1 → pbs2 don't exist at the PBS level.** Verified both servers directly with ticket-auth:
  - pbs1 (192.168.22.8): `/config/sync=[]`, `/admin/sync=[]`
  - pbs2 (10.0.0.4): `/config/sync=[]`, `/admin/sync=[]`, **`/config/remote=[]`**
  Neither PBS has any sync job *or* a configured remote. Whatever the UI showed — PBS itself is empty. The Create-Sync-Job flow (v2.2.30) must have either failed to save or was not actually submitted. Try it again: PBS Management → Add Server (re-add pbs2 if not already registered), then use the **+ Create Sync Job** button on pbs1's card. First pick the remote (it'll scan pbs2's datastores), then the local datastore, schedule, Save.
  Network view of Topology: hard-refresh the page and look at the **View** toggle in the top-left toolbar — three buttons: **Infrastructure · Network · Combined**.

## [2.2.43] - 2026-04-22 🌐 Topology network view + PBS sync-jobs tile

### Added
- **Topology page now has three view modes** — Infrastructure / Network / Combined — toggled via a segmented button at the top-left toolbar.
  - **Network mode**: bridges explode into their `bridge_ports`, bonds appear as their own nodes with `bond_slaves` as child NICs, VLAN sub-interfaces get their own node type. BMC + storage are auto-hidden in this mode for readability.
  - **Cross-node L2 peer edges**: bridges with the same name on multiple PVE nodes (e.g. `vmbr0` spanning the cluster) get a dashed peer link so you can see where a VLAN or LAN domain extends.
  - New node types: **bond** (purple rounded), **nic** (cyan dot), **vlan** (teal dot).
  - Backend: new `view_mode` query param on `GET /api/v1/topology/graph` — `infrastructure` | `network` | `combined`.
- **PBS Management sync-job counter tile.** The per-server card now shows **Sync Jobs** as its own pill (total sync-type jobs + inline "N failed" sub-text in red if any last run with errors), plus a separate **Other Jobs** pill (verify / prune / tape-backup). Replaces the previous ambiguous "Jobs" pill that lumped everything together.

### Verified
- Network view on live cluster: 46 nodes (1 host, 4 nodes, 29 VMs, 10 bridges, 2 PBS) with 4 `l2-peer` edges plus 30 VM-attached edges.

## [2.2.42] - 2026-04-22 🛠️ Topology physics loop + pve05 apt repair

### Fixed
- **Topology graph still rendered blank after v2.2.41** — the rAF spam in the console was force-directed physics running indefinitely with nodes laid out beyond the viewport. The initial view wasn't calling `network.fit()` after stabilization and physics never turned off.
  - Now listens for `stabilizationIterationsDone`, then calls `network.fit({ animation: false })` and `setOptions({ physics: { enabled: false } })`.
  - Hard fallback: even if stabilization never fires, a 4-second `setTimeout` force-fits and kills physics.
  - Result: nodes are visible on load, rAF loop stops.

### Fixed (operator action taken)
- **pve05 `apt-get update` exit 100** — resolved directly on the host.
  - pve05 is Debian trixie which uses the deb822 `.sources` format (not `.list`). Two sources pointed at enterprise repos and returned 401:
    - `/etc/apt/sources.list.d/pve-enterprise.sources` → `https://enterprise.proxmox.com/debian/pve`
    - `/etc/apt/sources.list.d/ceph.sources` → `https://enterprise.proxmox.com/debian/ceph-squid`
  - Added `Enabled: no` to both. `proxmox.sources` already had `pve-no-subscription` configured, so the no-subscription repo was always working — the 401 from the enterprise repos was the only reason apt exited 100.
  - Verified: `apt-get update` now exits 0 on pve05.

## [2.2.41] - 2026-04-22 🔧 Topology canvas fix + sync-alert diagnosis

### Fixed
- **Topology page rendered a blank canvas** — two issues: `vis-network/styles/vis-network.css` was never imported (the library needs it for proper canvas layout), and `.topo-graph` used `min-height` only while the inner `.graph-container` tried to `height: 100%` — which collapses when the parent has no explicit height. Added the CSS import and set `.topo-graph` to `height: calc(100vh - 200px)`. Graph now renders all 84+ nodes on load.

### Clarified (not code)
- **pbs1 → pbs2 sync alerts aren't firing because pbs2 isn't in depl0y's DB.** `SELECT * FROM pbs_servers` returns only pbs1 (id=5). The alert engine can only watch servers it knows about; a pull sync job on pbs2 is invisible to us until pbs2 is re-added. **Re-add pbs2 under PBS Management → Add Server** (use Password auth per v2.2.29 or an API token). Alerts will start firing on the next engine cycle once pbs2 is registered and its `/config/sync` list contains a job whose `last-run-state` contains "error".
- **pve05 `apt-get update` exit code 100** is a Proxmox-without-subscription footgun, not a depl0y bug. The stock `/etc/apt/sources.list.d/pve-enterprise.list` points at `https://enterprise.proxmox.com` which returns 401 for unsubscribed hosts; `apt-get` always exits 100 when any repo fails, even though the other repos parsed successfully. That's why depl0y still shows **129 pending updates** despite the task failing. Fix on the node: disable the enterprise repo and enable the no-subscription one:
  ```bash
  # on pve05 as root
  sed -i 's|^deb |# deb |' /etc/apt/sources.list.d/pve-enterprise.list
  sed -i 's|^deb |# deb |' /etc/apt/sources.list.d/ceph.list 2>/dev/null || true
  echo 'deb http://download.proxmox.com/debian/pve bookworm pve-no-subscription' > /etc/apt/sources.list.d/pve-no-subscription.list
  apt-get update
  ```
  Then re-click Refresh in the UI.

## [2.2.40] - 2026-04-22 🗺️ Topology map + draw.io / PNG / SVG exports

### Added
- **New Topology page** at `/topology` (Infrastructure → Topology in the sidebar). Interactive live graph of the whole environment: PVE hosts, nodes, VMs, LXC, storage, network bridges, PBS servers, iDRAC/BMC. PBS sync edges show last-run state — dashed red when in error.
- **Filter toolbar** on the left: Show stopped VMs / LXC / storage / bridges / BMC / PBS / sync edges. Each toggle reshapes the graph.
- **Click a node** to jump to its detail page (VMDetail / NodeDetail / PBSManagement / IDracManagement).
- **Double-click** to zoom-focus on a node.
- **Exports:**
  - **draw.io** — uncompressed `.drawio` XML with mxCell vertices + edges. Opens directly in app.diagrams.net. Each node type maps to an appropriate mxShape (rounded/rhombus/hexagon/cylinder/triangle).
  - **PNG** — full-frame raster from the vis-network canvas. Filename `topology-YYYYMMDD-HHmm.png`.
  - **SVG** — synthesized from vis-computed positions; no canvas2svg dependency.
- Endpoint: `GET /api/v1/topology/graph` with query flags `include_stopped|include_bridges|include_storage|include_bmc|include_pbs|include_lxc|include_sync|refresh`. 60-second in-memory cache keyed by filter combo. Per-host + per-PBS fan-out via `ThreadPoolExecutor`. Graceful degradation: unreachable sub-trees attach `data.error` instead of 500ing.
- New deps: `vis-network@^10.0.2`, `vis-data@^8.0.3`.

### Performance
- Cold fetch 4.6s / cached 10ms on live infra (1 host, 5 nodes, 29 VMs → 84–88 nodes + 141–151 edges).

### Deferred
- Bridge-to-bridge uplink edges (bond_slaves / bridge_ports parsing) — node-to-bridge + VM-to-bridge already covered.
- Per-NIC MAC/IP on edges.
- Layout presets (hierarchical by layer) — force-directed default is usable.

## [2.2.39] - 2026-04-21 📣 PBS sync-failure alerts with jump-to-fix

### Added
- **Built-in alert rule: PBS sync job failed.** `alert_engine._check_pbs_sync_failed()` iterates every active PBS server, reads `/config/sync` + `/admin/sync`, and fires an alert for any job whose `last-run-state` contains "error". Alert severity `warning`, 30-minute cooldown.
- **Rule key** `pbs_sync_fail:{server_id}:{job_id}` — one alert per job, deduplicated.
- **Auto-resolve** — when the same job's next run returns state=ok, any open alert events for that job are auto-acknowledged. No stuck alerts when the problem clears itself.
- **Message includes** the target remote, remote datastore, local datastore, PBS-reported state, and when it failed.
- **Action URL** points at `/pbs-management?highlight=sync:{server_id}:{job_id}`. Clicking the notification scrolls to the failed sync row on the PBS Management page and pulses a red border around it for 4–6 seconds. Click **Run Now** (added in v2.2.30) to retry.
- `_fire_builtin()` now accepts an `action_url` so custom built-in rules can route the notification anywhere — previous checks still default to `/alerts`.

## [2.2.38] - 2026-04-21 🛡️ NodeDetail undefined-hostId guard

### Fixed
- **`/api/v1/pve-node/undefined/disk-io-rates` 422** and similar — `NodeDetail.vue`'s 10-second polling timer kept firing `loadNodeStatus` even when the route params were missing, and `loadRrd` called `diskIoRates` without guarding. Added a single `_routeReady()` gate used by `fetchHostName`, `loadNodeStatus`, `loadRrd` (including the delayed second `diskIoRates` sample) — no more requests to `/undefined/`. Existing interval cleanup on unmount stays.

## [2.2.37] - 2026-04-21 🔁 iDRAC log-tab fallback + inline BMC Edit

### Fixed
- **"Loading system event log…" stuck for 25+ seconds after clearing the SEL on pbs1.** The detail panel was falling back to SSH logs whenever Redfish returned empty — which is exactly what a cleared log looks like. For PBS with a **dedicated BMC** (idrac_hostname ≠ hostname) that SSH call lands on the iDRAC's racadm shell (~25s) with nothing useful to show. Fallback now only triggers on legacy setups where `idrac_hostname === hostname` (SSH goes to the OS journal there).

### Added
- **Inline "Edit" button next to BMC IP** on the iDRAC Details → Overview tab. Opens the existing Edit-BMC modal so you can update hostname, port, or credentials without digging through the actions row.

### Clarified (not code)
- **pbs1's DIMMSLOTA4 Warning is a real hardware fault**, not a stale log entry. The memory module itself is flagging an ECC-correctable condition at the BMC level. Clearing the SEL will never dismiss it. Reseat or replace the DIMM in slot A4 — that's the only fix.

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
