# Architecture and internals

How Depl0y is put together, where it keeps state, and how to run it from source.

---

## Shape

```
┌─────────────────────────────────────┐
│         Frontend (Vue 3 SPA)        │
│   Axios · Chart.js · Leaflet        │
│   xterm.js · noVNC · widget grid    │
└──────────────┬──────────────────────┘
               │ HTTP REST (/api/v1), served by nginx
┌──────────────▼──────────────────────┐
│        Backend (FastAPI)            │
│  auth · VMs · cluster · storage     │
│  backup · HA · import · LLM         │
│  iDRAC · alerts · audit · updates   │
│  APScheduler background jobs        │
└──────┬───────────────┬──────────────┘
       │               │
┌──────▼──────┐  ┌─────▼───────────────────────┐
│  SQLite DB  │  │  Proxmox VE API (8006)      │
│ users, host │  │  Redfish on BMCs (443)      │
│ creds, VMs, │  │  SSH to nodes / guests (22) │
│ settings    │  │  PBS API                    │
└─────────────┘  └─────────────────────────────┘
```

Depl0y runs on its own host, not on the Proxmox nodes. It holds no hypervisor
state of its own — Proxmox remains the source of truth; Depl0y stores
credentials, its own users, settings, and caches.

**Key libraries:** proxmoxer, requests, paramiko, pyVmomi, SQLAlchemy, Pydantic,
APScheduler, python-jose, cryptography (Fernet), Vue 3, Chart.js, Leaflet,
xterm.js.

---

## Background jobs

APScheduler runs inside the backend process:

| Job | Default cadence | What it does |
|---|---|---|
| Proxmox node poll | 1 min | refreshes node status, resource counters and guest counts |
| BMC poll | 2 min (configurable 1/2/5/10) | Redfish + SSH sweep of every configured BMC |
| Dell firmware catalog | 24 h | compares installed BIOS/iDRAC versions against Dell's catalog |
| Update check | 24 h (configurable) | guest OS update scan |
| Alert engine | continuous | evaluates alert rules and raises events |

BMC results live in an in-process cache keyed `pve:{id}`, `pve_node:{id}`,
`pbs:{id}` or `standalone:{id}`, served raw at `GET /api/v1/idrac/status`.

---

## Caching

Proxmox reads that the UI polls hard are wrapped in a small TTL cache
(`app/core/cache.py`). VM status uses a 10 second TTL, config 30 seconds. This
is why a rate widget that diffs two 5-second samples sometimes reads zero: the
second sample can be the same cached payload.

---

## State on disk

| Path | Contents |
|---|---|
| `/var/lib/depl0y/db/depl0y.db` | SQLite database |
| `/var/lib/depl0y/isos` | uploaded ISO images |
| `/var/lib/depl0y/cloud-images` | cloud image templates |
| `/var/lib/depl0y/ssh_keys` | generated SSH key pairs |
| `/var/log/depl0y/` | application logs |
| `/tmp/depl0y-imports/` | VM import working directory |
| `/etc/depl0y/config.env` | secrets and configuration |

---

## Configuration

`/etc/depl0y/config.env`, read by the systemd unit:

```bash
SECRET_KEY=<jwt signing key, 32+ chars>
ENCRYPTION_KEY=<Fernet key — decrypts every stored credential>
DATABASE_URL=sqlite:////var/lib/depl0y/db/depl0y.db
DEBUG=false
LOG_LEVEL=INFO
# CORS_ORIGINS=https://panel.example.com
```

`ENCRYPTION_KEY` is the one value you cannot regenerate. Lose it and every
stored Proxmox and BMC credential has to be re-entered.

Other environment variables honoured by the backend: `ISO_STORAGE_PATH`,
`UPLOAD_DIR`, `CORS_ORIGINS`.

---

## Services

```bash
systemctl status depl0y-backend     # FastAPI on 127.0.0.1:8000
systemctl status nginx              # serves the SPA, proxies /api
journalctl -u depl0y-backend -f
```

nginx config lives at `/etc/nginx/sites-available/depl0y`; the built frontend is
served from `/opt/depl0y/frontend/dist`.

---

## Running from source

```bash
# Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

The dev server proxies `/api/v1` to the backend on port 8000. Set
`DATABASE_URL`, `SECRET_KEY` and `ENCRYPTION_KEY` in the environment before
starting the backend, or it will generate throwaway values on each run.

---

## API

- Swagger UI — `/api/v1/docs`
- ReDoc — `/api/v1/redoc`
- In-app — sidebar → **API Explorer**

All routes are under `/api/v1`. Authentication is a bearer JWT from
`POST /api/v1/auth/login`, with refresh tokens and optional TOTP challenge.
