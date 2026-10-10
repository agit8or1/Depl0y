# Depl0y Deployment Guide

This guide covers how to deploy Depl0y updates, make code changes, and manage the production environment.

## Table of Contents
- [Development Workflow](#development-workflow)
- [Making Code Changes](#making-code-changes)
- [Deploying Changes](#deploying-changes)
- [Creating a Release](#creating-a-release)
- [Update Distribution](#update-distribution)
- [Rollback Procedures](#rollback-procedures)

---

## Development Workflow

### Project Structure
```
/home/administrator/depl0y/          # Development directory
├── backend/                         # Python FastAPI backend
│   ├── app/
│   │   ├── api/                    # API endpoints
│   │   ├── core/                   # Core functionality
│   │   ├── models/                 # Database models
│   │   └── services/               # Business logic
│   ├── requirements.txt
│   └── main.py
├── frontend/                        # Vue.js frontend
│   ├── src/
│   │   ├── views/                  # Page components
│   │   ├── services/               # API services
│   │   ├── store/                  # State management
│   │   └── router/                 # Routes
│   ├── package.json
│   └── vite.config.js
├── scripts/                         # Deployment scripts
├── install.sh                       # One-line installer
└── *.md                            # Documentation

/opt/depl0y/                         # Production directory
├── backend/                         # Production backend
├── frontend/dist/                   # Built frontend assets
└── ...

/var/lib/depl0y/                     # Data directory
├── db/                             # SQLite database
├── isos/                           # ISO images
├── cloud-images/                   # Cloud image cache
└── ssh_keys/                       # SSH keys
```

---

## Making Code Changes

### Backend Changes

1. **Edit Backend Code**
   ```bash
   cd /home/administrator/depl0y/backend
   # Edit files in app/ directory
   ```

2. **Test Changes Locally (Optional)**
   ```bash
   cd /home/administrator/depl0y/backend
   source venv/bin/activate
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
   ```

3. **Check Logs**
   ```bash
   sudo journalctl -u depl0y-backend -f
   ```

### Frontend Changes

1. **Edit Frontend Code**
   ```bash
   cd /home/administrator/depl0y/frontend
   # Edit files in src/ directory
   ```

2. **Test Changes Locally (Optional)**
   ```bash
   cd /home/administrator/depl0y/frontend
   npm run dev
   # Access at http://localhost:5173
   ```

3. **Check Console**
   - Open browser Developer Tools (F12)
   - Check Console for errors
   - Check Network tab for API calls

---

## Deploying Changes

### Quick Deploy Script

Create a deployment script for convenience:

```bash
cat > /home/administrator/depl0y/deploy.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Deploying Depl0y..."

# Build frontend
echo "📦 Building frontend..."
cd /home/administrator/depl0y/frontend
npm run build

# Deploy frontend
echo "📤 Deploying frontend..."
sudo rm -rf /opt/depl0y/frontend/dist/*
sudo cp -r dist/* /opt/depl0y/frontend/dist/
sudo chown -R www-data:www-data /opt/depl0y/frontend/dist
sudo chmod -R 755 /opt/depl0y/frontend/dist

# Deploy backend
echo "📤 Deploying backend..."
sudo cp -r /home/administrator/depl0y/backend/* /opt/depl0y/backend/
sudo chown -R depl0y:depl0y /opt/depl0y/backend
sudo chmod -R 755 /opt/depl0y/backend

# Restart services
echo "🔄 Restarting services..."
sudo systemctl restart depl0y-backend
sudo systemctl reload nginx

# Check status
echo "✅ Checking status..."
sleep 2
sudo systemctl status depl0y-backend --no-pager | head -15

echo ""
echo "✅ Deployment complete!"
echo "Check logs: sudo journalctl -u depl0y-backend -f"
EOF

chmod +x /home/administrator/depl0y/deploy.sh
```

### Deploy with Script

```bash
/home/administrator/depl0y/deploy.sh
```

### Manual Deployment Steps

#### Deploy Backend Only

```bash
# Copy backend files to production
sudo cp -r /home/administrator/depl0y/backend/* /opt/depl0y/backend/

# Fix permissions
sudo chown -R depl0y:depl0y /opt/depl0y/backend
sudo chmod -R 755 /opt/depl0y/backend

# Restart backend service
sudo systemctl restart depl0y-backend

# Check status
sudo systemctl status depl0y-backend
sudo journalctl -u depl0y-backend -n 50
```

#### Deploy Frontend Only

```bash
# Build frontend
cd /home/administrator/depl0y/frontend
npm run build

# Deploy to production
sudo rm -rf /opt/depl0y/frontend/dist/*
sudo cp -r dist/* /opt/depl0y/frontend/dist/

# Fix permissions
sudo chown -R www-data:www-data /opt/depl0y/frontend/dist
sudo chmod -R 755 /opt/depl0y/frontend/dist

# Reload nginx (optional, usually not needed)
sudo systemctl reload nginx
```

#### Deploy Both (Full Deploy)

```bash
# Build frontend
cd /home/administrator/depl0y/frontend
npm run build

# Deploy frontend
sudo rm -rf /opt/depl0y/frontend/dist/*
sudo cp -r dist/* /opt/depl0y/frontend/dist/
sudo chown -R www-data:www-data /opt/depl0y/frontend/dist
sudo chmod -R 755 /opt/depl0y/frontend/dist

# Deploy backend
sudo cp -r /home/administrator/depl0y/backend/* /opt/depl0y/backend/
sudo chown -R depl0y:depl0y /opt/depl0y/backend
sudo chmod -R 755 /opt/depl0y/backend

# Restart services
sudo systemctl restart depl0y-backend
sudo systemctl reload nginx

# Verify
sudo systemctl status depl0y-backend
```

---

## Creating a Release

Installs and in-app updates only see versions that are published as GitHub
releases, so every version that should reach users goes through these steps.

1. **Bump the version** in `backend/app/core/config.py` (`return "X.Y.Z"`) and
   `frontend/package.json`, and add a `## [X.Y.Z]` entry at the top of `CHANGELOG.md`.
2. **Commit and push** to `main`.
3. **Sign and publish the release**, from your own terminal (it asks for the signing
   key's password):
   ```bash
   scripts/release.sh            # or --dry-run to build the assets without signing or publishing
   ```
   It refuses to run with uncommitted changes, if `main` is not pushed, or if the key in
   `minisign.pub` differs from the copies in `install.sh` and `scripts/depl0y-update`.
   It builds `depl0y.tar.gz` (the tree at `HEAD` plus a pre-built `frontend/dist`),
   writes `SHA256SUMS`, signs it with the minisign key at `~/.minisign/depl0y.key`
   (override with `DEPL0Y_MINISIGN_KEY`) and trusted comment `depl0y vX.Y.Z`, checks the
   signature against `minisign.pub`, tags `vX.Y.Z`, and creates the GitHub release with
   the three assets and the CHANGELOG entry as notes. Needs `minisign` and an
   authenticated `gh`.

   Installs refuse releases that are not signed by this key, so **keep an offline backup
   of `~/.minisign/depl0y.key` and its password**. Without it no further release can be
   installed by existing servers until each one is updated by hand. To change the key,
   put the new public key in `minisign.pub`, `install.sh` and `scripts/depl0y-update`
   and publish that release signed with the *old* key; later releases use the new one.
4. **Update this server** from Settings → System Updates (or
   `sudo -u depl0y sudo /usr/local/sbin/depl0y-update apply`).
5. If `install.sh` or `uninstall.sh` changed, copy them from the release to
   `/opt/depl0y/static/downloads/`, which nginx serves at
   `https://deploy.agit8or.net/install.sh` and `/downloads/`.

---

## Update Distribution

Every install updates itself from the GitHub releases of this repository.

1. **Check:** `GET /api/v1/system-updates/check` compares the running version with
   the latest GitHub release.
2. **Apply:** `POST /api/v1/system-updates/apply` (admin only) runs
   `sudo /usr/local/sbin/depl0y-update apply`. That is the only command the `depl0y`
   user may run as root for updates (`scripts/sudoers.depl0y`); it takes no paths or
   versions from the backend.
3. **The updater** (`scripts/depl0y-update`, installed root-owned) runs in its own
   systemd unit so the backend restart does not kill it. It downloads the latest
   release's `depl0y.tar.gz`, `SHA256SUMS` and `SHA256SUMS.minisig`, checks the minisign
   signature against the release key built into it (and that it was made for this
   version), verifies the checksum, refuses downgrades, backs up the current version, installs as the user that owns each
   directory, restarts the backend and checks `/health`. If the backend does not come
   back, it restores the backup. It also refreshes the nginx config, the sudoers file
   and itself from the release.
4. **Progress** is written to `/var/log/depl0y-update/update.log` (readable by
   `depl0y`), which the UI shows through `GET /api/v1/system-updates/log`.

`GET /api/v1/system-updates/download` on this server only redirects to the latest
release asset, for copies of `install.sh` older than 2.2.90.

---

## Rollback Procedures

### Automatic Backups

Before installing, the updater backs up the backend (without the virtualenv) and
`frontend/dist` to:
```
/var/backups/depl0y/<previous-version>-YYYYMMDD-HHMMSS/{backend,dist}
```
A failed update restores it automatically.

### Manual Rollback

1. **Stop the service**
   ```bash
   sudo systemctl stop depl0y-backend
   ```

2. **Restore from backup** (as the owning users, like the updater does)
   ```bash
   ls -la /var/backups/depl0y/
   B=/var/backups/depl0y/<previous-version>-YYYYMMDD-HHMMSS
   sudo -u depl0y rsync -a "$B/backend/" /opt/depl0y/backend/
   sudo -u depl0y /opt/depl0y/backend/venv/bin/pip install -r /opt/depl0y/backend/requirements.txt
   sudo -u "$(stat -c %U /opt/depl0y/frontend/dist)" rsync -a --delete "$B/dist/" /opt/depl0y/frontend/dist/
   ```

3. **Restart service**
   ```bash
   sudo systemctl start depl0y-backend
   sudo systemctl status depl0y-backend
   ```

4. **Record the version** so the next update compares against it
   ```bash
   grep -o 'return "[0-9.]*"' /opt/depl0y/backend/app/core/config.py
   echo X.Y.Z | sudo tee /var/lib/depl0y-update/installed
   ```

### Manual Backup Before Changes

```bash
BACKUP_DIR="/var/backups/depl0y/manual-$(date +%Y%m%d-%H%M%S)"
sudo mkdir -p "$BACKUP_DIR"
sudo cp -a /opt/depl0y/backend "$BACKUP_DIR/"
sudo cp -a /opt/depl0y/frontend/dist "$BACKUP_DIR/"
sudo cp -a /var/lib/depl0y/db "$BACKUP_DIR/"
echo "Backup created at $BACKUP_DIR"
```

---

## Common Deployment Issues

### Issue: Backend Service Won't Start

**Check logs:**
```bash
sudo journalctl -u depl0y-backend -n 100
```

**Common causes:**
- Python syntax errors
- Missing dependencies
- Database connection issues
- Port already in use

**Fix:**
```bash
# Check if port 8000 is in use
sudo lsof -i :8000

# Reinstall dependencies if needed
cd /opt/depl0y/backend
sudo -u depl0y venv/bin/pip install -r requirements.txt
```

### Issue: Frontend Shows Blank Page

**Check:**
1. Browser console (F12) for JavaScript errors
2. Nginx error logs: `sudo tail -f /var/log/nginx/depl0y_error.log`
3. Verify build was successful
4. Check file permissions

**Fix:**
```bash
# Rebuild and redeploy
cd /home/administrator/depl0y/frontend
npm run build
sudo rm -rf /opt/depl0y/frontend/dist/*
sudo cp -r dist/* /opt/depl0y/frontend/dist/
sudo chown -R www-data:www-data /opt/depl0y/frontend/dist
sudo chmod -R 755 /opt/depl0y/frontend/dist
```

### Issue: API Calls Failing (500 Errors)

**Check backend logs:**
```bash
sudo journalctl -u depl0y-backend -f
```

**Common causes:**
- Backend crashed
- Database errors
- API endpoint errors

**Quick restart:**
```bash
sudo systemctl restart depl0y-backend
```

### Issue: Changes Not Appearing

**For backend:**
```bash
# Make sure you restarted the service
sudo systemctl restart depl0y-backend

# Verify files were copied
ls -la /opt/depl0y/backend/app/api/
```

**For frontend:**
```bash
# Make sure you rebuilt
cd /home/administrator/depl0y/frontend
npm run build

# Verify files were copied
ls -la /opt/depl0y/frontend/dist/

# Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
```

---

## Monitoring and Maintenance

### Check Service Status
```bash
sudo systemctl status depl0y-backend
sudo systemctl status nginx
```

### View Logs
```bash
# Live backend logs
sudo journalctl -u depl0y-backend -f

# Last 100 lines
sudo journalctl -u depl0y-backend -n 100

# Nginx access logs
sudo tail -f /var/log/nginx/depl0y_access.log

# Nginx error logs
sudo tail -f /var/log/nginx/depl0y_error.log
```

### Restart Services
```bash
# Backend only
sudo systemctl restart depl0y-backend

# Nginx only
sudo systemctl reload nginx

# Both
sudo systemctl restart depl0y-backend
sudo systemctl reload nginx
```

### Check Disk Space
```bash
df -h /opt/depl0y
df -h /var/lib/depl0y
```

### Clean Up Old Backups
```bash
# List backups (made by the updater before each update)
sudo ls -lah /var/backups/depl0y/

# Remove old backups (keep last 5)
sudo find /var/backups/depl0y -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
    | sort -rn | tail -n +6 | cut -d' ' -f2- | xargs -r sudo rm -rf
```

---

## Quick Reference

### Deploy Everything
```bash
cd /home/administrator/depl0y/frontend && npm run build && \
sudo rm -rf /opt/depl0y/frontend/dist/* && \
sudo cp -r dist/* /opt/depl0y/frontend/dist/ && \
sudo cp -r /home/administrator/depl0y/backend/* /opt/depl0y/backend/ && \
sudo chown -R www-data:www-data /opt/depl0y/frontend/dist && \
sudo chown -R depl0y:depl0y /opt/depl0y/backend && \
sudo systemctl restart depl0y-backend
```

### Check Everything
```bash
sudo systemctl status depl0y-backend nginx && \
curl -s http://localhost/api/v1/system-updates/version | head -5 && \
sudo journalctl -u depl0y-backend -n 10
```

### Emergency Restart
```bash
sudo systemctl restart depl0y-backend nginx && \
sleep 2 && \
sudo systemctl status depl0y-backend
```

---

**For more information, see:**
- [INSTALL.md](INSTALL.md) - Installation guide
- [README.md](README.md) - Project overview
- [CLOUD_IMAGES_GUIDE.md](CLOUD_IMAGES_GUIDE.md) - Cloud images setup
