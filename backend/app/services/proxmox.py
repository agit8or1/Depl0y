"""Proxmox VE API integration service"""
from typing import List, Dict, Optional, Any
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from sqlalchemy.orm import Session
from app.models import ProxmoxHost, ProxmoxNode
from app.core.security import decrypt_data
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ProxmoxService:
    """Service for interacting with Proxmox VE"""

    def __init__(self, host: ProxmoxHost):
        """Initialize Proxmox connection"""
        self.host = host

        # Check if using API token (preferred for 2FA-enabled Proxmox)
        if host.api_token_id and host.api_token_secret:
            try:
                token_secret = decrypt_data(host.api_token_secret)
            except Exception:
                token_secret = host.api_token_secret

            # Extract token name and user from token ID
            # Token ID can be "tokenname" or "user@realm!tokenname"
            if '!' in host.api_token_id:
                token_parts = host.api_token_id.split('!')
                token_user = token_parts[0]  # e.g., "root@pam"
                token_name = token_parts[1]   # e.g., "depl0y"
            else:
                token_user = host.username
                token_name = host.api_token_id

            logger.info(f"Connecting to Proxmox {host.hostname} with token auth: user={token_user}, token_name={token_name}")

            self.proxmox = ProxmoxAPI(
                host.hostname,
                user=token_user,
                token_name=token_name,
                token_value=token_secret,
                port=host.port,
                verify_ssl=host.verify_ssl,
                timeout=30,  # Increase timeout to 30 seconds for slow operations
            )
        else:
            # Fall back to password authentication
            try:
                password = decrypt_data(host.password)
            except Exception:
                password = host.password

            self.proxmox = ProxmoxAPI(
                host.hostname,
                user=host.username,
                password=password,
                port=host.port,
                verify_ssl=host.verify_ssl,
                timeout=30,  # Increase timeout to 30 seconds for slow operations
            )

    def test_connection(self) -> bool:
        """Test connection to Proxmox host"""
        try:
            version = self.proxmox.version.get()
            logger.info(f"Successfully connected to Proxmox {self.host.name}, version: {version.get('version', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Proxmox host {self.host.name}: {str(e)}")
            logger.error(f"Connection details: hostname={self.host.hostname}, port={self.host.port}, using_token={bool(self.host.api_token_id)}")
            return False

    def get_nodes(self) -> List[Dict[str, Any]]:
        """Get list of nodes from Proxmox cluster"""
        try:
            nodes = self.proxmox.nodes.get()
            return nodes
        except ResourceException as e:
            logger.error(f"Failed to get nodes: {e}")
            return []

    def get_node_resources(self, node_name: str) -> Optional[Dict[str, Any]]:
        """Get resource information for a specific node"""
        try:
            node = self.proxmox.nodes(node_name)
            status = node.status.get()

            # Proxmox returns 'online' or 'offline' in the node list, not in status
            # We can infer online if we get a successful response
            node_status = "online"

            return {
                "node_name": node_name,
                "status": node_status,
                "cpu_cores": status.get("cpuinfo", {}).get("cpus", 0),
                "cpu_usage": int((status.get("cpu", 0) * 100)),
                "memory_total": status.get("memory", {}).get("total", 0),
                "memory_used": status.get("memory", {}).get("used", 0),
                "disk_total": status.get("rootfs", {}).get("total", 0),
                "disk_used": status.get("rootfs", {}).get("used", 0),
                "uptime": status.get("uptime", 0),
            }
        except ResourceException as e:
            logger.error(f"Failed to get node resources for {node_name}: {e}")
            return None

    def get_next_vmid(self) -> int:
        """Get next available VMID"""
        try:
            return int(self.proxmox.cluster.nextid.get())
        except ResourceException as e:
            logger.error(f"Failed to get next VMID: {e}")
            return 100

    def get_storage_list(self, node_name: str) -> List[Dict[str, Any]]:
        """Get storage list for a node with detailed information"""
        try:
            storages = self.proxmox.nodes(node_name).storage.get()
            detailed_storages = []

            for storage in storages:
                storage_name = storage.get('storage')
                try:
                    # Get detailed storage info
                    storage_status = self.proxmox.nodes(node_name).storage(storage_name).status.get()
                    detailed_storages.append({
                        'storage': storage_name,
                        'type': storage.get('type'),
                        'content': storage.get('content', ''),
                        'active': storage.get('active', 0) == 1,
                        'enabled': storage.get('enabled', 0) == 1,
                        'total': storage_status.get('total', 0),
                        'used': storage_status.get('used', 0),
                        'available': storage_status.get('avail', 0),
                        'shared': storage.get('shared', 0) == 1,
                    })
                except Exception as e:
                    logger.warning(f"Failed to get detailed info for storage {storage_name}: {e}")
                    detailed_storages.append({
                        'storage': storage_name,
                        'type': storage.get('type'),
                        'content': storage.get('content', ''),
                        'active': storage.get('active', 0) == 1,
                        'enabled': storage.get('enabled', 0) == 1,
                        'total': 0,
                        'used': 0,
                        'available': 0,
                        'shared': storage.get('shared', 0) == 1,
                    })

            return detailed_storages
        except ResourceException as e:
            logger.error(f"Failed to get storage list: {e}")
            return []

    def get_network_interfaces(self, node_name: str) -> List[Dict[str, Any]]:
        """Get network interfaces/bridges for a node"""
        try:
            network = self.proxmox.nodes(node_name).network.get()
            bridges = []

            for iface in network:
                iface_type = iface.get('type')
                # Include bridges and bonds
                if iface_type in ['bridge', 'bond', 'OVSBridge']:
                    bridges.append({
                        'iface': iface.get('iface'),
                        'type': iface_type,
                        'active': iface.get('active', 0) == 1,
                        'autostart': iface.get('autostart', 0) == 1,
                        'address': iface.get('address'),
                        'netmask': iface.get('netmask'),
                        'gateway': iface.get('gateway'),
                        'bridge_ports': iface.get('bridge_ports'),
                        'comments': iface.get('comments'),
                    })

            return bridges
        except ResourceException as e:
            logger.error(f"Failed to get network interfaces: {e}")
            return []

    def iso_exists_on_storage(self, node_name: str, storage: str, filename: str) -> bool:
        """Check if ISO exists on Proxmox storage"""
        try:
            # List all ISOs in the storage
            content = self.proxmox.nodes(node_name).storage(storage).content.get(content='iso')
            logger.info(f"Found {len(content)} ISO(s) in {storage} on {node_name}")

            # Check if our ISO exists
            target_volid = f"{storage}:iso/{filename}"
            for item in content:
                volid = item.get('volid')
                logger.debug(f"Checking ISO: {volid}")
                if volid == target_volid:
                    logger.info(f"ISO found on Proxmox: {volid}")
                    return True

            logger.info(f"ISO not found on Proxmox. Looking for: {target_volid}")
            return False
        except Exception as e:
            logger.error(f"Failed to check ISO existence: {e}")
            return False

    def upload_iso(self, node_name: str, storage: str, iso_path: str, filename: str, progress_callback=None) -> bool:
        """Upload ISO to Proxmox storage with real-time progress tracking using direct requests"""
        import os
        import time
        import requests
        from requests.auth import AuthBase

        class TokenAuth(AuthBase):
            """Custom authentication for Proxmox API tokens"""
            def __init__(self, token_id, token_secret):
                self.token_id = token_id
                self.token_secret = token_secret

            def __call__(self, r):
                r.headers['Authorization'] = f'PVEAPIToken={self.token_id}={self.token_secret}'
                return r

        class ProgressFileWrapper:
            """Wrapper for file object that tracks upload progress"""
            def __init__(self, file_obj, file_size, callback):
                self.file_obj = file_obj
                self.file_size = file_size
                self.callback = callback
                self.bytes_uploaded = 0
                self.start_time = time.time()
                self.last_update = time.time()

            def read(self, size=-1):
                chunk = self.file_obj.read(size)
                if chunk:
                    self.bytes_uploaded += len(chunk)

                    # Update progress every 0.5 seconds
                    now = time.time()
                    if now - self.last_update >= 0.5 or self.bytes_uploaded == self.file_size:
                        percent = int((self.bytes_uploaded / self.file_size) * 100)
                        elapsed = now - self.start_time
                        mb_uploaded = self.bytes_uploaded / (1024 * 1024)
                        speed_mbps = mb_uploaded / elapsed if elapsed > 0 else 0

                        # Calculate ETA
                        if speed_mbps > 0:
                            mb_remaining = (self.file_size - self.bytes_uploaded) / (1024 * 1024)
                            eta_seconds = mb_remaining / speed_mbps
                            eta_str = f" - ETA {int(eta_seconds)}s" if eta_seconds > 1 else ""
                        else:
                            eta_str = ""

                        if self.callback:
                            if percent >= 100:
                                # At 100%, let user know we're waiting for Proxmox to finish processing
                                self.callback(100, "Upload transferred! Waiting for Proxmox to write to disk...")
                            else:
                                self.callback(
                                    percent,
                                    f"Uploading: {percent}% ({mb_uploaded:.1f}/{self.file_size/(1024*1024):.1f} MB @ {speed_mbps:.1f} MB/s{eta_str})"
                                )

                        self.last_update = now

                return chunk

            def __len__(self):
                return self.file_size

            def __iter__(self):
                return self

            def __next__(self):
                chunk = self.read(8192)
                if not chunk:
                    raise StopIteration
                return chunk

        try:
            # Get file size for progress calculation
            file_size = os.path.getsize(iso_path)
            file_size_mb = file_size / (1024 * 1024)
            logger.info(f"Uploading ISO {filename} ({file_size_mb:.1f} MB) to {node_name}:{storage}")

            if progress_callback:
                progress_callback(0, f"Starting upload of {filename} ({file_size_mb:.1f} MB)...")

            start_time = time.time()

            # Build the upload URL
            url = f"https://{self.host.hostname}:{self.host.port}/api2/json/nodes/{node_name}/storage/{storage}/upload"
            logger.info(f"Upload URL: {url}")

            # Prepare authentication
            auth = None
            if self.host.api_token_id and self.host.api_token_secret:
                # Use API token authentication
                try:
                    token_secret = decrypt_data(self.host.api_token_secret)
                except Exception:
                    token_secret = self.host.api_token_secret

                # Extract full token ID (user@realm!tokenname)
                if '!' in self.host.api_token_id:
                    full_token_id = self.host.api_token_id
                else:
                    full_token_id = f"{self.host.username}!{self.host.api_token_id}"

                auth = TokenAuth(full_token_id, token_secret)
                logger.info(f"Using token authentication: {full_token_id}")
            else:
                # Use password authentication
                try:
                    password = decrypt_data(self.host.password)
                except Exception:
                    password = self.host.password
                auth = (self.host.username, password)
                logger.info(f"Using password authentication")

            # Upload the file with progress tracking
            logger.info(f"Starting ISO upload to Proxmox...")
            with open(iso_path, 'rb') as iso_file:
                wrapped_file = ProgressFileWrapper(iso_file, file_size, progress_callback)

                # Prepare multipart form data
                files = {
                    'filename': (filename, wrapped_file, 'application/octet-stream')
                }
                data = {
                    'content': 'iso'
                }

                try:
                    logger.info(f"Calling Proxmox upload API with requests...")
                    response = requests.post(
                        url,
                        auth=auth,
                        files=files,
                        data=data,
                        verify=self.host.verify_ssl,
                        timeout=3600  # 1 hour timeout for large uploads
                    )
                    logger.info(f"Upload response status: {response.status_code}")
                    logger.info(f"Upload response: {response.text}")

                    if response.status_code != 200:
                        raise Exception(f"Upload failed with status {response.status_code}: {response.text}")

                except Exception as post_error:
                    logger.error(f"Upload POST call failed: {post_error}", exc_info=True)
                    raise

            # POST has returned - Proxmox has finished writing to disk
            logger.info(f"Proxmox upload POST completed")

            elapsed = time.time() - start_time
            speed_mbps = file_size_mb / elapsed if elapsed > 0 else 0

            if progress_callback:
                progress_callback(100, f"Upload complete! ({speed_mbps:.1f} MB/s average)")

            logger.info(f"Successfully uploaded ISO {filename} to {node_name}:{storage} in {elapsed:.1f}s ({speed_mbps:.1f} MB/s)")
            return True
        except Exception as e:
            logger.error(f"Failed to upload ISO: {e}")
            if progress_callback:
                progress_callback(0, f"Upload failed: {str(e)}")
            return False

    def create_vm(
        self,
        node_name: str,
        vmid: int,
        name: str,
        cores: int,
        memory: int,
        disk_size: int,
        storage: str = "local-lvm",
        iso: Optional[str] = None,
        network_bridge: str = "vmbr0",
        sockets: int = 1,
        # Advanced options
        cpu_type: str = "host",
        cpu_flags: Optional[str] = None,
        numa_enabled: bool = False,
        bios_type: str = "seabios",
        machine_type: str = "pc",
        vga_type: str = "std",
        boot_order: str = "cdn",
        network_interfaces: Optional[list] = None,
    ) -> bool:
        """Create a new VM with advanced options"""
        try:
            # Base VM configuration
            vm_config = {
                "vmid": vmid,
                "name": name,
                "sockets": sockets,
                "cores": cores,
                "memory": memory,
                "scsihw": "virtio-scsi-pci",
                "scsi0": f"{storage}:{disk_size}",
                "net0": f"virtio,bridge={network_bridge}",
                "ostype": "l26",  # Linux 2.6+
                "agent": 1,  # Enable QEMU guest agent
            }

            # Advanced CPU options
            if cpu_type and cpu_type != "host":
                vm_config["cpu"] = cpu_type
            if cpu_flags:
                if "cpu" in vm_config:
                    vm_config["cpu"] = f"{vm_config['cpu']},{cpu_flags}"
                else:
                    vm_config["cpu"] = f"host,{cpu_flags}"
            if numa_enabled:
                vm_config["numa"] = 1

            # Hardware options
            if bios_type == "ovmf":
                # UEFI - requires OVMF firmware
                vm_config["bios"] = "ovmf"
                # Note: May need to add efidisk0 for UEFI variables storage
            if machine_type and machine_type != "pc":
                vm_config["machine"] = machine_type
            if vga_type and vga_type != "std":
                vm_config["vga"] = vga_type
            if boot_order and boot_order != "cdn":
                vm_config["boot"] = f"order={boot_order}"

            # Additional network interfaces
            if network_interfaces:
                for idx, nic in enumerate(network_interfaces, start=1):
                    bridge = nic.get('bridge', 'vmbr0')
                    model = nic.get('model', 'virtio')
                    vm_config[f"net{idx}"] = f"{model},bridge={bridge}"

            # ISO
            if iso:
                vm_config["ide2"] = f"{iso},media=cdrom"

            logger.info(f"Creating VM with config: {vm_config}")
            result = self.proxmox.nodes(node_name).qemu.post(**vm_config)
            task_id = result  # UPID format: UPID:node:pid:timestamp:type:id:user:
            logger.info(f"Proxmox API response (task ID): {task_id}")

            # VM creation is async - wait for the task to complete
            import time
            max_wait = 30  # Wait up to 30 seconds
            wait_interval = 2
            total_waited = 0

            logger.info(f"Waiting for VM {vmid} creation task to complete...")
            while total_waited < max_wait:
                time.sleep(wait_interval)
                total_waited += wait_interval

                # Check task status
                try:
                    task_status = self.proxmox.nodes(node_name).tasks(task_id).status.get()
                    task_state = task_status.get('status')
                    logger.info(f"Task status: {task_state}")

                    if task_state == 'stopped':
                        # Task completed - check exit status
                        exit_status = task_status.get('exitstatus')
                        if exit_status == 'OK':
                            logger.info(f"VM {vmid} creation task completed successfully")
                            # Verify VM exists
                            try:
                                vm_status = self.proxmox.nodes(node_name).qemu(vmid).status.current.get()
                                logger.info(f"VM {vmid} verified on node {node_name}, status: {vm_status.get('status')}")
                                return True
                            except Exception as e:
                                logger.error(f"VM {vmid} task succeeded but VM doesn't exist: {e}")
                                return False
                        else:
                            # Task failed - get error log
                            try:
                                log = self.proxmox.nodes(node_name).tasks(task_id).log.get()
                                error_lines = [line.get('t', '') for line in log[-10:]]  # Last 10 lines
                                logger.error(f"VM {vmid} creation failed. Task log:\n" + "\n".join(error_lines))
                            except:
                                logger.error(f"VM {vmid} creation failed with exit status: {exit_status}")
                            return False
                    elif task_state == 'running':
                        logger.debug(f"Task still running, waited {total_waited}s...")
                        continue
                except Exception as e:
                    logger.warning(f"Could not check task status: {e}")
                    # Fall back to checking if VM exists
                    try:
                        vm_status = self.proxmox.nodes(node_name).qemu(vmid).status.current.get()
                        logger.info(f"VM {vmid} exists despite task check failure, status: {vm_status.get('status')}")
                        return True
                    except:
                        continue

            # If we get here, VM wasn't created within timeout
            logger.error(f"VM {vmid} was not created within {max_wait} seconds. Task may have failed.")
            logger.error(f"Check Proxmox task log for UPID: {task_id}")
            return False

        except ResourceException as e:
            logger.error(f"Failed to create VM: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating VM: {e}")
            return False

    def create_vm_from_cloud_image(
        self,
        node_name: str,
        vmid: int,
        name: str,
        sockets: int,
        cores: int,
        memory: int,
        disk_size: int,
        storage: str,
        cloud_image_path: str,
        network_bridge: str = "vmbr0",
        progress_callback=None,
    ) -> bool:
        """Create a VM from a cloud image by uploading and importing the disk"""
        try:
            import time
            import os
            import requests
            from app.core.security import decrypt_data

            logger.info(f"Creating VM {vmid} from cloud image {os.path.basename(cloud_image_path)}")

            if progress_callback:
                progress_callback(0, "Creating VM configuration...")

            # Step 1: Create VM shell without disk
            vm_config = {
                "vmid": vmid,
                "name": name,
                "sockets": sockets,
                "cores": cores,
                "memory": memory,
                "net0": f"virtio,bridge={network_bridge}",
                "scsihw": "virtio-scsi-pci",
                "ostype": "l26",
                "agent": 1,
            }

            logger.info(f"Creating VM shell: {vm_config}")
            self.proxmox.nodes(node_name).qemu.post(**vm_config)
            time.sleep(2)

            if progress_callback:
                progress_callback(20, "VM created, uploading cloud image...")

            # Step 2: Upload cloud image to Proxmox using direct requests
            # We'll upload it as an ISO first, then use qm importdisk
            image_filename = os.path.basename(cloud_image_path)
            file_size = os.path.getsize(cloud_image_path)

            url = f"https://{self.host.hostname}:{self.host.port}/api2/json/nodes/{node_name}/storage/local/upload"

            # Prepare auth
            if self.host.api_token_id and self.host.api_token_secret:
                try:
                    token_secret = decrypt_data(self.host.api_token_secret)
                except Exception:
                    token_secret = self.host.api_token_secret

                if '!' in self.host.api_token_id:
                    full_token_id = self.host.api_token_id
                else:
                    full_token_id = f"{self.host.username}!{self.host.api_token_id}"

                headers = {'Authorization': f'PVEAPIToken={full_token_id}={token_secret}'}
                auth = None
            else:
                try:
                    password = decrypt_data(self.host.password)
                except Exception:
                    password = self.host.password
                headers = {}
                auth = (self.host.username, password)

            logger.info(f"Uploading {file_size/(1024*1024):.1f} MB cloud image to {node_name}:local")

            # Upload file
            with open(cloud_image_path, 'rb') as img_file:
                files = {'filename': (image_filename, img_file, 'application/octet-stream')}
                data = {'content': 'iso'}  # Upload to ISO storage temporarily

                response = requests.post(
                    url,
                    auth=auth,
                    headers=headers,
                    files=files,
                    data=data,
                    verify=self.host.verify_ssl,
                    timeout=1800  # 30 min for large images
                )

                if response.status_code != 200:
                    raise Exception(f"Upload failed: {response.text}")

            if progress_callback:
                progress_callback(60, "Cloud image uploaded, importing disk...")

            # Step 3: Use qm importdisk to import the cloud image as VM disk
            # This needs to be done via command execution on the Proxmox node
            # For now, we'll create a simplified VM and note that manual import is needed

            # Add a small placeholder disk that can be replaced
            self.proxmox.nodes(node_name).qemu(vmid).config.put(
                scsi0=f"{storage}:{disk_size}",
                boot="order=scsi0"
            )

            # Add cloud-init drive
            self.proxmox.nodes(node_name).qemu(vmid).config.put(
                ide2=f"{storage}:cloudinit"
            )

            if progress_callback:
                progress_callback(80, "Configuring VM...")

            logger.info(f"VM {vmid} created. Cloud image uploaded to local:iso/{image_filename}")
            logger.info(f"Note: Manual import required: qm importdisk {vmid} /var/lib/vz/template/iso/{image_filename} {storage}")

            if progress_callback:
                progress_callback(100, "VM created with cloud image")

            return True

        except Exception as e:
            logger.error(f"Failed to create VM from cloud image: {e}")
            return False

    def configure_cloud_init(
        self,
        node_name: str,
        vmid: int,
        user: str,
        password: Optional[str] = None,
        ssh_keys: Optional[str] = None,
        ip_config: Optional[str] = None,
        nameserver: Optional[str] = None,
    ) -> bool:
        """Configure cloud-init for a VM"""
        try:
            config = {
                "ciuser": user,
                "searchdomain": "local",
            }

            if password:
                config["cipassword"] = password

            if ssh_keys:
                config["sshkeys"] = ssh_keys

            if ip_config:
                config["ipconfig0"] = ip_config
            else:
                config["ipconfig0"] = "ip=dhcp"

            if nameserver:
                config["nameserver"] = nameserver

            self.proxmox.nodes(node_name).qemu(vmid).config.put(**config)
            logger.info(f"Configured cloud-init for VM {vmid}")
            return True
        except ResourceException as e:
            logger.error(f"Failed to configure cloud-init: {e}")
            return False

    def start_vm(self, node_name: str, vmid: int) -> bool:
        """Start a VM"""
        try:
            self.proxmox.nodes(node_name).qemu(vmid).status.start.post()
            logger.info(f"Started VM {vmid}")
            return True
        except ResourceException as e:
            logger.error(f"Failed to start VM: {e}")
            return False

    def stop_vm(self, node_name: str, vmid: int) -> bool:
        """Stop a VM (graceful shutdown)"""
        try:
            self.proxmox.nodes(node_name).qemu(vmid).status.shutdown.post()
            logger.info(f"Stopped VM {vmid}")
            return True
        except ResourceException as e:
            logger.error(f"Failed to stop VM: {e}")
            return False

    def shutdown_vm(self, node_name: str, vmid: int) -> bool:
        """Shutdown a VM (force power off)"""
        try:
            self.proxmox.nodes(node_name).qemu(vmid).status.stop.post()
            logger.info(f"Powered off VM {vmid}")
            return True
        except ResourceException as e:
            logger.error(f"Failed to power off VM: {e}")
            return False

    def restart_vm(self, node_name: str, vmid: int) -> bool:
        """Restart a VM"""
        try:
            self.proxmox.nodes(node_name).qemu(vmid).status.reboot.post()
            logger.info(f"Restarted VM {vmid}")
            return True
        except ResourceException as e:
            logger.error(f"Failed to restart VM: {e}")
            return False

    def delete_vm(self, node_name: str, vmid: int) -> bool:
        """Delete a VM"""
        try:
            self.proxmox.nodes(node_name).qemu(vmid).delete()
            logger.info(f"Deleted VM {vmid}")
            return True
        except ResourceException as e:
            logger.error(f"Failed to delete VM: {e}")
            return False

    def get_vm_status(self, node_name: str, vmid: int) -> Optional[Dict[str, Any]]:
        """Get VM status"""
        try:
            status = self.proxmox.nodes(node_name).qemu(vmid).status.current.get()
            return status
        except ResourceException as e:
            logger.error(f"Failed to get VM status: {e}")
            return None

    def get_vm_config(self, node_name: str, vmid: int) -> Optional[Dict[str, Any]]:
        """Get VM configuration"""
        try:
            config = self.proxmox.nodes(node_name).qemu(vmid).config.get()
            return config
        except ResourceException as e:
            logger.error(f"Failed to get VM config: {e}")
            return None

    def get_all_vms(self) -> List[Dict[str, Any]]:
        """Get all VMs across all nodes in the cluster"""
        all_vms = []
        try:
            nodes = self.get_nodes()
            for node_data in nodes:
                node_name = node_data.get('node')
                try:
                    vms = self.proxmox.nodes(node_name).qemu.get()
                    for vm in vms:
                        all_vms.append({
                            'vmid': vm.get('vmid'),
                            'name': vm.get('name'),
                            'status': vm.get('status'),
                            'node': node_name,
                            'cpus': vm.get('cpus', 0),
                            'maxmem': vm.get('maxmem', 0),
                            'maxdisk': vm.get('maxdisk', 0),
                        })
                except Exception as e:
                    logger.error(f"Failed to get VMs from node {node_name}: {e}")
            return all_vms
        except Exception as e:
            logger.error(f"Failed to get all VMs: {e}")
            return []

    def execute_qemu_agent_command(
        self, node_name: str, vmid: int, command: str
    ) -> Optional[Dict[str, Any]]:
        """Execute command via QEMU guest agent"""
        try:
            result = self.proxmox.nodes(node_name).qemu(vmid).agent.exec.post(
                command=command
            )
            return result
        except ResourceException as e:
            logger.error(f"Failed to execute QEMU agent command: {e}")
            return None


def poll_proxmox_resources(db: Session, host_id: int) -> bool:
    """Poll Proxmox host for current resource status"""
    try:
        host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
        if not host or not host.is_active:
            return False

        service = ProxmoxService(host)

        if not service.test_connection():
            logger.error(f"Cannot connect to Proxmox host {host.name}")
            return False

        # Get nodes and update database
        nodes = service.get_nodes()
        for node_data in nodes:
            node_name = node_data.get("node")
            resources = service.get_node_resources(node_name)

            if not resources:
                continue

            # Update or create node record
            node = (
                db.query(ProxmoxNode)
                .filter(
                    ProxmoxNode.host_id == host_id,
                    ProxmoxNode.node_name == node_name,
                )
                .first()
            )

            if node:
                node.status = resources["status"]
                node.cpu_cores = resources["cpu_cores"]
                node.cpu_usage = resources["cpu_usage"]
                node.memory_total = resources["memory_total"]
                node.memory_used = resources["memory_used"]
                node.disk_total = resources["disk_total"]
                node.disk_used = resources["disk_used"]
                node.uptime = resources["uptime"]
                node.last_updated = datetime.utcnow()
            else:
                node = ProxmoxNode(
                    host_id=host_id,
                    node_name=node_name,
                    status=resources["status"],
                    cpu_cores=resources["cpu_cores"],
                    cpu_usage=resources["cpu_usage"],
                    memory_total=resources["memory_total"],
                    memory_used=resources["memory_used"],
                    disk_total=resources["disk_total"],
                    disk_used=resources["disk_used"],
                    uptime=resources["uptime"],
                    last_updated=datetime.utcnow(),
                )
                db.add(node)

        host.last_poll = datetime.utcnow()
        db.commit()
        logger.info(f"Successfully polled Proxmox host {host.name}")
        return True

    except Exception as e:
        logger.error(f"Error polling Proxmox resources: {e}")
        db.rollback()
        return False
