# Installation

**The installation guide now lives in [QUICKSTART.md](QUICKSTART.md).** It covers
requirements, the installer, connecting a Proxmox endpoint, attaching a BMC,
permissions and troubleshooting.

Short version — on an Ubuntu or Debian VM of its own:

```bash
curl -fsSL https://raw.githubusercontent.com/agit8or1/Depl0y/main/install.sh -o install.sh
less install.sh          # read it before running it
sudo bash install.sh
```

Then open `http://<server-ip>/` and sign in with `admin` / `admin`, changing that
password immediately.

---

## About the Docker Compose path

This file previously documented a Docker Compose deployment backed by MariaDB,
driven by `scripts/setup.sh` and `docker-compose.yml`. Both files are still in
the tree, but that path is **not the supported one and is not routinely tested**.
It also diverges from what `install.sh` produces:

| | `install.sh` (supported) | `docker-compose.yml` |
|---|---|---|
| Database | SQLite at `/var/lib/depl0y/db/depl0y.db` | MariaDB in a container |
| Process manager | `depl0y-backend` systemd unit | Compose |
| Web server | nginx on the host | container |

Because the two produce different layouts, the upgrade, backup and
troubleshooting instructions in [QUICKSTART.md](QUICKSTART.md) and
[ARCHITECTURE.md](ARCHITECTURE.md) apply to the `install.sh` layout only.

If you want the container path maintained, please open an issue — it would be
good to know someone is using it.
