"""VM deployment service"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import (
    VirtualMachine,
    VMStatus,
    ProxmoxHost,
    ProxmoxNode,
    ISOImage,
    OSType,
)
from app.services.proxmox import ProxmoxService
from app.services.cloudinit import CloudInitService
from app.core.security import encrypt_data
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class DeploymentService:
    """Service for deploying VMs"""

    def __init__(self, db: Session):
        self.db = db

    def _clear_vm_locks(self, proxmox, node, vmid, host):
        """
        Proactively clear any locks on a VM before operations using SSH as root

        Args:
            proxmox: ProxmoxService instance
            node: ProxmoxNode instance
            vmid: VM ID to clear locks from
            host: ProxmoxHost instance
        """
        import subprocess

        try:
            # Check if VM has a lock attribute
            vm_config = proxmox.proxmox.nodes(node.node_name).qemu(vmid).config.get()
            if 'lock' in vm_config:
                lock_type = vm_config['lock']
                logger.warning(f"VM {vmid} has '{lock_type}' lock, removing it via SSH as root...")

                try:
                    # Get node IP from corosync.conf
                    get_ip_cmd = f"ssh -o StrictHostKeyChecking=no root@{host.hostname} \"grep -A3 'name: {node.node_name}' /etc/pve/corosync.conf | grep ring0_addr | awk '{{print \\$2}}'\""
                    ip_result = subprocess.run(get_ip_cmd, shell=True, capture_output=True, text=True)

                    if ip_result.returncode == 0 and ip_result.stdout.strip():
                        node_ip = ip_result.stdout.strip()

                        # Remove lock directly from config file via SSH
                        # Use qm unlock command which requires root privileges
                        unlock_cmd = f"ssh -o StrictHostKeyChecking=no root@{host.hostname} 'ssh -o StrictHostKeyChecking=no root@{node_ip} \"qm unlock {vmid}\"'"
                        unlock_result = subprocess.run(unlock_cmd, shell=True, capture_output=True, text=True)

                        if unlock_result.returncode == 0:
                            logger.info(f"Successfully removed '{lock_type}' lock from VM {vmid} using qm unlock")

                            # Wait for lock to be fully released
                            time.sleep(2)

                            # Verify lock was removed
                            vm_config_after = proxmox.proxmox.nodes(node.node_name).qemu(vmid).config.get()
                            if 'lock' not in vm_config_after:
                                logger.info(f"Verified lock removed from VM {vmid}")
                            else:
                                logger.warning(f"Lock still present on VM {vmid} after qm unlock")
                        else:
                            logger.error(f"Failed to unlock VM {vmid} via SSH: {unlock_result.stderr}")
                    else:
                        logger.error(f"Failed to get node IP for lock removal")

                except Exception as lock_err:
                    logger.error(f"Failed to remove lock from VM {vmid}: {lock_err}")
        except Exception as e:
            # If VM doesn't exist or other error, just log and continue
            logger.debug(f"Could not check/clear locks on VM {vmid}: {e}")

    def _retry_with_lock_cleanup(self, operation_func, host, node, proxmox=None, vmid=None, max_retries=2):
        """
        Retry an operation with automatic stale lock cleanup

        Args:
            operation_func: Function to execute (should raise exception on lock error)
            host: ProxmoxHost instance
            node: ProxmoxNode instance
            proxmox: ProxmoxService instance (optional, needed for VM lock removal)
            vmid: VM ID (optional, needed for VM lock removal)
            max_retries: Maximum number of retry attempts

        Returns:
            Result of operation_func
        """
        import subprocess
        import re

        # Proactively clear any VM locks before starting
        if proxmox and vmid:
            self._clear_vm_locks(proxmox, node, vmid, host)

        for attempt in range(max_retries):
            try:
                return operation_func()
            except Exception as e:
                error_msg = str(e)

                # Check for VM lock error (e.g., "VM is locked (clone)")
                if "VM is locked" in error_msg and attempt < max_retries - 1:
                    if proxmox and vmid:
                        logger.warning(f"VM {vmid} is locked, removing lock via SSH...")
                        # Use SSH-based lock removal since API requires root
                        self._clear_vm_locks(proxmox, node, vmid, host)
                        time.sleep(2)
                        continue

                # Check for file lock error (e.g., "can't lock file '/var/lock/qemu-server/lock-XXX.conf'")
                if "can't lock file" in error_msg and attempt < max_retries - 1:
                    # Extract VMID from lock error
                    lock_match = re.search(r'lock-(\d+)\.conf', error_msg)
                    if lock_match:
                        locked_vmid = lock_match.group(1)
                        logger.warning(f"Stale lock file detected for VM {locked_vmid} during operation, removing it...")

                        # Get node IP from corosync.conf
                        get_ip_cmd = f"ssh -o StrictHostKeyChecking=no root@{host.hostname} \"grep -A3 'name: {node.node_name}' /etc/pve/corosync.conf | grep ring0_addr | awk '{{print \\$2}}'\""
                        ip_result = subprocess.run(get_ip_cmd, shell=True, capture_output=True, text=True)

                        if ip_result.returncode == 0 and ip_result.stdout.strip():
                            node_ip = ip_result.stdout.strip()
                            # Remove stale lock file
                            cleanup_cmd = f"ssh -o StrictHostKeyChecking=no root@{host.hostname} 'ssh -o StrictHostKeyChecking=no root@{node_ip} \"rm -f /var/lock/qemu-server/lock-{locked_vmid}.conf\"'"
                            cleanup_result = subprocess.run(cleanup_cmd, shell=True, capture_output=True, text=True)

                            if cleanup_result.returncode == 0:
                                logger.info(f"Successfully removed stale lock file for VM {locked_vmid}, retrying operation...")

                                # Also clear VM lock attribute after removing lock file
                                if proxmox and vmid:
                                    self._clear_vm_locks(proxmox, node, vmid, host)

                                time.sleep(2)
                                continue
                            else:
                                logger.error(f"Failed to remove lock file: {cleanup_result.stderr}")
                        else:
                            logger.error(f"Failed to get node IP for lock cleanup")

                # If not a lock error, or retry failed, re-raise
                raise

    def _ensure_virtio_iso(
        self,
        proxmox: ProxmoxService,
        node_name: str,
        storage: str = "local"
    ) -> Optional[str]:
        """
        Ensure VirtIO drivers ISO exists in storage, download if needed

        Args:
            proxmox: ProxmoxService instance
            node_name: Node name where to check/download
            storage: Storage name (default: local)

        Returns:
            ISO path if available, None otherwise
        """
        try:
            virtio_filename = "virtio-win.iso"

            # Check if VirtIO ISO already exists in storage
            logger.info(f"Checking for VirtIO ISO in {storage}:iso/")
            try:
                storage_content = proxmox.proxmox.nodes(node_name).storage(storage).content.get()
                for item in storage_content:
                    if item.get('volid', '').endswith(virtio_filename):
                        logger.info(f"Found existing VirtIO ISO: {item['volid']}")
                        return f"{storage}:iso/{virtio_filename}"
            except Exception as e:
                logger.warning(f"Could not check storage content: {e}")

            # VirtIO ISO not found, download it
            logger.info(f"VirtIO ISO not found in {storage}, downloading...")

            # Use latest stable VirtIO drivers ISO URL
            virtio_url = "https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.iso"

            # Download ISO to storage using Proxmox API
            logger.info(f"Downloading VirtIO ISO from {virtio_url}")
            download_task = proxmox.proxmox.nodes(node_name).storage(storage).download_url.post(
                content='iso',
                filename=virtio_filename,
                url=virtio_url
            )

            logger.info(f"VirtIO ISO download initiated: {download_task}")

            # Wait for download to complete (with timeout)
            max_wait = 300  # 5 minutes timeout
            waited = 0
            while waited < max_wait:
                try:
                    # Check if ISO now exists
                    storage_content = proxmox.proxmox.nodes(node_name).storage(storage).content.get()
                    for item in storage_content:
                        if item.get('volid', '').endswith(virtio_filename):
                            logger.info(f"VirtIO ISO download completed: {item['volid']}")
                            return f"{storage}:iso/{virtio_filename}"
                except Exception:
                    pass

                time.sleep(5)
                waited += 5

            logger.warning("VirtIO ISO download timed out")
            return None

        except Exception as e:
            logger.error(f"Failed to ensure VirtIO ISO: {e}")
            return None

    def deploy_linux_vm(
        self,
        vm_id: int,
    ) -> bool:
        """
        Deploy a Linux VM with cloud-init

        Args:
            vm_id: Database ID of the VM to deploy

        Returns:
            True if deployment successful, False otherwise
        """
        try:
            # Get VM record
            vm = self.db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
            if not vm:
                logger.error(f"VM {vm_id} not found")
                return False

            logger.info(f"Starting Linux VM deployment for VM ID {vm_id}, Name: {vm.name}, OS: {vm.os_type.value}")

            # Update status
            vm.status = VMStatus.CREATING
            vm.status_message = "Initializing VM deployment..."
            self.db.commit()

            # Get Proxmox host
            vm.status_message = "Connecting to Proxmox datacenter..."
            self.db.commit()
            host = (
                self.db.query(ProxmoxHost)
                .filter(ProxmoxHost.id == vm.proxmox_host_id)
                .first()
            )
            if not host:
                raise Exception("Proxmox host not found")

            # Get node
            vm.status_message = "Locating target node..."
            self.db.commit()
            node = self.db.query(ProxmoxNode).filter(ProxmoxNode.id == vm.node_id).first()
            if not node:
                raise Exception("Proxmox node not found")

            # Initialize Proxmox service
            vm.status_message = "Establishing connection to Proxmox API..."
            self.db.commit()
            proxmox = ProxmoxService(host)

            # Get next VMID
            vm.status_message = "Allocating VM ID..."
            self.db.commit()
            vmid = proxmox.get_next_vmid()
            vm.vmid = vmid
            logger.info(f"Allocated VMID {vmid} for VM {vm.name}")

            # Check if using cloud image instead of ISO
            if vm.cloud_image_id:
                from app.models import CloudImage
                cloud_image = self.db.query(CloudImage).filter(CloudImage.id == vm.cloud_image_id).first()
                if not cloud_image:
                    raise Exception("Cloud image not found")

                logger.info(f"Using cloud image {cloud_image.name} for VM {vm.name}")
                return self._deploy_from_cloud_image(vm, host, node, proxmox, vmid, cloud_image)

            # Get ISO if specified
            vm.status_message = "Preparing installation media..."
            self.db.commit()
            iso_path = None
            if vm.iso_id:
                iso = self.db.query(ISOImage).filter(ISOImage.id == vm.iso_id).first()
                if iso:
                    # Use user-selected ISO storage or default to 'local'
                    iso_storage = vm.iso_storage if vm.iso_storage else "local"
                    logger.info(f"Using ISO storage: {iso_storage}")

                    # Sanitize filename for Proxmox (replace spaces and special chars)
                    # Proxmox has issues with spaces and parentheses in filenames
                    import re
                    sanitized_filename = re.sub(r'[^\w\.-]', '_', iso.filename)
                    logger.info(f"Original filename: {iso.filename}, Sanitized: {sanitized_filename}")

                    # Check if ISO exists on Proxmox storage (with sanitized name)
                    logger.info(f"Checking if ISO {sanitized_filename} exists on {node.node_name}:{iso_storage}")
                    iso_exists = proxmox.iso_exists_on_storage(node.node_name, iso_storage, sanitized_filename)

                    if not iso_exists:
                        logger.info(f"ISO {sanitized_filename} not found on Proxmox, uploading...")

                        # Define progress callback to update VM status
                        def update_progress(percent, message):
                            vm.status_message = message
                            self.db.commit()
                            logger.info(f"Upload progress: {message}")

                        vm.status_message = f"Uploading ISO {iso.name} to Proxmox (this may take several minutes)..."
                        self.db.commit()

                        # Upload ISO to Proxmox with sanitized filename
                        upload_success = proxmox.upload_iso(
                            node_name=node.node_name,
                            storage=iso_storage,
                            iso_path=iso.storage_path,
                            filename=sanitized_filename,
                            progress_callback=update_progress
                        )

                        if not upload_success:
                            raise Exception(f"Failed to upload ISO {sanitized_filename} to Proxmox")

                        logger.info(f"Successfully uploaded ISO {sanitized_filename} to Proxmox")
                        vm.status_message = "ISO upload complete! Preparing VM configuration..."
                        self.db.commit()
                    else:
                        logger.info(f"ISO {sanitized_filename} already exists on Proxmox")
                        vm.status_message = "ISO found on Proxmox. Preparing VM configuration..."
                        self.db.commit()

                    iso_path = f"{iso_storage}:iso/{sanitized_filename}"

            # Create VM
            vm.status_message = f"Creating VM {vmid} on node {node.node_name}..."
            self.db.commit()
            logger.info(f"Creating VM {vmid} on node {node.node_name}")

            # Use selected storage or default to local-lvm
            storage = vm.storage if vm.storage else "local-lvm"
            network_bridge = vm.network_bridge if vm.network_bridge else "vmbr0"
            logger.info(f"Using storage: {storage}, network bridge: {network_bridge} for VM {vmid}")

            success = proxmox.create_vm(
                node_name=node.node_name,
                vmid=vmid,
                name=vm.name,
                sockets=vm.cpu_sockets,
                cores=vm.cpu_cores,
                memory=vm.memory,
                disk_size=vm.disk_size,
                storage=storage,
                iso=iso_path,
                network_bridge=network_bridge,
                # Advanced options
                cpu_type=vm.cpu_type or "host",
                cpu_flags=vm.cpu_flags,
                numa_enabled=vm.numa_enabled or False,
                bios_type=vm.bios_type or "seabios",
                machine_type=vm.machine_type or "pc",
                vga_type=vm.vga_type or "std",
                boot_order=vm.boot_order or "cdn",
                network_interfaces=vm.network_interfaces,
            )

            if not success:
                raise Exception("Failed to create VM in Proxmox")

            # Wait a moment for Proxmox to finalize VM creation
            vm.status_message = "VM created successfully! Finalizing configuration..."
            self.db.commit()
            logger.info(f"Waiting for Proxmox to finalize VM {vmid} configuration...")
            time.sleep(2)

            # NOTE: Cloud-init only works with cloud images, not ISO deployments
            # ISO deployments always require manual setup through the installer
            logger.info(f"ISO deployment for {vm.os_type.value} - manual OS installation required")
            vm.status_message = f"VM created from ISO. Boot VM to begin OS installation..."
            self.db.commit()

            # Start VM
            vm.status_message = "Starting VM and initializing OS..."
            self.db.commit()
            logger.info(f"Starting VM {vmid}")
            success = proxmox.start_vm(node.node_name, vmid)

            if not success:
                raise Exception("Failed to start VM")

            # Wait for VM to start
            vm.status_message = "Waiting for VM to boot up..."
            self.db.commit()
            time.sleep(5)

            # Update VM status with appropriate message
            # Check again which OSes support cloud-init for status message
            cloud_init_os_types = [OSType.UBUNTU, OSType.DEBIAN, OSType.CENTOS, OSType.ROCKY, OSType.ALMA]
            vm.status = VMStatus.RUNNING
            if vm.os_type in cloud_init_os_types:
                vm.status_message = "VM deployed successfully! Cloud-init is configuring the OS..."
            else:
                vm.status_message = f"VM created successfully! Access via console for initial {vm.os_type.value} setup."
            vm.deployed_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Successfully deployed VM {vmid} ({vm.os_type.value})")
            return True

        except Exception as e:
            logger.error(f"Failed to deploy VM: {e}")
            if vm:
                vm.status = VMStatus.ERROR
                vm.error_message = str(e)
                self.db.commit()
            return False

    def deploy_windows_vm(
        self,
        vm_id: int,
    ) -> bool:
        """
        Deploy a Windows VM

        Args:
            vm_id: Database ID of the VM to deploy

        Returns:
            True if deployment successful, False otherwise
        """
        try:
            # Get VM record
            vm = self.db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
            if not vm:
                logger.error(f"VM {vm_id} not found")
                return False

            logger.info(f"Starting Windows VM deployment for VM ID {vm_id}, Name: {vm.name}, OS: {vm.os_type.value}")

            # Update status
            vm.status = VMStatus.CREATING
            vm.status_message = "Initializing Windows VM deployment..."
            self.db.commit()

            # Get Proxmox host
            vm.status_message = "Connecting to Proxmox datacenter..."
            self.db.commit()
            host = (
                self.db.query(ProxmoxHost)
                .filter(ProxmoxHost.id == vm.proxmox_host_id)
                .first()
            )
            if not host:
                raise Exception("Proxmox host not found")

            # Get node
            vm.status_message = "Locating target node..."
            self.db.commit()
            node = self.db.query(ProxmoxNode).filter(ProxmoxNode.id == vm.node_id).first()
            if not node:
                raise Exception("Proxmox node not found")

            # Initialize Proxmox service
            vm.status_message = "Establishing connection to Proxmox API..."
            self.db.commit()
            proxmox = ProxmoxService(host)

            # Get next VMID
            vm.status_message = "Allocating VM ID..."
            self.db.commit()
            vmid = proxmox.get_next_vmid()
            vm.vmid = vmid
            logger.info(f"Allocated VMID {vmid} for VM {vm.name}")

            # Get ISO
            vm.status_message = "Preparing Windows installation media..."
            self.db.commit()
            iso_path = None
            if vm.iso_id:
                iso = self.db.query(ISOImage).filter(ISOImage.id == vm.iso_id).first()
                if iso:
                    # Use user-selected ISO storage or default to 'local'
                    iso_storage = vm.iso_storage if vm.iso_storage else "local"
                    logger.info(f"Using ISO storage: {iso_storage} for Windows VM")

                    # Sanitize filename for Proxmox (replace spaces and special chars)
                    import re
                    sanitized_filename = re.sub(r'[^\w\.-]', '_', iso.filename)
                    logger.info(f"Original filename: {iso.filename}, Sanitized: {sanitized_filename}")
                    iso_path = f"{iso_storage}:iso/{sanitized_filename}"

            # Create Windows VM (different settings than Linux)
            vm.status_message = f"Creating Windows VM {vmid} on node {node.node_name}..."
            self.db.commit()
            logger.info(f"Creating Windows VM {vmid} on node {node.node_name}")

            # Use selected storage or default to local-lvm
            storage = vm.storage if vm.storage else "local-lvm"
            network_bridge = vm.network_bridge if vm.network_bridge else "vmbr0"
            logger.info(f"Using storage: {storage}, network bridge: {network_bridge} for Windows VM {vmid}")

            # For Windows, we create the VM manually with appropriate settings
            vm_config = {
                "vmid": vmid,
                "name": vm.name,
                "cores": vm.cpu_cores,
                "memory": vm.memory,
                "scsihw": "virtio-scsi-pci",
                "scsi0": f"{storage}:{vm.disk_size}",
                "net0": f"virtio,bridge={network_bridge}",
                "ostype": "win10",  # Windows OS type
                "agent": 1,  # Enable QEMU guest agent
                "cpu": "host",
                "bios": "ovmf",  # UEFI for modern Windows
            }

            if iso_path:
                vm_config["ide2"] = f"{iso_path},media=cdrom"

            # Ensure VirtIO drivers ISO is available and add it
            vm.status_message = "Preparing VirtIO drivers..."
            self.db.commit()
            iso_storage = vm.iso_storage if vm.iso_storage else "local"
            virtio_iso_path = self._ensure_virtio_iso(proxmox, node.node_name, iso_storage)

            if virtio_iso_path:
                logger.info(f"Adding VirtIO ISO: {virtio_iso_path}")
                vm_config["ide0"] = f"{virtio_iso_path},media=cdrom"
            else:
                logger.warning("VirtIO ISO not available, Windows VM will be created without VirtIO drivers ISO")

            proxmox.proxmox.nodes(node.node_name).qemu.post(**vm_config)

            # Update VM status
            vm.status = VMStatus.STOPPED  # Windows needs manual installation
            vm.status_message = "Windows VM created. Ready for manual OS installation."
            vm.deployed_at = datetime.utcnow()
            self.db.commit()

            logger.info(
                f"Successfully created Windows VM {vmid}. Manual installation required."
            )
            return True

        except Exception as e:
            logger.error(f"Failed to deploy Windows VM: {e}")
            if vm:
                vm.status = VMStatus.ERROR
                vm.error_message = str(e)
                self.db.commit()
            return False

    def check_vm_status(self, vm_id: int) -> Optional[Dict[str, Any]]:
        """Check VM status in Proxmox"""
        try:
            vm = self.db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
            if not vm or not vm.vmid:
                return None

            host = (
                self.db.query(ProxmoxHost)
                .filter(ProxmoxHost.id == vm.proxmox_host_id)
                .first()
            )
            if not host:
                return None

            node = self.db.query(ProxmoxNode).filter(ProxmoxNode.id == vm.node_id).first()
            if not node:
                return None

            proxmox = ProxmoxService(host)
            status = proxmox.get_vm_status(node.node_name, vm.vmid)

            return status

        except Exception as e:
            logger.error(f"Failed to check VM status: {e}")
            return None

    def _deploy_from_cloud_image(self, vm, host, node, proxmox, vmid, cloud_image) -> bool:
        """Deploy a VM from a cloud image using API-only approach (no SSH required)"""
        try:
            import time
            from app.services.cloudinit import CloudInitService

            vm.status_message = f"Preparing cloud image: {cloud_image.name}..."
            self.db.commit()
            logger.info(f"Deploying VM {vmid} from cloud image {cloud_image.name}")

            # Use selected storage or default to local-lvm
            storage = vm.storage if vm.storage else "local-lvm"
            network_bridge = vm.network_bridge if vm.network_bridge else "vmbr0"
            logger.info(f"Using storage: {storage}, network bridge: {network_bridge} for VM {vmid}")

            # Validate storage availability on target node
            vm.status_message = "Validating storage availability..."
            self.db.commit()
            try:
                node_storage = proxmox.proxmox.nodes(node.node_name).storage.get()
                storage_names = [s['storage'] for s in node_storage if s.get('enabled', True)]
                if storage not in storage_names:
                    available_storages = ', '.join(storage_names[:5])
                    raise Exception(
                        f"Storage '{storage}' is not available on node '{node.node_name}'. "
                        f"Available storage: {available_storages}"
                    )
                logger.info(f"Validated storage '{storage}' exists on node '{node.node_name}'")
            except Exception as e:
                if "not available on node" in str(e) or "Storage" in str(e):
                    raise
                logger.warning(f"Could not validate storage (continuing anyway): {e}")

            # FULLY AUTOMATED TEMPLATE-BASED APPROACH
            # Automatically creates templates as needed, then clones instantly
            import time
            import subprocess

            # Make template VMID node-specific to avoid conflicts
            # Node 1: 9001-9099, Node 2: 9101-9199, Node 3: 9201-9299, etc.
            node_offset = (node.id - 1) * 100
            template_vmid = 9000 + node_offset + cloud_image.id

            logger.info(f"Using template VMID {template_vmid} for cloud image {cloud_image.id} on node {node.node_name} (node_id={node.id})")

            # Check if template exists ANYWHERE in the cluster
            template_exists = False
            template_node = None

            # Get all nodes in cluster
            from app.models import ProxmoxNode
            all_nodes = self.db.query(ProxmoxNode).filter(ProxmoxNode.host_id == host.id).all()

            # Check each node for ANY VM with this VMID (not just templates)
            for check_node in all_nodes:
                try:
                    # Try to get the VM config - this will raise exception if VM doesn't exist
                    vm_config = proxmox.proxmox.nodes(check_node.node_name).qemu(template_vmid).config.get()

                    # VM exists on this node!
                    is_template = vm_config.get('template', 0) == 1
                    logger.info(f"Found VM {template_vmid} on node {check_node.node_name}, is_template={is_template}")

                    if check_node.node_name == node.node_name:
                        # VM is on correct node
                        if is_template:
                            # Perfect - it's already a template on the correct node!
                            template_exists = True
                            template_node = check_node.node_name
                            logger.info(f"Found existing template {template_vmid} on correct node {template_node}")
                            break
                        else:
                            # VM exists but is not a template - delete and recreate
                            logger.warning(f"VM {template_vmid} exists on correct node {check_node.node_name} but is NOT a template, deleting it...")
                            try:
                                proxmox.proxmox.nodes(check_node.node_name).qemu(template_vmid).delete()
                                logger.info(f"Deleted non-template VM {template_vmid} from {check_node.node_name}")
                                time.sleep(3)  # Wait for deletion to complete
                            except Exception as del_err:
                                logger.error(f"Failed to delete non-template VM: {del_err}")
                    else:
                        # VM/template is on WRONG node - delete it to enforce node-specific VMID scheme
                        logger.warning(f"Found VM {template_vmid} on WRONG node {check_node.node_name} (expected {node.node_name}), deleting it...")
                        try:
                            proxmox.proxmox.nodes(check_node.node_name).qemu(template_vmid).delete()
                            logger.info(f"Deleted misplaced VM {template_vmid} from {check_node.node_name}")
                            time.sleep(3)  # Wait for deletion to complete
                        except Exception as del_err:
                            logger.error(f"Failed to delete misplaced VM: {del_err}")
                            raise Exception(f"Cannot proceed: VM {template_vmid} exists on wrong node {check_node.node_name} and could not be deleted: {del_err}")
                except Exception as e:
                    # VM doesn't exist on this node (or other error), continue checking
                    error_msg = str(e)
                    if "does not exist" not in error_msg.lower() and "not found" not in error_msg.lower():
                        logger.debug(f"Error checking node {check_node.node_name} for VM {template_vmid}: {e}")
                    continue

            if not template_exists:
                logger.info(f"Template {template_vmid} does not exist on any node in cluster, will create on {node.node_name}")

            # Create template automatically if needed
            if not template_exists:
                vm.status_message = f"Setting up cloud image (first time - takes ~5 min)..."
                self.db.commit()
                logger.info(f"Template {template_vmid} not found, creating automatically...")

                try:
                    # Create template using automated process
                    self._create_cloud_template_automated(
                        host=host,
                        node=node,
                        template_vmid=template_vmid,
                        cloud_image=cloud_image,
                        storage=storage
                    )
                    logger.info(f"Template {template_vmid} created successfully")

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Failed to create template: {error_msg}")

                    if "Permission denied" in error_msg or "Host key verification failed" in error_msg:
                        raise Exception(
                            f"SSH access not configured. Please run this ONE-TIME setup command:\n\n"
                            f"    sudo /tmp/enable_cloud_images.sh\n\n"
                            f"After that, cloud images will deploy automatically!"
                        )
                    else:
                        raise Exception(f"Failed to create cloud image template: {error_msg}")

            # Clone template to create VM (pure API - instant!)
            vm.status_message = f"Cloning cloud image template..."
            self.db.commit()

            # Clone from the node where the template actually exists
            source_node = template_node if template_node else node.node_name
            logger.info(f"Cloning template {template_vmid} from node {source_node} to create VM {vmid} on node {node.node_name}")

            # Use retry helper with automatic lock cleanup
            clone_result = self._retry_with_lock_cleanup(
                lambda: proxmox.proxmox.nodes(source_node).qemu(template_vmid).clone.post(
                    newid=vmid,
                    name=vm.name,
                    full=1,  # Full clone
                    target=node.node_name,  # Clone to target node
                    storage=storage
                ),
                host=host,
                node=node
            )
            logger.info(f"Clone initiated: {clone_result}")

            # Wait for clone to complete
            vm.status_message = "Cloning VM from template (copying disks)..."
            self.db.commit()
            time.sleep(5)
            max_wait = 180
            waited = 0
            clone_completed = False
            
            while waited < max_wait:
                try:
                    # Get VM config
                    vm_config = proxmox.proxmox.nodes(node.node_name).qemu(vmid).config.get()
                    
                    # Check if clone lock is still active
                    if 'lock' in vm_config and vm_config['lock'] == 'clone':
                        logger.info(f"VM {vmid} is still cloning (lock active), waiting...")
                        time.sleep(3)
                        waited += 3
                        continue
                    
                    # Clone lock is gone, check for disk
                    if 'scsi0' in vm_config:
                        logger.info(f"VM {vmid} clone completed successfully, disk verified: scsi0={vm_config.get('scsi0')}")
                        clone_completed = True
                        break
                    else:
                        logger.warning(f"VM {vmid} clone lock released but no scsi0 disk found yet, waiting...")
                        time.sleep(3)
                        waited += 3
                        
                except Exception as e:
                    logger.debug(f"Error checking clone status: {e}")
                    time.sleep(3)
                    waited += 3
            
            if not clone_completed:
                logger.error(f"Clone timeout: VM {vmid} did not complete within {max_wait} seconds")
                vm_config = proxmox.proxmox.nodes(node.node_name).qemu(vmid).config.get()
                logger.error(f"Final VM config: {vm_config}")
                raise Exception(f"VM {vmid} clone timeout. Clone did not complete within {max_wait} seconds.")

            # Customize VM resources
            vm.status_message = "Customizing VM resources..."
            self.db.commit()

            # Build config update with all options
            config_update = {
                'cores': vm.cpu_cores,
                'sockets': vm.cpu_sockets,
                'memory': vm.memory
            }

            # CPU options
            if vm.cpu_type and vm.cpu_type != "host":
                config_update['cpu'] = vm.cpu_type
            if vm.cpu_flags:
                cpu_val = config_update.get('cpu', 'host')
                config_update['cpu'] = f"{cpu_val},{vm.cpu_flags}"
            if vm.cpu_limit:
                config_update['cpulimit'] = vm.cpu_limit
            if vm.cpu_units:
                config_update['cpuunits'] = vm.cpu_units
            if vm.numa_enabled:
                config_update['numa'] = 1

            # Memory options
            if vm.balloon is not None:
                config_update['balloon'] = vm.balloon
            if vm.shares:
                config_update['shares'] = vm.shares

            # Hardware options
            if vm.bios_type == "ovmf":
                config_update['bios'] = 'ovmf'
            if vm.machine_type and vm.machine_type != "pc":
                config_update['machine'] = vm.machine_type
            # Always apply VGA type to override Proxmox defaults (which may be spice)
            if vm.vga_type:
                config_update['vga'] = vm.vga_type
            if vm.scsihw and vm.scsihw != "virtio-scsi-pci":
                config_update['scsihw'] = vm.scsihw

            # Device options
            if not vm.tablet:
                config_update['tablet'] = 0
            if vm.hotplug:
                config_update['hotplug'] = vm.hotplug
            if vm.protection:
                config_update['protection'] = 1
            if not vm.kvm:
                config_update['kvm'] = 0
            if not vm.acpi:
                config_update['acpi'] = 0
            if not vm.agent_enabled:
                config_update['agent'] = 0

            # Startup options
            if vm.startup_order or vm.startup_up or vm.startup_down:
                startup_parts = []
                if vm.startup_order:
                    startup_parts.append(f"order={vm.startup_order}")
                if vm.startup_up:
                    startup_parts.append(f"up={vm.startup_up}")
                if vm.startup_down:
                    startup_parts.append(f"down={vm.startup_down}")
                config_update['startup'] = ','.join(startup_parts)

            # Description and tags
            if vm.description:
                config_update['description'] = vm.description
            if vm.tags:
                config_update['tags'] = vm.tags

            # ALWAYS set boot order using Proxmox 8.x format (order=device1;device2;...)
            # Convert legacy format to new format
            boot_order_map = {
                'cdn': 'scsi0;ide2;net0',  # CD, Disk, Network -> Disk, CD, Network (disk should be first!)
                'dnc': 'scsi0;net0;ide2',  # Disk, Network, CD
                'ncd': 'net0;scsi0;ide2',  # Network, CD, Disk (for PXE boot)
                'ndc': 'net0;scsi0;ide2',  # Network, Disk, CD
                'c': 'scsi0',              # Disk only
                'd': 'scsi0',              # Disk only (legacy)
                'n': 'net0',               # Network only
            }

            if vm.boot_order:
                # If already in new format (contains semicolon or equals), use as-is
                if ';' in vm.boot_order or '=' in vm.boot_order:
                    config_update['boot'] = vm.boot_order if '=' in vm.boot_order else f"order={vm.boot_order}"
                else:
                    # Convert legacy format to new format
                    boot_devices = boot_order_map.get(vm.boot_order.lower(), 'scsi0;ide2;net0')
                    config_update['boot'] = f"order={boot_devices}"
                    logger.info(f"Converted boot order '{vm.boot_order}' to 'order={boot_devices}'")
            else:
                # Default: disk first for cloud images
                config_update['boot'] = 'order=scsi0;net0'
                logger.info(f"Using default boot order: order=scsi0;net0")

            # Set onboot (start at boot) if specified
            if hasattr(vm, 'onboot') and vm.onboot is not None:
                config_update['onboot'] = 1 if vm.onboot else 0
                logger.info(f"Setting onboot={config_update['onboot']}")

            # Use retry helper with automatic lock cleanup
            self._retry_with_lock_cleanup(
                lambda: proxmox.proxmox.nodes(node.node_name).qemu(vmid).config.put(**config_update),
                host=host,
                node=node,
                proxmox=proxmox,
                vmid=vmid
            )

            # Resize disk if needed
            if vm.disk_size > 10:
                logger.info(f"Resizing disk to {vm.disk_size}GB")
                try:
                    self._retry_with_lock_cleanup(
                        lambda: proxmox.proxmox.nodes(node.node_name).qemu(vmid).resize.put(
                            disk='scsi0',
                            size=f'+{vm.disk_size - 10}G'
                        ),
                        host=host,
                        node=node,
                        proxmox=proxmox,
                        vmid=vmid
                    )
                    time.sleep(2)
                except Exception as e:
                    logger.warning(f"Disk resize: {e}")

            logger.info(f"VM {vmid} cloned and customized successfully")

            # Step 2: Configure cloud-init
            vm.status_message = "Configuring cloud-init..."
            self.db.commit()

            use_dhcp = not bool(vm.ip_address)

            # Prepare IP configuration for cloud-init
            ip_config = None
            if not use_dhcp:
                # Format: ip=192.168.1.100/24,gw=192.168.1.1
                ip_config = f"ip={vm.ip_address}/{vm.netmask},gw={vm.gateway}"

            # Prepare nameserver
            nameserver = None
            if vm.dns_servers:
                nameserver = vm.dns_servers.replace(",", " ")

            # Apply cloud-init config to VM
            proxmox.configure_cloud_init(
                node_name=node.node_name,
                vmid=vmid,
                user=vm.username,
                password=vm.password,
                ssh_keys=vm.ssh_key if vm.ssh_key else None,
                ip_config=ip_config,
                nameserver=nameserver
            )

            # Create custom cloud-init user-data snippet to install packages and enable SSH password auth
            logger.info(f"Creating cloud-init user-data snippet for VM {vmid}")
            try:
                import subprocess
                import tempfile
                import os

                # Create user-data with user, packages and SSH configuration
                # Create the specified user with proper home directory and password
                user_data = f"""#cloud-config
users:
  - name: {vm.username}
    gecos: {vm.username}
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: users, admin, sudo
    shell: /bin/bash
    lock_passwd: false
chpasswd:
  list: |
    {vm.username}:{vm.password}
  expire: false
disable_root: false
ssh_pwauth: true
package_update: true
package_upgrade: true
packages:
  - qemu-guest-agent
  - openssh-server
runcmd:
  - systemctl enable qemu-guest-agent
  - systemctl start qemu-guest-agent
  - systemctl enable ssh
  - systemctl start ssh
  - sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
  - sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
  - sed -i 's/^#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
  - systemctl restart ssh || systemctl restart sshd
"""

                # Create temporary file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yml') as f:
                    f.write(user_data)
                    temp_file = f.name

                # Get node IP
                get_ip_cmd = f"ssh -o StrictHostKeyChecking=no root@{host.hostname} \"grep -A3 'name: {node.node_name}' /etc/pve/corosync.conf | grep ring0_addr | awk '{{print \\$2}}'\""
                ip_result = subprocess.run(get_ip_cmd, shell=True, capture_output=True, text=True)

                if ip_result.returncode == 0 and ip_result.stdout.strip():
                    node_ip = ip_result.stdout.strip()

                    # Create snippets directory on target node
                    snippet_path = f"/var/lib/vz/snippets/cloud-init-{vmid}.yml"
                    mkdir_cmd = f"ssh -o StrictHostKeyChecking=no root@{host.hostname} 'ssh -o StrictHostKeyChecking=no root@{node_ip} \"mkdir -p /var/lib/vz/snippets\"'"
                    mkdir_result = subprocess.run(mkdir_cmd, shell=True, capture_output=True, text=True)

                    if mkdir_result.returncode != 0:
                        logger.error(f"Failed to create snippets directory: {mkdir_result.stderr}")
                        raise Exception(f"Failed to create snippets directory: {mkdir_result.stderr}")

                    # Upload snippet file using ProxyJump to go directly to target node
                    scp_cmd = f"scp -o StrictHostKeyChecking=no -o ProxyJump=root@{host.hostname} {temp_file} root@{node_ip}:{snippet_path}"
                    scp_result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)

                    if scp_result.returncode != 0:
                        logger.error(f"Failed to upload snippet file: {scp_result.stderr}")
                        raise Exception(f"Failed to upload snippet file: {scp_result.stderr}")

                    logger.info(f"Uploaded cloud-init snippet to {node_ip}:{snippet_path}")

                    # Verify the file exists
                    verify_cmd = f"ssh -o StrictHostKeyChecking=no root@{host.hostname} 'ssh -o StrictHostKeyChecking=no root@{node_ip} \"test -f {snippet_path} && echo EXISTS\"'"
                    verify_result = subprocess.run(verify_cmd, shell=True, capture_output=True, text=True)

                    if "EXISTS" not in verify_result.stdout:
                        logger.error(f"Snippet file verification failed - file does not exist at {snippet_path}")
                        raise Exception(f"Snippet file not found at {snippet_path}")

                    logger.info(f"Verified snippet file exists at {snippet_path}")

                    # Apply the custom user-data snippet
                    # Note: Snippets must be on directory-based storage (local), not LVM
                    proxmox.proxmox.nodes(node.node_name).qemu(vmid).config.put(
                        cicustom=f"user=local:snippets/cloud-init-{vmid}.yml"
                    )
                    logger.info(f"Applied custom cloud-init user-data for VM {vmid}")
                else:
                    logger.error(f"Failed to get node IP for {node.node_name}")
                    raise Exception(f"Failed to get node IP for {node.node_name}")

                os.unlink(temp_file)
            except Exception as e:
                logger.warning(f"Could not create custom cloud-init snippet: {e}")

            # IMPORTANT: Regenerate cloud-init drive after configuration
            # This ensures the new cloud-init settings are applied
            logger.info(f"Regenerating cloud-init drive for VM {vmid}")
            try:
                # Delete and recreate the cloud-init drive to apply new config
                self._retry_with_lock_cleanup(
                    lambda: proxmox.proxmox.nodes(node.node_name).qemu(vmid).config.put(
                        ide2=f"{storage}:cloudinit"
                    ),
                    host=host,
                    node=node,
                    proxmox=proxmox,
                    vmid=vmid
                )
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to regenerate cloud-init drive: {e}")

            # Step 3: Start the VM
            vm.status_message = "Starting VM..."
            self.db.commit()
            logger.info(f"Starting VM {vmid}")

            start_success = proxmox.start_vm(node.node_name, vmid)
            if not start_success:
                logger.warning(f"Failed to start VM {vmid}, but VM was created successfully")

            # Update VM status
            vm.status = VMStatus.RUNNING
            vm.status_message = f"VM {vmid} deployed successfully from cloud image!"
            vm.deployed_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Successfully deployed VM {vmid} from cloud image {cloud_image.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to deploy VM from cloud image: {e}", exc_info=True)
            vm.status = VMStatus.ERROR
            vm.status_message = "Deployment failed"
            vm.error_message = str(e)
            self.db.commit()
            return False

    def _create_cloud_template_automated(self, host, node, template_vmid, cloud_image, storage):
        """
        Automatically create a cloud image template on Proxmox via SSH
        This runs automatically when needed - no manual steps required
        """
        import subprocess

        logger.info(f"Creating cloud image template {template_vmid} on node {node.node_name} automatically...")

        # Download cloud image if needed
        cloud_image_path = cloud_image.storage_path or f"/var/lib/depl0y/cloud-images/{cloud_image.filename}"

        if not cloud_image.is_downloaded:
            logger.info(f"Downloading {cloud_image.name} from {cloud_image.download_url}")
            import os
            os.makedirs(os.path.dirname(cloud_image_path), exist_ok=True)

            download_cmd = f"wget -q -O {cloud_image_path} {cloud_image.download_url}"
            result = subprocess.run(download_cmd, shell=True, capture_output=True)
            if result.returncode != 0:
                raise Exception(f"Failed to download cloud image: {result.stderr.decode()}")

            cloud_image.is_downloaded = True
            cloud_image.download_status = 'completed'
            cloud_image.download_progress = 100
            self.db.commit()
            logger.info(f"Downloaded to {cloud_image_path}")

        # SSH to cluster host and execute commands that target the specific node
        # Use pvesh or qm commands directly on cluster host with node parameter
        ssh_host = f"root@{host.hostname}"
        target_node = node.node_name
        logger.info(f"SSH target: {ssh_host}, will create template on node: {target_node}")

        # Step 1: Create VM (delete first if it exists but isn't a template)
        logger.info(f"Creating VM {template_vmid} on Proxmox...")

        # All commands executed via SSH to cluster host
        # Commands target specific node using -node parameter or pvesh

        # Check if VM exists - if it's already a template, we're done
        # Use pvesh to check if template exists on the target node
        check_template = f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} 'pvesh get /nodes/{target_node}/qemu/{template_vmid}/status/current >/dev/null 2>&1 && pvesh get /nodes/{target_node}/qemu/{template_vmid}/config | grep -q \"^template: 1\"'"
        check_result = subprocess.run(check_template, shell=True, capture_output=True)
        if check_result.returncode == 0:
            logger.info(f"Template {template_vmid} already exists on {target_node}, skipping creation")
            return

        # Delete if VM exists but isn't a template
        cleanup_script = f"""
ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} '
if pvesh get /nodes/{target_node}/qemu/{template_vmid}/status/current >/dev/null 2>&1; then
  echo VM {template_vmid} exists but is not a template, deleting...
  pvesh delete /nodes/{target_node}/qemu/{template_vmid} --purge=1 || true
fi
'
"""
        subprocess.run(cleanup_script, shell=True, capture_output=True)

        # Create new VM on specific node using pvesh
        create_vm_script = f"""
ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} '
pvesh create /nodes/{target_node}/qemu \\
  -vmid {template_vmid} \\
  -name {cloud_image.name.replace(' ', '-')} \\
  -memory 2048 \\
  -cores 2 \\
  -net0 virtio,bridge=vmbr0 \\
  -vga qxl \\
  -ostype l26 \\
  -scsihw virtio-scsi-pci \\
  -agent enabled=1
'
"""
        result = subprocess.run(create_vm_script, shell=True, capture_output=True)
        if result.returncode != 0:
            raise Exception(f"Failed to create VM on {target_node}: {result.stderr.decode()}")

        # Step 2: Upload cloud image to the cluster host
        # In a Proxmox cluster, storage is typically shared or accessible via the cluster
        # We upload to the cluster host and execute commands there that target the specific node
        logger.info(f"Uploading cloud image to cluster host...")
        upload_script = f"""
scp -o StrictHostKeyChecking=no -o BatchMode=yes {cloud_image_path} {ssh_host}:/tmp/{cloud_image.filename}
"""
        result = subprocess.run(upload_script, shell=True, capture_output=True)
        if result.returncode != 0:
            raise Exception(f"Failed to upload to cluster host: {result.stderr.decode()}")

        # Step 3: Get node IP address from corosync config
        logger.info(f"Getting IP address for node {target_node}...")
        get_ip_cmd = f"""
ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} "grep -A3 'name: {target_node}' /etc/pve/corosync.conf | grep ring0_addr | awk '{{print \\$2}}'"
"""
        ip_result = subprocess.run(get_ip_cmd, shell=True, capture_output=True, text=True)
        if ip_result.returncode != 0 or not ip_result.stdout.strip():
            raise Exception(f"Failed to get IP for node {target_node}")

        node_ip = ip_result.stdout.strip()
        logger.info(f"Node {target_node} IP: {node_ip}")

        # Step 4: Import disk and configure on specific node
        # qm importdisk MUST run on the node where the VM exists
        logger.info(f"Importing disk and configuring template on {target_node}...")

        # Use node IP for SSH instead of hostname
        import_script = f"""
ssh -o StrictHostKeyChecking=no -o BatchMode=yes {ssh_host} '
# Copy image file to target node
scp -o StrictHostKeyChecking=no /tmp/{cloud_image.filename} root@{node_ip}:/tmp/{cloud_image.filename}

# Run qm importdisk ON the target node (needs local VM config)
# This outputs: "Successfully imported disk as unused0"
echo "Importing disk to {storage}..."
ssh -o StrictHostKeyChecking=no root@{node_ip} "qm importdisk {template_vmid} /tmp/{cloud_image.filename} {storage} --format qcow2"

# Attach the imported disk (qm importdisk puts it in unused0)
# Auto-detect the disk format from unused0 to handle both LVM and directory storage
echo "Detecting disk format and attaching to scsi0..."
DISK_PATH=$(ssh -o StrictHostKeyChecking=no root@{node_ip} "qm config {template_vmid} | grep unused0 | awk -F: '"'"'{{print \\$2\":\"\\$3}}'"'"' | tr -d ''''[:space:]''''")
echo "Detected disk path: $DISK_PATH"
ssh -o StrictHostKeyChecking=no root@{node_ip} "qm set {template_vmid} --scsi0 $DISK_PATH"

# Configure boot order and cloud-init using pvesh on cluster host
echo "Configuring boot order and cloud-init..."
pvesh set /nodes/{target_node}/qemu/{template_vmid}/config -boot order=scsi0
pvesh set /nodes/{target_node}/qemu/{template_vmid}/config -ide2 {storage}:cloudinit

# Cleanup and convert to template
echo "Converting to template..."
ssh -o StrictHostKeyChecking=no root@{node_ip} "rm -f /tmp/{cloud_image.filename}"
rm -f /tmp/{cloud_image.filename}
pvesh create /nodes/{target_node}/qemu/{template_vmid}/template
echo "Template {template_vmid} creation complete!"
'
"""
        result = subprocess.run(import_script, shell=True, capture_output=True, timeout=300, text=True)

        # Log the full output for debugging
        if result.stdout:
            logger.info(f"Template creation output:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"Template creation warnings:\n{result.stderr}")

        if result.returncode != 0:
            error_details = f"Return code: {result.returncode}\nStdout: {result.stdout}\nStderr: {result.stderr}"
            logger.error(f"Failed to import disk on {target_node}: {error_details}")
            raise Exception(f"Failed to import disk on {target_node}: {result.stderr}")

        logger.info(f"Template {template_vmid} created successfully on node {target_node}!")

    def _ensure_ssh_access(self, host) -> bool:
        """
        Ensure SSH key access is configured for the Proxmox host
        Automatically attempts to configure if not already set up

        Args:
            host: ProxmoxHost model instance

        Returns:
            True if SSH access is configured, False otherwise
        """
        import subprocess

        ssh_pub_key_path = "/opt/depl0y/.ssh/id_rsa.pub"

        # Check if SSH key already works
        try:
            logger.info(f"Checking SSH access to {host.hostname}...")
            result = subprocess.run(
                [
                    'ssh', '-o', 'StrictHostKeyChecking=no',
                    '-o', 'UserKnownHostsFile=/dev/null',
                    '-o', 'BatchMode=yes',
                    '-o', 'ConnectTimeout=5',
                    f'root@{host.hostname}',
                    'echo', 'SSH_KEY_CONFIGURED'
                ],
                capture_output=True,
                timeout=10
            )

            if result.returncode == 0 and b'SSH_KEY_CONFIGURED' in result.stdout:
                logger.info(f"✓ SSH key already configured for {host.hostname}")
                return True

            logger.info(f"SSH key not yet configured for {host.hostname}")

        except Exception as e:
            logger.debug(f"SSH key check failed: {e}")

        # Try to configure SSH key automatically using password
        if not host.password:
            logger.warning(f"No password stored for Proxmox host {host.hostname}. Cannot automatically configure SSH.")
            logger.info(f"To enable automatic SSH setup, please add the root password for {host.hostname} in the Proxmox Hosts settings.")
            return False

        logger.info(f"Attempting automatic SSH key setup for {host.hostname}...")

        try:
            # Read the public key
            with open(ssh_pub_key_path, 'r') as f:
                public_key = f.read().strip()

            # Use sshpass to copy the key
            result = subprocess.run(
                [
                    'sshpass', '-p', host.password,
                    'ssh-copy-id',
                    '-o', 'StrictHostKeyChecking=no',
                    '-o', 'UserKnownHostsFile=/dev/null',
                    '-i', ssh_pub_key_path,
                    f'root@{host.hostname}'
                ],
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"✓ SSH key automatically configured for {host.hostname}")
                return True
            else:
                stderr = result.stderr.decode() if result.stderr else ""
                logger.warning(f"Failed to copy SSH key: {stderr}")

                # Try alternative method - direct SSH command
                ssh_command = f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '{public_key}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

                result = subprocess.run(
                    [
                        'sshpass', '-p', host.password,
                        'ssh',
                        '-o', 'StrictHostKeyChecking=no',
                        '-o', 'UserKnownHostsFile=/dev/null',
                        f'root@{host.hostname}',
                        ssh_command
                    ],
                    capture_output=True,
                    timeout=30
                )

                if result.returncode == 0:
                    logger.info(f"✓ SSH key automatically configured for {host.hostname} (alternative method)")
                    return True

        except Exception as e:
            logger.error(f"Failed to automatically configure SSH: {e}")

        # Provide helpful error message
        if not host.password:
            logger.error(f"Could not configure SSH for {host.hostname}: No password stored")
            logger.info(f"To enable cloud image support, you must either:")
            logger.info(f"1. Add the Proxmox root password in Settings > Proxmox Hosts > Edit Host")
            logger.info(f"2. OR manually configure SSH key by running on this server:")
            logger.info(f"   cat /opt/depl0y/.ssh/id_rsa.pub | ssh root@{host.hostname} 'cat >> ~/.ssh/authorized_keys'")
        else:
            logger.warning(f"Could not automatically configure SSH for {host.hostname}")

        return False

    def _create_cloud_template_auto(
        self,
        proxmox: ProxmoxService,
        node_name: str,
        host_hostname: str,
        template_vmid: int,
        cloud_image,
        storage: str
    ) -> None:
        """
        Automatically create a cloud image template via SSH

        This method:
        1. Downloads the cloud image file from the internet to Proxmox
        2. Creates a VM template with the cloud image
        3. Configures it for cloud-init

        Args:
            proxmox: ProxmoxService instance
            node_name: Name of the Proxmox node
            host_hostname: Hostname/IP of the Proxmox host
            template_vmid: VMID to use for the template
            cloud_image: CloudImage model instance
            storage: Storage pool to use
        """
        import subprocess

        logger.info(f"Creating cloud template {template_vmid} for {cloud_image.name} via SSH")

        # Map cloud image names to their download URLs
        cloud_image_urls = {
            "Ubuntu 24.04 LTS": "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img",
            "Ubuntu 22.04 LTS": "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img",
            "Ubuntu 20.04 LTS": "https://cloud-images.ubuntu.com/focal/current/focal-server-cloudimg-amd64.img",
            "Debian 12": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2",
            "Debian 11": "https://cloud.debian.org/images/cloud/bullseye/latest/debian-11-generic-amd64.qcow2",
        }

        image_url = cloud_image_urls.get(cloud_image.name)
        if not image_url:
            raise Exception(f"Unknown cloud image: {cloud_image.name}")

        # Construct the SSH command to create the template
        template_name = cloud_image.name.lower().replace(' ', '-').replace('.', '-')
        image_filename = image_url.split('/')[-1]

        # Create a script that will be executed on the Proxmox host
        script = f"""#!/bin/bash
set -e

echo "Creating cloud image template {template_vmid} for {cloud_image.name}"

# Check if template already exists
if qm status {template_vmid} &>/dev/null 2>&1; then
    echo "Template {template_vmid} already exists"
    exit 0
fi

# Download cloud image to Proxmox
cd /var/lib/vz/template/iso
if [ ! -f "{image_filename}" ]; then
    echo "Downloading cloud image..."
    wget -q --show-progress "{image_url}" -O {image_filename}
fi

# Create VM
echo "Creating VM {template_vmid}..."
qm create {template_vmid} \\
    --name "{template_name}" \\
    --memory 2048 \\
    --cores 2 \\
    --net0 virtio,bridge=vmbr0 \\
    --scsihw virtio-scsi-pci

# Import disk
echo "Importing disk..."
qm importdisk {template_vmid} {image_filename} {storage}

# Configure VM
echo "Configuring VM..."
qm set {template_vmid} --scsi0 {storage}:vm-{template_vmid}-disk-0
qm set {template_vmid} --ide2 {storage}:cloudinit
qm set {template_vmid} --boot order=scsi0
qm set {template_vmid} --serial0 socket --vga serial0
qm set {template_vmid} --agent enabled=1

# Convert to template
echo "Converting to template..."
qm template {template_vmid}

echo "Template {template_vmid} created successfully"
"""

        try:
            # Execute the script via SSH
            ssh_command = [
                'ssh',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                '-o', 'BatchMode=yes',
                '-o', 'ConnectTimeout=10',
                f'root@{host_hostname}',
                'bash', '-s'
            ]

            # Run as depl0y user
            result = subprocess.run(
                ['sudo', '-u', 'depl0y'] + ssh_command,
                input=script.encode(),
                capture_output=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode != 0:
                stderr = result.stderr.decode()
                stdout = result.stdout.decode()
                logger.error(f"SSH command failed: {stderr}")
                logger.error(f"stdout: {stdout}")
                raise Exception(f"Failed to create template via SSH: {stderr}")

            logger.info(f"Template {template_vmid} created successfully")
            logger.info(result.stdout.decode())

        except subprocess.TimeoutExpired:
            raise Exception(f"Template creation timed out after 10 minutes")
        except Exception as e:
            logger.error(f"Error creating template: {e}")
            raise

    def delete_vm(self, vm_id: int) -> bool:
        """Delete a VM"""
        try:
            vm = self.db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
            if not vm:
                logger.error(f"VM {vm_id} not found")
                return False

            if vm.vmid:
                host = (
                    self.db.query(ProxmoxHost)
                    .filter(ProxmoxHost.id == vm.proxmox_host_id)
                    .first()
                )
                node = self.db.query(ProxmoxNode).filter(ProxmoxNode.id == vm.node_id).first()

                if host and node:
                    proxmox = ProxmoxService(host)

                    # Stop VM first
                    proxmox.stop_vm(node.node_name, vm.vmid)
                    time.sleep(2)

                    # Delete VM
                    proxmox.delete_vm(node.node_name, vm.vmid)

            # Delete from database
            self.db.delete(vm)
            self.db.commit()

            logger.info(f"Successfully deleted VM {vm_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete VM: {e}")
            return False

    def _create_cloud_template(
        self,
        proxmox: ProxmoxService,
        node_name: str,
        template_vmid: int,
        cloud_image,
        storage: str
    ) -> None:
        """
        Automatically create a cloud image template on a Proxmox node

        Args:
            proxmox: ProxmoxService instance
            node_name: Name of the Proxmox node
            template_vmid: VMID to use for the template
            cloud_image: CloudImage model instance
            storage: Storage pool to use
        """
        import requests
        import os
        import subprocess
        import tempfile

        logger.info(f"Creating cloud template {template_vmid} for {cloud_image.name}")

        # Step 1: Download cloud image if not already downloaded
        if not cloud_image.is_downloaded or not cloud_image.storage_path:
            logger.info(f"Downloading cloud image {cloud_image.name}")
            from app.services.cloud_images import download_cloud_image_task
            download_cloud_image_task(cloud_image.id, self.db)

            # Wait for download to complete
            max_wait = 1800  # 30 minutes max
            waited = 0
            while not cloud_image.is_downloaded and waited < max_wait:
                time.sleep(5)
                waited += 5
                self.db.refresh(cloud_image)

            if not cloud_image.is_downloaded:
                raise Exception(f"Cloud image download timed out after {max_wait} seconds")

        logger.info(f"Cloud image available at: {cloud_image.storage_path}")

        # Step 2: Upload image to Proxmox node and create template via SSH
        # We need to use SSH to run qm importdisk command
        from app.models import ProxmoxHost
        host = self.db.query(ProxmoxHost).filter(
            ProxmoxHost.id == proxmox.host.id
        ).first()

        if not host:
            raise Exception("Proxmox host not found")

        try:
            # Use subprocess to SSH and create the template
            # This assumes SSH key authentication is configured

            # Create a temporary script to run on Proxmox
            script_content = f"""#!/bin/bash
set -e

# Upload cloud image to Proxmox
TEMP_IMG="/tmp/cloud-image-{template_vmid}.img"

# Check if template already exists
if qm status {template_vmid} &>/dev/null; then
    echo "Template {template_vmid} already exists"
    exit 0
fi

# Create VM shell
qm create {template_vmid} \\
    --name "{cloud_image.name.lower().replace(' ', '-')}" \\
    --memory 2048 \\
    --cores 2 \\
    --net0 virtio,bridge=vmbr0 \\
    --scsihw virtio-scsi-pci

# Import the disk (we'll upload the image file first)
qm importdisk {template_vmid} "$TEMP_IMG" {storage}

# Attach the disk
qm set {template_vmid} --scsi0 {storage}:vm-{template_vmid}-disk-0

# Add cloud-init drive
qm set {template_vmid} --ide2 {storage}:cloudinit

# Set boot order
qm set {template_vmid} --boot order=scsi0

# Enable serial console
qm set {template_vmid} --serial0 socket --vga serial0

# Enable QEMU guest agent
qm set {template_vmid} --agent enabled=1

# Convert to template
qm template {template_vmid}

# Clean up
rm -f "$TEMP_IMG"

echo "Template {template_vmid} created successfully"
"""

            # Upload the cloud image file to Proxmox
            logger.info(f"Uploading cloud image to Proxmox node {node_name}")

            # Use scp to copy the file
            subprocess.run(
                [
                    "scp",
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    cloud_image.storage_path,
                    f"root@{host.hostname}:/tmp/cloud-image-{template_vmid}.img"
                ],
                check=True,
                capture_output=True,
                timeout=600  # 10 minute timeout for upload
            )

            logger.info(f"Cloud image uploaded, creating template via SSH")

            # Run the script via SSH
            result = subprocess.run(
                [
                    "ssh",
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    f"root@{host.hostname}",
                    script_content
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            logger.info(f"Template creation output: {result.stdout}")

            if result.returncode != 0:
                raise Exception(f"Failed to create template: {result.stderr}")

            logger.info(f"Successfully created template {template_vmid}")

        except subprocess.TimeoutExpired as e:
            raise Exception(f"Template creation timed out: {e}")
        except subprocess.CalledProcessError as e:
            error_msg = f"SSH command failed: {e.stderr if e.stderr else str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Failed to create cloud template via SSH: {e}")
            raise
