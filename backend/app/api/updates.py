"""Updates API routes"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.models import UpdateLog, User
from app.api.auth import get_current_user, require_operator
from app.services.updates import UpdateService

router = APIRouter()


# Pydantic models
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


@router.post("/vm/{vm_id}/check")
async def check_vm_updates(
    vm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check for available updates on a VM"""
    update_service = UpdateService(db)
    result = update_service.check_updates(vm_id)

    if not result:
        raise HTTPException(status_code=500, detail="Failed to check updates")

    return result


@router.post("/vm/{vm_id}/install")
async def install_vm_updates(
    vm_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Install updates on a VM"""
    update_service = UpdateService(db)

    # Run update in background
    background_tasks.add_task(update_service.install_updates, vm_id, current_user.id)

    return {"status": "started", "message": "Update process started"}


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
