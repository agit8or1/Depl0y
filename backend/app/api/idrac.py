"""iDRAC / iLO out-of-band management API routes."""
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import encrypt_data, decrypt_data
from app.api.auth import get_current_user, require_admin, require_operator
from app.models.database import ProxmoxHost, StandaloneBMC, User
from app.services.idrac import RedfishClient
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# ─────────────────────────────────────────────────────────────
# BMC status cache (updated by scheduler every 2 min)
# ─────────────────────────────────────────────────────────────
# Keys: "pve:{id}", "pbs:{id}", "standalone:{id}"
bmc_status_cache: dict = {}


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────

class StandaloneBMCCreate(BaseModel):
    name: str
    description: Optional[str] = None
    idrac_hostname: str
    idrac_port: int = 443
    idrac_username: str
    idrac_password: str
    idrac_type: str = "idrac"
    idrac_use_ssh: bool = False


class StandaloneBMCUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    idrac_hostname: Optional[str] = None
    idrac_port: Optional[int] = None
    idrac_username: Optional[str] = None
    idrac_password: Optional[str] = None
    idrac_type: Optional[str] = None
    idrac_use_ssh: Optional[bool] = None
    is_active: Optional[bool] = None


class StandaloneBMCResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    idrac_hostname: str
    idrac_port: int
    idrac_username: str
    idrac_type: str
    idrac_use_ssh: Optional[bool] = False
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _get_host_or_404(db: Session, host_id: int) -> ProxmoxHost:
    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")
    return host


def _build_client_from_obj(obj) -> RedfishClient:
    """Build a RedfishClient from any object with idrac_* fields."""
    if not getattr(obj, "idrac_hostname", None):
        raise HTTPException(status_code=400, detail="No iDRAC/iLO configured")
    if not obj.idrac_username or not obj.idrac_password:
        raise HTTPException(status_code=400, detail="iDRAC/iLO credentials not configured")
    try:
        password = decrypt_data(obj.idrac_password)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decrypt iDRAC/iLO password")
    return RedfishClient(
        hostname=obj.idrac_hostname,
        username=obj.idrac_username,
        password=password,
        port=obj.idrac_port or 443,
        bmc_type=obj.idrac_type or "idrac",
    )


def _build_client(host: ProxmoxHost) -> RedfishClient:
    return _build_client_from_obj(host)


# ─────────────────────────────────────────────────────────────
# BMC status cache endpoint
# ─────────────────────────────────────────────────────────────

@router.get("/status")
def get_bmc_status(current_user: User = Depends(get_current_user)):
    """Return cached BMC status for all servers (updated by scheduler)."""
    return bmc_status_cache


@router.post("/poll")
def trigger_bmc_poll(current_user: User = Depends(get_current_user)):
    """Trigger an immediate BMC poll and return the updated cache."""
    from app.services.scheduler import run_bmc_poll
    run_bmc_poll()
    return bmc_status_cache


# ─────────────────────────────────────────────────────────────
# Proxmox host iDRAC endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/{host_id}/test")
def test_idrac_connection(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        success = client.test_connection()
        if success:
            return {"status": "success", "message": f"Connected to {host.idrac_type or 'BMC'} successfully"}
        return {"status": "error", "message": "Connection established but Redfish response invalid"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/{host_id}/info")
def get_server_info(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        return client.get_system_info()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{host_id}/power")
def get_power_state(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        state = client.get_power_state()
        return {"host_id": host_id, "power_state": state}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.post("/{host_id}/power/{action}")
def power_action(
    host_id: int,
    action: str = Path(...),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    valid_actions = ("on", "off", "graceful_off", "reset", "graceful_reset", "power_cycle", "pxe")
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action '{action}'")
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        result = client.power_action(action)
        logger.info(f"Power action '{action}' on host {host_id} by {current_user.username}")
        return {"status": "success", "action": action, "result": result}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{host_id}/logs")
def get_event_log(
    host_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        entries = client.get_event_log(limit=limit)
        return {"host_id": host_id, "entries": entries}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{host_id}/thermal")
def get_thermal(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        return client.get_thermal()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{host_id}/power-usage")
def get_power_usage(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        return client.get_power_usage()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{host_id}/manager")
def get_manager_info(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        return client.get_manager_info()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{host_id}/network")
def get_network_interfaces(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        return client.get_network_interfaces()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.patch("/{host_id}/network/{iface_id}")
def patch_network_interface(
    host_id: int,
    iface_id: str,
    config: dict,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        return client.patch_network_interface(iface_id, config)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{host_id}/processors")
def get_processors(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        return client.get_processors()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{host_id}/memory")
def get_memory_modules(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        return client.get_memory_modules()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{host_id}/storage")
def get_storage(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        return client.get_storage()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{host_id}/firmware")
def get_firmware_inventory(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        return client.get_firmware_inventory()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/{host_id}/sensors")
def get_sensors(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return unified IPMI-style sensor table (temperatures, fans, voltages, PSUs)."""
    host = _get_host_or_404(db, host_id)
    client = _build_client(host)
    try:
        return client.get_sensors()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


# ─────────────────────────────────────────────────────────────
# SSH-based hardware / network (host OS, not BMC)
# ─────────────────────────────────────────────────────────────

def _get_ssh_creds(obj, hostname_attr: str = "hostname"):
    """Extract SSH hostname + decrypted credentials from a host object."""
    ssh_host = getattr(obj, hostname_attr, None)
    if not ssh_host:
        raise HTTPException(status_code=400, detail="No hostname configured for SSH")
    if not getattr(obj, "idrac_username", None) or not getattr(obj, "idrac_password", None):
        raise HTTPException(status_code=400, detail="iDRAC credentials not configured (used for SSH)")
    try:
        password = decrypt_data(obj.idrac_password)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decrypt credentials")
    return ssh_host, obj.idrac_username, password


@router.post("/{host_id}/ssh/update")
def run_ssh_update(host_id: int, current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    host = _get_host_or_404(db, host_id)
    ssh_host, username, password = _get_ssh_creds(host, "hostname")
    try:
        from app.services.ssh_hw import run_system_update
        return run_system_update(ssh_host, username, password)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")

@router.post("/standalone/{bmc_id}/ssh/update")
def run_standalone_ssh_update(bmc_id: int, current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    ssh_host, username, password = _get_ssh_creds(bmc, "idrac_hostname")
    try:
        from app.services.ssh_hw import run_system_update
        return run_system_update(ssh_host, username, password)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")

@router.get("/{host_id}/ssh/test")
def test_ssh_connection(host_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    host = _get_host_or_404(db, host_id)
    ssh_host, username, password = _get_ssh_creds(host, "hostname")
    try:
        from app.services.ssh_hw import test_ssh
        test_ssh(ssh_host, username, password)
        return {"status": "success", "message": f"SSH connection to {ssh_host} successful"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/{host_id}/ssh/hardware")
def get_ssh_hardware(
    host_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    host = _get_host_or_404(db, host_id)
    ssh_host, username, password = _get_ssh_creds(host, "hostname")
    try:
        from app.services.ssh_hw import get_hardware_info
        return get_hardware_info(ssh_host, username, password)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")


@router.get("/{host_id}/ssh/network")
def get_ssh_network(host_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    host = _get_host_or_404(db, host_id)
    ssh_host, username, password = _get_ssh_creds(host, "hostname")
    try:
        from app.services.ssh_hw import get_network_info
        return get_network_info(ssh_host, username, password)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")

@router.get("/{host_id}/ssh/firmware")
def get_ssh_firmware(host_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    host = _get_host_or_404(db, host_id)
    ssh_host, username, password = _get_ssh_creds(host, "hostname")
    try:
        from app.services.ssh_hw import get_firmware_info
        return get_firmware_info(ssh_host, username, password)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")

@router.get("/{host_id}/ssh/logs")
def get_ssh_logs(host_id: int, limit: int = 100, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    host = _get_host_or_404(db, host_id)
    ssh_host, username, password = _get_ssh_creds(host, "hostname")
    try:
        from app.services.ssh_hw import get_log_entries
        return get_log_entries(ssh_host, username, password, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")


# ─────────────────────────────────────────────────────────────
# Standalone BMC CRUD
# ─────────────────────────────────────────────────────────────

@router.get("/standalone/", response_model=list[StandaloneBMCResponse])
def list_standalone_bmc(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(StandaloneBMC).order_by(StandaloneBMC.name).all()


@router.post("/standalone/", response_model=StandaloneBMCResponse)
def create_standalone_bmc(
    data: StandaloneBMCCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(StandaloneBMC).filter(StandaloneBMC.name == data.name).first():
        raise HTTPException(status_code=400, detail="A BMC entry with this name already exists")
    if data.idrac_type not in ("idrac", "ilo"):
        raise HTTPException(status_code=400, detail="idrac_type must be 'idrac' or 'ilo'")
    bmc = StandaloneBMC(
        name=data.name,
        description=data.description,
        idrac_hostname=data.idrac_hostname,
        idrac_port=data.idrac_port,
        idrac_username=data.idrac_username,
        idrac_password=encrypt_data(data.idrac_password),
        idrac_type=data.idrac_type,
        idrac_use_ssh=data.idrac_use_ssh,
    )
    db.add(bmc)
    db.commit()
    db.refresh(bmc)
    return bmc


@router.get("/standalone/{bmc_id}", response_model=StandaloneBMCResponse)
def get_standalone_bmc(
    bmc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc:
        raise HTTPException(status_code=404, detail="Standalone BMC not found")
    return bmc


@router.put("/standalone/{bmc_id}", response_model=StandaloneBMCResponse)
def update_standalone_bmc(
    bmc_id: int,
    data: StandaloneBMCUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc:
        raise HTTPException(status_code=404, detail="Standalone BMC not found")
    for field in ("name", "description", "idrac_hostname", "idrac_port", "idrac_username", "idrac_type", "is_active"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(bmc, field, val)
    if data.idrac_use_ssh is not None:
        bmc.idrac_use_ssh = data.idrac_use_ssh
    if data.idrac_password:
        bmc.idrac_password = encrypt_data(data.idrac_password)
    db.commit()
    db.refresh(bmc)
    return bmc


@router.delete("/standalone/{bmc_id}")
def delete_standalone_bmc(
    bmc_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc:
        raise HTTPException(status_code=404, detail="Standalone BMC not found")
    db.delete(bmc)
    db.commit()
    bmc_status_cache.pop(f"standalone:{bmc_id}", None)
    return {"message": "Standalone BMC deleted"}


@router.get("/standalone/{bmc_id}/test")
def test_standalone_bmc(
    bmc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc:
        raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try:
        success = client.test_connection()
        if success:
            return {"status": "success", "message": f"Connected to {bmc.idrac_type} successfully"}
        return {"status": "error", "message": "Connection established but Redfish response invalid"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/standalone/{bmc_id}/info")
def get_standalone_info(
    bmc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc:
        raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try:
        return client.get_system_info()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.post("/standalone/{bmc_id}/power/{action}")
def standalone_power_action(
    bmc_id: int,
    action: str = Path(...),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    valid_actions = ("on", "off", "graceful_off", "reset", "graceful_reset", "power_cycle", "pxe")
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action '{action}'")
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc:
        raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try:
        result = client.power_action(action)
        return {"status": "success", "action": action, "result": result}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/standalone/{bmc_id}/logs")
def get_standalone_logs(
    bmc_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc:
        raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try:
        entries = client.get_event_log(limit=limit)
        return {"bmc_id": bmc_id, "entries": entries}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/standalone/{bmc_id}/thermal")
def get_standalone_thermal(
    bmc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc:
        raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try:
        return client.get_thermal()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/standalone/{bmc_id}/power-usage")
def get_standalone_power_usage(
    bmc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc:
        raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try:
        return client.get_power_usage()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")


@router.get("/standalone/{bmc_id}/manager")
def get_standalone_manager(bmc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try: return client.get_manager_info()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/standalone/{bmc_id}/network")
def get_standalone_network(bmc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try: return client.get_network_interfaces()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.patch("/standalone/{bmc_id}/network/{iface_id}")
def patch_standalone_network(bmc_id: int, iface_id: str, config: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try: return client.patch_network_interface(iface_id, config)
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/standalone/{bmc_id}/processors")
def get_standalone_processors(bmc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try: return client.get_processors()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/standalone/{bmc_id}/memory")
def get_standalone_memory(bmc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try: return client.get_memory_modules()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/standalone/{bmc_id}/storage")
def get_standalone_storage(bmc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try: return client.get_storage()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/standalone/{bmc_id}/firmware")
def get_standalone_firmware(bmc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try: return client.get_firmware_inventory()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/standalone/{bmc_id}/sensors")
def get_standalone_sensors(bmc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return unified IPMI-style sensor table for a standalone BMC."""
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    client = _build_client_from_obj(bmc)
    try: return client.get_sensors()
    except Exception as e: raise HTTPException(status_code=502, detail=f"Redfish error: {str(e)}")

@router.get("/standalone/{bmc_id}/ssh/test")
def test_standalone_ssh(bmc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    ssh_host, username, password = _get_ssh_creds(bmc, "idrac_hostname")
    try:
        from app.services.ssh_hw import test_ssh
        test_ssh(ssh_host, username, password)
        return {"status": "success", "message": f"SSH connection to {ssh_host} successful"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/standalone/{bmc_id}/ssh/hardware")
def get_standalone_ssh_hardware(bmc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    ssh_host, username, password = _get_ssh_creds(bmc, "idrac_hostname")
    try:
        from app.services.ssh_hw import get_hardware_info
        return get_hardware_info(ssh_host, username, password)
    except Exception as e: raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")

@router.get("/standalone/{bmc_id}/ssh/network")
def get_standalone_ssh_network(bmc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    ssh_host, username, password = _get_ssh_creds(bmc, "idrac_hostname")
    try:
        from app.services.ssh_hw import get_network_info
        return get_network_info(ssh_host, username, password)
    except Exception as e: raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")

@router.get("/standalone/{bmc_id}/ssh/firmware")
def get_standalone_ssh_firmware(bmc_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    ssh_host, username, password = _get_ssh_creds(bmc, "idrac_hostname")
    try:
        from app.services.ssh_hw import get_firmware_info
        return get_firmware_info(ssh_host, username, password)
    except Exception as e: raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")

@router.get("/standalone/{bmc_id}/ssh/logs")
def get_standalone_ssh_logs(bmc_id: int, limit: int = 100, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bmc = db.query(StandaloneBMC).filter(StandaloneBMC.id == bmc_id).first()
    if not bmc: raise HTTPException(status_code=404, detail="Standalone BMC not found")
    ssh_host, username, password = _get_ssh_creds(bmc, "idrac_hostname")
    try:
        from app.services.ssh_hw import get_log_entries
        return get_log_entries(ssh_host, username, password, limit=limit)
    except Exception as e: raise HTTPException(status_code=502, detail=f"SSH error: {str(e)}")
