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

    def _get_ssh_password(self, vm: VirtualMachine) -> Optional[str]:
        """Return decrypted password, falling back to raw value for legacy records"""
        if not vm.password:
            return None
        try:
            from app.core.security import decrypt_data
            return decrypt_data(vm.password)
        except Exception:
            return vm.password  # legacy unencrypted

    def _connect_ssh(self, ip: str, username: str, password: Optional[str], ssh_key: Optional[str] = None) -> Optional[paramiko.SSHClient]:
        """Create SSH connection with explicit credentials"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if ssh_key:
                from io import StringIO
                pkey = paramiko.RSAKey.from_private_key(StringIO(ssh_key))
                client.connect(hostname=ip, username=username, pkey=pkey, timeout=30)
            else:
                client.connect(hostname=ip, username=username, password=password, timeout=30)
            return client
        except Exception as e:
            logger.error(f"SSH connection to {ip} failed: {e}")
            return None

    def _get_ssh_client(self, vm: VirtualMachine, override_ip: str = None, override_user: str = None, override_pass: str = None) -> Optional[paramiko.SSHClient]:
        """Create SSH connection to VM, using overrides if provided"""
        ip = override_ip or vm.ip_address
        username = override_user or vm.username
        password = override_pass or self._get_ssh_password(vm)
        if not ip:
            logger.error(f"No IP address for VM {vm.id}")
            return None
        return self._connect_ssh(ip, username, password, vm.ssh_key if not override_pass else None)

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

    def check_updates(self, vm_id: int, override_ip: str = None, override_user: str = None, override_pass: str = None) -> Optional[Dict[str, Any]]:
        """Check for available updates"""
        try:
            vm = self.db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
            if not vm:
                logger.error(f"VM {vm_id} not found")
                return None

            client = self._get_ssh_client(vm, override_ip, override_user, override_pass)
            if not client:
                return None

            commands = self._get_update_commands(vm.os_type)

            stdin, stdout, stderr = client.exec_command(commands["update"])
            stdout.channel.recv_exit_status()

            stdin, stdout, stderr = client.exec_command(commands["check"])
            output = stdout.read().decode()
            stdout.channel.recv_exit_status()
            client.close()

            lines = output.strip().split("\n")
            update_count = len([line for line in lines if line.strip()])

            return {
                "updates_available": update_count,
                "output": output,
                "checked_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to check updates: {e}")
            return None

    def install_updates(self, vm_id: int, user_id: int, override_ip: str = None, override_user: str = None, override_pass: str = None) -> Optional[int]:
        """Install updates on a VM"""
        try:
            vm = self.db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
            if not vm:
                logger.error(f"VM {vm_id} not found")
                return None

            ip = override_ip or vm.ip_address
            if not ip:
                logger.error(f"VM {vm_id} has no IP address")
                return None

            update_log = UpdateLog(
                vm_id=vm_id,
                initiated_by=user_id,
                status="running",
                started_at=datetime.utcnow(),
            )
            self.db.add(update_log)
            self.db.commit()

            try:
                client = self._get_ssh_client(vm, override_ip, override_user, override_pass)
                if not client:
                    raise Exception("Failed to connect via SSH")

                commands = self._get_update_commands(vm.os_type)

                logger.info(f"Updating package lists on VM {vm_id}")
                stdin, stdout, stderr = client.exec_command(commands["update"])
                stdout.channel.recv_exit_status()

                logger.info(f"Installing updates on VM {vm_id}")
                stdin, stdout, stderr = client.exec_command(commands["upgrade"])
                output = stdout.read().decode()
                error_output = stderr.read().decode()
                exit_status = stdout.channel.recv_exit_status()
                client.close()

                if exit_status != 0:
                    raise Exception(f"Update failed with exit code {exit_status}")

                update_log.status = "completed"
                update_log.output = output
                update_log.completed_at = datetime.utcnow()

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

    def scan_security(self, vm_id: int, override_ip: str = None, override_user: str = None, override_pass: str = None) -> Dict[str, Any]:
        """Run security and dependency scan on a VM via SSH"""
        try:
            vm = self.db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
            if not vm:
                return {"error": "VM not found"}

            client = self._get_ssh_client(vm, override_ip, override_user, override_pass)
            if not client:
                return {"error": "SSH connection failed — check IP and credentials"}

            results = {}

            def run(cmd, timeout=30):
                try:
                    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
                    out = stdout.read().decode("utf-8", errors="replace").strip()
                    stdout.channel.recv_exit_status()
                    return out
                except Exception:
                    return ""

            # OS security updates (apt-based; graceful for other distros)
            run("apt-get update -qq 2>/dev/null; true")
            upgradable_raw = run("apt list --upgradable 2>/dev/null | tail -n +2")
            pkgs = [l.strip() for l in upgradable_raw.split("\n") if l.strip()]
            security_pkgs = [p for p in pkgs if "security" in p.lower()]
            results["os_updates"] = {
                "total_upgradable": len(pkgs),
                "security_updates": len(security_pkgs),
                "security_packages": security_pkgs[:20],
            }

            # Open listening ports
            ports_raw = run("ss -tlnp 2>/dev/null | tail -n +2 | head -25")
            results["open_ports"] = [l.strip() for l in ports_raw.split("\n") if l.strip()] if ports_raw else []

            # Failed SSH login attempts
            failed_raw = run("grep -c 'Failed password' /var/log/auth.log 2>/dev/null || echo 0")
            try:
                results["failed_ssh_attempts"] = int(failed_raw)
            except ValueError:
                results["failed_ssh_attempts"] = 0

            # Python outdated packages
            pip_raw = run("pip3 list --outdated --format=columns 2>/dev/null | tail -n +3 | head -20")
            pip_lines = [l.strip() for l in pip_raw.split("\n") if l.strip()] if pip_raw else []
            results["python_outdated"] = {
                "count": len(pip_lines),
                "packages": pip_lines[:15],
            }

            # npm outdated global packages
            npm_raw = run("npm outdated -g --parseable 2>/dev/null | head -15")
            npm_lines = [l.strip() for l in npm_raw.split("\n") if l.strip()] if npm_raw else []
            results["npm_outdated"] = {
                "count": len(npm_lines),
                "packages": npm_lines[:10],
            }

            client.close()

            # Overall severity
            sec = results["os_updates"]["security_updates"]
            failed = results["failed_ssh_attempts"]
            if sec > 10 or failed > 100:
                severity = "critical"
            elif sec > 0 or failed > 10:
                severity = "warning"
            else:
                severity = "ok"

            results["severity"] = severity
            results["scanned_at"] = datetime.utcnow().isoformat()
            return results

        except Exception as e:
            logger.error(f"Security scan failed for VM {vm_id}: {e}")
            return {"error": str(e)}

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
                logger.error(f"Unsupported OS type for QEMU agent: {vm.os_type}")
                return False

            stdin, stdout, stderr = client.exec_command(install_cmd)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                logger.error(f"Failed to install QEMU agent: {stderr.read().decode()}")
                return False

            client.exec_command(start_cmd)[1].channel.recv_exit_status()
            client.exec_command(enable_cmd)[1].channel.recv_exit_status()
            client.close()
            logger.info(f"Successfully installed QEMU guest agent on VM {vm_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to install QEMU agent: {e}")
            return False
