#!/bin/bash

# Depl0y Quick Setup with SQLite (simplest installation)

set -e

echo "========================================="
echo "  Depl0y Quick Setup (SQLite)"
echo "========================================="
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit 1
fi

cd /home/administrator/depl0y

# Create directories
echo "Creating directories..."
mkdir -p /opt/depl0y/{backend,frontend}
mkdir -p /var/lib/depl0y/{isos,cloud-init,ssh_keys,db}
mkdir -p /var/log/depl0y
mkdir -p /etc/depl0y

# Copy files
echo "Copying files..."
cp -r backend/* /opt/depl0y/backend/
cp -r frontend/* /opt/depl0y/frontend/

# Create user
useradd -r -s /bin/bash -d /opt/depl0y -m depl0y 2>/dev/null || true

# Set permissions
chown -R depl0y:depl0y /opt/depl0y /var/lib/depl0y /var/log/depl0y

# Generate config
echo "Generating configuration..."
SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

cat > /etc/depl0y/config.env << EOF
DATABASE_URL=sqlite:////var/lib/depl0y/db/depl0y.db
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

# Install Python deps
echo "Installing Python dependencies..."
cd /opt/depl0y/backend
sudo -u depl0y python3 -m venv venv
sudo -u depl0y venv/bin/pip install --upgrade pip -q
sudo -u depl0y venv/bin/pip install -r requirements.txt -q

echo "✓ Python dependencies installed"

# Init database
echo "Initializing database..."
sudo -u depl0y bash -c "source venv/bin/activate && source /etc/depl0y/config.env && python3 -c 'from app.core.database import init_db; init_db()'"

echo "✓ Database initialized"

# Create admin
echo "Creating admin user..."
sudo -u depl0y bash -c "source venv/bin/activate && source /etc/depl0y/config.env && python3" << 'PYEOF'
from app.core.database import SessionLocal
from app.models import User, UserRole
from app.core.security import get_password_hash

db = SessionLocal()
try:
    admin = User(
        username="admin",
        email="admin@depl0y.local",
        hashed_password=get_password_hash("Admin123!"),
        role=UserRole.ADMIN,
        is_active=True
    )
    db.add(admin)
    db.commit()
    print("✓ Admin created")
except Exception as e:
    print(f"Note: {e}")
finally:
    db.close()
PYEOF

# Build frontend
echo "Building frontend..."
cd /opt/depl0y/frontend
sudo -u depl0y npm install -q
sudo -u depl0y npm run build

echo "✓ Frontend built"

# Create service
cat > /etc/systemd/system/depl0y-backend.service << 'EOF'
[Unit]
Description=Depl0y Backend
After=network.target

[Service]
Type=simple
User=depl0y
Group=depl0y
WorkingDirectory=/opt/depl0y/backend
EnvironmentFile=/etc/depl0y/config.env
ExecStart=/opt/depl0y/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Configure nginx
cat > /etc/nginx/sites-available/depl0y << 'EOF'
server {
    listen 80 default_server;
    server_name _;

    client_max_body_size 10G;

    location / {
        root /opt/depl0y/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
}
EOF

ln -sf /etc/nginx/sites-available/depl0y /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t

# Start everything
echo "Starting services..."
systemctl daemon-reload
systemctl enable depl0y-backend
systemctl restart depl0y-backend
systemctl reload nginx

sleep 3

SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "========================================="
echo "  ✓ Depl0y is Running!"
echo "========================================="
echo ""
echo "URL: http://${SERVER_IP}"
echo ""
echo "Login:"
echo "  Username: admin"
echo "  Password: Admin123!"
echo ""
echo "Commands:"
echo "  sudo systemctl status depl0y-backend"
echo "  sudo systemctl restart depl0y-backend"
echo "  sudo journalctl -u depl0y-backend -f"
echo ""
echo "========================================="
