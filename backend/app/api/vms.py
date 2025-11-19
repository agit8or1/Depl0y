"""Virtual Machines API routes"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import encrypt_data
from app.models import VirtualMachine, VMStatus, OSType, User
from app.api.auth import get_current_user, require_operator
from app.services.deployment import DeploymentService

router = APIRouter()


# Pydantic models
class VMCreate(BaseModel):
    name: str
    hostname: str
    proxmox_host_id: int
    node_id: int
    iso_id: Optional[int] = None
    cloud_image_id: Optional[int] = None  # Use cloud image template instead of ISO
    os_type: str  # Accept any string, will be validated/converted internally

    # CPU options
    cpu_sockets: int = 1
    cpu_cores: int
    cpu_type: Optional[str] = "host"  # host, qemu64, kvm64, etc.
    cpu_flags: Optional[str] = None  # Additional CPU flags
    cpu_limit: Optional[int] = None  # CPU usage limit (0 = unlimited)
    cpu_units: int = 1024  # CPU weight for scheduler
    numa_enabled: bool = False  # NUMA support

    # Memory and disk
    memory: int  # MB
    balloon: Optional[int] = None  # Balloon device (0 = disabled, MB)
    shares: Optional[int] = None  # Memory shares for scheduler
    disk_size: int  # GB
    storage: Optional[str] = None  # Storage pool name for VM disks
    iso_storage: Optional[str] = None  # Storage pool name for ISO files
    scsihw: str = "virtio-scsi-pci"  # SCSI controller type

    # Hardware options
    bios_type: str = "seabios"  # seabios or ovmf (UEFI)
    machine_type: Optional[str] = "pc"  # pc, q35, etc.
    vga_type: str = "std"  # std, virtio, qxl, vmware, cirrus
    boot_order: str = "cdn"  # c=disk, d=cdrom, n=network
    onboot: bool = True  # Start VM at boot
    tablet: bool = True  # Enable tablet pointer device
    hotplug: Optional[str] = None  # Hotplug options: disk,network,usb,memory,cpu
    protection: bool = False  # Prevent accidental deletion
    startup_order: Optional[int] = None  # Startup order
    startup_up: Optional[int] = None  # Startup delay in seconds
    startup_down: Optional[int] = None  # Shutdown timeout in seconds
    kvm: bool = True  # Enable KVM hardware virtualization
    acpi: bool = True  # Enable ACPI
    agent_enabled: bool = True  # QEMU guest agent
    description: Optional[str] = None  # VM description
    tags: Optional[str] = None  # VM tags (semicolon-separated)

    # Network configuration
    network_bridge: Optional[str] = None  # Primary network bridge
    network_interfaces: Optional[list] = None  # Additional network interfaces
    ip_address: Optional[str] = None
    gateway: Optional[str] = None
    netmask: Optional[str] = None
    dns_servers: Optional[str] = None

    # Credentials
    username: str
    password: str
    ssh_key: Optional[str] = None


class VMUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[VMStatus] = None
    ip_address: Optional[str] = None


class VMResponse(BaseModel):
    id: int
    vmid: Optional[int]
    name: str
    hostname: str
    proxmox_host_id: int
    node_id: Optional[int]
    iso_id: Optional[int]
    cloud_image_id: Optional[int]
    os_type: str  # Return as string for flexibility
    cpu_cores: int
    memory: int
    disk_size: int
    ip_address: Optional[str]
    gateway: Optional[str]
    netmask: Optional[str]
    dns_servers: Optional[str]
    username: str
    status: str  # Return as string for flexibility
    error_message: Optional[str]
    created_at: datetime
    deployed_at: Optional[datetime]
    created_by: int

    class Config:
        from_attributes = True


class ProxmoxVMResponse(BaseModel):
    """Response model for VMs queried directly from Proxmox"""
    vmid: int
    name: str
    status: str
    node: str
    cpus: int
    maxmem: int  # bytes
    maxdisk: int  # bytes

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ProxmoxVMResponse])
async def list_vms(
    skip: int = 0,
    limit: int = 1000,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all virtual machines from Proxmox"""
    from app.services.proxmox import ProxmoxService
    from app.models import ProxmoxHost
    import logging

    logger = logging.getLogger(__name__)

    # Query all active Proxmox hosts and get VMs from Proxmox itself
    active_hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()

    all_vms = []
    for host in active_hosts:
        try:
            service = ProxmoxService(host)
            vms = service.get_all_vms()

            # Convert to response format
            for vm in vms:
                all_vms.append({
                    'vmid': vm.get('vmid'),
                    'name': vm.get('name', f"VM {vm.get('vmid')}"),
                    'status': vm.get('status', 'unknown'),
                    'node': vm.get('node', 'unknown'),
                    'cpus': vm.get('cpus', 0),
                    'maxmem': vm.get('maxmem', 0),
                    'maxdisk': vm.get('maxdisk', 0),
                })
        except Exception as e:
            logger.error(f"Failed to get VMs from host {host.name}: {e}")

    return all_vms


@router.post("/", response_model=VMResponse, status_code=status.HTTP_201_CREATED)
async def create_vm(
    vm_data: VMCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Create and deploy a new virtual machine"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Received VM create request: {vm_data.model_dump()}")

    # Convert os_type string to enum
    try:
        os_type_enum = OSType(vm_data.os_type)
    except ValueError:
        # If not a valid enum value, default to OTHER
        os_type_enum = OSType.OTHER
        logger.warning(f"Unknown os_type '{vm_data.os_type}', defaulting to OTHER")

    # Create VM record
    new_vm = VirtualMachine(
        name=vm_data.name,
        hostname=vm_data.hostname,
        proxmox_host_id=vm_data.proxmox_host_id,
        node_id=vm_data.node_id,
        iso_id=vm_data.iso_id,
        cloud_image_id=vm_data.cloud_image_id,
        os_type=os_type_enum,

        # CPU options
        cpu_sockets=vm_data.cpu_sockets,
        cpu_cores=vm_data.cpu_cores,
        cpu_type=vm_data.cpu_type,
        cpu_flags=vm_data.cpu_flags,
        cpu_limit=vm_data.cpu_limit,
        cpu_units=vm_data.cpu_units,
        numa_enabled=vm_data.numa_enabled,

        # Memory and disk
        memory=vm_data.memory,
        balloon=vm_data.balloon,
        shares=vm_data.shares,
        disk_size=vm_data.disk_size,
        storage=vm_data.storage,
        iso_storage=vm_data.iso_storage,
        scsihw=vm_data.scsihw,

        # Hardware options
        bios_type=vm_data.bios_type,
        machine_type=vm_data.machine_type,
        vga_type=vm_data.vga_type,
        boot_order=vm_data.boot_order,
        onboot=vm_data.onboot,
        tablet=vm_data.tablet,
        hotplug=vm_data.hotplug,
        protection=vm_data.protection,
        startup_order=vm_data.startup_order,
        startup_up=vm_data.startup_up,
        startup_down=vm_data.startup_down,
        kvm=vm_data.kvm,
        acpi=vm_data.acpi,
        agent_enabled=vm_data.agent_enabled,
        description=vm_data.description,
        tags=vm_data.tags,

        # Network configuration
        network_bridge=vm_data.network_bridge,
        network_interfaces=vm_data.network_interfaces,
        ip_address=vm_data.ip_address,
        gateway=vm_data.gateway,
        netmask=vm_data.netmask,
        dns_servers=vm_data.dns_servers,

        # Credentials
        username=vm_data.username,
        password=vm_data.password,  # Should be encrypted in production
        ssh_key=vm_data.ssh_key,

        status=VMStatus.CREATING,
        created_by=current_user.id,
    )

    db.add(new_vm)
    db.commit()
    db.refresh(new_vm)

    # Deploy VM in background
    deployment_service = DeploymentService(db)

    # Determine deployment type based on OS
    windows_types = [
        OSType.WINDOWS_SERVER_2016,
        OSType.WINDOWS_SERVER_2019,
        OSType.WINDOWS_SERVER_2022,
        OSType.WINDOWS_10,
        OSType.WINDOWS_11
    ]

    if os_type_enum in windows_types:
        logger.info(f"Deploying Windows VM {new_vm.id} ({os_type_enum.value})")
        background_tasks.add_task(deployment_service.deploy_windows_vm, new_vm.id)
    else:
        logger.info(f"Deploying Linux/Other VM {new_vm.id} ({os_type_enum.value})")
        background_tasks.add_task(deployment_service.deploy_linux_vm, new_vm.id)

    return new_vm


@router.get("/{vm_id}", response_model=VMResponse)
async def get_vm(
    vm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get virtual machine by ID"""
    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    # Check permissions
    if current_user.role.value == "viewer" and vm.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this VM")

    return vm


@router.put("/{vm_id}", response_model=VMResponse)
async def update_vm(
    vm_id: int,
    vm_data: VMUpdate,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Update virtual machine"""
    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    # Update fields
    if vm_data.name is not None:
        vm.name = vm_data.name

    if vm_data.status is not None:
        vm.status = vm_data.status

    if vm_data.ip_address is not None:
        vm.ip_address = vm_data.ip_address

    vm.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(vm)

    return vm


@router.delete("/{vm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vm(
    vm_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Delete virtual machine"""
    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    # Delete from Proxmox and database
    deployment_service = DeploymentService(db)
    success = deployment_service.delete_vm(vm_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete VM")

    return None


@router.post("/{vm_id}/start")
async def start_vm(
    vm_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Start virtual machine"""
    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    from app.services.proxmox import ProxmoxService
    from app.models import ProxmoxHost, ProxmoxNode

    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == vm.proxmox_host_id).first()
    node = db.query(ProxmoxNode).filter(ProxmoxNode.id == vm.node_id).first()

    if not host or not node or not vm.vmid:
        raise HTTPException(status_code=400, detail="VM not fully configured")

    proxmox = ProxmoxService(host)
    success = proxmox.start_vm(node.node_name, vm.vmid)

    if success:
        vm.status = VMStatus.RUNNING
        db.commit()
        return {"status": "success", "message": "VM started"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start VM")


@router.post("/{vm_id}/stop")
async def stop_vm(
    vm_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Stop virtual machine"""
    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    from app.services.proxmox import ProxmoxService
    from app.models import ProxmoxHost, ProxmoxNode

    host = db.query(ProxmoxHost).filter(ProxmoxHost.id == vm.proxmox_host_id).first()
    node = db.query(ProxmoxNode).filter(ProxmoxNode.id == vm.node_id).first()

    if not host or not node or not vm.vmid:
        raise HTTPException(status_code=400, detail="VM not fully configured")

    proxmox = ProxmoxService(host)
    success = proxmox.stop_vm(node.node_name, vm.vmid)

    if success:
        vm.status = VMStatus.STOPPED
        db.commit()
        return {"status": "success", "message": "VM stopped"}
    else:
        raise HTTPException(status_code=500, detail="Failed to stop VM")


@router.get("/{vm_id}/status")
async def get_vm_status(
    vm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get VM status from Proxmox"""
    deployment_service = DeploymentService(db)
    status_info = deployment_service.check_vm_status(vm_id)

    if not status_info:
        raise HTTPException(status_code=404, detail="Could not retrieve VM status")

    return status_info


@router.get("/{vm_id}/progress")
async def get_vm_progress(
    vm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get VM deployment progress"""
    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    return {
        "id": vm.id,
        "name": vm.name,
        "status": vm.status.value,
        "status_message": vm.status_message,
        "error_message": vm.error_message,
        "vmid": vm.vmid
    }


@router.post("/control/{node_name}/{vmid}/start")
async def start_vm_by_vmid(
    node_name: str,
    vmid: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Start a VM by VMID and node name"""
    from app.services.proxmox import ProxmoxService
    from app.models import ProxmoxHost
    import logging

    logger = logging.getLogger(__name__)

    # Find the host that has this node
    active_hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()

    for host in active_hosts:
        try:
            service = ProxmoxService(host)
            nodes = service.get_nodes()

            # Check if this host has the requested node
            if any(n.get('node') == node_name for n in nodes):
                success = service.start_vm(node_name, vmid)
                if success:
                    return {"status": "success", "message": f"VM {vmid} started"}
                else:
                    raise HTTPException(status_code=500, detail="Failed to start VM")
        except Exception as e:
            logger.error(f"Error starting VM on host {host.name}: {e}")
            continue

    raise HTTPException(status_code=404, detail="Node or VM not found")


@router.post("/control/{node_name}/{vmid}/stop")
async def stop_vm_by_vmid(
    node_name: str,
    vmid: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Stop a VM by VMID and node name (graceful shutdown)"""
    from app.services.proxmox import ProxmoxService
    from app.models import ProxmoxHost
    import logging

    logger = logging.getLogger(__name__)

    active_hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()

    for host in active_hosts:
        try:
            service = ProxmoxService(host)
            nodes = service.get_nodes()

            if any(n.get('node') == node_name for n in nodes):
                success = service.stop_vm(node_name, vmid)
                if success:
                    return {"status": "success", "message": f"VM {vmid} stopped"}
                else:
                    raise HTTPException(status_code=500, detail="Failed to stop VM")
        except Exception as e:
            logger.error(f"Error stopping VM on host {host.name}: {e}")
            continue

    raise HTTPException(status_code=404, detail="Node or VM not found")


@router.post("/control/{node_name}/{vmid}/shutdown")
async def shutdown_vm_by_vmid(
    node_name: str,
    vmid: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Shutdown a VM by VMID and node name (force power off)"""
    from app.services.proxmox import ProxmoxService
    from app.models import ProxmoxHost
    import logging

    logger = logging.getLogger(__name__)

    active_hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()

    for host in active_hosts:
        try:
            service = ProxmoxService(host)
            nodes = service.get_nodes()

            if any(n.get('node') == node_name for n in nodes):
                success = service.shutdown_vm(node_name, vmid)
                if success:
                    return {"status": "success", "message": f"VM {vmid} powered off"}
                else:
                    raise HTTPException(status_code=500, detail="Failed to power off VM")
        except Exception as e:
            logger.error(f"Error powering off VM on host {host.name}: {e}")
            continue

    raise HTTPException(status_code=404, detail="Node or VM not found")


@router.post("/control/{node_name}/{vmid}/restart")
async def restart_vm_by_vmid(
    node_name: str,
    vmid: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Restart a VM by VMID and node name"""
    from app.services.proxmox import ProxmoxService
    from app.models import ProxmoxHost
    import logging

    logger = logging.getLogger(__name__)

    active_hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()

    for host in active_hosts:
        try:
            service = ProxmoxService(host)
            nodes = service.get_nodes()

            if any(n.get('node') == node_name for n in nodes):
                success = service.restart_vm(node_name, vmid)
                if success:
                    return {"status": "success", "message": f"VM {vmid} restarted"}
                else:
                    raise HTTPException(status_code=500, detail="Failed to restart VM")
        except Exception as e:
            logger.error(f"Error restarting VM on host {host.name}: {e}")
            continue

    raise HTTPException(status_code=404, detail="Node or VM not found")


@router.delete("/control/{node_name}/{vmid}/delete")
async def delete_vm_by_vmid(
    node_name: str,
    vmid: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    """Delete a VM by VMID and node name - permanently removes from Proxmox"""
    from app.services.proxmox import ProxmoxService
    from app.models import ProxmoxHost
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"Delete request for VM {vmid} on node {node_name} by user {current_user.username}")

    active_hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()

    for host in active_hosts:
        try:
            service = ProxmoxService(host)
            nodes = service.get_nodes()

            if any(n.get('node') == node_name for n in nodes):
                # Delete VM from Proxmox
                try:
                    service.proxmox.nodes(node_name).qemu(vmid).delete()
                    logger.info(f"Successfully deleted VM {vmid} from node {node_name}")

                    # Also remove from database if it exists
                    vm_record = db.query(VirtualMachine).filter(VirtualMachine.vmid == vmid).first()
                    if vm_record:
                        db.delete(vm_record)
                        db.commit()
                        logger.info(f"Removed VM {vmid} record from database")

                    return {"status": "success", "message": f"VM {vmid} deleted successfully"}
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Failed to delete VM {vmid}: {error_msg}")
                    raise HTTPException(status_code=500, detail=f"Failed to delete VM: {error_msg}")
        except Exception as e:
            logger.error(f"Error accessing host {host.name}: {e}")
            continue

    raise HTTPException(status_code=404, detail="Node or VM not found")
