"""Main FastAPI application"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import init_db
from app.api import auth, users, proxmox, vms, isos, cloud_images, updates, dashboard, bug_report, logs, docs, setup, system_updates, ha, system
import logging
from logging.handlers import RotatingFileHandler
import os

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
    description="Automated VM Deployment Panel for Proxmox VE",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
