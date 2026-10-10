# Threat model — Depl0y

## What this project does
Depl0y is a self-hosted web control panel for Proxmox VE clusters. A FastAPI backend
(`backend/app`) and a Vue 3 SPA (`frontend/src`) run on a dedicated host behind nginx. The backend
holds high-value credentials for the whole estate and acts on them:

- Proxmox VE API tokens / root passwords, PBS credentials, BMC (iDRAC/iLO/Redfish) credentials,
  SSH keys and passwords for nodes and guests, VMware vCenter credentials, webhook/SMTP secrets.
  These are stored Fernet-encrypted in a SQLite DB (`/var/lib/depl0y/db/depl0y.db`); the key and
  JWT `SECRET_KEY` come from `/etc/depl0y/config.env`.
- It drives Proxmox (create/delete/migrate VMs, firewall, SDN, HA, users/ACLs), opens SSH sessions
  to nodes, relays VNC/terminal WebSockets, generates cloud-init, imports VM disks, and can update
  itself through the root-owned `/usr/local/sbin/depl0y-update` (`scripts/depl0y-update`),
  the only root entry point in its sudoers policy (`scripts/sudoers.depl0y`).

A compromise of Depl0y therefore usually means compromise of every hypervisor it manages.

## Trust levels and where untrusted input enters
1. **Unauthenticated network clients** (highest concern). Anything reachable without a valid
   session: `/api/v1/auth/login`, `/auth/2fa/login`, `/auth/refresh`, `/api/v1/setup/*` (first-run
   setup), `/api/v1/vm-agent/register`, `/vm-agent/report` and `/vm-agent/install.sh` (guest-agent
   token auth), health/docs endpoints, and the middleware stack in `backend/app/middleware`
   (IP filter / GeoIP, rate limit, security headers) plus the audit middleware in `main.py`.
2. **Authenticated low-privilege users.** Roles are `admin`, `operator`, `viewer`
   (`require_admin` / `require_operator` / `get_current_user` in `backend/app/api/auth.py`).
   A viewer or operator reaching an admin-only action, another user's sessions/API keys, or any
   stored secret in plaintext is a privilege escalation.
3. **Managed infrastructure as an adversary.** Responses from Proxmox, PBS, BMC/Redfish, vCenter,
   SSH command output, guest-agent reports, GitHub release metadata (`services/github_updates.py`),
   Dell firmware catalog XML (`services/firmware_check.py`), and LLM/AI-report output are
   attacker-influenced if a guest VM or a single node is compromised. Injection from these into
   shell commands, SSH commands, file paths, SQL, or the SPA (XSS) is in scope.
4. **Files supplied by users:** ISO uploads (`api/isos.py`), VM import uploads/OVA/VMDK
   (`api/vm_import.py`, `services/vm_import_service.py`), node file upload (`api/node.py`),
   cloud-init user data and templates (`services/cloudinit.py`, `services/llm_cloudinit.py`).

## Components that matter most
- Authentication and session handling: JWT issue/verify, refresh, TOTP and backup codes, API keys
  (`core/security.py`, `api/auth.py`), and role checks on every router under `backend/app/api`.
- Command execution: any `subprocess`, `paramiko` `exec_command`, `sshpass`/`ssh` invocation, or
  generated shell script — notably `services/deployment.py`, `api/vm_agent.py`,
  `api/system_updates.py`, `api/setup.py`, `api/ha.py`, `api/system.py`, `api/logs.py`,
  `services/ssh_hw.py`, `services/vm_import_service.py`, `services/llm_cloudinit.py`.
- Failover wizard (`api/ha_wizard.py`, `services/ha_failover.py`, admin only): it moves
  disks, creates replication jobs and HA resources/rules/groups, and changes the cluster
  HA option. A non-admin reaching it, or input that makes it act on a different guest,
  storage or node than planned, is in scope.
- WebSocket console proxies (`api/console.py`): token handling in query strings, authorization of
  `host_id`/`node`/`vmid`, and relaying to Proxmox with stored credentials.
- Path handling for uploads, ISO/cloud-image storage, log viewing, and import working directories.
- Secret storage: anything that returns decrypted credentials, logs them, or lets one tenant of the
  UI read another host's secrets.
- SSRF: endpoints that take a host/URL (adding Proxmox/PBS/BMC hosts, webhooks, integrations,
  cloud-image URLs) and make server-side requests with stored credentials attached.
- Self-update path: `scripts/depl0y-update` (runs as root: release selection, download and
  SHA256SUMS check, archive extraction, privilege drops via `runuser`, rollback),
  `scripts/sudoers.depl0y`, `scripts/install-updater.sh`, the `/system-updates/*` endpoints,
  and `install.sh`'s download and checksum check.
- Frontend: XSS in the SPA, especially rendering of Markdown (`marked` + `dompurify`), VM/node names,
  descriptions, notes, alert text, and AI report output.

## Components that matter less / out of scope
- `docs/`, `*.md`, screenshots, `frontend/public` static assets.
- Vulnerabilities that live entirely in third-party dependencies (Proxmox VE itself, proxmoxer,
  paramiko, FastAPI, Vue, etc.) unless Depl0y's own code makes them reachable.
- Issues that require an attacker who is already a Depl0y **admin** (admins can legitimately run
  commands on nodes) — unless the issue escapes to root on the Depl0y host itself, bypasses audit
  logging, or exposes secrets beyond what the UI is designed to show an admin.
- `docker-compose.yml` default placeholder passwords (documented as examples, not used by
  `install.sh`).
- Missing hardening that is documented as the operator's job (TLS termination, firewalling).

## How to exercise it
- The image has the backend venv on `PATH` and `PYTHONPATH=/src/backend`. Start the API offline:
  `cd /src/backend && uvicorn app.main:app --host 127.0.0.1 --port 8000`. With no `DATABASE_URL`
  set it creates a SQLite DB at `/var/lib/depl0y/db/depl0y.db`; create an admin with
  `python /src/backend/create_admin.py` or via the `/api/v1/setup` flow.
- OpenAPI is at `/docs` and `/openapi.json` once running; routers are mounted in `backend/app/main.py`.
- There is no Proxmox/BMC in the sandbox. Mock outbound calls (e.g. a local HTTP server pretending to
  be Proxmox on 8006) to show injection from a malicious hypervisor/guest response.
- The built SPA is in `frontend/dist`. There is no automated test suite.

## How we rate severity
- **Critical:** unauthenticated RCE on the Depl0y host; unauthenticated auth bypass to any role;
  unauthenticated disclosure of stored credentials, the Fernet key, or the JWT secret; any
  unauthenticated path to running commands on managed nodes.
- **High:** RCE / command or SSH injection reachable by a viewer or operator; privilege escalation
  viewer/operator → admin; decryption or disclosure of stored infrastructure secrets to a non-admin;
  injection from a malicious guest/node response that leads to code execution on the Depl0y host
  or on other nodes; local privilege escalation from the `depl0y` service user to root through
  the sudoers policy or update path; stored XSS that executes in an admin session; 2FA bypass.
- **Medium:** SSRF that carries stored credentials or reaches internal services; path traversal
  read/write limited to the service user; IDOR across hosts/VMs within the same role; reflected
  XSS; CSRF on state-changing endpoints; secrets written to logs; authentication rate-limit bypass.
- **Low:** information disclosure of non-secret metadata (versions, hostnames), DoS requiring
  authentication, missing security headers, open redirects, issues needing an admin to configure
  something clearly unsafe.
- Unauthenticated DoS of the whole backend from a single request is medium.

## Reports and patches
- Please include the exact endpoint, required role (or "unauthenticated"), and a minimal `curl` or
  Python reproducer against a locally started backend.
- Patches should be minimal and in the existing style (FastAPI dependencies for authz, argument
  lists rather than `shell=True`, `shlex.quote` for remote commands).
- Group findings by root cause: one report for a missing role check that affects many endpoints in
  the same router, not one per endpoint.
