#!/bin/bash
# Runs INSIDE an unprivileged user+mount+network namespace.
# The namespace has only a loopback device, so nothing started here can reach
# any real host — the synthetic fixtures are physically unable to touch
# production infrastructure.
set -euo pipefail

DEMO="$(cd "$(dirname "$0")" && pwd)"
STATE="${DEMO_STATE:-/tmp/depl0y-demo-state}"
REPO="${DEMO_REPO:-$(cd "$DEMO/../../.." && pwd)}"
# Defaults to the installed backend's virtualenv. Override with DEMO_VENV to run
# the rig against a candidate dependency set without touching the live install.
VENV="${DEMO_VENV:-/opt/depl0y/backend/venv}/bin"

mkdir -p "$STATE"/{db,isos,cloud-images,logs,run}

# ---------------------------------------------------------------- networking
ip link set lo up
for a in 203.0.113.11 203.0.113.12 203.0.113.13 \
         203.0.113.21 203.0.113.22 203.0.113.23 \
         198.51.100.11 198.51.100.12 198.51.100.21 198.51.100.22 \
         192.0.2.11 192.0.2.21; do
  ip addr add "$a/32" dev lo
done

cat > "$STATE/hosts" <<'EOF'
127.0.0.1       localhost
203.0.113.11    pve-east.example.net
203.0.113.12    pve-west.example.net
203.0.113.13    pve-lab.example.net
EOF
mount --bind "$STATE/hosts" /etc/hosts

echo "== namespace routes =="; ip -4 -br addr show

# ---------------------------------------------------------------------- TLS
if [ ! -f "$STATE/demo.crt" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
    -keyout "$STATE/demo.key" -out "$STATE/demo.crt" \
    -subj "/CN=depl0y-demo-fixture" >/dev/null 2>&1
fi

# ------------------------------------------------------------- mock services
cd "$DEMO"
"$VENV/uvicorn" mock_pve:app --host 0.0.0.0 --port 8006 \
  --ssl-keyfile "$STATE/demo.key" --ssl-certfile "$STATE/demo.crt" \
  --log-level warning > "$STATE/logs/mock_pve.log" 2>&1 &
"$VENV/uvicorn" mock_redfish:app --host 0.0.0.0 --port 443 \
  --ssl-keyfile "$STATE/demo.key" --ssl-certfile "$STATE/demo.crt" \
  --log-level warning > "$STATE/logs/mock_redfish.log" 2>&1 &

sleep 4
echo "== mock PVE check =="
curl -sk https://pve-east.example.net:8006/api2/json/version | head -c 200; echo
echo "== mock Redfish check =="
curl -sk https://203.0.113.21/redfish/v1 | head -c 160; echo

# ------------------------------------------------------------- demo backend
export DATABASE_URL="sqlite:///$STATE/db/depl0y.db"
export SECRET_KEY="demo-only-secret-key-not-used-anywhere-else-0123456789"
export ENCRYPTION_KEY="${DEMO_ENCRYPTION_KEY}"
export UPLOAD_DIR="$STATE"
export ISO_STORAGE_PATH="$STATE/isos"
export DEBUG=false
export LOG_LEVEL=WARNING
export PYTHONPATH="$REPO/backend"

"$VENV/python" "$DEMO/seed_db.py"

cd "$REPO/backend"
"$VENV/uvicorn" app.main:app --host 127.0.0.1 --port 8010 --log-level warning \
  > "$STATE/logs/backend.log" 2>&1 &

# ----------------------------------------------------------------- frontend
"$VENV/python" "$DEMO/serve.py" "$REPO/frontend/dist" "http://127.0.0.1:8010" 8080 \
  > "$STATE/logs/serve.log" 2>&1 &

cd "$DEMO"
"$VENV/python" "$DEMO/seed_api.py"

echo "== READY =="
"$@"
