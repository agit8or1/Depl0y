# Installation Guide

This guide provides detailed instructions for installing Depl0y.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Automated Installation](#automated-installation)
- [Manual Installation](#manual-installation)
- [Post-Installation](#post-installation)
- [Upgrading](#upgrading)

## Prerequisites

### System Requirements

**Minimum:**
- 2 CPU cores
- 2GB RAM
- 20GB disk space
- Ubuntu 22.04, Debian 11, or similar Linux distribution

**Recommended:**
- 4 CPU cores
- 4GB RAM
- 50GB disk space
- Ubuntu 22.04 LTS

### Software Requirements

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ (for manual installation)
- Node.js 18+ (for frontend development)

### Proxmox VE Requirements

- Proxmox VE 7.0 or later
- API access enabled
- User with sufficient permissions (or root@pam)

## Automated Installation

The easiest way to install Depl0y is using the provided setup script.

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/depl0y.git
cd depl0y
```

### Step 2: Run Setup Script

```bash
sudo ./scripts/setup.sh
```

The script will:
1. Install Docker and Docker Compose (if not present)
2. Generate secure secrets
3. Create necessary directories
4. Build and start containers
5. Create the default admin user

### Step 3: Access the Interface

Open your browser and navigate to:
```
http://your-server-ip
```

## Manual Installation

### Step 1: Install Dependencies

**Ubuntu/Debian:**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker
sudo systemctl start docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Python and Node.js (for development)
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm
```

### Step 2: Clone and Configure

```bash
# Clone repository
git clone https://github.com/yourusername/depl0y.git
cd depl0y

# Create environment file
cp .env.example .env
```

### Step 3: Generate Secrets

```bash
# Generate SECRET_KEY
SECRET_KEY=$(openssl rand -hex 32)
echo "SECRET_KEY=$SECRET_KEY" >> .env

# Generate ENCRYPTION_KEY
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env

# Generate database passwords
MYSQL_ROOT_PASSWORD=$(openssl rand -hex 16)
MYSQL_PASSWORD=$(openssl rand -hex 16)
echo "MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD" >> .env
echo "MYSQL_PASSWORD=$MYSQL_PASSWORD" >> .env
```

### Step 4: Create Directories

```bash
sudo mkdir -p /var/lib/depl0y/{isos,cloud-init,ssh_keys}
sudo mkdir -p /var/log/depl0y
sudo chown -R $USER:$USER /var/lib/depl0y /var/log/depl0y
```

### Step 5: Build and Start

```bash
docker-compose up -d --build
```

### Step 6: Create Admin User

```bash
docker-compose exec backend python3 << 'EOF'
from app.core.database import SessionLocal
from app.models import User, UserRole
from app.core.security import get_password_hash

db = SessionLocal()
try:
    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("changeme123"),
        role=UserRole.ADMIN,
        is_active=True
    )
    db.add(admin)
    db.commit()
    print("Admin user created")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
EOF
```

## Post-Installation

### 1. Change Default Password

Log in to Depl0y and immediately change the default admin password:
1. Click on your username in the top-right
2. Go to Settings
3. Change Password

### 2. Enable 2FA

For enhanced security, enable two-factor authentication:
1. Go to Settings
2. Enable 2FA
3. Scan the QR code with your authenticator app
4. Enter the verification code

### 3. Configure SSL/HTTPS

For production use, configure SSL:

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Update nginx configuration
sudo nano /etc/nginx/sites-available/depl0y
```

Uncomment the SSL section in `nginx/depl0y.conf` and update with your domain.

### 4. Add Proxmox Hosts

1. Navigate to "Proxmox Hosts"
2. Click "Add Host"
3. Enter details:
   - Name: Friendly name for the host
   - Hostname: IP or FQDN of Proxmox server
   - Port: 8006 (default)
   - Username: root@pam or API user
   - Password: Proxmox password or token
   - Verify SSL: Disable for self-signed certificates

### 5. Upload ISOs

1. Navigate to "ISO Images"
2. Click "Upload ISO"
3. Select OS type and upload your ISO file
4. Wait for upload and checksum verification

## Upgrading

### From Git

```bash
cd depl0y
git pull origin main
docker-compose down
docker-compose up -d --build
```

### Database Migrations

If database schema changes:

```bash
docker-compose exec backend alembic upgrade head
```

### Backing Up

Before upgrading, always backup:

```bash
# Backup database
docker-compose exec db mysqldump -u root -p depl0y > backup.sql

# Backup configuration
cp .env .env.backup

# Backup volumes
sudo tar -czf depl0y-volumes-$(date +%Y%m%d).tar.gz /var/lib/docker/volumes/depl0y_*
```

## Troubleshooting Installation

### Docker Daemon Not Running

```bash
sudo systemctl start docker
sudo systemctl enable docker
```

### Permission Denied

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Port Already in Use

Check what's using port 80:
```bash
sudo lsof -i :80
```

Kill the process or change Depl0y's port in `docker-compose.yml`.

### Database Connection Failed

Check database logs:
```bash
docker-compose logs db
```

Verify credentials in `.env` match `docker-compose.yml`.

### Container Won't Start

View container logs:
```bash
docker-compose logs backend
docker-compose logs frontend
```

## Uninstallation

To completely remove Depl0y:

```bash
# Stop and remove containers
docker-compose down -v

# Remove directories
sudo rm -rf /var/lib/depl0y
sudo rm -rf /var/log/depl0y

# Remove repository
cd ..
rm -rf depl0y
```

## Next Steps

- [User Guide](USER_GUIDE.md)
- [API Documentation](API.md)
- [Troubleshooting](TROUBLESHOOTING.md)
