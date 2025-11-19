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
