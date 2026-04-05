"""VM Groups — local logical groupings stored in the Depl0y database."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import json

from app.core.database import get_db
from app.models.database import VMGroup
from app.api.auth import get_current_user, require_operator

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class VMGroupCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    color: str = Field("#3b82f6", max_length=7)
    host_id: Optional[int] = None
    vmids: List[str] = []


class VMGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, max_length=7)
    host_id: Optional[int] = None
    vmids: Optional[List[str]] = None


class VMGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    color: str
    host_id: Optional[int]
    vmids: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class VmidBody(BaseModel):
    vmid: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_vmids(group: VMGroup) -> List[str]:
    try:
        return json.loads(group.vmids or "[]")
    except Exception:
        return []


def _dump_vmids(vmids: List[str]) -> str:
    return json.dumps(list(dict.fromkeys(vmids)))  # deduplicate, preserve order


def _group_to_response(group: VMGroup) -> VMGroupResponse:
    return VMGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        color=group.color or "#3b82f6",
        host_id=group.host_id,
        vmids=_load_vmids(group),
        created_at=group.created_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[VMGroupResponse])
def list_vm_groups(db: Session = Depends(get_db),
                   current_user=Depends(get_current_user)):
    """List all VM groups."""
    groups = db.query(VMGroup).order_by(VMGroup.name).all()
    return [_group_to_response(g) for g in groups]


@router.post("/", response_model=VMGroupResponse, status_code=status.HTTP_201_CREATED)
def create_vm_group(body: VMGroupCreate, db: Session = Depends(get_db),
                    current_user=Depends(require_operator)):
    """Create a new VM group."""
    existing = db.query(VMGroup).filter(VMGroup.name == body.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="A group with this name already exists")
    group = VMGroup(
        name=body.name,
        description=body.description,
        color=body.color,
        host_id=body.host_id,
        vmids=_dump_vmids(body.vmids),
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return _group_to_response(group)


@router.get("/{group_id}", response_model=VMGroupResponse)
def get_vm_group(group_id: int, db: Session = Depends(get_db),
                 current_user=Depends(get_current_user)):
    """Get a VM group by ID."""
    group = db.query(VMGroup).filter(VMGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return _group_to_response(group)


@router.put("/{group_id}", response_model=VMGroupResponse)
def update_vm_group(group_id: int, body: VMGroupUpdate, db: Session = Depends(get_db),
                    current_user=Depends(require_operator)):
    """Update a VM group."""
    group = db.query(VMGroup).filter(VMGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if body.name is not None:
        conflict = db.query(VMGroup).filter(
            VMGroup.name == body.name, VMGroup.id != group_id
        ).first()
        if conflict:
            raise HTTPException(status_code=400, detail="A group with this name already exists")
        group.name = body.name
    if body.description is not None:
        group.description = body.description
    if body.color is not None:
        group.color = body.color
    if body.host_id is not None:
        group.host_id = body.host_id
    if body.vmids is not None:
        group.vmids = _dump_vmids(body.vmids)
    db.commit()
    db.refresh(group)
    return _group_to_response(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vm_group(group_id: int, db: Session = Depends(get_db),
                    current_user=Depends(require_operator)):
    """Delete a VM group."""
    group = db.query(VMGroup).filter(VMGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(group)
    db.commit()
    return None


@router.post("/{group_id}/add-vm", response_model=VMGroupResponse)
def add_vm_to_group(group_id: int, body: VmidBody, db: Session = Depends(get_db),
                    current_user=Depends(require_operator)):
    """Add a VM (by vmid string) to a group."""
    group = db.query(VMGroup).filter(VMGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    vmids = _load_vmids(group)
    if body.vmid not in vmids:
        vmids.append(body.vmid)
        group.vmids = _dump_vmids(vmids)
        db.commit()
        db.refresh(group)
    return _group_to_response(group)


@router.delete("/{group_id}/remove-vm/{vmid}", response_model=VMGroupResponse)
def remove_vm_from_group(group_id: int, vmid: str, db: Session = Depends(get_db),
                         current_user=Depends(require_operator)):
    """Remove a VM from a group."""
    group = db.query(VMGroup).filter(VMGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    vmids = [v for v in _load_vmids(group) if v != vmid]
    group.vmids = _dump_vmids(vmids)
    db.commit()
    db.refresh(group)
    return _group_to_response(group)
