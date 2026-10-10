# Depl0y Installation Guide

## One-Line Installation

Install Depl0y with a single command:

```bash
curl -fsSL https://raw.githubusercontent.com/agit8or1/Depl0y/main/install.sh -o install.sh
less install.sh          # read it before running it
sudo bash install.sh
```

The installer is fetched from the repository rather than piped straight into
`sudo bash`, so you can read what will run as root before it runs. The copy at
`https://deploy.agit8or.net/downloads/install.sh` is the same script, but the
repository is the authoritative source.

The installer will:
- Install all dependencies (Python, Node.js, nginx, etc.)
- Create the depl0y system user
- Download the latest GitHub release and check its minisign signature and `SHA256SUMS`
- Configure the backend service
- Configure nginx as reverse proxy
- Set up proper permissions

## After Installation

1. **Access the Web Interface**
   ```
   http://YOUR_SERVER_IP
   ```

2. **Default Credentials**
   ```
   Username: admin
   Password: admin
   ```

   ⚠️ **IMPORTANT:** Change the default password immediately after first login!

3. **Add Your Proxmox Host**
   - Go to Settings → Proxmox Hosts
   - Add your Proxmox datacenter details
   - Generate API token in Proxmox and add it

4. **Enable Cloud Images** (Optional but Recommended)
   - Go to Settings → Cloud Images
   - Click "🚀 Enable Cloud Images Now"
   - Enter your Proxmox root password
   - Wait ~30 seconds for automated setup

5. **Configure Inter-Node SSH** (For Multi-Node Clusters Only)
   - Go to Settings → Proxmox Cluster Inter-Node SSH
   - Click "🔐 Enable Inter-Node SSH"
   - Enter your Proxmox root password
   - Wait ~30 seconds for automated setup

## Manual Installation

If you prefer to install manually, see [README.md](README.md) for detailed instructions.

## Deployment Guide

For developers and operations teams who need to deploy code changes or manage updates:

📖 **See [DEPLOYMENT.md](DEPLOYMENT.md)** for complete deployment procedures including:
- Making and deploying code changes
- Creating releases and updates
- Rollback procedures
- Troubleshooting deployment issues

## Requirements

- Ubuntu 20.04+ or Debian 11+ (recommended)
- 2GB RAM minimum
- 20GB disk space minimum
- Root access
- Network access to your Proxmox server

## Update Mechanism

Depl0y includes an automatic update system:

1. **Check for Updates**
   - Go to Settings → System Updates
   - Click "🔍 Check for Updates"

2. **Install Updates**
   - If an update is available, click "⬇️ Install Update" (admins only)
   - The root-owned updater `/usr/local/sbin/depl0y-update` downloads the latest
     GitHub release, checks its minisign signature and `SHA256SUMS`, backs up the current version to
     `/var/backups/depl0y/`, installs it and restarts the backend
   - If the backend does not come back healthy, the previous version is restored
   - Progress is shown in the page and logged to `/var/log/depl0y-update/update.log`

Installs made with an `install.sh` older than 2.2.90 may not be able to update from
the UI. Re-run the current `install.sh`; it keeps your database and keys.

## Where releases come from

Installs and updates use the [GitHub releases](https://github.com/agit8or1/Depl0y/releases)
of this repository: each has `depl0y.tar.gz` (source plus the built frontend) and
`SHA256SUMS`.

## Troubleshooting

### Installation Failed
```bash
# Check logs
sudo journalctl -u depl0y-backend -n 50

# Restart service
sudo systemctl restart depl0y-backend

# Check nginx
sudo nginx -t
sudo systemctl status nginx
```

### Cannot Access Web Interface
```bash
# Check if service is running
sudo systemctl status depl0y-backend

# Check nginx
sudo systemctl status nginx

# Check firewall
sudo ufw status
sudo ufw allow 80/tcp
```

### Database Issues
```bash
# Reset database (WARNING: Deletes all data!)
sudo systemctl stop depl0y-backend
sudo rm -rf /var/lib/depl0y/db/*
sudo systemctl start depl0y-backend
```

## Uninstallation

To completely remove Depl0y:

```bash
# Stop services
sudo systemctl stop depl0y-backend
sudo systemctl disable depl0y-backend

# Remove files
sudo rm -rf /opt/depl0y
sudo rm -rf /var/lib/depl0y
sudo rm /etc/systemd/system/depl0y-backend.service
sudo rm /etc/nginx/sites-enabled/depl0y
sudo rm /etc/nginx/sites-available/depl0y
sudo rm /etc/sudoers.d/depl0y

# Remove user
sudo userdel -r depl0y

# Reload services
sudo systemctl daemon-reload
sudo systemctl restart nginx
```

## Support

- **Documentation:** https://deploy.agit8or.net/docs
- **Issues:** Report bugs and request features on GitHub
- **Updates:** [GitHub releases](https://github.com/agit8or1/Depl0y/releases), installed from Settings → System Updates

---

**Depl0y** - Automated VM Deployment Panel for Proxmox VE
