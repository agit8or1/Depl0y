# Quick start

Install Depl0y, connect your first Proxmox endpoint, and add a BMC.

---

## 1. Requirements

**Depl0y server** — a small VM or LXC of its own; it does not run on the
Proxmox nodes.

| | |
|---|---|
| OS | Ubuntu or Debian (the installer refuses anything else) |
| CPU / RAM | 2 vCPU, 2 GB RAM is enough for a handful of endpoints |
| Disk | 20 GB |
| Installed for you | Python 3, Node.js, nginx, SQLite and supporting libraries |
| Ports | 80/tcp inbound (nginx); the backend listens on 127.0.0.1:8000 |

**Reachability from the Depl0y server**

| Target | Why |
|---|---|
| Proxmox API, `tcp/8006` | everything |
| Proxmox node SSH, `tcp/22` | VM import, inter-node SSH setup, node terminal, OS-level power actions |
| BMC HTTPS, `tcp/443` | iDRAC / iLO health, inventory and power control |
| `github.com` | in-app update check and download |
| `downloads.dell.com` | daily Dell firmware-catalog check (optional) |

**Browser** — the noVNC console loads its client from `cdn.jsdelivr.net`, and the
map view loads OpenStreetMap tiles. Both are optional features; the rest of the
panel works without outbound browser access.

---

## 2. Install

The installer is a single script. Fetch it from this repository, read it, then
run it:

```bash
curl -fsSL https://raw.githubusercontent.com/agit8or1/Depl0y/main/install.sh -o install.sh
less install.sh
sudo bash install.sh
```

It creates a `depl0y` system user, installs the dependencies, downloads the
current application bundle, writes `/etc/depl0y/config.env` with freshly
generated `SECRET_KEY` and `ENCRYPTION_KEY` values, installs the
`depl0y-backend` systemd unit, and configures nginx as the reverse proxy.

When it finishes, open `http://<server-ip>/` and sign in with `admin` / `admin`.

> **Change the admin password immediately**, then enable TOTP under
> **Settings → User Profile**.

Re-running the installer on an existing server upgrades in place and keeps the
existing `ENCRYPTION_KEY`, which is what makes your stored credentials readable.

---

## 3. Connect a Proxmox endpoint

An API token is the recommended credential — it is not affected by 2FA on the
Proxmox side and can be revoked on its own.

**In Proxmox:** Datacenter → Permissions → API Tokens → **Add**

- **User:** `root@pam` (or another account with the rights you want Depl0y to have)
- **Token ID:** e.g. `depl0y`
- **Privilege Separation:** **unchecked** — see [Permissions](#4-permissions)
- Copy the secret; Proxmox shows it exactly once.

**In Depl0y:** Proxmox Hosts → **+ Add Datacenter**

| Field | Value |
|---|---|
| Name | anything — it labels the site in the UI |
| Hostname / IP | your Proxmox host |
| Port | `8006` |
| Username | the token's owner, e.g. `root@pam` |
| API Token ID | `root@pam!depl0y`, or just `depl0y` |
| API Token Secret | the UUID you copied |
| Verify SSL | leave off for the default self-signed Proxmox certificate |

Depl0y tests the connection before saving. Repeat for every cluster or
standalone host you want in one dashboard.

Username/password authentication also works and is the fallback when tokens are
not an option.

---

## 4. Permissions

Depl0y is exercised with a token whose **privilege separation is disabled**, so
the token carries the owner's full rights. Several features need that level of
access:

- `pvesh`-based OS shutdown / reboot, node terminal and cluster join/unjoin
  effectively require `root@pam`.
- VM import and inter-node SSH setup need SSH access to the nodes.

A reduced-privilege Proxmox role that still covers everything has **not** been
validated. If you want to limit blast radius, create a dedicated Proxmox user
with only the privileges your team actually uses, accept that some views will
return errors, and open an issue describing what broke.

Inside Depl0y, accounts are separate from Proxmox realms and come in three
roles:

| Role | Can |
|---|---|
| Admin | everything, including user management and host credentials |
| Operator | create, change and delete guests; manage hosts and images |
| Viewer | read-only |

Every action lands in the audit log, and accounts can be scoped to specific
Proxmox endpoints.

---

## 5. Add a BMC (iDRAC / iLO)

Hardware data is attached per node, not per cluster.

1. Go to **Proxmox Hosts** and expand the cluster's nodes, or open
   **iDRAC / iLO**.
2. Use **Edit BMC** on the node and enter the BMC address, port (`443`),
   credentials and type (`idrac` or `ilo`).
3. Save. The background poller picks it up on the next cycle; **Poll Now**
   forces one immediately.

Depl0y tries Redfish and SSH against the same address and merges whatever each
returns, so a box that answers only one of them still reports.

If a Dell box shows a blank model — common on iDRAC 7 — click the pencil on the
model chip and set it manually; the override is stored and applied to the live
cache.

---

## 6. Optional setup

- **Cloud images** — Settings → Cloud Images → *Enable Cloud Images*. Needs the
  Proxmox root password once, to stage templates on the node.
- **Inter-node SSH** — Settings → Proxmox Cluster Inter-Node SSH. Required for
  migrations and imports across a multi-node cluster.
- **Proxmox Backup Server** — add PBS endpoints under PBS Management to browse
  datastores and trigger backups.

---

## Troubleshooting

**Cannot connect to the Proxmox host**
Check the credentials, confirm `tcp/8006` is reachable from the Depl0y server,
and turn *Verify SSL* off if the node uses the default self-signed certificate.

**BMC shows "Pending first poll" or "Unreachable"**
Confirm `tcp/443` to the BMC from the Depl0y server, and that the account can
read Redfish. iDRAC 7 needs the legacy TLS path Depl0y already enables — if it
still fails, the BMC is usually locked out after repeated bad credentials.

**VM import fails**
The target node needs a storage with enough free space, and SSH between the
Depl0y server and the Proxmox host must be configured (Settings → SSH Setup).

**Cluster join fails**
The cluster master's `root@pam` password must be correct. The fingerprint is
fetched automatically; if that fails, read it from `pvecm status` on the master.

**Backend logs**

```bash
sudo journalctl -u depl0y-backend -f
```
