#!/bin/bash
set -e

echo "🚀 Deploying Depl0y..."

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "📦 Building frontend..."
cd /home/administrator/depl0y/frontend

# Build into local dist/ (vite config outDir: 'dist')
npm run build

# Stamp the service worker with a build timestamp so browsers pick up the new
# SW immediately and clear their old caches.
BUILD_TS=$(date +%Y%m%d%H%M%S)
sed -i "s/const CACHE_VERSION = '[^']*'/const CACHE_VERSION = 'v${BUILD_TS}'/" dist/sw.js
echo "Service worker cache version set to v${BUILD_TS}"

# Atomic swap: rename old dist aside, move new dist into place, remove old.
# This keeps nginx always serving a COMPLETE directory — never a partial build.
PROD_DIST=/opt/depl0y/frontend/dist
OLD_DIST=/opt/depl0y/frontend/dist.old

sudo rm -rf "$OLD_DIST"
if [ -d "$PROD_DIST" ]; then
    sudo mv "$PROD_DIST" "$OLD_DIST"
fi
sudo mv dist "$PROD_DIST"
sudo chown -R www-data:www-data "$PROD_DIST"
sudo chmod -R 755 "$PROD_DIST"
sudo rm -rf "$OLD_DIST"

echo "✅ Frontend deployed."

# ── Backend ───────────────────────────────────────────────────────────────────
echo "📤 Deploying backend..."
sudo cp -r /home/administrator/depl0y/backend/* /opt/depl0y/backend/
sudo chown -R depl0y:depl0y /opt/depl0y/backend
sudo chmod -R 755 /opt/depl0y/backend

# ── Services ──────────────────────────────────────────────────────────────────
echo "🔄 Restarting services..."
sudo systemctl restart depl0y-backend
sudo systemctl reload nginx

echo "✅ Checking status..."
sleep 2
sudo systemctl status depl0y-backend --no-pager | head -15

echo ""
echo "✅ Deployment complete!"
echo "Check logs: sudo journalctl -u depl0y-backend -f"
