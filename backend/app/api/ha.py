"""High Availability API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.api.auth import get_current_user, require_admin
from app.core.database import get_db
from sqlalchemy.orm import Session
import logging
import subprocess

logger = logging.getLogger(__name__)

router = APIRouter()


class HAEnableRequest(BaseModel):
    proxmox_password: str


@router.get("/status")
def check_ha_status(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Check if High Availability is enabled on Proxmox cluster"""
    try:
        from app.models import ProxmoxHost
        import json

        # Get first Proxmox host to check HA status
        host = db.query(ProxmoxHost).first()
        if not host:
            return {
                "enabled": False,
                "protected_vms": 0,
                "manager_status": "unknown",
                "quorum": False,
                "message": "No Proxmox hosts configured"
            }

        # Check if HA is enabled using pvesh
        ssh_host = f"root@{host.hostname}"
        check_ha = f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} 'pvesh get /cluster/ha/status/manager_status --output-format json 2>/dev/null'"

        result = subprocess.run(check_ha, shell=True, capture_output=True, timeout=10, text=True)

        manager_status = "unknown"
        quorum = False
        protected_vms = 0

        if result.returncode == 0 and result.stdout:
            try:
                ha_data = json.loads(result.stdout)

                # Parse quorum status
                if "quorum" in ha_data and isinstance(ha_data["quorum"], dict):
                    quorum = ha_data["quorum"].get("quorate") == "1"

                # Parse manager status
                if "manager_status" in ha_data and isinstance(ha_data["manager_status"], dict):
                    node_status = ha_data["manager_status"].get("node_status", {})
                    if node_status:
                        # Get first node's status
                        first_node = next(iter(node_status.values()), {})
                        manager_status = first_node.get("state", "unknown")
                    else:
                        manager_status = "active"

                # Get number of protected resources
                get_resources = f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} 'pvesh get /cluster/ha/resources --output-format json 2>/dev/null'"
                resources_result = subprocess.run(get_resources, shell=True, capture_output=True, timeout=10, text=True)

                if resources_result.returncode == 0:
                    try:
                        resources = json.loads(resources_result.stdout)
                        protected_vms = len(resources) if isinstance(resources, list) else 0
                    except:
                        pass

                return {
                    "enabled": True,
                    "protected_vms": protected_vms,
                    "manager_status": manager_status,
                    "quorum": quorum,
                    "message": "High Availability is enabled"
                }
            except json.JSONDecodeError:
                logger.error(f"Failed to parse HA status JSON: {result.stdout}")

        return {
            "enabled": False,
            "protected_vms": 0,
            "manager_status": "unknown",
            "quorum": False,
            "message": "High Availability not configured"
        }

    except Exception as e:
        logger.error(f"Failed to check HA status: {e}")
        return {
            "enabled": False,
            "protected_vms": 0,
            "manager_status": "unknown",
            "quorum": False,
            "message": "Failed to check HA status"
        }


@router.post("/enable")
def enable_ha(
    request: HAEnableRequest,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Enable High Availability on Proxmox cluster"""
    try:
        from app.models import ProxmoxHost

        host = db.query(ProxmoxHost).first()
        if not host:
            raise HTTPException(status_code=400, detail="No Proxmox hosts configured")

        ssh_host = f"root@{host.hostname}"
        logger.info(f"Enabling HA on {ssh_host}")

        # Enable HA Manager
        # This requires the cluster to have a quorum
        enable_script = f"""
ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} '
# Check if cluster has quorum
if ! pvesh get /cluster/status 2>/dev/null | grep -q "quorate.*1"; then
    echo "ERROR: Cluster does not have quorum. HA requires a multi-node cluster with quorum."
    exit 1
fi

# HA Manager is usually enabled by default if cluster exists
# Just verify it is running
if ! systemctl is-active --quiet pve-ha-lrm && ! systemctl is-active --quiet pve-ha-crm; then
    echo "Starting HA services..."
    systemctl start pve-ha-lrm
    systemctl start pve-ha-crm
    systemctl enable pve-ha-lrm
    systemctl enable pve-ha-crm
fi

echo "HA services are running"
'
"""

        result = subprocess.run(enable_script, shell=True, capture_output=True, timeout=30)

        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else result.stdout.decode()
            if "does not have quorum" in error_msg or "quorate" in error_msg:
                raise HTTPException(
                    status_code=400,
                    detail="High Availability requires a multi-node Proxmox cluster with quorum. Single-node setups cannot use HA."
                )
            raise HTTPException(status_code=500, detail=f"Failed to enable HA: {error_msg}")

        logger.info("HA enabled successfully")
        return {
            "success": True,
            "message": "High Availability enabled successfully. You can now add VMs to HA groups via the Proxmox web interface."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable HA: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enable HA: {str(e)}")


@router.get("/groups")
def list_ha_groups(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List HA groups (migrated to rules in Proxmox 8+)"""
    try:
        from app.models import ProxmoxHost

        host = db.query(ProxmoxHost).first()
        if not host:
            return {"groups": [], "message": "No Proxmox hosts configured"}

        ssh_host = f"root@{host.hostname}"

        # Get HA groups - handle migration to rules
        get_groups = f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} 'pvesh get /cluster/ha/groups --output-format json 2>&1'"
        result = subprocess.run(get_groups, shell=True, capture_output=True, timeout=10, text=True)

        # Check if groups migrated to rules (Proxmox 8+)
        if "migrated to rules" in result.stderr or "migrated to rules" in result.stdout:
            return {
                "groups": [],
                "message": "HA groups migrated to rules in Proxmox 8+. Manage via Proxmox web interface."
            }

        if result.returncode == 0:
            import json
            try:
                groups = json.loads(result.stdout)
                return {"groups": groups if isinstance(groups, list) else []}
            except:
                return {"groups": []}
        else:
            return {"groups": [], "message": "HA groups not configured"}

    except Exception as e:
        logger.error(f"Failed to list HA groups: {e}")
        return {"groups": [], "error": str(e)}


@router.post("/disable")
def disable_ha(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Disable High Availability (note: this just stops the services, VMs remain in HA config)"""
    try:
        from app.models import ProxmoxHost

        host = db.query(ProxmoxHost).first()
        if not host:
            raise HTTPException(status_code=400, detail="No Proxmox hosts configured")

        ssh_host = f"root@{host.hostname}"

        # Stop HA services
        disable_script = f"""
ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} '
systemctl stop pve-ha-lrm
systemctl stop pve-ha-crm
systemctl disable pve-ha-lrm
systemctl disable pve-ha-crm
echo "HA services stopped"
'
"""

        result = subprocess.run(disable_script, shell=True, capture_output=True, timeout=30)

        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else "Unknown error"
            raise HTTPException(status_code=500, detail=f"Failed to disable HA: {error_msg}")

        return {
            "success": True,
            "message": "HA services disabled. VMs remain in HA configuration but will not be automatically restarted."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable HA: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disable HA: {str(e)}")


class HAGroupCreate(BaseModel):
    group: str
    nodes: str  # Comma-separated list of nodes
    restricted: int = 0  # 0 or 1
    nofailback: int = 0  # 0 or 1
    comment: str = None


@router.post("/groups")
def create_ha_group(
    request: HAGroupCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new HA group"""
    try:
        from app.models import ProxmoxHost

        host = db.query(ProxmoxHost).first()
        if not host:
            raise HTTPException(status_code=400, detail="No Proxmox hosts configured")

        ssh_host = f"root@{host.hostname}"

        # Build pvesh command to create HA group
        cmd = f"pvesh create /cluster/ha/groups -group {request.group} -nodes {request.nodes}"
        if request.restricted:
            cmd += f" -restricted {request.restricted}"
        if request.nofailback:
            cmd += f" -nofailback {request.nofailback}"
        if request.comment:
            cmd += f" -comment '{request.comment}'"

        create_cmd = f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} '{cmd}'"
        result = subprocess.run(create_cmd, shell=True, capture_output=True, timeout=10)

        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else "Unknown error"
            raise HTTPException(status_code=500, detail=f"Failed to create HA group: {error_msg}")

        logger.info(f"Created HA group {request.group}")
        return {
            "success": True,
            "message": f"HA group {request.group} created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create HA group: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create HA group: {str(e)}")


class HAGroupUpdate(BaseModel):
    nodes: str = None
    restricted: int = None
    nofailback: int = None
    comment: str = None


@router.put("/groups/{group_id}")
def update_ha_group(
    group_id: str,
    request: HAGroupUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update an existing HA group"""
    try:
        from app.models import ProxmoxHost

        host = db.query(ProxmoxHost).first()
        if not host:
            raise HTTPException(status_code=400, detail="No Proxmox hosts configured")

        ssh_host = f"root@{host.hostname}"

        # Build pvesh command to update HA group
        cmd = f"pvesh set /cluster/ha/groups/{group_id}"
        if request.nodes:
            cmd += f" -nodes {request.nodes}"
        if request.restricted is not None:
            cmd += f" -restricted {request.restricted}"
        if request.nofailback is not None:
            cmd += f" -nofailback {request.nofailback}"
        if request.comment is not None:
            cmd += f" -comment '{request.comment}'"

        update_cmd = f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} '{cmd}'"
        result = subprocess.run(update_cmd, shell=True, capture_output=True, timeout=10)

        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else "Unknown error"
            raise HTTPException(status_code=500, detail=f"Failed to update HA group: {error_msg}")

        logger.info(f"Updated HA group {group_id}")
        return {
            "success": True,
            "message": f"HA group {group_id} updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update HA group: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update HA group: {str(e)}")


@router.delete("/groups/{group_id}")
def delete_ha_group(
    group_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete an HA group"""
    try:
        from app.models import ProxmoxHost

        host = db.query(ProxmoxHost).first()
        if not host:
            raise HTTPException(status_code=400, detail="No Proxmox hosts configured")

        ssh_host = f"root@{host.hostname}"

        delete_cmd = f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} 'pvesh delete /cluster/ha/groups/{group_id}'"
        result = subprocess.run(delete_cmd, shell=True, capture_output=True, timeout=10)

        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else "Unknown error"
            raise HTTPException(status_code=500, detail=f"Failed to delete HA group: {error_msg}")

        logger.info(f"Deleted HA group {group_id}")
        return {
            "success": True,
            "message": f"HA group {group_id} deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete HA group: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete HA group: {str(e)}")


@router.get("/resources")
def list_ha_resources(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all HA-protected resources"""
    try:
        from app.models import ProxmoxHost

        host = db.query(ProxmoxHost).first()
        if not host:
            raise HTTPException(status_code=400, detail="No Proxmox hosts configured")

        ssh_host = f"root@{host.hostname}"

        get_resources = f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} 'pvesh get /cluster/ha/resources --output-format json 2>/dev/null'"
        result = subprocess.run(get_resources, shell=True, capture_output=True, timeout=10)

        if result.returncode == 0:
            import json
            try:
                resources = json.loads(result.stdout.decode())
                return {"resources": resources if isinstance(resources, list) else []}
            except:
                return {"resources": []}
        else:
            return {"resources": []}

    except Exception as e:
        logger.error(f"Failed to list HA resources: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list HA resources: {str(e)}")


class HAResourceAdd(BaseModel):
    sid: str  # Resource ID (e.g., "vm:100")
    group: str = None  # HA group name
    max_relocate: int = 1  # Maximum relocate attempts
    max_restart: int = 1  # Maximum restart attempts
    state: str = "started"  # started, stopped, ignored, disabled
    comment: str = None


@router.post("/resources")
def add_ha_resource(
    request: HAResourceAdd,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Add a VM to HA protection"""
    try:
        from app.models import ProxmoxHost

        host = db.query(ProxmoxHost).first()
        if not host:
            raise HTTPException(status_code=400, detail="No Proxmox hosts configured")

        ssh_host = f"root@{host.hostname}"

        # Build pvesh command to add HA resource
        cmd = f"pvesh create /cluster/ha/resources -sid {request.sid}"
        if request.group:
            cmd += f" -group {request.group}"
        cmd += f" -max_relocate {request.max_relocate}"
        cmd += f" -max_restart {request.max_restart}"
        cmd += f" -state {request.state}"
        if request.comment:
            cmd += f" -comment '{request.comment}'"

        add_cmd = f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} '{cmd}'"
        result = subprocess.run(add_cmd, shell=True, capture_output=True, timeout=10)

        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else "Unknown error"
            raise HTTPException(status_code=500, detail=f"Failed to add HA resource: {error_msg}")

        logger.info(f"Added HA resource {request.sid}")
        return {
            "success": True,
            "message": f"Resource {request.sid} added to HA protection"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add HA resource: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add HA resource: {str(e)}")


@router.delete("/resources/{sid}")
def remove_ha_resource(
    sid: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Remove a VM from HA protection"""
    try:
        from app.models import ProxmoxHost

        host = db.query(ProxmoxHost).first()
        if not host:
            raise HTTPException(status_code=400, detail="No Proxmox hosts configured")

        ssh_host = f"root@{host.hostname}"

        # URL encode the sid (e.g., vm:100 becomes vm%3A100)
        import urllib.parse
        encoded_sid = urllib.parse.quote(sid, safe='')

        delete_cmd = f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} 'pvesh delete /cluster/ha/resources/{encoded_sid}'"
        result = subprocess.run(delete_cmd, shell=True, capture_output=True, timeout=10)

        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else "Unknown error"
            raise HTTPException(status_code=500, detail=f"Failed to remove HA resource: {error_msg}")

        logger.info(f"Removed HA resource {sid}")
        return {
            "success": True,
            "message": f"Resource {sid} removed from HA protection"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove HA resource: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove HA resource: {str(e)}")
