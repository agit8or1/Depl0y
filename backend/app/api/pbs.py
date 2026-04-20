"""Proxmox Backup Server (PBS) API routes."""
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import encrypt_data, decrypt_data
from app.api.auth import get_current_user, require_admin, require_operator
from app.models.database import PBSServer, User
from app.services.idrac import RedfishClient
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_ssh_creds(server: PBSServer) -> tuple[str, str, str]:
    """Return (hostname, username, password) for SSH to a PBS server's BMC.

    One IP per BMC: the `idrac_hostname` + `idrac_*` credentials handle
    both Redfish (HTTPS) and SSH.
    """
    if not server.idrac_hostname or not server.idrac_username or not server.idrac_password:
        raise HTTPException(status_code=400, detail="BMC credentials not configured")
    pw = decrypt_data(server.idrac_password)
    return server.idrac_hostname, server.idrac_username, pw


# ─────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────

class PBSServerCreate(BaseModel):
    name: str
    hostname: str
    port: int = 8007
    username: Optional[str] = 'root@pam'
    password: Optional[str] = None
    api_token_id: Optional[str] = None
    api_token_secret: Optional[str] = None
    verify_ssl: bool = False
    # iDRAC / iLO
    idrac_hostname: Optional[str] = None
    idrac_port: Optional[int] = 443
    idrac_username: Optional[str] = None
    idrac_password: Optional[str] = None
    idrac_type: Optional[str] = None
    idrac_use_ssh: Optional[bool] = False


class PBSServerUpdate(BaseModel):
    name: Optional[str] = None
    hostname: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_token_id: Optional[str] = None
    api_token_secret: Optional[str] = None
    verify_ssl: Optional[bool] = None
    is_active: Optional[bool] = None
    # iDRAC / iLO
    idrac_hostname: Optional[str] = None
    idrac_port: Optional[int] = None
    idrac_username: Optional[str] = None
    idrac_password: Optional[str] = None
    idrac_type: Optional[str] = None
    idrac_use_ssh: Optional[bool] = None


class PBSServerResponse(BaseModel):
    id: int
    name: str
    hostname: str
    port: int
    username: str
    verify_ssl: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    api_token_id: Optional[str] = None
    idrac_hostname: Optional[str] = None
    idrac_port: Optional[int] = None
    idrac_username: Optional[str] = None
    idrac_type: Optional[str] = None
    idrac_use_ssh: Optional[bool] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────
# CRUD helpers
# ─────────────────────────────────────────────────────────────

def _get_or_404(db: Session, server_id: int) -> PBSServer:
    s = db.query(PBSServer).filter(PBSServer.id == server_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="PBS server not found")
    return s


def _build_client(server: PBSServer) -> RedfishClient:
    if not server.idrac_hostname:
        raise HTTPException(status_code=400, detail="No iDRAC/iLO configured for this PBS server")
    if not server.idrac_username or not server.idrac_password:
        raise HTTPException(status_code=400, detail="iDRAC/iLO credentials not configured")
    try:
        password = decrypt_data(server.idrac_password)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decrypt iDRAC/iLO password")
    return RedfishClient(
        hostname=server.idrac_hostname,
        username=server.idrac_username,
        password=password,
        port=server.idrac_port or 443,
        bmc_type=server.idrac_type or "idrac",
    )


# ─────────────────────────────────────────────────────────────
# CRUD endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/", response_model=list[PBSServerResponse])
def list_pbs_servers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(PBSServer).order_by(PBSServer.name).all()


@router.post("/", response_model=PBSServerResponse)
def create_pbs_server(
    data: PBSServerCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(PBSServer).filter(PBSServer.name == data.name).first():
        raise HTTPException(status_code=400, detail="A PBS server with this name already exists")

    server = PBSServer(
        name=data.name,
        hostname=data.hostname,
        port=data.port,
        username=data.username or 'root@pam',
        verify_ssl=data.verify_ssl,
        api_token_id=data.api_token_id,
        idrac_hostname=data.idrac_hostname,
        idrac_port=data.idrac_port,
        idrac_username=data.idrac_username,
        idrac_type=data.idrac_type,
    )
    if data.password:
        server.password = encrypt_data(data.password)
    if data.api_token_secret:
        server.api_token_secret = encrypt_data(data.api_token_secret)
    if data.idrac_password:
        server.idrac_password = encrypt_data(data.idrac_password)

    db.add(server)
    db.commit()
    db.refresh(server)
    return server


@router.get("/{server_id}", response_model=PBSServerResponse)
def get_pbs_server(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_or_404(db, server_id)


@router.put("/{server_id}", response_model=PBSServerResponse)
def update_pbs_server(
    server_id: int,
    data: PBSServerUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    server = _get_or_404(db, server_id)

    for field in ("name", "hostname", "port", "username", "verify_ssl", "is_active",
                  "api_token_id", "idrac_hostname", "idrac_port", "idrac_username", "idrac_type", "idrac_use_ssh"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(server, field, val)

    if data.password is not None:
        server.password = encrypt_data(data.password) if data.password else None
    if data.api_token_secret is not None:
        server.api_token_secret = encrypt_data(data.api_token_secret) if data.api_token_secret else None
    if data.idrac_password is not None:
        server.idrac_password = encrypt_data(data.idrac_password) if data.idrac_password else None

    db.commit()
    db.refresh(server)
    return server


@router.delete("/{server_id}")
def delete_pbs_server(
    server_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    server = _get_or_404(db, server_id)
    db.delete(server)
    db.commit()
    return {"message": "PBS server deleted"}


# ─────────────────────────────────────────────────────────────
# iDRAC / iLO sub-endpoints for PBS servers
# ─────────────────────────────────────────────────────────────

@router.get("/{server_id}/idrac/test")
def test_pbs_idrac(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try:
        success = client.test_connection()
        if success:
            return {"status": "success", "message": f"Connected to {server.idrac_type or 'BMC'} successfully"}
        return {"status": "error", "message": "Connection established but Redfish response invalid"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/{server_id}/idrac/info")
def get_pbs_idrac_info(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try:
        return client.get_system_info()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{server_id}/idrac/power")
def get_pbs_power_state(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try:
        state = client.get_power_state()
        return {"server_id": server_id, "power_state": state}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.post("/{server_id}/idrac/power/{action}")
def pbs_power_action(
    server_id: int,
    action: str = Path(...),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    valid_actions = ("on", "off", "graceful_off", "reset", "graceful_reset", "pxe")
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action '{action}'")
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try:
        result = client.power_action(action)
        return {"status": "success", "action": action, "result": result}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{server_id}/idrac/logs")
def get_pbs_event_log(
    server_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try:
        entries = client.get_event_log(limit=limit)
        return {"server_id": server_id, "entries": entries}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{server_id}/idrac/thermal")
def get_pbs_thermal(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try:
        return client.get_thermal()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{server_id}/idrac/power-usage")
def get_pbs_power_usage(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try:
        return client.get_power_usage()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{server_id}/idrac/manager")
def get_pbs_manager_info(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try: return client.get_manager_info()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/{server_id}/idrac/network")
def get_pbs_network(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try: return client.get_network_interfaces()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.patch("/{server_id}/idrac/network/{iface_id}")
def patch_pbs_network(server_id: int, iface_id: str, config: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try: return client.patch_network_interface(iface_id, config)
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/{server_id}/idrac/processors")
def get_pbs_processors(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try: return client.get_processors()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/{server_id}/idrac/memory")
def get_pbs_memory(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try: return client.get_memory_modules()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/{server_id}/idrac/storage")
def get_pbs_storage(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try: return client.get_storage()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/{server_id}/idrac/firmware")
def get_pbs_firmware(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try: return client.get_firmware_inventory()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/{server_id}/idrac/sensors")
def get_pbs_sensors(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return unified IPMI-style sensor table for a PBS server's BMC."""
    server = _get_or_404(db, server_id)
    client = _build_client(server)
    try: return client.get_sensors()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.post("/{server_id}/idrac/ssh/update")
def run_pbs_ssh_update(server_id: int, current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    host, user, pw = _get_ssh_creds(server)
    try:
        from app.services.ssh_hw import run_system_update
        return run_system_update(host, user, pw)
    except Exception as e: raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")

@router.get("/{server_id}/idrac/ssh/test")
def test_pbs_ssh(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    try: host, user, pw = _get_ssh_creds(server)
    except HTTPException as e: return {"status": "error", "message": e.detail}
    try:
        from app.services.ssh_hw import test_ssh
        test_ssh(host, user, pw)
        return {"status": "success", "message": f"SSH connection to {host} successful"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/{server_id}/idrac/ssh/hardware")
def get_pbs_ssh_hardware(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    host, user, pw = _get_ssh_creds(server)
    try:
        from app.services.ssh_hw import get_hardware_info
        return get_hardware_info(host, user, pw)
    except Exception as e:
        # SSH may not be usable on some BMCs (iDRAC CLI doesn't run Linux
        # commands). Return empty shape so the frontend falls back to Redfish
        # cleanly instead of erroring.
        logger.info(f"SSH hardware unavailable for pbs:{server_id} ({host}): {e}")
        return {"processors": [], "modules": [], "controllers": [], "system": {},
                "max_temp_c": None, "consumed_watts": None, "raid_arrays": [],
                "_ssh_error": str(e)}

@router.get("/{server_id}/idrac/ssh/network")
def get_pbs_ssh_network(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    host, user, pw = _get_ssh_creds(server)
    try:
        from app.services.ssh_hw import get_network_info
        return get_network_info(host, user, pw)
    except Exception as e: raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")

@router.get("/{server_id}/idrac/ssh/firmware")
def get_pbs_ssh_firmware(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    host, user, pw = _get_ssh_creds(server)
    try:
        from app.services.ssh_hw import get_firmware_info
        return get_firmware_info(host, user, pw)
    except Exception as e: raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")

@router.get("/{server_id}/idrac/ssh/logs")
def get_pbs_ssh_logs(server_id: int, limit: int = 100, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = _get_or_404(db, server_id)
    host, user, pw = _get_ssh_creds(server)
    try:
        from app.services.ssh_hw import get_log_entries
        return get_log_entries(host, user, pw, limit=limit)
    except Exception as e:
        logger.info(f"SSH logs unavailable for pbs:{server_id} ({host}): {e}")
        return {"entries": [], "_ssh_error": str(e)}
