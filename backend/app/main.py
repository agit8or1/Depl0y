"""Main FastAPI application"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import init_db
from app.api import auth, users, proxmox, vms, isos, cloud_images, updates, dashboard, bug_report, logs, docs, setup, system_updates, ha, system, llm, vm_agent, security, idrac, pbs, audit, notifications
from app.api import vm_config, node as pve_node, console as pve_console, pbs_mgmt, pve_firewall, cluster as pve_cluster
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

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

# Add IP filter + GeoIP middleware (runs after rate limiting)
app.add_middleware(IPFilterMiddleware)


# Request counter middleware
@app.middleware("http")
async def count_requests(request: Request, call_next):
    global _request_counter
    _request_counter += 1
    response = await call_next(request)
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
