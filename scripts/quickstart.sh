#!/bin/bash

# Depl0y Quick Start (assumes MariaDB already installed)

set -e

echo "========================================="
echo "  Depl0y Quick Start"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

PROJECT_DIR="/home/administrator/depl0y"
cd "$PROJECT_DIR"

# Setup MariaDB database
echo "Setting up database..."
mysql -u root << 'EOF'
CREATE DATABASE IF NOT EXISTS depl0y;
CREATE USER IF NOT EXISTS 'depl0y'@'localhost' IDENTIFIED BY 'depl0y_password_123';
GRANT ALL PRIVILEGES ON depl0y.* TO 'depl0y'@'localhost';
FLUSH PRIVILEGES;
EOF

echo "Database created"

# Create application user and directories
echo "Creating directories..."
useradd -r -s /bin/bash -d /opt/depl0y -m depl0y 2>/dev/null || true
mkdir -p /opt/depl0y/{backend,frontend}
mkdir -p /var/lib/depl0y/{isos,cloud-init,ssh_keys}
mkdir -p /var/log/depl0y
mkdir -p /etc/depl0y

# Copy files
echo "Copying application files..."
cp -r "$PROJECT_DIR/backend"/* /opt/depl0y/backend/
cp -r "$PROJECT_DIR/frontend"/* /opt/depl0y/frontend/

# Set permissions
chown -R depl0y:depl0y /opt/depl0y
chown -R depl0y:depl0y /var/lib/depl0y
chown -R depl0y:depl0y /var/log/depl0y

# Generate secrets
echo "Generating configuration..."
SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Create config file
cat > /etc/depl0y/config.env << EOF
DATABASE_URL=mysql+pymysql://depl0y:depl0y_password_123@localhost:3306/depl0y
SECRET_KEY=${SECRET_KEY}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
DEBUG=false
LOG_LEVEL=INFO
LOG_FILE=/var/log/depl0y/app.log
ISO_STORAGE_PATH=/var/lib/depl0y/isos
CLOUDINIT_TEMPLATE_PATH=/var/lib/depl0y/cloud-init
SSH_KEY_PATH=/var/lib/depl0y/ssh_keys
API_V1_PREFIX=/api/v1
EOF

chmod 600 /etc/depl0y/config.env
chown depl0y:depl0y /etc/depl0y/config.env

# Install Python dependencies
echo "Installing Python dependencies (this may take a few minutes)..."
cd /opt/depl0y/backend
sudo -u depl0y python3 -m venv venv
sudo -u depl0y /opt/depl0y/backend/venv/bin/pip install --upgrade pip --quiet
sudo -u depl0y /opt/depl0y/backend/venv/bin/pip install -r requirements.txt --quiet

echo "Python dependencies installed"

# Initialize database
echo "Initializing database..."
cd /opt/depl0y/backend
sudo -u depl0y bash -c "source venv/bin/activate && source /etc/depl0y/config.env && python3 -c 'from app.core.database import init_db; init_db()'"

echo "Database initialized"

# Build frontend
echo "Building frontend (this may take a few minutes)..."
cd /opt/depl0y/frontend
sudo -u depl0y npm install --quiet
sudo -u depl0y npm run build

echo "Frontend built"

# Create systemd service
echo "Creating systemd service..."
cat > /etc/systemd/system/depl0y-backend.service << 'SVCEOF'
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
SVCEOF

# Configure Nginx
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/depl0y << 'NGEOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 10G;

    location / {
        root /opt/depl0y/frontend/dist;
        try_files $uri $uri/ /index.html;

        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

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

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }

    access_log /var/log/nginx/depl0y_access.log;
    error_log /var/log/nginx/depl0y_error.log;
}
NGEOF

ln -sf /etc/nginx/sites-available/depl0y /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test nginx
nginx -t

# Create admin user
echo ""
echo "Creating admin user..."
cd /opt/depl0y/backend
sudo -u depl0y bash -c "source venv/bin/activate && source /etc/depl0y/config.env && python3" << 'PYEOF'
from app.core.database import SessionLocal
from app.models import User, UserRole
from app.core.security import get_password_hash

db = SessionLocal()
try:
    # Delete existing admin if exists
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        db.delete(existing)
        db.commit()

    # Create new admin
    admin = User(
        username="admin",
        email="admin@depl0y.local",
        hashed_password=get_password_hash("Admin123!"),
        role=UserRole.ADMIN,
        is_active=True
    )
    db.add(admin)
    db.commit()
    print("✓ Admin user created")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
PYEOF

# Start services
echo ""
echo "Starting services..."
systemctl daemon-reload
systemctl enable depl0y-backend
systemctl restart depl0y-backend
systemctl reload nginx

# Wait for startup
echo "Waiting for services to start..."
sleep 5

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "========================================="
echo "  Installation Complete!"
echo "========================================="
echo ""
echo "✓ Depl0y is now running!"
echo ""
echo "Access: http://${SERVER_IP}"
echo ""
echo "Login:"
echo "  Username: admin"
echo "  Password: Admin123!"
echo ""
echo "Commands:"
echo "  Status:  sudo systemctl status depl0y-backend"
echo "  Restart: sudo systemctl restart depl0y-backend"
echo "  Logs:    sudo journalctl -u depl0y-backend -f"
echo ""
echo "========================================="
