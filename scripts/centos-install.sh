#!/bin/bash
#
# Depl0y - Automated VM Deployment Panel Installer
# RHEL/CentOS/Rocky/AlmaLinux Compatible Version
# Complete automated installation - no manual steps required!
# One-line install: curl -fsSL http://your-server/install-rhel.sh | sudo bash
#

set -e

# Installer version for tracking
INSTALLER_VERSION="1.1.0"
INSTALLER_BUILD="$(date +%Y%m%d%H%M%S)"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║   ██████╗ ███████╗██████╗ ██╗      ██████╗ ██╗   ██╗   ║"
echo "║   ██╔══██╗██╔════╝██╔══██╗██║     ██╔═████╗╚██╗ ██╔╝   ║"
echo "║   ██║  ██║█████╗  ██████╔╝██║     ██║██╔██║ ╚████╔╝    ║"
echo "║   ██║  ██║██╔══╝  ██╔═══╝ ██║     ████╔╝██║  ╚██╔╝     ║"
echo "║   ██████╔╝███████╗██║     ███████╗╚██████╔╝   ██║      ║"
echo "║   ╚═════╝ ╚══════╝╚═╝     ╚══════╝ ╚═════╝    ╚═╝      ║"
echo "║                                                          ║"
echo "║       Automated VM Deployment Panel for Proxmox VE      ║"
echo "║              https://deploy.agit8or.net                 ║"
echo "║           Version 1.1.5 (RHEL/CentOS Edition)           ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "This installer will:"
echo "  ✓ Install all dependencies"
echo "  ✓ Set up Depl0y application"
echo "  ✓ Configure cloud images (optional)"
echo "  ✓ Configure inter-node SSH (optional)"
echo "  ✓ No manual steps required!"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
   echo "ERROR: Please run as root (use sudo)"
   exit 1
fi

echo "🚀 Starting Depl0y installation..."
echo ""

# Check if Depl0y is already installed
UPGRADE_MODE=false
if [ -d "/opt/depl0y" ] && [ -f "/etc/systemd/system/depl0y-backend.service" ]; then
    UPGRADE_MODE=true
    echo "📦 Existing Depl0y installation detected"
    echo "   This will upgrade your installation while preserving your database"
    echo ""
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VER=$VERSION_ID
else
    echo "ERROR: Cannot detect OS"
    exit 1
fi

echo "✓ Detected OS: $OS $VER"

# Check if RHEL-based (CentOS, RHEL, Rocky, AlmaLinux, Fedora)
if [[ "$OS" != "centos" && "$OS" != "rhel" && "$OS" != "rocky" && "$OS" != "almalinux" && "$OS" != "fedora" ]]; then
    echo "ERROR: This installer supports RHEL, CentOS, Rocky Linux, AlmaLinux, and Fedora"
    echo "       For Ubuntu/Debian, use the original install.sh"
    exit 1
fi

# Update system
echo ""
echo "📦 Updating system packages..."
dnf update -y -q

# Enable EPEL and CRB/PowerTools repositories if needed
echo "📦 Enabling required repositories..."
if [[ "$OS" == "centos" || "$OS" == "rhel" || "$OS" == "rocky" || "$OS" == "almalinux" ]]; then
    dnf install -y -q epel-release || true
    # CRB (CodeReady Builder) for RHEL 9+/CentOS Stream 9+
    dnf config-manager --set-enabled crb 2>/dev/null || \
    dnf config-manager --set-enabled powertools 2>/dev/null || \
    dnf config-manager --set-enabled codeready-builder-for-rhel-* 2>/dev/null || true
fi

# Install ALL dependencies
echo "📦 Installing dependencies..."
echo "   This includes: Python, Node.js, nginx, SQLite, PDF libraries, and more"

# Install base dependencies
dnf install -y -q \
    python3 \
    python3-pip \
    python3-devel \
    gcc \
    gcc-c++ \
    make \
    nginx \
    sqlite \
    curl \
    wget \
    git \
    sshpass \
    openssh-clients \
    at \
    ca-certificates \
    gnupg2 \
    redhat-lsb-core \
    pango \
    cairo \
    gdk-pixbuf2 \
    libffi-devel \
    shared-mime-info \
    openssl-devel 2>/dev/null || \
dnf install -y \
    python3 \
    python3-pip \
    python3-devel \
    gcc \
    gcc-c++ \
    make \
    nginx \
    sqlite \
    curl \
    wget \
    git \
    sshpass \
    openssh-clients \
    at \
    ca-certificates \
    pango \
    cairo \
    gdk-pixbuf2 \
    libffi-devel \
    shared-mime-info \
    openssl-devel

# Install Node.js (using NodeSource or dnf module)
echo "📦 Installing Node.js..."
if ! command -v node &> /dev/null; then
    # Try dnf module first
    dnf module enable -y nodejs:18 2>/dev/null || true
    dnf install -y -q nodejs npm 2>/dev/null || {
        # Fallback to NodeSource
        curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
        dnf install -y nodejs
    }
fi

echo "✓ Dependencies installed"

# Create depl0y user
echo ""
echo "👤 Creating depl0y system user..."
if ! id -u depl0y > /dev/null 2>&1; then
    useradd -r -m -d /opt/depl0y -s /bin/bash depl0y
    echo "✓ User 'depl0y' created"
else
    echo "✓ User 'depl0y' already exists"
fi

# If upgrading, stop the backend service and backup encryption keys
if [ "$UPGRADE_MODE" = true ]; then
    echo "🔄 Preparing for upgrade..."

    # Clear any stale Python cache first
    echo "🗑️  Clearing old Python cache..."
    find /opt/depl0y/backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find /opt/depl0y/backend -type f -name "*.pyc" -delete 2>/dev/null || true
    echo "✓ Cache cleared"

    if systemctl is-active --quiet depl0y-backend; then
        systemctl stop depl0y-backend
        echo "✓ Stopped backend service"
    fi

    # Backup encryption keys from existing service
    KEYS_VALID=false
    if [ -f /etc/systemd/system/depl0y-backend.service ]; then
        echo "🔍 Extracting existing encryption keys..."
        EXISTING_SECRET=$(grep "SECRET_KEY=" /etc/systemd/system/depl0y-backend.service | sed 's/.*SECRET_KEY=\([^"]*\).*/\1/')
        EXISTING_ENCRYPTION=$(grep "ENCRYPTION_KEY=" /etc/systemd/system/depl0y-backend.service | sed 's/.*ENCRYPTION_KEY=\([^"]*\).*/\1/')

        if [ -n "$EXISTING_SECRET" ] && [ -n "$EXISTING_ENCRYPTION" ]; then
            echo "   Found existing keys, validating..."
            # Validate the encryption key (use venv Python if available, otherwise skip validation)
            if /opt/depl0y/backend/venv/bin/python3 -c "from cryptography.fernet import Fernet; Fernet('${EXISTING_ENCRYPTION}'.encode())" 2>/dev/null || \
               python3 -c "from cryptography.fernet import Fernet; Fernet('${EXISTING_ENCRYPTION}'.encode())" 2>/dev/null; then
                echo "✓ Existing encryption keys are valid and will be preserved"
                KEYS_VALID=true
            else
                echo "⚠️  Existing encryption keys are INVALID (wrong format)"
                echo "   Will generate new keys - you'll need to re-enter Proxmox credentials"
            fi
        else
            echo "⚠️  Could not extract existing keys from service file"
            echo "   Will generate new keys"
        fi
    fi
fi

# Download latest Depl0y
echo ""
echo "⬇️  Downloading Depl0y from deploy.agit8or.net..."
cd /tmp
rm -f depl0y-latest.tar.gz
# Add cache-busting timestamp to ensure fresh download
CACHE_BUST=$(date +%s)
curl -fsSL "http://deploy.agit8or.net/api/v1/system-updates/download?v=${CACHE_BUST}" -o depl0y-latest.tar.gz

echo "📦 Extracting Depl0y..."
rm -rf /tmp/depl0y-install
mkdir -p /tmp/depl0y-install
cd /tmp/depl0y-install
tar -xzf /tmp/depl0y-latest.tar.gz

# Install backend
echo ""
echo "🔧 Installing backend..."
mkdir -p /opt/depl0y
chmod 755 /opt/depl0y  # Allow nginx to traverse
cp -r backend /opt/depl0y/
chown -R depl0y:depl0y /opt/depl0y/backend
chmod -R 755 /opt/depl0y/backend

# Create Python virtual environment
echo "🐍 Setting up Python environment..."
cd /opt/depl0y/backend
sudo -u depl0y python3 -m venv venv
sudo -u depl0y venv/bin/pip install --upgrade pip -q
sudo -u depl0y venv/bin/pip install -r requirements.txt -q

# Install additional Python packages for features
echo "   Installing additional Python packages..."
sudo -u depl0y venv/bin/pip install -q weasyprint markdown requests

echo "✓ Backend installed"

# Install scripts
echo ""
echo "📜 Installing scripts..."
if [ -d "/tmp/depl0y-install/scripts" ]; then
    mkdir -p /opt/depl0y/scripts
    cp -r /tmp/depl0y-install/scripts/* /opt/depl0y/scripts/
    chmod -R 755 /opt/depl0y/scripts
    echo "✓ Scripts installed"
else
    echo "⚠️  No scripts directory found in package"
fi

# Install frontend
echo ""
echo "🎨 Installing frontend..."

if [ "$UPGRADE_MODE" = true ]; then
    # During upgrade, use pre-built frontend from package (much faster!)
    echo "   Using pre-built frontend from package..."
    if [ -d "/tmp/depl0y-install/frontend/dist" ]; then
        mkdir -p /opt/depl0y/frontend/dist
        chmod 755 /opt/depl0y/frontend
        cp -r /tmp/depl0y-install/frontend/dist/* /opt/depl0y/frontend/dist/
        chown -R nginx:nginx /opt/depl0y/frontend/dist
        chmod -R 755 /opt/depl0y/frontend/dist
        echo "✓ Frontend installed (pre-built)"
    else
        echo "⚠️  Pre-built frontend not found, building from source..."
        cd /tmp/depl0y-install/frontend
        npm install --silent
        npm run build
        mkdir -p /opt/depl0y/frontend/dist
        chmod 755 /opt/depl0y/frontend
        cp -r dist/* /opt/depl0y/frontend/dist/
        chown -R nginx:nginx /opt/depl0y/frontend/dist
        chmod -R 755 /opt/depl0y/frontend/dist
        echo "✓ Frontend installed (built from source)"
    fi
else
    # Fresh install - try to use pre-built frontend first
    if [ -d "/tmp/depl0y-install/frontend/dist" ]; then
        echo "   Using pre-built frontend from package..."
        mkdir -p /opt/depl0y/frontend/dist
        chmod 755 /opt/depl0y/frontend
        cp -r /tmp/depl0y-install/frontend/dist/* /opt/depl0y/frontend/dist/
        chown -R nginx:nginx /opt/depl0y/frontend/dist
        chmod -R 755 /opt/depl0y/frontend/dist
        echo "✓ Frontend installed (pre-built)"
    else
        echo "   Building frontend from source (this may take 3-5 minutes)..."
        cd /tmp/depl0y-install/frontend
        npm install
        npm run build
        mkdir -p /opt/depl0y/frontend/dist
        chmod 755 /opt/depl0y/frontend
        cp -r dist/* /opt/depl0y/frontend/dist/
        chown -R nginx:nginx /opt/depl0y/frontend/dist
        chmod -R 755 /opt/depl0y/frontend/dist
        echo "✓ Frontend installed (built from source)"
    fi
fi

# Create database directory
echo ""
echo "💾 Setting up database..."
mkdir -p /var/lib/depl0y/db
mkdir -p /var/lib/depl0y/cloud-images
mkdir -p /var/lib/depl0y/isos
mkdir -p /var/lib/depl0y/ssh_keys
mkdir -p /var/log/depl0y
chown -R depl0y:depl0y /var/lib/depl0y
chown -R depl0y:depl0y /var/log/depl0y
chmod -R 755 /var/lib/depl0y

echo "✓ Database directories created"

# Copy documentation
echo ""
echo "📚 Installing documentation..."
if [ -d "/tmp/depl0y-install/docs" ]; then
    mkdir -p /opt/depl0y/docs
    cp -r /tmp/depl0y-install/docs/* /opt/depl0y/docs/
    chown -R depl0y:depl0y /opt/depl0y/docs
    echo "✓ Documentation installed"
fi

# Generate or reuse encryption keys
echo ""
if [ "$UPGRADE_MODE" = true ] && [ "$KEYS_VALID" = true ]; then
    echo "🔐 Reusing existing encryption keys..."
    SECRET_KEY="$EXISTING_SECRET"
    ENCRYPTION_KEY="$EXISTING_ENCRYPTION"
    echo "✓ Existing encryption keys preserved"
else
    echo "🔐 Generating new encryption keys..."
    SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
    # Use the venv Python which has cryptography installed
    ENCRYPTION_KEY=$(/opt/depl0y/backend/venv/bin/python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
    echo "✓ New encryption keys generated"

    if [ "$UPGRADE_MODE" = true ]; then
        echo ""
        echo "⚠️  IMPORTANT: New encryption keys have been generated"
        echo "   This means you will need to:"
        echo "   • Log in again (previous sessions are now invalid)"
        echo "   • Re-enter all Proxmox host credentials"
        echo "   • Your database and settings are preserved"
    fi
fi

# Create systemd service
echo ""
echo "⚙️  Creating systemd service..."
cat > /etc/systemd/system/depl0y-backend.service << SVCEOF
[Unit]
Description=Depl0y Backend API
After=network.target

[Service]
Type=simple
User=depl0y
Group=depl0y
WorkingDirectory=/opt/depl0y/backend
Environment="PATH=/opt/depl0y/backend/venv/bin"
Environment="SECRET_KEY=${SECRET_KEY}"
Environment="ENCRYPTION_KEY=${ENCRYPTION_KEY}"
ExecStart=/opt/depl0y/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SVCEOF

# Clear Python cache to ensure new code is loaded
if [ "$UPGRADE_MODE" = true ]; then
    echo "🗑️  Clearing Python cache again (ensuring fresh code)..."
else
    echo "🗑️  Clearing Python cache..."
fi
find /opt/depl0y/backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find /opt/depl0y/backend -type f -name "*.pyc" -delete 2>/dev/null || true

systemctl daemon-reload
systemctl enable depl0y-backend

# Use restart to ensure service loads new code (important for upgrades)
if [ "$UPGRADE_MODE" = true ]; then
    echo "🔄 Restarting backend service with new code..."
    systemctl restart depl0y-backend
else
    echo "🚀 Starting backend service..."
    systemctl start depl0y-backend
fi

echo "✓ Backend service started"

# Configure nginx
echo ""
echo "🌐 Configuring nginx..."

# RHEL/CentOS uses /etc/nginx/conf.d/ instead of sites-available
cat > /etc/nginx/conf.d/depl0y.conf << 'NGEOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 10G;

    # Frontend
    location / {
        root /opt/depl0y/frontend/dist;
        try_files $uri $uri/ /index.html;

        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Backend API
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    access_log /var/log/nginx/depl0y_access.log;
    error_log /var/log/nginx/depl0y_error.log;
}
NGEOF

# Remove default nginx config if it exists
rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true

# Comment out default server block in nginx.conf (RHEL/CentOS specific)
# The default nginx.conf has a server block that conflicts with our config
if grep -q "^    server {" /etc/nginx/nginx.conf 2>/dev/null; then
    echo "   Disabling default server block in nginx.conf..."
    sed -i '/^    server {/,/^    }/s/^/#/' /etc/nginx/nginx.conf
fi

# Configure SELinux if enabled
if command -v getenforce &> /dev/null && [ "$(getenforce)" != "Disabled" ]; then
    echo "🔐 Configuring SELinux..."
    setsebool -P httpd_can_network_connect 1 2>/dev/null || true
    setsebool -P httpd_read_user_content 1 2>/dev/null || true
    # Allow nginx to serve content from /opt/depl0y
    chcon -R -t httpd_sys_content_t /opt/depl0y/frontend/dist 2>/dev/null || true
    echo "✓ SELinux configured"
fi

# Open firewall ports if firewalld is active
if systemctl is-active --quiet firewalld; then
    echo "🔥 Configuring firewall..."
    firewall-cmd --permanent --add-service=http 2>/dev/null || true
    firewall-cmd --permanent --add-service=https 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    echo "✓ Firewall configured"
fi

nginx -t
systemctl enable nginx
systemctl restart nginx

echo "✓ Nginx configured"

# Setup sudoers for depl0y user
echo ""
echo "🔐 Configuring permissions..."
cat > /etc/sudoers.d/depl0y << 'SUDOEOF'
# Depl0y user sudo permissions (RHEL/CentOS version)
depl0y ALL=(ALL) NOPASSWD: /usr/bin/dnf install -y sshpass
depl0y ALL=(ALL) NOPASSWD: /usr/bin/which sshpass
depl0y ALL=(depl0y) NOPASSWD: /usr/bin/mkdir -p /opt/depl0y/.ssh
depl0y ALL=(depl0y) NOPASSWD: /usr/bin/ssh-keygen *
depl0y ALL=(depl0y) NOPASSWD: /usr/bin/sshpass *
depl0y ALL=(depl0y) NOPASSWD: /usr/bin/ssh *
depl0y ALL=(depl0y) NOPASSWD: /usr/bin/ssh-copy-id *
depl0y ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart depl0y-backend
depl0y ALL=(ALL) NOPASSWD: /bin/systemctl restart depl0y-backend
depl0y ALL=(ALL) NOPASSWD: /usr/bin/systemctl status depl0y-backend
depl0y ALL=(ALL) NOPASSWD: /bin/bash /tmp/depl0y-update-install.sh
depl0y ALL=(ALL) NOPASSWD: /opt/depl0y/scripts/update-wrapper.sh *
depl0y ALL=(ALL) NOPASSWD: /usr/bin/journalctl -u depl0y-backend *
SUDOEOF

chmod 440 /etc/sudoers.d/depl0y
visudo -c

echo "✓ Permissions configured"

# Wait for backend to start
echo ""
echo "⏳ Waiting for backend to start..."
sleep 5

# Check if backend is running
if systemctl is-active --quiet depl0y-backend; then
    echo "✓ Backend is running"
else
    echo ""
    echo "❌ ERROR: Backend failed to start!"
    echo ""
    echo "Last 30 lines of backend logs:"
    journalctl -u depl0y-backend -n 30 --no-pager
    echo ""
    echo "Installation failed. Please check the logs above for errors."
    exit 1
fi

# Create default admin user
echo ""
echo "👤 Creating default admin user..."
cd /opt/depl0y/backend
if sudo -u depl0y /opt/depl0y/backend/venv/bin/python3 create_admin.py; then
    echo "✓ Default credentials: admin / admin"
else
    echo "❌ ERROR: Failed to create admin user!"
    echo "Check permissions and database connection."
    exit 1
fi

# Initialize system settings in database
echo ""
echo "⚙️  Initializing system settings..."
sudo -u depl0y sqlite3 /var/lib/depl0y/db/depl0y.db "CREATE TABLE IF NOT EXISTS system_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);" 2>/dev/null || true

sudo -u depl0y sqlite3 /var/lib/depl0y/db/depl0y.db "INSERT OR REPLACE INTO system_settings (key, value, description) VALUES
    ('app_version', '1.2.0', 'Current application version'),
    ('app_name', 'Depl0y', 'Application name');" 2>/dev/null || true

echo "✓ System settings initialized"

# Optional Proxmox setup
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Optional: Proxmox Integration Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Would you like to configure Proxmox integration now?"
echo "This will:"
echo "  • Set up cloud images for fast VM deployment"
echo "  • Configure inter-node SSH for multi-node clusters"
echo ""
read -p "Configure Proxmox now? (y/N): " -n 1 -r SETUP_PROXMOX < /dev/tty || SETUP_PROXMOX="N"
echo ""

if [[ $SETUP_PROXMOX =~ ^[Yy]$ ]]; then
    echo ""
    echo "📋 Proxmox Configuration"
    echo ""

    # Get Proxmox details
    read -p "Enter Proxmox hostname or IP: " PROXMOX_HOST < /dev/tty
    read -p "Enter Proxmox root username [root]: " PROXMOX_USER < /dev/tty
    PROXMOX_USER=${PROXMOX_USER:-root}

    echo ""
    echo "⚠️  Note: Password will be used to set up SSH keys only"
    read -s -p "Enter Proxmox root password: " PROXMOX_PASSWORD < /dev/tty
    echo ""
    echo ""

    # Setup SSH keys for depl0y user
    echo "🔑 Setting up SSH keys..."
    if [ ! -f "/opt/depl0y/.ssh/id_rsa" ]; then
        sudo -u depl0y mkdir -p /opt/depl0y/.ssh
        sudo -u depl0y ssh-keygen -t rsa -b 4096 -f /opt/depl0y/.ssh/id_rsa -N "" -q
        echo "✓ SSH keys generated"
    else
        echo "✓ SSH keys already exist"
    fi

    # Copy SSH key to Proxmox
    echo "📤 Copying SSH key to Proxmox..."
    sudo -u depl0y sshpass -p "$PROXMOX_PASSWORD" ssh-copy-id -o StrictHostKeyChecking=no "${PROXMOX_USER}@${PROXMOX_HOST}" 2>/dev/null || {
        echo "⚠️  Failed to copy SSH key. You may need to do this manually later."
    }

    # Test SSH connection
    if sudo -u depl0y ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no "${PROXMOX_USER}@${PROXMOX_HOST}" "echo SSH_OK" 2>/dev/null | grep -q "SSH_OK"; then
        echo "✓ SSH connection verified"

        # Setup cloud images
        echo ""
        echo "☁️  Setting up cloud images..."
        sudo -u depl0y ssh -o StrictHostKeyChecking=no "${PROXMOX_USER}@${PROXMOX_HOST}" 'bash -s' << 'CLOUDEOF'
# Check if cloud-init is available
if ! which cloud-init >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq cloud-init
fi

# Create cloud-init snippet storage if needed
mkdir -p /var/lib/vz/snippets
chmod 755 /var/lib/vz/snippets

echo "✓ Cloud images configured"
CLOUDEOF

        # Setup inter-node SSH for cluster
        echo ""
        echo "🔗 Setting up inter-node SSH for cluster..."
        sudo -u depl0y ssh -o StrictHostKeyChecking=no "${PROXMOX_USER}@${PROXMOX_HOST}" 'bash -s' << 'SSHEOF'
# Get cluster nodes
NODES=$(pvesh get /cluster/status --output-format json 2>/dev/null | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | grep -v "^$" || echo "")

if [ -n "$NODES" ]; then
    echo "   Found cluster nodes: $NODES"

    # Generate SSH key on this node if needed
    if [ ! -f ~/.ssh/id_rsa ]; then
        ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N "" -q
    fi

    # Copy key to other nodes
    for node in $NODES; do
        if [ "$node" != "$(hostname)" ]; then
            echo "   Setting up SSH to $node..."
            ssh-copy-id -o StrictHostKeyChecking=no "root@$node" 2>/dev/null || true
        fi
    done

    echo "✓ Inter-node SSH configured"
else
    echo "   Single node or cluster not configured, skipping"
fi
SSHEOF

        echo ""
        echo "✓ Proxmox integration complete!"
    else
        echo "⚠️  SSH connection failed. You can set this up later via Settings in the web interface."
    fi
else
    echo ""
    echo "⏭️  Skipping Proxmox setup. You can configure this later via:"
    echo "   Settings → Cloud Images"
    echo "   Settings → Proxmox Cluster SSH"
fi

# Cleanup
echo ""
echo "🧹 Cleaning up..."
cd /
rm -rf /tmp/depl0y-install
rm -f /tmp/depl0y-latest.tar.gz

# Final restart for upgrades to ensure new code is loaded
if [ "$UPGRADE_MODE" = true ]; then
    echo ""
    echo "🔄 Final restart to load new code..."
    find /opt/depl0y/backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find /opt/depl0y/backend -type f -name "*.pyc" -delete 2>/dev/null || true
    systemctl restart depl0y-backend
    sleep 3
    if systemctl is-active --quiet depl0y-backend; then
        echo "✓ Backend restarted successfully"
    else
        echo "⚠️  Backend restart may have issues, check logs"
    fi
fi

# Get IP address
IP=$(hostname -I | awk '{print $1}')

echo ""
if [ "$UPGRADE_MODE" = true ]; then
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║                                                          ║"
    echo "║                  ✅ UPGRADE COMPLETE                      ║"
    echo "║                                                          ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo "🎉 Depl0y v1.2.0 has been successfully upgraded!"
    echo ""
    echo "📍 Access Depl0y at:"
    echo "   http://$IP"
    echo ""
    echo "✨ What's new in v1.2.0:"
    echo "   • Fast fresh installs using pre-built frontend"
    echo "   • No more 5-minute npm builds during installation"
    echo "   • Automatic backend restart after upgrades"
    echo "   • One-click automatic updates from Settings"
    echo ""
    echo "📚 Note:"
    echo "   • Your database has been preserved"
    echo "   • Your encryption keys have been preserved"
    echo "   • All users and settings retained"
else
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║                                                          ║"
    echo "║                  ✅ INSTALLATION COMPLETE                 ║"
    echo "║                                                          ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo "🎉 Depl0y v1.2.0 has been successfully installed!"
    echo ""
    echo "📍 Access Depl0y at:"
    echo "   http://$IP"
    echo ""
    echo "👤 Default Credentials:"
    echo "   Username: admin"
    echo "   Password: admin"
    echo "   🔐 2FA: Disabled (enable in Settings after login)"
    echo "   ⚠️  CHANGE PASSWORD IMMEDIATELY AFTER FIRST LOGIN!"
    echo ""
    echo "✨ Features:"
    echo "   • High Availability wizard"
    echo "   • Cloud image management"
    echo "   • Automated VM deployment"
    echo ""
    echo "📚 Next Steps:"
    echo "   1. Access the web interface"
    echo "   2. Change the default password"
    echo "   3. Add your Proxmox host in Settings (if not done)"
    echo "   4. Try the HA Setup Wizard!"
fi
echo ""
echo "📖 Documentation: http://$IP → Documentation"
echo "🆘 Support: Check /opt/depl0y/docs/"
echo ""
echo "Thank you for using Depl0y! 🚀"
echo ""
