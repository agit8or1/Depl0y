"""Proxmox hosts API routes"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import encrypt_data, decrypt_data
from app.models import ProxmoxHost, ProxmoxNode
from app.api.auth import get_current_user, require_admin
from app.models import User
from app.services.proxmox import ProxmoxService, poll_proxmox_resources

router = APIRouter()


# Pydantic models
class ProxmoxHostCreate(BaseModel):
    name: str
    hostname: str
    port: int = 8006
    username: str
    password: Optional[str] = None
    api_token_id: Optional[str] = None  # e.g., "mytoken" or "root@pam!mytoken"
    api_token_secret: Optional[str] = None
    verify_ssl: bool = False


class ProxmoxHostUpdate(BaseModel):
    name: Optional[str] = None
    hostname: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_token_id: Optional[str] = None
    api_token_secret: Optional[str] = None
    verify_ssl: Optional[bool] = None
    is_active: Optional[bool] = None


class ProxmoxHostResponse(BaseModel):
    id: int
    name: str
    hostname: str
    port: int
    username: str
    verify_ssl: bool
    is_active: bool
    last_poll: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProxmoxNodeResponse(BaseModel):
    id: int
    host_id: int
    node_name: str
    status: Optional[str]
    cpu_cores: Optional[int]
    cpu_usage: Optional[int]
    memory_total: Optional[int]
    memory_used: Optional[int]
    disk_total: Optional[int]
    disk_used: Optional[int]
    uptime: Optional[int]
    last_updated: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ProxmoxHostResponse])
async def list_proxmox_hosts(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all Proxmox hosts"""
    hosts = db.query(ProxmoxHost).offset(skip).limit(limit).all()
    return hosts


@router.post("/", response_model=ProxmoxHostResponse, status_code=status.HTTP_201_CREATED)
async def create_proxmox_host(
    host_data: ProxmoxHostCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new Proxmox host (admin only)"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Received Proxmox host create request: name={host_data.name}, hostname={host_data.hostname}, username={host_data.username}, has_password={bool(host_data.password)}, has_token_id={bool(host_data.api_token_id)}, has_token_secret={bool(host_data.api_token_secret)}")

    # Check if name already exists
    existing_host = db.query(ProxmoxHost).filter(ProxmoxHost.name == host_data.name).first()
    if existing_host:
        raise HTTPException(status_code=400, detail="Host name already exists")

    # Validate that either password or API token is provided
    if not host_data.password and not (host_data.api_token_id and host_data.api_token_secret):
        raise HTTPException(
            status_code=400,
            detail="Either password or API token (both token ID and secret) must be provided"
        )

    # Encrypt password if provided
    encrypted_password = encrypt_data(host_data.password) if host_data.password else None

    # Encrypt API token secret if provided
    encrypted_token_secret = encrypt_data(host_data.api_token_secret) if host_data.api_token_secret else None

    # Create new host
    new_host = ProxmoxHost(
        name=host_data.name,
        hostname=host_data.hostname,
        port=host_data.port,
        username=host_data.username,
        password=encrypted_password,
        api_token_id=host_data.api_token_id,
        api_token_secret=encrypted_token_secret,
        verify_ssl=host_data.verify_ssl,
    )

    db.add(new_host)
    db.commit()
    db.refresh(new_host)

    # Test connection
    try:
        service = ProxmoxService(new_host)
        if not service.test_connection():
            raise HTTPException(
                status_code=400, detail="Cannot connect to Proxmox host. Check credentials and connectivity."
            )
    except Exception as e:
        db.delete(new_host)
        db.commit()
        raise HTTPException(status_code=400, detail=f"Failed to connect: {str(e)}")

    return new_host


@router.get("/{host_id}", response_model=ProxmoxHostResponse)
async def get_proxmox_host(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get Proxmox host by ID"""
    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    return host


@router.put("/{host_id}", response_model=ProxmoxHostResponse)
async def update_proxmox_host(
    host_id: int,
    host_data: ProxmoxHostUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update Proxmox host (admin only)"""
    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    # Update fields
    if host_data.name is not None:
        # Check if name already exists
        existing_host = (
            db.query(ProxmoxHost)
            .filter(ProxmoxHost.name == host_data.name, ProxmoxHost.id != host_id)
            .first()
        )
        if existing_host:
            raise HTTPException(status_code=400, detail="Host name already exists")
        host.name = host_data.name

    if host_data.hostname is not None:
        host.hostname = host_data.hostname

    if host_data.port is not None:
        host.port = host_data.port

    if host_data.username is not None:
        host.username = host_data.username

    if host_data.password is not None:
        host.password = encrypt_data(host_data.password)

    if host_data.api_token_id is not None:
        host.api_token_id = host_data.api_token_id

    if host_data.api_token_secret is not None:
        host.api_token_secret = encrypt_data(host_data.api_token_secret)

    if host_data.verify_ssl is not None:
        host.verify_ssl = host_data.verify_ssl

    if host_data.is_active is not None:
        host.is_active = host_data.is_active

    host.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(host)

    return host


@router.delete("/{host_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxmox_host(
    host_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete Proxmox host (admin only)"""
    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    db.delete(host)
    db.commit()

    return None


@router.post("/{host_id}/test")
async def test_proxmox_connection(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test connection to Proxmox host"""
    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    try:
        service = ProxmoxService(host)
        success = service.test_connection()

        if success:
            return {"status": "success", "message": "Connection successful"}
        else:
            return {"status": "error", "message": "Connection failed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/{host_id}/poll")
async def poll_proxmox_host(
    host_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Poll Proxmox host for resources"""
    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    # Run polling in background
    background_tasks.add_task(poll_proxmox_resources, db, host_id)

    return {"status": "success", "message": "Polling started"}


@router.get("/{host_id}/nodes", response_model=List[ProxmoxNodeResponse])
async def list_proxmox_nodes(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List nodes for a Proxmox host"""
    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    nodes = db.query(ProxmoxNode).filter(ProxmoxNode.host_id == host_id).all()
    return nodes


@router.get("/{host_id}/stats")
async def get_datacenter_stats(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get datacenter statistics including VM counts"""
    from app.models import VirtualMachine, VMStatus
    from sqlalchemy import func

    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    # Get VM counts by status
    vm_counts = db.query(
        VirtualMachine.status,
        func.count(VirtualMachine.id).label('count')
    ).filter(
        VirtualMachine.proxmox_host_id == host_id
    ).group_by(VirtualMachine.status).all()

    # Convert to dict
    status_counts = {status: count for status, count in vm_counts}

    # Get total VMs
    total_vms = sum(status_counts.values())

    return {
        "total_vms": total_vms,
        "running": status_counts.get(VMStatus.RUNNING, 0),
        "stopped": status_counts.get(VMStatus.STOPPED, 0),
        "creating": status_counts.get(VMStatus.CREATING, 0),
        "error": status_counts.get(VMStatus.ERROR, 0),
    }


@router.get("/nodes/{node_id}", response_model=ProxmoxNodeResponse)
async def get_proxmox_node(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get Proxmox node by ID"""
    node = db.query(ProxmoxNode).filter(ProxmoxNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.get("/nodes/{node_id}/storage")
async def get_node_storage(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get storage pools available on a node"""
    node = db.query(ProxmoxNode).filter(ProxmoxNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == node.host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    try:
        service = ProxmoxService(host)
        storage_list = service.get_storage_list(node.node_name)
        return {"storage": storage_list}
    except Exception as e:
        logger.error(f"Failed to get storage for node {node.node_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get storage: {str(e)}")


@router.get("/nodes/{node_id}/network")
async def get_node_network(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get network interfaces/bridges available on a node"""
    node = db.query(ProxmoxNode).filter(ProxmoxNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == node.host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    try:
        service = ProxmoxService(host)
        network_list = service.get_network_interfaces(node.node_name)
        return {"network": network_list}
    except Exception as e:
        logger.error(f"Failed to get network for node {node.node_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get network: {str(e)}")
