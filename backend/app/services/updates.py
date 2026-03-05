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

    def _sudo_exec(self, client: paramiko.SSHClient, cmd: str, password: Optional[str] = None):
        """Execute a sudo command, supplying password via stdin (sudo -S) when available.

        Works with both NOPASSWD sudo (password is ignored) and password-required sudo.
        """
        stdin, stdout, stderr = client.exec_command(f"sudo -S {cmd}")
        if password:
            stdin.write((password + "\n").encode())
            stdin.flush()
            stdin.channel.shutdown_write()
        return stdin, stdout, stderr

    def _get_update_commands(self, os_type: OSType) -> Dict[str, str]:
        """Get update commands for different OS types (without sudo prefix — use _sudo_exec)"""
        commands = {
            OSType.UBUNTU: {
                "update": "apt-get update -qq 2>/dev/null",
                "upgrade": "DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
                "check": "apt list --upgradable 2>/dev/null",
            },
            OSType.DEBIAN: {
                "update": "apt-get update -qq 2>/dev/null",
                "upgrade": "DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
                "check": "apt list --upgradable 2>/dev/null",
            },
            OSType.CENTOS: {
                "update": "yum check-update 2>/dev/null; true",
                "upgrade": "yum update -y",
                "check": "yum list updates 2>/dev/null",
            },
            OSType.ROCKY: {
                "update": "dnf check-update 2>/dev/null; true",
                "upgrade": "dnf update -y",
                "check": "dnf list updates 2>/dev/null",
            },
            OSType.ALMA: {
                "update": "dnf check-update 2>/dev/null; true",
                "upgrade": "dnf update -y",
                "check": "dnf list updates 2>/dev/null",
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

            actual_password = override_pass or self._get_ssh_password(vm)
            commands = self._get_update_commands(vm.os_type)

            # Refresh package cache
            _, stdout, _ = self._sudo_exec(client, commands["update"], actual_password)
            stdout.channel.recv_exit_status()

            # List upgradable (no sudo needed)
            _, stdout, _ = client.exec_command(commands["check"])
            output = stdout.read().decode()
            stdout.channel.recv_exit_status()
            client.close()

            lines = [l for l in output.strip().split("\n") if l.strip() and not l.startswith("Listing...")]
            update_count = len(lines)

            return {
                "updates_available": update_count,
                "output": output,
                "checked_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to check updates: {e}")
            return None

    def install_updates(self, vm_id: int, user_id: int, override_ip: str = None, override_user: str = None, override_pass: str = None) -> Optional[int]:
        """Install updates on a VM.

        NOTE: Intended to be called from a background task that owns its own DB session.
        """
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
            self.db.refresh(update_log)

            try:
                actual_password = override_pass or self._get_ssh_password(vm)
                client = self._get_ssh_client(vm, override_ip, override_user, override_pass)
                if not client:
                    raise Exception("Failed to connect via SSH")

                commands = self._get_update_commands(vm.os_type)

                logger.info(f"Refreshing package lists on VM {vm_id}")
                _, stdout, _ = self._sudo_exec(client, commands["update"], actual_password)
                stdout.channel.recv_exit_status()

                logger.info(f"Installing updates on VM {vm_id}")
                _, stdout, stderr = self._sudo_exec(client, commands["upgrade"], actual_password)

                # Stream output line-by-line and commit incrementally so the
                # frontend polling endpoint can show real-time progress.
                output_lines = []
                flush_count = 0
                for line in stdout:
                    output_lines.append(line)
                    flush_count += 1
                    if flush_count >= 4:
                        update_log.output = "".join(output_lines)
                        try:
                            self.db.commit()
                        except Exception:
                            pass
                        flush_count = 0

                output = "".join(output_lines)
                error_output = stderr.read().decode()
                exit_status = stdout.channel.recv_exit_status()
                client.close()

                # sudo -S writes a password prompt to stderr even on success — filter it
                real_errors = "\n".join(
                    l for l in error_output.splitlines()
                    if l.strip() and not l.startswith("[sudo]") and "password for" not in l.lower()
                )

                if exit_status != 0:
                    raise Exception(f"Update failed (exit {exit_status}): {real_errors or 'check VM logs'}")

                update_log.status = "completed"
                update_log.output = output
                update_log.completed_at = datetime.utcnow()

                if "ubuntu" in vm.os_type.value or "debian" in vm.os_type.value:
                    packages_updated = output.count("Setting up")
                else:
                    packages_updated = output.count("Installed") + output.count("Updated")

                update_log.packages_updated = packages_updated
                self.db.commit()

                logger.info(f"Successfully installed updates on VM {vm_id} ({packages_updated} packages)")
                return update_log.id

            except Exception as e:
                logger.error(f"Failed to install updates on VM {vm_id}: {e}")
                update_log.status = "failed"
                update_log.error_message = str(e)
                update_log.completed_at = datetime.utcnow()
                self.db.commit()
                return None

        except Exception as e:
            logger.error(f"Failed to create update log for VM {vm_id}: {e}")
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

            # OS security updates
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

            actual_password = self._get_ssh_password(vm)

            if vm.os_type in [OSType.UBUNTU, OSType.DEBIAN]:
                install_cmd = "apt-get install -y qemu-guest-agent"
            elif vm.os_type in [OSType.CENTOS]:
                install_cmd = "yum install -y qemu-guest-agent"
            elif vm.os_type in [OSType.ROCKY, OSType.ALMA]:
                install_cmd = "dnf install -y qemu-guest-agent"
            else:
                logger.error(f"Unsupported OS type for QEMU agent: {vm.os_type}")
                return False

            _, stdout, stderr = self._sudo_exec(client, install_cmd, actual_password)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                logger.error(f"Failed to install QEMU agent: {stderr.read().decode()}")
                return False

            self._sudo_exec(client, "systemctl start qemu-guest-agent", actual_password)[1].channel.recv_exit_status()
            self._sudo_exec(client, "systemctl enable qemu-guest-agent", actual_password)[1].channel.recv_exit_status()
            client.close()
            logger.info(f"Successfully installed QEMU guest agent on VM {vm_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to install QEMU agent: {e}")
            return False
