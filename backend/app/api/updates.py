"""Updates API routes"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db, SessionLocal
from app.models import UpdateLog, User, SystemSettings, VmScanCache
from app.api.auth import get_current_user, require_operator
from app.services.updates import UpdateService

router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────────

class UpdateLogResponse(BaseModel):
    id: int
    vm_id: int
    initiated_by: int
    status: str
    packages_updated: int
    output: Optional[str]
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class InlineCreds(BaseModel):
    """Optional inline SSH credentials — used when not saved to DB"""
    ip_address: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class ScheduleSettings(BaseModel):
    auto_update_check_enabled: bool
    auto_update_check_interval_hours: int = 24
    auto_security_scan_enabled: bool
    auto_security_scan_interval_hours: int = 24


# ── background task helper (owns its own DB session) ─────────────────────────

def _install_updates_bg(vm_id: int, user_id: int, override_ip=None, override_user=None, override_pass=None):
    """Run update installation in a background thread with a dedicated DB session."""
    db = SessionLocal()
    try:
        service = UpdateService(db)
        service.install_updates(
            vm_id, user_id,
            override_ip=override_ip,
            override_user=override_user,
            override_pass=override_pass,
        )
    finally:
        db.close()


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/vm/{vm_id}/check")
async def check_vm_updates(
    vm_id: int,
    creds: Optional[InlineCreds] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check for available updates on a VM"""
    update_service = UpdateService(db)
    result = update_service.check_updates(
        vm_id,
        override_ip=creds.ip_address if creds else None,
        override_user=creds.username if creds else None,
        override_pass=creds.password if creds else None,
    )

    if not result:
        raise HTTPException(
            status_code=500,
            detail="Failed to check updates — ensure VM is running and SSH credentials are set",
        )

    # Cache the result so the auto-check dashboard can use it too
    try:
        _upsert_scan_cache(
            db, vm_id, "updates", result,
            severity="warning" if result["updates_available"] > 0 else "ok",
            summary=f"{result['updates_available']} update(s) available",
        )
    except Exception:
        pass  # cache write failure should not fail the request

    return result


@router.post("/vm/{vm_id}/install")
async def install_vm_updates(
    vm_id: int,
    background_tasks: BackgroundTasks,
    creds: Optional[InlineCreds] = Body(default=None),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Install updates on a VM (runs in background)"""
    background_tasks.add_task(
        _install_updates_bg,
        vm_id,
        current_user.id,
        creds.ip_address if creds else None,
        creds.username if creds else None,
        creds.password if creds else None,
    )
    return {"status": "started", "message": "Update process started — check History for progress"}


@router.post("/vm/{vm_id}/scan-security")
async def scan_vm_security(
    vm_id: int,
    creds: Optional[InlineCreds] = Body(default=None),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Run security and dependency scan on a VM"""
    update_service = UpdateService(db)
    result = update_service.scan_security(
        vm_id,
        override_ip=creds.ip_address if creds else None,
        override_user=creds.username if creds else None,
        override_pass=creds.password if creds else None,
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    # Cache the result
    try:
        sec = result.get("os_updates", {}).get("security_updates", 0)
        failed = result.get("failed_ssh_attempts", 0)
        _upsert_scan_cache(
            db, vm_id, "security", result,
            severity=result.get("severity", "ok"),
            summary=f"{sec} security updates, {failed} failed SSH logins",
        )
    except Exception:
        pass

    return result


@router.get("/vm/{vm_id}/history", response_model=List[UpdateLogResponse])
async def get_vm_update_history(
    vm_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get update history for a VM"""
    logs = (
        db.query(UpdateLog)
        .filter(UpdateLog.vm_id == vm_id)
        .order_by(UpdateLog.started_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return logs


@router.get("/log/{log_id}", response_model=UpdateLogResponse)
async def get_update_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get update log by ID"""
    log = db.query(UpdateLog).filter(UpdateLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Update log not found")
    return log


@router.post("/vm/{vm_id}/install-qemu-agent")
async def install_vm_qemu_agent(
    vm_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Install QEMU guest agent on a VM"""
    update_service = UpdateService(db)
    success = update_service.install_qemu_agent(vm_id)
    if success:
        return {"status": "success", "message": "QEMU guest agent installed"}
    else:
        raise HTTPException(status_code=500, detail="Failed to install QEMU guest agent")


# ── schedule settings ─────────────────────────────────────────────────────────

@router.get("/schedule")
async def get_schedule(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get auto-check schedule settings"""
    def _get(key, default):
        row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
        return row.value if row else default

    return {
        "auto_update_check_enabled": _get("auto_update_check_enabled", "false") == "true",
        "auto_update_check_interval_hours": int(_get("auto_update_check_interval_hours", "24")),
        "auto_security_scan_enabled": _get("auto_security_scan_enabled", "false") == "true",
        "auto_security_scan_interval_hours": int(_get("auto_security_scan_interval_hours", "24")),
    }


@router.put("/schedule")
async def update_schedule(
    settings: ScheduleSettings,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Update auto-check schedule settings"""
    from app.services.scheduler import reschedule

    def _upsert(key, value):
        row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
        if row:
            row.value = value
        else:
            db.add(SystemSettings(key=key, value=value, description="auto-check schedule"))

    _upsert("auto_update_check_enabled", str(settings.auto_update_check_enabled).lower())
    _upsert("auto_update_check_interval_hours", str(settings.auto_update_check_interval_hours))
    _upsert("auto_security_scan_enabled", str(settings.auto_security_scan_enabled).lower())
    _upsert("auto_security_scan_interval_hours", str(settings.auto_security_scan_interval_hours))
    db.commit()

    reschedule(settings.auto_update_check_interval_hours, settings.auto_security_scan_interval_hours)
    return {"status": "ok"}


# ── scan cache ────────────────────────────────────────────────────────────────

@router.get("/cache")
async def get_scan_cache(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get latest cached scan results for all VMs"""
    rows = db.query(VmScanCache).all()
    return [
        {
            "vm_id": r.vm_id,
            "scan_type": r.scan_type,
            "scanned_at": r.scanned_at.isoformat() if r.scanned_at else None,
            "severity": r.severity,
            "summary": r.summary,
        }
        for r in rows
    ]


# ── internal helper ───────────────────────────────────────────────────────────

def _upsert_scan_cache(db, vm_id: int, scan_type: str, result: dict, severity: str, summary: str):
    import json
    cache = (
        db.query(VmScanCache)
        .filter(VmScanCache.vm_id == vm_id, VmScanCache.scan_type == scan_type)
        .first()
    )
    if cache:
        cache.result_json = json.dumps(result)
        cache.scanned_at = datetime.utcnow()
        cache.severity = severity
        cache.summary = summary
    else:
        cache = VmScanCache(
            vm_id=vm_id,
            scan_type=scan_type,
            result_json=json.dumps(result),
            scanned_at=datetime.utcnow(),
            severity=severity,
            summary=summary,
        )
        db.add(cache)
    db.commit()
