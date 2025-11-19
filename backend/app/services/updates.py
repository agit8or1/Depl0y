"""VM update management service"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import VirtualMachine, UpdateLog, OSType
from app.services.proxmox import ProxmoxService
from app.models import ProxmoxHost, ProxmoxNode
import paramiko
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class UpdateService:
    """Service for managing VM updates"""

    def __init__(self, db: Session):
        self.db = db

    def _get_ssh_client(self, vm: VirtualMachine) -> Optional[paramiko.SSHClient]:
        """Create SSH connection to VM"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if vm.ssh_key:
                # Use SSH key authentication
                from io import StringIO
                key_file = StringIO(vm.ssh_key)
                pkey = paramiko.RSAKey.from_private_key(key_file)
                client.connect(
                    hostname=vm.ip_address,
                    username=vm.username,
                    pkey=pkey,
                    timeout=30,
                )
            else:
                # Use password authentication
                client.connect(
                    hostname=vm.ip_address,
                    username=vm.username,
                    password=vm.password,
                    timeout=30,
                )

            return client

        except Exception as e:
            logger.error(f"Failed to connect to VM via SSH: {e}")
            return None

    def _get_update_commands(self, os_type: OSType) -> Dict[str, str]:
        """Get update commands for different OS types"""
        commands = {
            OSType.UBUNTU: {
                "update": "sudo apt-get update",
                "upgrade": "sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
                "check": "apt list --upgradable",
            },
            OSType.DEBIAN: {
                "update": "sudo apt-get update",
                "upgrade": "sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
                "check": "apt list --upgradable",
            },
            OSType.CENTOS: {
                "update": "sudo yum check-update",
                "upgrade": "sudo yum update -y",
                "check": "yum list updates",
            },
            OSType.ROCKY: {
                "update": "sudo dnf check-update",
                "upgrade": "sudo dnf update -y",
                "check": "dnf list updates",
            },
            OSType.ALMA: {
                "update": "sudo dnf check-update",
                "upgrade": "sudo dnf update -y",
                "check": "dnf list updates",
            },
        }

        return commands.get(os_type, commands[OSType.UBUNTU])

    def check_updates(self, vm_id: int) -> Optional[Dict[str, Any]]:
        """Check for available updates"""
        try:
            vm = self.db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
            if not vm:
                logger.error(f"VM {vm_id} not found")
                return None

            if not vm.ip_address:
                logger.error(f"VM {vm_id} has no IP address")
                return None

            client = self._get_ssh_client(vm)
            if not client:
                return None

            commands = self._get_update_commands(vm.os_type)

            # Update package lists
            stdin, stdout, stderr = client.exec_command(commands["update"])
            stdout.channel.recv_exit_status()  # Wait for command to complete

            # Check for updates
            stdin, stdout, stderr = client.exec_command(commands["check"])
            output = stdout.read().decode()
            exit_status = stdout.channel.recv_exit_status()

            client.close()

            # Parse output to count available updates
            lines = output.strip().split("\n")
            update_count = len([line for line in lines if line.strip()])

            return {
                "updates_available": update_count,
                "output": output,
            }

        except Exception as e:
            logger.error(f"Failed to check updates: {e}")
            return None

    def install_updates(self, vm_id: int, user_id: int) -> Optional[int]:
        """
        Install updates on a VM

        Args:
            vm_id: Database ID of the VM
            user_id: User initiating the update

        Returns:
            Update log ID if successful, None otherwise
        """
        try:
            vm = self.db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
            if not vm:
                logger.error(f"VM {vm_id} not found")
                return None

            if not vm.ip_address:
                logger.error(f"VM {vm_id} has no IP address")
                return None

            # Create update log
            update_log = UpdateLog(
                vm_id=vm_id,
                initiated_by=user_id,
                status="running",
                started_at=datetime.utcnow(),
            )
            self.db.add(update_log)
            self.db.commit()

            try:
                client = self._get_ssh_client(vm)
                if not client:
                    raise Exception("Failed to connect via SSH")

                commands = self._get_update_commands(vm.os_type)

                # Update package lists
                logger.info(f"Updating package lists on VM {vm_id}")
                stdin, stdout, stderr = client.exec_command(commands["update"])
                stdout.channel.recv_exit_status()

                # Install updates
                logger.info(f"Installing updates on VM {vm_id}")
                stdin, stdout, stderr = client.exec_command(commands["upgrade"])
                output = stdout.read().decode()
                error_output = stderr.read().decode()
                exit_status = stdout.channel.recv_exit_status()

                client.close()

                if exit_status != 0:
                    raise Exception(f"Update failed with exit code {exit_status}")

                # Update log
                update_log.status = "completed"
                update_log.output = output
                update_log.completed_at = datetime.utcnow()

                # Try to count packages updated (rough estimate)
                if "ubuntu" in vm.os_type.value or "debian" in vm.os_type.value:
                    packages_updated = output.count("Setting up")
                else:
                    packages_updated = output.count("Installed") + output.count("Updated")

                update_log.packages_updated = packages_updated
                self.db.commit()

                logger.info(f"Successfully installed updates on VM {vm_id}")
                return update_log.id

            except Exception as e:
                logger.error(f"Failed to install updates: {e}")
                update_log.status = "failed"
                update_log.error_message = str(e)
                update_log.completed_at = datetime.utcnow()
                self.db.commit()
                return None

        except Exception as e:
            logger.error(f"Failed to create update log: {e}")
            return None

    def get_update_history(self, vm_id: int) -> list:
        """Get update history for a VM"""
        try:
            logs = (
                self.db.query(UpdateLog)
                .filter(UpdateLog.vm_id == vm_id)
                .order_by(UpdateLog.started_at.desc())
                .all()
            )
            return logs
        except Exception as e:
            logger.error(f"Failed to get update history: {e}")
            return []

    def install_qemu_agent(self, vm_id: int) -> bool:
        """Install QEMU guest agent on a VM if not already installed"""
        try:
            vm = self.db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
            if not vm or not vm.ip_address:
                return False

            client = self._get_ssh_client(vm)
            if not client:
                return False

            # Determine package name based on OS
            if vm.os_type in [OSType.UBUNTU, OSType.DEBIAN]:
                install_cmd = "sudo apt-get install -y qemu-guest-agent"
                start_cmd = "sudo systemctl start qemu-guest-agent"
                enable_cmd = "sudo systemctl enable qemu-guest-agent"
            elif vm.os_type in [OSType.CENTOS]:
                install_cmd = "sudo yum install -y qemu-guest-agent"
                start_cmd = "sudo systemctl start qemu-guest-agent"
                enable_cmd = "sudo systemctl enable qemu-guest-agent"
            elif vm.os_type in [OSType.ROCKY, OSType.ALMA]:
                install_cmd = "sudo dnf install -y qemu-guest-agent"
                start_cmd = "sudo systemctl start qemu-guest-agent"
                enable_cmd = "sudo systemctl enable qemu-guest-agent"
            else:
                logger.error(f"Unsupported OS type for QEMU agent installation: {vm.os_type}")
                return False

            # Install
            stdin, stdout, stderr = client.exec_command(install_cmd)
            exit_status = stdout.channel.recv_exit_status()

            if exit_status != 0:
                logger.error(f"Failed to install QEMU agent: {stderr.read().decode()}")
                return False

            # Start
            stdin, stdout, stderr = client.exec_command(start_cmd)
            stdout.channel.recv_exit_status()

            # Enable on boot
            stdin, stdout, stderr = client.exec_command(enable_cmd)
            stdout.channel.recv_exit_status()

            client.close()

            logger.info(f"Successfully installed QEMU guest agent on VM {vm_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to install QEMU agent: {e}")
            return False
