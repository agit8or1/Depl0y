#!/bin/bash

# Depl0y Native Installation Script (No Docker)
# This script sets up Depl0y directly on the host system

set -e

echo "========================================="
echo "  Depl0y Native Installation"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Installing to: $PROJECT_DIR"
echo ""

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS. Exiting."
    exit 1
fi

echo "Detected OS: $OS"
echo ""

# Install system dependencies
echo "Installing system dependencies..."
if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    apt-get update
    apt-get install -y \
        python3 \
        python3-venv \
        python3-pip \
        mariadb-server \
        nginx \
        nodejs \
        npm \
        gcc \
        g++ \
        libmariadb-dev \
        pkg-config \
        git
elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ] || [ "$OS" = "rocky" ] || [ "$OS" = "almalinux" ]; then
    yum install -y epel-release
    yum install -y \
        python311 \
        python3-pip \
        mariadb-server \
        nginx \
        nodejs \
        npm \
        gcc \
        gcc-c++ \
        mariadb-devel \
        git
else
    echo "Unsupported OS: $OS"
    exit 1
fi

echo "System dependencies installed"
echo ""

# Start and enable MariaDB
echo "Configuring MariaDB..."
systemctl enable mariadb
systemctl start mariadb

# Secure MariaDB installation
DB_ROOT_PASSWORD=$(openssl rand -hex 16)
mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '${DB_ROOT_PASSWORD}';" || true
mysql -u root -p"${DB_ROOT_PASSWORD}" -e "DELETE FROM mysql.user WHERE User='';" || true
mysql -u root -p"${DB_ROOT_PASSWORD}" -e "DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');" || true
mysql -u root -p"${DB_ROOT_PASSWORD}" -e "DROP DATABASE IF EXISTS test;" || true
mysql -u root -p"${DB_ROOT_PASSWORD}" -e "DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';" || true
mysql -u root -p"${DB_ROOT_PASSWORD}" -e "FLUSH PRIVILEGES;" || true

# Create database and user
DB_PASSWORD=$(openssl rand -hex 16)
mysql -u root -p"${DB_ROOT_PASSWORD}" << EOF
CREATE DATABASE IF NOT EXISTS depl0y;
CREATE USER IF NOT EXISTS 'depl0y'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON depl0y.* TO 'depl0y'@'localhost';
FLUSH PRIVILEGES;
EOF

echo "MariaDB configured"
echo ""

# Create application user
echo "Creating depl0y user..."
useradd -r -s /bin/bash -d /opt/depl0y -m depl0y || true

# Create directories
echo "Creating directories..."
mkdir -p /opt/depl0y/{backend,frontend}
mkdir -p /var/lib/depl0y/{isos,cloud-init,ssh_keys}
mkdir -p /var/log/depl0y
mkdir -p /etc/depl0y

# Copy application files
echo "Copying application files..."
cp -r "$PROJECT_DIR/backend"/* /opt/depl0y/backend/
cp -r "$PROJECT_DIR/frontend"/* /opt/depl0y/frontend/

# Set permissions
chown -R depl0y:depl0y /opt/depl0y
chown -R depl0y:depl0y /var/lib/depl0y
chown -R depl0y:depl0y /var/log/depl0y

# Generate secrets
echo "Generating secrets..."
SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Create environment file
cat > /etc/depl0y/config.env << EOF
# Database Configuration
DATABASE_URL=mysql+pymysql://depl0y:${DB_PASSWORD}@localhost:3306/depl0y

# Security
SECRET_KEY=${SECRET_KEY}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
DEBUG=false

# Application Settings
LOG_LEVEL=INFO
LOG_FILE=/var/log/depl0y/app.log

# Storage Paths
ISO_STORAGE_PATH=/var/lib/depl0y/isos
CLOUDINIT_TEMPLATE_PATH=/var/lib/depl0y/cloud-init
SSH_KEY_PATH=/var/lib/depl0y/ssh_keys

# API
API_V1_PREFIX=/api/v1
EOF

chmod 600 /etc/depl0y/config.env
chown depl0y:depl0y /etc/depl0y/config.env

# Install Python dependencies
echo "Installing Python dependencies..."
cd /opt/depl0y/backend
sudo -u depl0y python3 -m venv venv
sudo -u depl0y /opt/depl0y/backend/venv/bin/pip install --upgrade pip
sudo -u depl0y /opt/depl0y/backend/venv/bin/pip install -r requirements.txt

# Initialize database
echo "Initializing database..."
cd /opt/depl0y/backend
sudo -u depl0y bash -c "source venv/bin/activate && source /etc/depl0y/config.env && python3 -c 'from app.core.database import init_db; init_db()'"

# Build frontend
echo "Building frontend..."
cd /opt/depl0y/frontend
sudo -u depl0y npm install
sudo -u depl0y npm run build

# Create systemd service for backend
echo "Creating systemd service..."
cat > /etc/systemd/system/depl0y-backend.service << 'EOF'
[Unit]
Description=Depl0y Backend API
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=simple
User=depl0y
Group=depl0y
WorkingDirectory=/opt/depl0y/backend
EnvironmentFile=/etc/depl0y/config.env
ExecStart=/opt/depl0y/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/depl0y << 'EOF'
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
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }

    access_log /var/log/nginx/depl0y_access.log;
    error_log /var/log/nginx/depl0y_error.log;
}
EOF

# Enable nginx site
if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    ln -sf /etc/nginx/sites-available/depl0y /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
else
    cp /etc/nginx/sites-available/depl0y /etc/nginx/conf.d/depl0y.conf
fi

# Test nginx configuration
nginx -t

# Create admin user
echo ""
echo "========================================="
echo "Creating admin user..."
echo "========================================="
read -p "Enter admin username (default: admin): " ADMIN_USER
ADMIN_USER=${ADMIN_USER:-admin}

read -p "Enter admin email: " ADMIN_EMAIL
while [ -z "$ADMIN_EMAIL" ]; do
    echo "Email cannot be empty"
    read -p "Enter admin email: " ADMIN_EMAIL
done

read -sp "Enter admin password: " ADMIN_PASSWORD
echo ""
while [ ${#ADMIN_PASSWORD} -lt 8 ]; do
    echo "Password must be at least 8 characters"
    read -sp "Enter admin password: " ADMIN_PASSWORD
    echo ""
done

cd /opt/depl0y/backend
sudo -u depl0y bash -c "source venv/bin/activate && source /etc/depl0y/config.env && python3" << PYEOF
from app.core.database import SessionLocal
from app.models import User, UserRole
from app.core.security import get_password_hash

db = SessionLocal()
try:
    existing_user = db.query(User).filter(User.username == "$ADMIN_USER").first()
    if existing_user:
        print("User '$ADMIN_USER' already exists")
    else:
        admin = User(
            username="$ADMIN_USER",
            email="$ADMIN_EMAIL",
            hashed_password=get_password_hash("$ADMIN_PASSWORD"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        db.commit()
        print("Admin user created successfully")
except Exception as e:
    print(f"Error creating admin user: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
PYEOF

# Enable and start services
echo ""
echo "Starting services..."
systemctl daemon-reload
systemctl enable depl0y-backend
systemctl start depl0y-backend
systemctl restart nginx

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 5

# Check service status
echo ""
echo "Checking service status..."
systemctl status depl0y-backend --no-pager || true

echo ""
echo "========================================="
echo "  Installation Complete!"
echo "========================================="
echo ""
echo "Depl0y is now running!"
echo ""
SERVER_IP=$(hostname -I | awk '{print $1}')
echo "Access the web interface at: http://${SERVER_IP}"
echo ""
echo "Login credentials:"
echo "  Username: $ADMIN_USER"
echo "  Password: (the one you just entered)"
echo ""
echo "Service management:"
echo "  Status:  sudo systemctl status depl0y-backend"
echo "  Stop:    sudo systemctl stop depl0y-backend"
echo "  Start:   sudo systemctl start depl0y-backend"
echo "  Restart: sudo systemctl restart depl0y-backend"
echo "  Logs:    sudo journalctl -u depl0y-backend -f"
echo ""
echo "Database credentials saved to: /etc/depl0y/config.env"
echo "MariaDB root password: ${DB_ROOT_PASSWORD}"
echo ""
echo "========================================="
