#!/bin/bash
#
# Depl0y Uninstaller
# Completely removes Depl0y from your system
#

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║   ██████╗ ███████╗██████╗ ██╗      ██████╗ ██╗   ██╗   ║"
echo "║   ██╔══██╗██╔════╝██╔══██╗██║     ██╔═████╗╚██╗ ██╔╝   ║"
echo "║   ██║  ██║█████╗  ██████╔╝██║     ██║██╔██║ ╚████╔╝    ║"
echo "║   ██║  ██║██╔══╝  ██╔═══╝ ██║     ████╔╝██║  ╚██╔╝     ║"
echo "║   ██████╔╝███████╗██║     ███████╗╚██████╔╝   ██║      ║"
echo "║   ╚═════╝ ╚══════╝╚═╝     ╚══════╝ ╚═════╝    ╚═╝      ║"
echo "║                                                          ║"
echo "║                    UNINSTALLER                          ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
   echo "ERROR: Please run as root (use sudo)"
   exit 1
fi

# Check for -y flag or if stdin is not a terminal (piped input)
SKIP_CONFIRM=false
if [[ "$1" == "-y" || "$1" == "--yes" ]]; then
    SKIP_CONFIRM=true
elif [ ! -t 0 ]; then
    # Not running in terminal (piped through curl)
    echo "⚠️  WARNING: Running in non-interactive mode"
    echo ""
    echo "To uninstall Depl0y, run this command:"
    echo "  curl -fsSL http://deploy.agit8or.net/downloads/uninstall.sh | sudo bash -s -- -y"
    echo ""
    echo "Or download and run locally:"
    echo "  curl -fsSL http://deploy.agit8or.net/downloads/uninstall.sh -o uninstall.sh"
    echo "  sudo bash uninstall.sh"
    echo ""
    exit 1
fi

if [ "$SKIP_CONFIRM" = false ]; then
    echo "⚠️  WARNING: This will completely remove Depl0y from your system"
    echo ""
    echo "This will:"
    echo "  • Stop and remove the depl0y-backend service"
    echo "  • Remove all Depl0y files from /opt/depl0y"
    echo "  • Remove database and logs from /var/lib/depl0y and /var/log/depl0y"
    echo "  • Remove nginx configuration"
    echo "  • Remove the depl0y system user"
    echo "  • Remove sudo permissions"
    echo "  • Remove installed dependencies (Python packages, Node.js packages)"
    echo ""
    echo "⚠️  DATABASE WILL BE DELETED - All VM configurations will be lost!"
    echo ""
    read -p "Are you sure you want to uninstall Depl0y? (yes/NO): " -r CONFIRM < /dev/tty || CONFIRM="NO"
    echo ""

    if [ "$CONFIRM" != "yes" ]; then
        echo "Uninstall cancelled."
        exit 0
    fi
else
    echo "⚠️  Uninstalling Depl0y (confirmation skipped with -y flag)..."
    echo ""
fi

echo "Starting uninstallation..."
echo ""

# Stop and disable backend service
echo "🛑 Stopping depl0y-backend service..."
if systemctl is-active --quiet depl0y-backend; then
    systemctl stop depl0y-backend
    echo "✓ Service stopped"
else
    echo "✓ Service was not running"
fi

if systemctl is-enabled --quiet depl0y-backend 2>/dev/null; then
    systemctl disable depl0y-backend
    echo "✓ Service disabled"
fi

# Remove systemd service file
echo ""
echo "🗑️  Removing systemd service..."
if [ -f /etc/systemd/system/depl0y-backend.service ]; then
    rm -f /etc/systemd/system/depl0y-backend.service
    systemctl daemon-reload
    echo "✓ Service file removed"
fi

# Remove application files
echo ""
echo "🗑️  Removing application files..."
if [ -d /opt/depl0y ]; then
    rm -rf /opt/depl0y
    echo "✓ Removed /opt/depl0y"
fi

# Remove data and logs
echo ""
echo "🗑️  Removing database and logs..."
if [ -d /var/lib/depl0y ]; then
    rm -rf /var/lib/depl0y
    echo "✓ Removed /var/lib/depl0y (database, cloud images, ISOs)"
fi

if [ -d /var/log/depl0y ]; then
    rm -rf /var/log/depl0y
    echo "✓ Removed /var/log/depl0y"
fi

# Remove nginx configuration
echo ""
echo "🗑️  Removing nginx configuration..."
if [ -f /etc/nginx/sites-enabled/depl0y ]; then
    rm -f /etc/nginx/sites-enabled/depl0y
    echo "✓ Removed nginx sites-enabled/depl0y"
fi

if [ -f /etc/nginx/sites-available/depl0y ]; then
    rm -f /etc/nginx/sites-available/depl0y
    echo "✓ Removed nginx sites-available/depl0y"
fi

# Restore default site if it existed
if [ -f /etc/nginx/sites-available/default ] && [ ! -f /etc/nginx/sites-enabled/default ]; then
    ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default
    echo "✓ Restored nginx default site"
fi

# Test and reload nginx
if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx
    echo "✓ Nginx reloaded"
else
    echo "⚠️  Nginx configuration test failed, skipping reload"
fi

# Remove sudoers file
echo ""
echo "🗑️  Removing sudo permissions..."
if [ -f /etc/sudoers.d/depl0y ]; then
    rm -f /etc/sudoers.d/depl0y
    echo "✓ Removed /etc/sudoers.d/depl0y"
fi

# Remove depl0y user
echo ""
echo "👤 Removing depl0y system user..."
if id -u depl0y >/dev/null 2>&1; then
    userdel -r depl0y 2>/dev/null || userdel depl0y 2>/dev/null || true
    echo "✓ User 'depl0y' removed"
else
    echo "✓ User 'depl0y' does not exist"
fi

# Remove temporary files and caches
echo ""
echo "🧹 Cleaning up temporary files and caches..."
rm -f /tmp/depl0y-*.tar.gz 2>/dev/null || true
rm -rf /tmp/depl0y-install 2>/dev/null || true
rm -f /tmp/enable_cloud_images.sh 2>/dev/null || true
rm -rf /tmp/depl0y* 2>/dev/null || true
echo "✓ Temporary files cleaned"

# Optional: Remove installed packages (commented out by default for safety)
echo ""
echo "📦 Package cleanup..."
echo "   Note: System packages (Python, Node.js, nginx, etc.) were NOT removed"
echo "   as they may be used by other applications."
echo ""
echo "   To remove them manually if desired:"
echo "     sudo apt-get remove --purge python3-venv python3-dev nodejs npm nginx"
echo "     sudo apt-get autoremove"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║              ✅ UNINSTALL COMPLETE                        ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Depl0y has been completely removed from your system."
echo ""
echo "The following were NOT automatically removed (remove manually if needed):"
echo "  • System packages: python3, nodejs, npm, nginx, sqlite3"
echo "  • (These may be used by other applications)"
echo ""
echo "To remove system packages manually:"
echo "  sudo apt-get remove --purge python3-venv python3-dev nodejs npm nginx sqlite3"
echo "  sudo apt-get autoremove"
echo ""
echo "To reinstall Depl0y:"
echo "  curl -fsSL http://deploy.agit8or.net/downloads/install.sh | sudo bash"
echo ""
