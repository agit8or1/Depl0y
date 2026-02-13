#!/bin/bash
# Depl0y Upgrade Script
# Upgrades an existing Depl0y installation from extracted files

set -e

EXTRACT_DIR="${1:-/tmp/depl0y-update}"
INSTALL_DIR="/opt/depl0y"

echo "🔄 Upgrading Depl0y from $EXTRACT_DIR..."

# Check if source directory exists
if [ ! -d "$EXTRACT_DIR" ]; then
    echo "❌ Source directory not found: $EXTRACT_DIR"
    exit 1
fi

# Check if installation exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo "❌ Depl0y not installed at $INSTALL_DIR"
    echo "   Use install.sh for fresh installations"
    exit 1
fi

# Stop backend service
echo "🛑 Stopping backend service..."
sudo systemctl stop depl0y-backend || true

# Backup current installation
BACKUP_DIR="/tmp/depl0y-backup-$(date +%Y%m%d-%H%M%S)"
echo "💾 Creating backup at $BACKUP_DIR..."
mkdir -p "$BACKUP_DIR"
cp -r "$INSTALL_DIR/backend" "$BACKUP_DIR/" || true
cp -r "$INSTALL_DIR/frontend" "$BACKUP_DIR/" || true

# Copy new files
echo "📦 Copying new backend files..."
sudo rsync -av --exclude='*.pyc' --exclude='__pycache__' --exclude='venv' --exclude='.env' \
    "$EXTRACT_DIR/backend/" "$INSTALL_DIR/backend/"

echo "📦 Copying new frontend files..."
sudo rsync -av "$EXTRACT_DIR/frontend/dist/" "$INSTALL_DIR/frontend/dist/"

echo "📦 Copying scripts..."
sudo cp -r "$EXTRACT_DIR/scripts/"* "$INSTALL_DIR/scripts/" 2>/dev/null || true

echo "📦 Copying config files..."
sudo cp "$EXTRACT_DIR/nginx-depl0y.conf" /etc/nginx/sites-available/depl0y.conf || true
sudo cp "$EXTRACT_DIR/deploy.sh" "$INSTALL_DIR/" || true

# Set correct permissions
echo "🔒 Setting permissions..."
sudo chown -R depl0y:depl0y "$INSTALL_DIR/backend"
sudo chown -R depl0y:depl0y "$INSTALL_DIR/frontend"
sudo chown -R root:root "$INSTALL_DIR/scripts"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
sudo -u depl0y "$INSTALL_DIR/backend/venv/bin/pip" install -q -r "$INSTALL_DIR/backend/requirements.txt"

# Clear Python cache
echo "🗑️  Clearing Python cache..."
find "$INSTALL_DIR/backend" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$INSTALL_DIR/backend" -type f -name '*.pyc' -delete 2>/dev/null || true

# Update version in database
echo "📝 Updating version in database..."
NEW_VERSION=$(grep -o 'return "[0-9]\+\.[0-9]\+\.[0-9]\+"' "$INSTALL_DIR/backend/app/core/config.py" | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)
echo "   Extracted version: $NEW_VERSION"
if [ -n "$NEW_VERSION" ]; then
    # Run sqlite3 as depl0y user (database is owned by depl0y)
    if sudo -u depl0y sqlite3 /var/lib/depl0y/db/depl0y.db "UPDATE system_settings SET value = '$NEW_VERSION' WHERE key = 'app_version';" 2>&1; then
        echo "   ✓ Database version updated to $NEW_VERSION"
    else
        echo "   ⚠ Warning: Failed to update database version"
    fi
else
    echo "   ⚠ Warning: Could not extract version from config.py"
fi

# Restart services
echo "🔄 Restarting services..."
sudo systemctl daemon-reload
sudo systemctl restart depl0y-backend
sudo systemctl reload nginx || sudo systemctl restart nginx

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 8

# Check if backend is running
if sudo systemctl is-active --quiet depl0y-backend; then
    echo "✅ Backend service is running"

    # Get new version from API (try multiple times with increasing delays)
    for i in {1..5}; do
        NEW_VERSION=$(curl -s --max-time 3 http://localhost:8000/ 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || echo "")
        if [ -n "$NEW_VERSION" ]; then
            break
        fi
        echo "   Waiting for API to respond (attempt $i/5)..."
        sleep 2
    done

    if [ -z "$NEW_VERSION" ]; then
        NEW_VERSION="unknown (API not responding)"
    fi

    echo "✅ Upgrade complete! New version: $NEW_VERSION"
    echo ""
    echo "Backup stored at: $BACKUP_DIR"
    echo "You can remove it after verifying the upgrade."
else
    echo "❌ Backend service failed to start"
    echo "   Check logs: journalctl -u depl0y-backend -n 50"
    echo "   Restore from backup: $BACKUP_DIR"
    exit 1
fi
