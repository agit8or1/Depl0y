"""Main FastAPI application"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import init_db
from app.api import auth, users, proxmox, vms, isos, cloud_images, updates, dashboard, bug_report, logs, docs, setup, system_updates, ha, system, llm, vm_agent, security, idrac, pbs, audit, notifications
from app.api import vm_config, node as pve_node, console as pve_console, pbs_mgmt, pve_firewall, cluster as pve_cluster, sdn
from app.api import vm_groups, vm_import
from app.api import pve_access
from app.api import tasks as task_api
from app.api import bulk_ops
from app.api import integrations
from app.api import alerts as alerts_api
from app.api import analysis as analysis_api
from app.api import ai_reports as ai_reports_api
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.ip_filter import IPFilterMiddleware
import logging
from logging.handlers import RotatingFileHandler
import os
import time

# Global request counter for metrics
_request_counter = 0
_app_start_time = time.time()

# Configure logging
os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(settings.LOG_FILE, maxBytes=10485760, backupCount=5),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "**Depl0y** is an open-source Proxmox VE management platform providing automated VM "
        "deployment, LXC container management, backup orchestration, security monitoring, "
        "and full infrastructure lifecycle management via a clean REST API.\n\n"
        "## Authentication\n"
        "All endpoints require authentication via **Bearer JWT token** (obtained from `/api/v1/auth/login`) "
        "or an **X-API-Key header** (`dk_...` prefix, created in your profile).\n\n"
        "## Rate Limits\n"
        "General API: 100 requests/minute per IP. Login endpoint: 5 requests/minute per IP."
    ),
    contact={
        "name": "Depl0y Project",
        "url": "https://github.com/agit8or1/Depl0y",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add rate limiting middleware (default rpm driven by config)
app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.RATE_LIMIT_DEFAULT)

# Add IP filter + GeoIP middleware (runs after rate limiting)
app.add_middleware(IPFilterMiddleware)


# Request counter middleware
@app.middleware("http")
async def count_requests(request: Request, call_next):
    global _request_counter
    _request_counter += 1
    response = await call_next(request)
    return response


# Audit middleware — logs mutating requests for authenticated users
@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    import time as _time
    start = _time.time()
    response = await call_next(request)
    duration_ms = int((_time.time() - start) * 1000)

    method = request.method
    path = request.url.path

    # Only audit mutating requests to API endpoints (not static/health)
    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        return response
    if not path.startswith(settings.API_V1_PREFIX):
        return response

    # Skip certain noisy/login endpoints (those handle their own audit entries)
    skip_suffixes = ("/auth/refresh", "/auth/login", "/auth/2fa/login",
                     "/auth/logout", "/notifications/in-app/mark-read",
                     "/auth/me/password", "/auth/totp/verify", "/auth/totp/disable",
                     "/auth/api-keys")
    if any(path.endswith(s) for s in skip_suffixes):
        return response
    # Also skip user creation/deletion which are logged explicitly
    import re as _re
    if _re.search(r'/users/\d+$', path) and method in ("DELETE", "PUT", "PATCH"):
        return response
    if path.endswith("/users/") and method == "POST":
        return response

    # Try to identify the user from the request
    try:
        from app.core.database import SessionLocal
        from app.core.security import decode_token
        from app.models.database import AuditLog, User as UserModel

        user_id = None
        token = request.headers.get("Authorization", "")
        if token.startswith("Bearer "):
            payload = decode_token(token[7:])
            if payload:
                username = payload.get("sub")
                if username:
                    _db = SessionLocal()
                    try:
                        u = _db.query(UserModel).filter(UserModel.username == username).first()
                        if u:
                            user_id = u.id
                    finally:
                        _db.close()

        # Determine action from method + path
        action = "api_call"
        p = path.lower()
        if method == "DELETE":
            action = "delete"
        elif method == "POST":
            action = "create"
            if "start" in p:
                action = "vm_start"
            elif "stop" in p or "shutdown" in p:
                action = "vm_stop"
            elif "reboot" in p or "restart" in p:
                action = "vm_reboot"
            elif "backup" in p or "vzdump" in p:
                action = "backup"
            elif "snapshot" in p:
                action = "snapshot_create"
            elif "migrate" in p:
                action = "vm_migrate"
            elif "clone" in p:
                action = "vm_clone"
        elif method in ("PUT", "PATCH"):
            action = "modify"

        # Determine resource type
        resource_type = None
        if "/vms/" in p or "/qemu/" in p or "/pve-vm/" in p:
            resource_type = "vm"
        elif "/lxc/" in p:
            resource_type = "lxc"
        elif "/users/" in p:
            resource_type = "user"
        elif "/proxmox/" in p or "/pve-node/" in p:
            resource_type = "node"
        elif "/pbs" in p:
            resource_type = "storage"
        elif "/auth/" in p:
            resource_type = "system"
        elif "/security/" in p:
            resource_type = "system"

        success = response.status_code < 400

        if user_id is not None:
            _db = SessionLocal()
            try:
                client_ip = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent", "")
                entry = AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    details={"path": path, "method": method},
                    ip_address=client_ip,
                    user_agent=user_agent[:500] if user_agent else None,
                    http_method=method,
                    request_path=path,
                    response_status=response.status_code,
                    duration_ms=duration_ms,
                    success=success,
                )
                _db.add(entry)
                _db.commit()
            except Exception:
                _db.rollback()
            finally:
                _db.close()
    except Exception:
        pass

    return response


# Add validation error handler for debugging
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors with details"""
    logger.error(f"Validation error on {request.method} {request.url}")
    logger.error(f"Validation errors: {exc.errors()}")
    try:
        body = await request.body()
        logger.error(f"Request body: {body.decode()}")
    except:
        pass
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    init_db()
    logger.info("Database initialized")

    # Start background scheduler for auto-checks
    from app.core.database import SessionLocal
    from app.models import SystemSettings
    from app.services.scheduler import start_scheduler
    db = SessionLocal()
    try:
        def _get(key, default):
            row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
            try:
                return int(row.value) if row else default
            except (TypeError, ValueError):
                return default
        update_h = _get("auto_update_check_interval_hours", 24)
        scan_h = _get("auto_security_scan_interval_hours", 24)
    finally:
        db.close()
    start_scheduler(update_h, scan_h)
    logger.info("Background scheduler started")

    # Start alert engine
    from app.services.alert_engine import alert_engine
    alert_engine.start()
    logger.info("Alert engine started")

    # Start analysis engine
    from app.services.analysis_engine import analysis_engine
    analysis_engine.start()
    logger.info("Analysis engine started")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get(f"{settings.API_V1_PREFIX}/openapi-summary", tags=["Developer Tools"])
async def openapi_summary():
    """Return a simplified list of all API routes with method, path, tag, and summary."""
    result = []
    for route in app.routes:
        # Only include APIRoutes (not websocket, mount, etc.)
        from fastapi.routing import APIRoute
        if isinstance(route, APIRoute):
            for method in route.methods or []:
                tags = list(route.tags) if route.tags else ["Untagged"]
                result.append({
                    "method": method,
                    "path": route.path,
                    "tag": tags[0] if tags else "Untagged",
                    "summary": route.summary or route.name or "",
                    "description": (route.description or "").strip()[:200] if route.description else "",
                })
    # Sort by tag then path
    result.sort(key=lambda x: (x["tag"], x["path"]))
    return result


# Include routers
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["Users"])
app.include_router(proxmox.router, prefix=f"{settings.API_V1_PREFIX}/proxmox", tags=["Proxmox"])
app.include_router(vms.router, prefix=f"{settings.API_V1_PREFIX}/vms", tags=["Virtual Machines"])
app.include_router(isos.router, prefix=f"{settings.API_V1_PREFIX}/isos", tags=["ISO Images"])
app.include_router(cloud_images.router, prefix=f"{settings.API_V1_PREFIX}/cloud-images", tags=["Cloud Images"])
app.include_router(updates.router, prefix=f"{settings.API_V1_PREFIX}/updates", tags=["Updates"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_PREFIX}/dashboard", tags=["Dashboard"])
app.include_router(bug_report.router, prefix=f"{settings.API_V1_PREFIX}/bug-report", tags=["Bug Report"])
app.include_router(logs.router, prefix=f"{settings.API_V1_PREFIX}/logs", tags=["System Logs"])
app.include_router(docs.router, prefix=f"{settings.API_V1_PREFIX}/docs", tags=["Documentation"])
app.include_router(setup.router, prefix=f"{settings.API_V1_PREFIX}/setup", tags=["Setup"])
app.include_router(system_updates.router, prefix=f"{settings.API_V1_PREFIX}/system-updates", tags=["System Updates"])
app.include_router(ha.router, prefix=f"{settings.API_V1_PREFIX}/ha", tags=["High Availability"])
app.include_router(system.router, prefix=f"{settings.API_V1_PREFIX}/system", tags=["System"])
app.include_router(llm.router, prefix=f"{settings.API_V1_PREFIX}/llm", tags=["LLM Deployment"])
app.include_router(vm_agent.router, prefix=f"{settings.API_V1_PREFIX}/vm-agent", tags=["VM Agent"])
app.include_router(security.router, prefix=f"{settings.API_V1_PREFIX}/security", tags=["Security"])
app.include_router(idrac.router, prefix=f"{settings.API_V1_PREFIX}/idrac", tags=["iDRAC/iLO"])
app.include_router(pbs.router, prefix=f"{settings.API_V1_PREFIX}/pbs", tags=["PBS Servers"])
app.include_router(vm_config.router, prefix=f"{settings.API_V1_PREFIX}/pve-vm", tags=["PVE VM Control"])
app.include_router(pve_node.router, prefix=f"{settings.API_V1_PREFIX}/pve-node", tags=["PVE Node/Cluster"])
app.include_router(pve_console.router, prefix=f"{settings.API_V1_PREFIX}/pve-console", tags=["PVE Console"])
app.include_router(pbs_mgmt.router, prefix=f"{settings.API_V1_PREFIX}/pbs-mgmt", tags=["PBS Management"])
app.include_router(audit.router, prefix=f"{settings.API_V1_PREFIX}/audit", tags=["Audit Log"])
app.include_router(notifications.router, prefix=f"{settings.API_V1_PREFIX}/notifications", tags=["Notifications"])
app.include_router(pve_firewall.router, prefix=f"{settings.API_V1_PREFIX}/pve-firewall", tags=["PVE Firewall"])
app.include_router(pve_cluster.router, prefix=f"{settings.API_V1_PREFIX}/cluster", tags=["Cluster Operations"])
app.include_router(sdn.router, prefix=f"{settings.API_V1_PREFIX}", tags=["SDN"])
app.include_router(vm_groups.router, prefix=f"{settings.API_V1_PREFIX}/vm-groups", tags=["VM Groups"])
app.include_router(vm_import.router, prefix=f"{settings.API_V1_PREFIX}/vm-import", tags=["VM Import"])
app.include_router(task_api.router, prefix=f"{settings.API_V1_PREFIX}/tasks", tags=["Task Queue"])
app.include_router(bulk_ops.router, prefix=f"{settings.API_V1_PREFIX}/pve-vm", tags=["Bulk Operations"])
app.include_router(integrations.router, prefix=f"{settings.API_V1_PREFIX}/integrations", tags=["Integrations"])
app.include_router(alerts_api.router, prefix=f"{settings.API_V1_PREFIX}/alerts", tags=["Alerts"])
app.include_router(analysis_api.router, prefix=f"{settings.API_V1_PREFIX}/analysis", tags=["Analysis"])
app.include_router(pve_access.router, prefix=f"{settings.API_V1_PREFIX}/pve-access", tags=["PVE Access Control"])
app.include_router(ai_reports_api.router, prefix=f"{settings.API_V1_PREFIX}/ai-reports", tags=["AI Reports"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
