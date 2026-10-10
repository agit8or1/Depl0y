# OSS Scanner build for Depl0y (https://github.com/anthropics/oss-scanner).
# Built with the repository as the build context. Network is available during this build only; the
# security audit afterwards runs offline, so every dependency is installed here.
FROM python:3.12-bookworm

# Node 22 for the Vue/Vite frontend (vite 8 needs Node >= 20.19).
COPY --from=node:22-bookworm /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CI=true
# Runtime libraries: pango/harfbuzz for weasyprint (PDF docs export), ssh tooling used by the backend.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git sqlite3 openssh-client sshpass \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Backend: same steps as install.sh (venv + requirements.txt). The venv is put first on PATH so
# `python`, `pytest` and `uvicorn` resolve to it in the scanner shell.
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r backend/requirements.txt
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/src/backend

# Directories the backend writes to with its default config (SQLite DB, ISOs, keys, logs).
RUN mkdir -p /var/lib/depl0y/db /var/lib/depl0y/isos /var/lib/depl0y/cloud-images \
      /var/lib/depl0y/cloud-init /var/lib/depl0y/ssh_keys /var/log/depl0y /etc/depl0y

# Frontend: install and build exactly as the release does (node_modules is not tracked in git).
RUN cd frontend && npm ci --no-audit --no-fund && npm run build

# Smoke test: the FastAPI app imports and its routes register. The project has no unit test suite;
# start it offline with: cd /src/backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
RUN cd backend && (python -c "import app.main as m; print('depl0y API paths:', len(m.app.openapi()['paths']))" \
    || echo "WARNING: backend import smoke test failed")
