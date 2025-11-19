#!/bin/bash

# Depl0y Setup Script
# This script sets up Depl0y on a fresh server

set -e

echo "========================================="
echo "  Depl0y Installation Script"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VERSION=$VERSION_ID
else
    echo "Cannot detect OS. Exiting."
    exit 1
fi

echo "Detected OS: $OS $VERSION"
echo ""

# Install Docker and Docker Compose
echo "Installing Docker and Docker Compose..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "Docker installed successfully"
else
    echo "Docker is already installed"
fi

if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "Docker Compose installed successfully"
else
    echo "Docker Compose is already installed"
fi

echo ""

# Generate secrets
echo "Generating secure secrets..."

if [ ! -f .env ]; then
    cp .env.example .env

    # Generate SECRET_KEY (64 character random string)
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env

    # Generate ENCRYPTION_KEY (Fernet key)
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || openssl rand -base64 32)
    sed -i "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|" .env

    # Generate database passwords
    MYSQL_ROOT_PASSWORD=$(openssl rand -hex 16)
    MYSQL_PASSWORD=$(openssl rand -hex 16)
    sed -i "s|MYSQL_ROOT_PASSWORD=.*|MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD|" .env
    sed -i "s|MYSQL_PASSWORD=.*|MYSQL_PASSWORD=$MYSQL_PASSWORD|" .env

    echo ".env file created with secure random secrets"
else
    echo ".env file already exists, skipping secret generation"
fi

echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p /var/lib/depl0y/{isos,cloud-init,ssh_keys}
mkdir -p /var/log/depl0y
chmod 755 /var/lib/depl0y
chmod 755 /var/log/depl0y

echo ""

# Build and start containers
echo "Building and starting Docker containers..."
docker-compose up -d --build

echo ""
echo "Waiting for services to start..."
sleep 10

# Run database migrations
echo "Running database migrations..."
docker-compose exec -T backend alembic upgrade head || echo "Note: Alembic migrations may need to be configured"

# Create default admin user
echo ""
echo "Creating default admin user..."
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

# Create admin user via Python script
docker-compose exec -T backend python3 << EOF
from app.core.database import SessionLocal
from app.models import User, UserRole
from app.core.security import get_password_hash

db = SessionLocal()
try:
    # Check if user exists
    existing_user = db.query(User).filter(User.username == "$ADMIN_USER").first()
    if existing_user:
        print("User '$ADMIN_USER' already exists")
    else:
        # Create admin user
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
finally:
    db.close()
EOF

echo ""
echo "========================================="
echo "  Installation Complete!"
echo "========================================="
echo ""
echo "Depl0y is now running!"
echo ""
echo "Access the web interface at: http://$(hostname -I | awk '{print $1}')"
echo ""
echo "Default credentials:"
echo "  Username: $ADMIN_USER"
echo "  Password: (the one you just entered)"
echo ""
echo "Important: Change the default admin password after first login!"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop Depl0y:"
echo "  docker-compose down"
echo ""
echo "To start Depl0y:"
echo "  docker-compose up -d"
echo ""
echo "========================================="
