"""High Availability API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.api.auth import get_current_user, require_admin
from app.core.database import get_db
from sqlalchemy.orm import Session
import logging
import re
import shlex
import subprocess

logger = logging.getLogger(__name__)

router = APIRouter()


class HAEnableRequest(BaseModel):
    proxmox_password: str


@router.get("/status")
def check_ha_status(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Check if High Availability is enabled on Proxmox cluster (via API, not SSH)."""
    try:
        from app.models import ProxmoxHost
        from app.services.proxmox import ProxmoxService

        host = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).first()
        if not host:
            return {
                "enabled": False,
                "protected_vms": 0,
                "manager_status": "unknown",
                "quorum": False,
                "master_node": None,
                "nodes_online": 0,
                "nodes_total": 0,
                "message": "No Proxmox hosts configured",
            }

        px = ProxmoxService(host).proxmox
        wrapper = px.cluster.ha.status.manager_status.get() or {}
        inner = wrapper.get("manager_status") or {}
        quorum_info = wrapper.get("quorum") or {}
        node_status = inner.get("node_status") or {}
        online = sum(1 for s in node_status.values() if s == "online")
        master_node = inner.get("master_node")
        quorate = str(quorum_info.get("quorate", "")) == "1"

        try:
            resources = px.cluster.ha.resources.get() or []
            protected_vms = len(resources) if isinstance(resources, list) else 0
        except Exception:
            protected_vms = 0

        if master_node and online > 0:
            manager_state = "active"
        elif online > 0:
            manager_state = "no-master"
        else:
            manager_state = "inactive"

        enabled = bool(node_status) or protected_vms > 0
        return {
            "enabled": enabled,
            "protected_vms": protected_vms,
            "manager_status": manager_state,
            "quorum": quorate,
            "master_node": master_node,
            "nodes_online": online,
            "nodes_total": len(node_status),
            "node_status": node_status,
            "message": "High Availability is enabled" if enabled else "High Availability not configured",
        }

    except Exception as e:
        logger.error(f"Failed to check HA status: {e}")
        return {
            "enabled": False,
            "protected_vms": 0,
            "manager_status": "unknown",
            "quorum": False,
            "master_node": None,
            "nodes_online": 0,
            "nodes_total": 0,
            "message": "Failed to check HA status",
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

        if not re.match(r'^[a-zA-Z0-9.\-_]+$', host.hostname):
            raise HTTPException(status_code=400, detail="Invalid Proxmox hostname")
        ssh_host = f"root@{host.hostname}"
        logger.info(f"Enabling HA on {ssh_host}")

        remote_script = (
            'if ! pvesh get /cluster/status 2>/dev/null | grep -q "quorate.*1"; then '
            'echo "ERROR: Cluster does not have quorum."; exit 1; fi; '
            'if ! systemctl is-active --quiet pve-ha-lrm && ! systemctl is-active --quiet pve-ha-crm; then '
            'systemctl start pve-ha-lrm; systemctl start pve-ha-crm; '
            'systemctl enable pve-ha-lrm; systemctl enable pve-ha-crm; fi; '
            'echo "HA services are running"'
        )
        result = subprocess.run(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes', ssh_host, remote_script],
            capture_output=True, timeout=30
        )

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

        if not re.match(r'^[a-zA-Z0-9.\-_]+$', host.hostname):
            return {"groups": [], "message": "Invalid Proxmox hostname"}
        ssh_host = f"root@{host.hostname}"

        result = subprocess.run(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
             ssh_host, 'pvesh get /cluster/ha/groups --output-format json 2>&1'],
            capture_output=True, timeout=10, text=True
        )

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

        if not re.match(r'^[a-zA-Z0-9.\-_]+$', host.hostname):
            raise HTTPException(status_code=400, detail="Invalid Proxmox hostname")
        ssh_host = f"root@{host.hostname}"

        remote_script = (
            'systemctl stop pve-ha-lrm; systemctl stop pve-ha-crm; '
            'systemctl disable pve-ha-lrm; systemctl disable pve-ha-crm; '
            'echo "HA services stopped"'
        )
        result = subprocess.run(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes', ssh_host, remote_script],
            capture_output=True, timeout=30
        )

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

        if not re.match(r'^[a-zA-Z0-9.\-_]+$', host.hostname):
            raise HTTPException(status_code=400, detail="Invalid Proxmox hostname")
        ssh_host = f"root@{host.hostname}"

        cmd_parts = ['pvesh', 'create', '/cluster/ha/groups',
                     '-group', request.group, '-nodes', request.nodes]
        if request.restricted:
            cmd_parts += ['-restricted', str(request.restricted)]
        if request.nofailback:
            cmd_parts += ['-nofailback', str(request.nofailback)]
        if request.comment:
            cmd_parts += ['-comment', request.comment]

        result = subprocess.run(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
             ssh_host, ' '.join(shlex.quote(p) for p in cmd_parts)],
            capture_output=True, timeout=10
        )

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

        if not re.match(r'^[a-zA-Z0-9.\-_]+$', host.hostname):
            raise HTTPException(status_code=400, detail="Invalid Proxmox hostname")
        if not re.match(r'^[a-zA-Z0-9.\-_]+$', group_id):
            raise HTTPException(status_code=400, detail="Invalid group ID")
        ssh_host = f"root@{host.hostname}"

        # Build pvesh command to update HA group using shlex.quote on all values
        cmd_parts = ['pvesh', 'set', f'/cluster/ha/groups/{group_id}']
        if request.nodes:
            cmd_parts += ['-nodes', request.nodes]
        if request.restricted is not None:
            cmd_parts += ['-restricted', str(request.restricted)]
        if request.nofailback is not None:
            cmd_parts += ['-nofailback', str(request.nofailback)]
        if request.comment is not None:
            cmd_parts += ['-comment', request.comment]

        result = subprocess.run(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
             ssh_host, ' '.join(shlex.quote(p) for p in cmd_parts)],
            capture_output=True, timeout=10
        )

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

        if not re.match(r'^[a-zA-Z0-9.\-_]+$', host.hostname):
            raise HTTPException(status_code=400, detail="Invalid Proxmox hostname")
        if not re.match(r'^[a-zA-Z0-9.\-_]+$', group_id):
            raise HTTPException(status_code=400, detail="Invalid group ID")
        ssh_host = f"root@{host.hostname}"

        result = subprocess.run(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
             ssh_host, f'pvesh delete /cluster/ha/groups/{shlex.quote(group_id)}'],
            capture_output=True, timeout=10
        )

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

        if not re.match(r'^[a-zA-Z0-9.\-_]+$', host.hostname):
            raise HTTPException(status_code=400, detail="Invalid Proxmox hostname")
        ssh_host = f"root@{host.hostname}"

        result = subprocess.run(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
             ssh_host, 'pvesh get /cluster/ha/resources --output-format json 2>/dev/null'],
            capture_output=True, timeout=10
        )

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

        if not re.match(r'^[a-zA-Z0-9.\-_]+$', host.hostname):
            raise HTTPException(status_code=400, detail="Invalid Proxmox hostname")
        ssh_host = f"root@{host.hostname}"

        # Build pvesh command to add HA resource using shlex.quote on all values
        cmd_parts = ['pvesh', 'create', '/cluster/ha/resources',
                     '-sid', request.sid,
                     '-max_relocate', str(request.max_relocate),
                     '-max_restart', str(request.max_restart),
                     '-state', request.state]
        if request.group:
            cmd_parts += ['-group', request.group]
        if request.comment:
            cmd_parts += ['-comment', request.comment]

        result = subprocess.run(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
             ssh_host, ' '.join(shlex.quote(p) for p in cmd_parts)],
            capture_output=True, timeout=10
        )

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

        if not re.match(r'^[a-zA-Z0-9.\-_]+$', host.hostname):
            raise HTTPException(status_code=400, detail="Invalid Proxmox hostname")
        # Validate sid format: must be "vm:NNN" or "ct:NNN"
        if not re.match(r'^(vm|ct):\d+$', sid):
            raise HTTPException(status_code=400, detail="Invalid resource ID format")
        ssh_host = f"root@{host.hostname}"

        # URL encode the sid (e.g., vm:100 becomes vm%3A100)
        import urllib.parse
        encoded_sid = urllib.parse.quote(sid, safe='')

        result = subprocess.run(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes',
             ssh_host, f'pvesh delete /cluster/ha/resources/{encoded_sid}'],
            capture_output=True, timeout=10
        )

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
