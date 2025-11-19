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

### 1. Update Version Number

Edit the version in the backend config:

```bash
nano /home/administrator/depl0y/backend/app/core/config.py
```

Change:
```python
APP_VERSION: str = "1.1.0"  # Update this
```

### 2. Update Release Notes

Edit the system updates endpoint:

```bash
nano /home/administrator/depl0y/backend/app/api/system_updates.py
```

Update the `release_notes` in the `/version` endpoint:
```python
"release_notes": f"""
Depl0y {settings.APP_VERSION} Release Notes:

✨ New Features:
- Feature 1
- Feature 2

🔧 Improvements:
- Improvement 1
- Improvement 2

🐛 Bug Fixes:
- Fix 1
- Fix 2
"""
```

### 3. Deploy to Production

```bash
/home/administrator/depl0y/deploy.sh
```

### 4. Test Update Endpoint

```bash
curl http://localhost/api/v1/system-updates/version
```

Verify the version and release notes are correct.

---

## Update Distribution

Depl0y uses a **pull-based update system** where client instances pull updates from the main server (`deploy.agit8or.net`).

### How Updates Work

1. **Main Server** (deploy.agit8or.net)
   - Serves version information via `/api/v1/system-updates/version`
   - Provides update packages via `/api/v1/system-updates/download`
   - Hosts the installer via `/install.sh`

2. **Client Instances**
   - Check for updates by querying main server
   - Compare local version with latest version
   - Download and apply updates if available

### Making Main Server the Update Source

If this is your main update server (`deploy.agit8or.net`):

1. **Ensure the installer is accessible**
   ```bash
   # The installer should be served by nginx
   curl http://deploy.agit8or.net/install.sh
   ```

2. **Update the backend config if needed**
   ```bash
   nano /home/administrator/depl0y/backend/app/api/system_updates.py
   ```

   Verify:
   ```python
   UPDATE_SERVER = "http://deploy.agit8or.net"
   ```

3. **Test the update endpoints**
   ```bash
   # Version info
   curl http://deploy.agit8or.net/api/v1/system-updates/version

   # Download package (requires auth)
   curl -H "Authorization: Bearer YOUR_TOKEN" \
        http://deploy.agit8or.net/api/v1/system-updates/download \
        -o test-package.tar.gz
   ```

### Client Update Process

When a client checks for updates (Settings → System Updates):

1. Client calls `/api/v1/system-updates/check`
2. Backend queries main server at `http://deploy.agit8or.net/api/v1/system-updates/version`
3. Compares versions
4. If update available, shows "Install Update" button
5. When clicked, downloads from `http://deploy.agit8or.net/api/v1/system-updates/download`
6. Extracts, builds, deploys, and restarts

---

## Rollback Procedures

### Automatic Backups

The update system creates automatic backups at:
```
/opt/depl0y-backups/backup-YYYYMMDD-HHMMSS/
```

### Manual Rollback

1. **Stop the service**
   ```bash
   sudo systemctl stop depl0y-backend
   ```

2. **Restore from backup**
   ```bash
   # Find latest backup
   ls -la /opt/depl0y-backups/

   # Restore backend
   sudo cp -r /opt/depl0y-backups/backup-YYYYMMDD-HHMMSS/backend/* /opt/depl0y/backend/

   # Restore frontend (if backed up)
   sudo cp -r /opt/depl0y-backups/backup-YYYYMMDD-HHMMSS/frontend/* /opt/depl0y/frontend/
   ```

3. **Fix permissions**
   ```bash
   sudo chown -R depl0y:depl0y /opt/depl0y/backend
   sudo chown -R www-data:www-data /opt/depl0y/frontend/dist
   ```

4. **Restart service**
   ```bash
   sudo systemctl start depl0y-backend
   sudo systemctl status depl0y-backend
   ```

### Manual Backup Before Changes

```bash
# Create backup directory
BACKUP_DIR="/opt/depl0y-backups/manual-$(date +%Y%m%d-%H%M%S)"
sudo mkdir -p "$BACKUP_DIR"

# Backup backend
sudo cp -r /opt/depl0y/backend "$BACKUP_DIR/"

# Backup frontend
sudo cp -r /opt/depl0y/frontend "$BACKUP_DIR/"

# Backup database
sudo cp -r /var/lib/depl0y/db "$BACKUP_DIR/"

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
# List backups
ls -lah /opt/depl0y-backups/

# Remove old backups (keep last 5)
cd /opt/depl0y-backups/
ls -t | tail -n +6 | xargs sudo rm -rf
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
