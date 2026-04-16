"""Proxmox hosts API routes"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
import re

from app.core.database import get_db
from app.core.security import encrypt_data, decrypt_data
from app.models import ProxmoxHost, ProxmoxNode
from app.api.auth import get_current_user, require_admin
from app.models import User, UserRole
from app.services.proxmox import ProxmoxService, poll_proxmox_resources
from app.core.cache import pve_cache
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)
router = APIRouter()


_TOKEN_FORMAT_RE = re.compile(r'^[^@]+@[^!]+![^\s]+$')  # user@realm!tokenname
_HOSTNAME_RE = re.compile(
    r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*'
    r'[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$'
)


# Pydantic models
class ProxmoxHostCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    hostname: str = Field(..., min_length=1, max_length=253)
    port: int = Field(8006, ge=1, le=65535, description="TCP port (1–65535)")
    username: str = Field(..., min_length=1, max_length=128)
    password: Optional[str] = None
    api_token_id: Optional[str] = None  # e.g., "mytoken" or "root@pam!mytoken"
    api_token_secret: Optional[str] = None
    verify_ssl: bool = False
    # Geographic location for federation map
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # iDRAC / iLO out-of-band management (optional)
    idrac_hostname: Optional[str] = None
    idrac_port: Optional[int] = Field(443, ge=1, le=65535)
    idrac_username: Optional[str] = None
    idrac_password: Optional[str] = None
    idrac_type: Optional[str] = None  # "idrac", "ilo"
    idrac_use_ssh: Optional[bool] = False

    @validator('hostname')
    def hostname_valid(cls, v):
        v = v.strip()
        # Allow bare IPs too — only validate format for hostnames
        ip_re = re.compile(r'^\d{1,3}(\.\d{1,3}){3}$')
        if not ip_re.match(v) and not _HOSTNAME_RE.match(v):
            raise ValueError(
                'hostname must be a valid hostname or IP address'
            )
        return v

    @validator('api_token_id')
    def token_id_format(cls, v):
        if v is None:
            return v
        v = v.strip()
        # Accept bare token name OR "user@realm!tokenname" full form
        if '!' in v and not _TOKEN_FORMAT_RE.match(v):
            raise ValueError(
                'api_token_id must be a plain token name or in '
                '"user@realm!tokenname" format (e.g. root@pam!mytoken)'
            )
        return v

    @validator('port')
    def port_range(cls, v):
        if v < 1 or v > 65535:
            raise ValueError('port must be between 1 and 65535')
        return v


class ProxmoxHostUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    hostname: Optional[str] = Field(None, min_length=1, max_length=253)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, min_length=1, max_length=128)
    password: Optional[str] = None
    api_token_id: Optional[str] = None
    api_token_secret: Optional[str] = None
    verify_ssl: Optional[bool] = None
    is_active: Optional[bool] = None
    # Geographic location for federation map
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Notes
    notes: Optional[str] = None
    # iDRAC / iLO fields
    idrac_hostname: Optional[str] = None
    idrac_port: Optional[int] = Field(None, ge=1, le=65535)
    idrac_username: Optional[str] = None
    idrac_password: Optional[str] = None
    idrac_type: Optional[str] = None
    idrac_use_ssh: Optional[bool] = None

    @validator('api_token_id')
    def token_id_format(cls, v):
        if v is None:
            return v
        v = v.strip()
        if '!' in v and not _TOKEN_FORMAT_RE.match(v):
            raise ValueError(
                'api_token_id must be in "user@realm!tokenname" format '
                'when "!" is present (e.g. root@pam!mytoken)'
            )
        return v


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
    # Geographic location for federation map
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Notes
    notes: Optional[str] = None
    # iDRAC / iLO info (no password)
    idrac_hostname: Optional[str] = None
    idrac_port: Optional[int] = None
    idrac_username: Optional[str] = None
    idrac_type: Optional[str] = None
    idrac_use_ssh: Optional[bool] = None

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
    vm_count: Optional[int] = 0
    lxc_count: Optional[int] = 0
    last_updated: datetime
    notes: Optional[str] = None
    idrac_hostname: Optional[str] = None
    idrac_port: Optional[int] = None
    idrac_username: Optional[str] = None
    idrac_type: Optional[str] = None
    idrac_use_ssh: Optional[bool] = None

    class Config:
        from_attributes = True


class NodeIdracUpdate(BaseModel):
    idrac_hostname: Optional[str] = None
    idrac_port: Optional[int] = None
    idrac_username: Optional[str] = None
    idrac_password: Optional[str] = None
    idrac_type: Optional[str] = None
    idrac_use_ssh: Optional[bool] = None
    notes: Optional[str] = None


class TestConnectionRequest(BaseModel):
    api_url: str
    username: str
    token_name: Optional[str] = None
    token_value: Optional[str] = None
    password: Optional[str] = None
    verify_ssl: bool = False


@router.post("/test-connection")
async def test_new_connection(
    request: TestConnectionRequest,
    current_user: User = Depends(require_admin),
):
    """Test a Proxmox connection before saving — accepts raw credentials, returns cluster info"""
    import urllib.parse
    from proxmoxer import ProxmoxAPI

    # Parse the API URL to extract hostname and port
    url = request.api_url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname or ""
    port = parsed.port or 8006

    if not hostname:
        return {"success": False, "error": "Invalid API URL — could not parse hostname"}

    try:
        if request.token_name and request.token_value:
            # Token authentication
            # token_name can be "user@realm!tokenname" or "tokenname"
            if "!" in request.token_name:
                parts = request.token_name.split("!")
                token_user = parts[0]
                token_id = parts[1]
            else:
                token_user = request.username
                token_id = request.token_name

            pve = ProxmoxAPI(
                hostname,
                user=token_user,
                token_name=token_id,
                token_value=request.token_value,
                port=port,
                verify_ssl=request.verify_ssl,
                timeout=15,
            )
        elif request.password:
            pve = ProxmoxAPI(
                hostname,
                user=request.username,
                password=request.password,
                port=port,
                verify_ssl=request.verify_ssl,
                timeout=15,
            )
        else:
            return {"success": False, "error": "No authentication credentials provided"}

        # Get version
        version_info = pve.version.get()
        proxmox_version = version_info.get("version", "unknown")

        # Get cluster status
        cluster_name = None
        node_count = 0
        nodes = []
        try:
            cluster_status = pve.cluster.status.get()
            for item in cluster_status:
                if item.get("type") == "cluster":
                    cluster_name = item.get("name")
                elif item.get("type") == "node":
                    node_count += 1
                    nodes.append({
                        "name": item.get("name"),
                        "online": bool(item.get("online", 0)),
                        "local": bool(item.get("local", 0)),
                    })
        except Exception:
            # Standalone node — no cluster
            try:
                raw_nodes = pve.nodes.get()
                node_count = len(raw_nodes)
                nodes = [{"name": n.get("node"), "online": n.get("status") == "online", "local": True} for n in raw_nodes]
            except Exception:
                node_count = 1

        # Get storages and networks from first available node if possible
        storages = []
        networks = []
        if nodes:
            first_node = nodes[0]["name"]
            try:
                raw_storage = pve.nodes(first_node).storage.get()
                storages = [
                    {"storage": s.get("storage"), "type": s.get("type"), "content": s.get("content", "")}
                    for s in raw_storage
                ]
            except Exception:
                pass
            try:
                raw_network = pve.nodes(first_node).network.get()
                networks = [
                    {"iface": n.get("iface"), "type": n.get("type"), "comments": n.get("comments", "")}
                    for n in raw_network
                    if n.get("type") in ("bridge", "bond", "vlan")
                ]
            except Exception:
                pass

        return {
            "success": True,
            "cluster_name": cluster_name,
            "node_count": node_count,
            "proxmox_version": proxmox_version,
            "nodes": nodes,
            "storages": storages,
            "networks": networks,
        }

    except Exception as e:
        error_msg = str(e)
        # Simplify common SSL errors
        if "SSL" in error_msg or "certificate" in error_msg.lower():
            error_msg = "SSL certificate error — try disabling SSL verification"
        elif "Connection refused" in error_msg or "timed out" in error_msg.lower():
            error_msg = "Cannot reach host — check the URL and port"
        elif "401" in error_msg or "Unauthorized" in error_msg:
            error_msg = "Authentication failed — check your credentials"
        elif "403" in error_msg or "Permission" in error_msg:
            error_msg = "Permission denied — check token permissions (Privilege Separation must be OFF)"
        return {"success": False, "error": error_msg}


@router.get("/", response_model=List[ProxmoxHostResponse])
async def list_proxmox_hosts(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List Proxmox hosts. Admins see all; operators/viewers see only hosts they have permission for."""
    from app.models.database import UserHostPermission
    if current_user.role == UserRole.ADMIN:
        hosts = db.query(ProxmoxHost).offset(skip).limit(limit).all()
    else:
        perms = db.query(UserHostPermission).filter(
            UserHostPermission.user_id == current_user.id,
            UserHostPermission.can_view == True,
        ).all()
        allowed_host_ids = {p.host_id for p in perms}
        hosts = db.query(ProxmoxHost).filter(
            ProxmoxHost.id.in_(allowed_host_ids)
        ).offset(skip).limit(limit).all()
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

    # Encrypt iDRAC password if provided
    encrypted_idrac_password = encrypt_data(host_data.idrac_password) if host_data.idrac_password else None

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
        idrac_hostname=host_data.idrac_hostname,
        idrac_port=host_data.idrac_port,
        idrac_username=host_data.idrac_username,
        idrac_password=encrypted_idrac_password,
        idrac_type=host_data.idrac_type,
    )

    try:
        db.add(new_host)
        db.commit()
        db.refresh(new_host)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error creating host '{host_data.name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}. The database schema may be out of date — restart the backend to apply migrations.")

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


@router.get("/federation/summary")
async def get_federation_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch aggregated summary across all registered Proxmox hosts in parallel. Cached for 60s."""
    cache_key = "federation:summary"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached

    hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()

    def _fetch_host_summary(host: ProxmoxHost) -> dict:
        """Fetch cluster/node/storage data for a single host. Runs in a thread."""
        result = {
            "host_id": host.id,
            "host_name": host.name,
            "api_url": f"https://{host.hostname}:{host.port}",
            "cluster_name": None,
            "status": "offline",
            "node_count": 0,
            "vm_count": 0,
            "lxc_count": 0,
            "storage_total_gb": 0.0,
            "storage_used_gb": 0.0,
            "cpu_usage_pct": 0.0,
            "memory_total_bytes": 0,
            "memory_used_bytes": 0,
            "memory_usage_pct": 0.0,
            "latency_ms": None,
            "quorate": None,
            "latitude": host.latitude,
            "longitude": host.longitude,
        }
        try:
            svc = ProxmoxService(host)
            pve = svc.proxmox

            t0 = time.time()
            # Cluster status gives node list + quorum info + cluster name
            cluster_status = pve.cluster.status.get()
            result["latency_ms"] = round((time.time() - t0) * 1000)
            result["status"] = "online"

            # Extract cluster name and quorate flag from cluster record
            for item in cluster_status:
                if item.get("type") == "cluster":
                    result["cluster_name"] = item.get("name")
                    result["quorate"] = bool(item.get("quorate", 0))
                elif item.get("type") == "node":
                    result["node_count"] += 1

            # Cluster resources — single call gives VMs, LXC, storage all at once
            resources = pve.cluster.resources.get()

            cpu_usages = []
            mem_total = 0
            mem_used = 0
            storage_total = 0
            storage_used = 0
            vm_count = 0
            lxc_count = 0

            for r in resources:
                rtype = r.get("type", "")
                if rtype == "qemu":
                    vm_count += 1
                elif rtype == "lxc":
                    lxc_count += 1
                elif rtype == "node":
                    cpu_val = r.get("cpu")
                    if cpu_val is not None:
                        cpu_usages.append(float(cpu_val))
                    mem_total += r.get("maxmem", 0) or 0
                    mem_used += r.get("mem", 0) or 0
                elif rtype == "storage":
                    storage_total += r.get("maxdisk", 0) or 0
                    storage_used += r.get("disk", 0) or 0

            result["vm_count"] = vm_count
            result["lxc_count"] = lxc_count
            result["memory_total_bytes"] = mem_total
            result["memory_used_bytes"] = mem_used
            result["memory_usage_pct"] = round((mem_used / mem_total * 100) if mem_total > 0 else 0.0, 1)
            result["cpu_usage_pct"] = round((sum(cpu_usages) / len(cpu_usages) * 100) if cpu_usages else 0.0, 1)
            result["storage_total_gb"] = round(storage_total / (1024 ** 3), 2)
            result["storage_used_gb"] = round(storage_used / (1024 ** 3), 2)

            # Determine cluster health
            if result["quorate"] is True:
                result["cluster_health"] = "healthy"
            elif result["quorate"] is False:
                result["cluster_health"] = "degraded"
            else:
                result["cluster_health"] = "unknown"

        except Exception as e:
            logger.warning(f"Federation summary failed for host {host.name}: {e}")
            result["status"] = "offline"
            result["cluster_health"] = "unknown"

        return result

    summaries = []
    if hosts:
        with ThreadPoolExecutor(max_workers=min(len(hosts), 10)) as executor:
            futures = {executor.submit(_fetch_host_summary, h): h for h in hosts}
            for future in as_completed(futures):
                try:
                    summaries.append(future.result())
                except Exception as e:
                    h = futures[future]
                    logger.error(f"Unexpected error fetching federation summary for {h.name}: {e}")

    # Sort by host_id for stable ordering
    summaries.sort(key=lambda x: x["host_id"])

    response = {
        "hosts": summaries,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "total_vms": sum(s["vm_count"] for s in summaries),
        "total_lxc": sum(s["lxc_count"] for s in summaries),
        "total_nodes": sum(s["node_count"] for s in summaries),
        "total_storage_total_gb": round(sum(s["storage_total_gb"] for s in summaries), 2),
        "total_storage_used_gb": round(sum(s["storage_used_gb"] for s in summaries), 2),
        "online_hosts": sum(1 for s in summaries if s["status"] == "online"),
        "offline_hosts": sum(1 for s in summaries if s["status"] == "offline"),
    }

    pve_cache.set(cache_key, response, ttl=60)
    return response


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

    # iDRAC / iLO fields
    if host_data.idrac_hostname is not None:
        host.idrac_hostname = host_data.idrac_hostname or None
    if host_data.idrac_port is not None:
        host.idrac_port = host_data.idrac_port
    if host_data.idrac_username is not None:
        host.idrac_username = host_data.idrac_username or None
    if host_data.idrac_password is not None:
        host.idrac_password = encrypt_data(host_data.idrac_password) if host_data.idrac_password else None
    if host_data.idrac_type is not None:
        host.idrac_type = host_data.idrac_type or None
    if host_data.idrac_use_ssh is not None:
        host.idrac_use_ssh = host_data.idrac_use_ssh

    if host_data.latitude is not None:
        host.latitude = host_data.latitude
    if host_data.longitude is not None:
        host.longitude = host_data.longitude
    if host_data.notes is not None:
        host.notes = host_data.notes or None

    host.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(host)

    # Invalidate federation summary cache so map updates immediately
    for key in (f"proxmox:version:{host_id}", f"datacenter:summary:{host_id}", "federation:summary"):
        pve_cache.delete(key) if hasattr(pve_cache, "delete") else None

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


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxmox_node(
    node_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a single Proxmox node record (admin only)"""
    node = db.query(ProxmoxNode).filter(ProxmoxNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    db.delete(node)
    db.commit()
    return None


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


@router.patch("/nodes/{node_id}/idrac", response_model=ProxmoxNodeResponse)
async def update_node_idrac(
    node_id: int,
    data: NodeIdracUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update iDRAC/BMC configuration for a specific cluster node (admin only)"""
    node = db.query(ProxmoxNode).filter(ProxmoxNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    if data.idrac_hostname is not None:
        node.idrac_hostname = data.idrac_hostname or None
    if data.idrac_port is not None:
        node.idrac_port = data.idrac_port
    if data.idrac_username is not None:
        node.idrac_username = data.idrac_username or None
    if data.idrac_password is not None:
        from app.core.security import encrypt_data
        node.idrac_password = encrypt_data(data.idrac_password) if data.idrac_password else None
    if data.idrac_type is not None:
        node.idrac_type = data.idrac_type or None
    if data.idrac_use_ssh is not None:
        node.idrac_use_ssh = data.idrac_use_ssh
    if data.notes is not None:
        node.notes = data.notes or None

    db.commit()
    db.refresh(node)
    return node


@router.get("/{host_id}/version")
async def get_host_version(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return Proxmox version string and release info fetched live from the host.
    Cached per-host for 5 minutes.
    """
    cache_key = f"proxmox:version:{host_id}"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached

    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    try:
        svc = ProxmoxService(host)
        pve = svc.proxmox
        t0 = time.time()
        version_info = pve.version.get()
        latency_ms = round((time.time() - t0) * 1000)
        response = {
            "host_id": host_id,
            "version": version_info.get("version", "unknown"),
            "release": version_info.get("release", ""),
            "repoid": version_info.get("repoid", ""),
            "latency_ms": latency_ms,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        }
        pve_cache.set(cache_key, response, ttl=300)
        return response
    except Exception as e:
        logger.warning(f"Failed to fetch version for host {host_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Could not reach host: {str(e)}")


@router.post("/{host_id}/reconnect")
async def reconnect_proxmox_host(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Re-test connectivity and clear all per-host caches so the next poll
    picks up fresh data. Returns the same payload as the /test endpoint
    plus the live version string.
    """
    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    # Bust caches
    for key in (
        f"proxmox:version:{host_id}",
        f"datacenter:summary:{host_id}",
        "federation:summary",
    ):
        pve_cache.delete(key) if hasattr(pve_cache, "delete") else None

    try:
        svc = ProxmoxService(host)
        t0 = time.time()
        ok = svc.test_connection()
        latency_ms = round((time.time() - t0) * 1000)

        version = None
        try:
            version_info = svc.proxmox.version.get()
            version = version_info.get("version", "unknown")
        except Exception:
            pass

        if ok:
            return {
                "status": "success",
                "message": "Connection successful",
                "latency_ms": latency_ms,
                "version": version,
            }
        else:
            return {"status": "error", "message": "Connection test failed", "latency_ms": latency_ms}
    except Exception as e:
        return {"status": "error", "message": str(e), "latency_ms": None}


@router.get("/{host_id}/datacenter/summary")
async def get_datacenter_summary(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Aggregate datacenter summary for a single Proxmox host.
    Returns VMs, nodes, storage, compute totals and recent tasks.
    Cached for 30 seconds.
    """
    cache_key = f"datacenter:summary:{host_id}"
    cached = pve_cache.get(cache_key)
    if cached is not None:
        return cached

    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    try:
        from app.services.proxmox import ProxmoxService
        svc = ProxmoxService(host)
        pve = svc.proxmox

        # Pull all cluster resources in one call
        resources = pve.cluster.resources.get()

        vms_running = 0
        vms_stopped = 0
        vms_paused = 0
        lxc_running = 0
        lxc_stopped = 0
        nodes_online = 0
        nodes_offline = 0
        total_cpu_cores = 0
        total_ram = 0
        cpu_usages = []
        mem_usages = []
        storages = []
        node_vm_map = {}  # node_name -> {vms, lxcs}

        for r in resources:
            rtype = r.get("type", "")
            node_name = r.get("node", "")

            if rtype == "qemu":
                status = r.get("status", "stopped")
                if status == "running":
                    vms_running += 1
                elif status == "paused":
                    vms_paused += 1
                else:
                    vms_stopped += 1
                # node->vm mapping
                if node_name not in node_vm_map:
                    node_vm_map[node_name] = {"vms": 0, "lxcs": 0, "name": node_name}
                node_vm_map[node_name]["vms"] += 1

            elif rtype == "lxc":
                status = r.get("status", "stopped")
                if status == "running":
                    lxc_running += 1
                else:
                    lxc_stopped += 1
                if node_name not in node_vm_map:
                    node_vm_map[node_name] = {"vms": 0, "lxcs": 0, "name": node_name}
                node_vm_map[node_name]["lxcs"] += 1

            elif rtype == "node":
                status = r.get("status", "unknown")
                if status == "online":
                    nodes_online += 1
                else:
                    nodes_offline += 1
                total_cpu_cores += r.get("maxcpu", 0) or 0
                total_ram += r.get("maxmem", 0) or 0
                cpu_val = r.get("cpu")
                if cpu_val is not None:
                    cpu_usages.append(float(cpu_val))
                mem_val = r.get("mem")
                max_mem = r.get("maxmem")
                if mem_val and max_mem:
                    mem_usages.append(float(mem_val) / float(max_mem))

            elif rtype == "storage":
                storages.append({
                    "storage": r.get("storage", ""),
                    "node": node_name,
                    "type": r.get("plugintype", ""),
                    "total": r.get("maxdisk", 0) or 0,
                    "used": r.get("disk", 0) or 0,
                    "shared": bool(r.get("shared", 0)),
                    "content": r.get("content", ""),
                })

        avg_cpu_pct = round((sum(cpu_usages) / len(cpu_usages)) * 100, 1) if cpu_usages else 0.0
        avg_mem_pct = round((sum(mem_usages) / len(mem_usages)) * 100, 1) if mem_usages else 0.0

        # Cluster efficiency score: average of (1 - avg_cpu_slack) and (1 - avg_mem_slack)
        # Score 0-100: higher means resources are being used efficiently
        efficiency_score = round((avg_cpu_pct + avg_mem_pct) / 2, 1)

        # Recent tasks — fetch from all known nodes
        node_names = list(node_vm_map.keys())
        recent_tasks = []
        for node_name in node_names[:5]:  # limit to 5 nodes max
            try:
                tasks = pve.nodes(node_name).tasks.get(limit=3)
                for t in tasks:
                    recent_tasks.append({
                        "node": node_name,
                        "upid": t.get("upid", ""),
                        "type": t.get("type", ""),
                        "user": t.get("user", ""),
                        "status": t.get("status", ""),
                        "starttime": t.get("starttime"),
                        "endtime": t.get("endtime"),
                        "id": t.get("id", ""),
                    })
            except Exception:
                pass

        # Sort by starttime descending, keep top 5
        recent_tasks.sort(key=lambda x: x.get("starttime") or 0, reverse=True)
        recent_tasks = recent_tasks[:5]

        # Fetch actual cluster name from PVE cluster status
        cluster_name = None
        try:
            cluster_status = pve.cluster.status.get()
            for item in cluster_status:
                if item.get("type") == "cluster":
                    cluster_name = item.get("name")
                    break
        except Exception:
            pass

        # Seed ALL type=node resources first so every node appears even with 0 guests
        for r in resources:
            if r.get("type") == "node":
                n = r.get("node", "")
                if n and n not in node_vm_map:
                    node_vm_map[n] = {"vms": 0, "lxcs": 0, "name": n,
                                      "cpu_pct": round(float(r.get("cpu", 0) or 0) * 100, 1),
                                      "mem_pct": round((float(r.get("mem", 0) or 0) / float(r.get("maxmem", 1) or 1)) * 100, 1),
                                      "status": r.get("status", "unknown")}

        # Node VM distribution
        node_distribution = list(node_vm_map.values())
        total_guests = sum(n["vms"] + n["lxcs"] for n in node_distribution)
        # Flag imbalanced nodes (>80% of cluster's guests)
        for nd in node_distribution:
            nd["guest_count"] = nd["vms"] + nd["lxcs"]
            nd["imbalanced"] = (
                len(node_distribution) > 1 and
                total_guests > 0 and
                (nd["guest_count"] / total_guests) > 0.8
            )

        response = {
            "host_id": host_id,
            "host_name": host.name,
            "cluster_name": cluster_name,
            # VM / LXC counts
            "vms_total": vms_running + vms_stopped + vms_paused,
            "vms_running": vms_running,
            "vms_stopped": vms_stopped,
            "vms_paused": vms_paused,
            "lxc_total": lxc_running + lxc_stopped,
            "lxc_running": lxc_running,
            "lxc_stopped": lxc_stopped,
            # Nodes
            "nodes_online": nodes_online,
            "nodes_offline": nodes_offline,
            "nodes_total": nodes_online + nodes_offline,
            # Compute
            "total_cpu_cores": total_cpu_cores,
            "total_ram_bytes": total_ram,
            "avg_cpu_pct": avg_cpu_pct,
            "avg_mem_pct": avg_mem_pct,
            "efficiency_score": efficiency_score,
            # Storage
            "storages": storages,
            "storage_total_bytes": sum(s["total"] for s in storages),
            "storage_used_bytes": sum(s["used"] for s in storages),
            # Node distribution
            "node_distribution": node_distribution,
            # Recent activity
            "recent_tasks": recent_tasks,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        }

        pve_cache.set(cache_key, response, ttl=30)
        return response

    except Exception as e:
        logger.error(f"Failed to get datacenter summary for host {host_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch datacenter summary: {str(e)}")
