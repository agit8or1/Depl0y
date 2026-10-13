"""Cloud-init configuration service"""
import yaml
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SSH password-authentication enablement
#
# Ubuntu 22.04/24.04 (and Debian 12) cloud images ship
# /etc/ssh/sshd_config.d/60-cloudimg-settings.conf containing
# "PasswordAuthentication no".  /etc/ssh/sshd_config has its
# "Include /etc/ssh/sshd_config.d/*.conf" line at the TOP of the file and sshd
# uses first-directive-wins, so the drop-in always beats anything written into
# the main config.  Editing /etc/ssh/sshd_config alone (what depl0y used to do)
# therefore has no effect on Ubuntu 24.04 and password logins stay disabled.
#
# Fix: strip the auth directives from every drop-in, then write our own drop-in
# that sorts first (00-), and only then touch the main config as a belt-and-
# braces fallback for images without an Include line.
#
# Keep these strings free of "{" / "}" - deployment.py interpolates them into an
# f-string.
# ---------------------------------------------------------------------------
SSH_AUTH_DROPIN = "/etc/ssh/sshd_config.d/00-depl0y-ssh.conf"

SSH_PASSWORD_AUTH_RUNCMD = [
    # 1. Remove conflicting directives from every shipped drop-in
    #    (60-cloudimg-settings.conf, 50-cloud-init.conf, vendor files, ...).
    "sed -ri '/^[[:space:]]*#?[[:space:]]*(PasswordAuthentication|PermitRootLogin|KbdInteractiveAuthentication|ChallengeResponseAuthentication)[[:space:]]/d' /etc/ssh/sshd_config.d/*.conf 2>/dev/null || true",
    # 2. Our own drop-in, sorted first so it wins under first-match-wins.
    "mkdir -p /etc/ssh/sshd_config.d",
    "printf 'PasswordAuthentication yes\\nPubkeyAuthentication yes\\nPermitRootLogin yes\\nKbdInteractiveAuthentication no\\n' > " + SSH_AUTH_DROPIN,
    "chmod 644 " + SSH_AUTH_DROPIN,
    # 3. Fallback for images whose sshd_config has no Include line.
    "sed -ri 's/^[[:space:]]*#?[[:space:]]*PasswordAuthentication[[:space:]].*/PasswordAuthentication yes/' /etc/ssh/sshd_config",
    "sed -ri 's/^[[:space:]]*#?[[:space:]]*PubkeyAuthentication[[:space:]].*/PubkeyAuthentication yes/' /etc/ssh/sshd_config",
    "sed -ri 's/^[[:space:]]*#?[[:space:]]*PermitRootLogin[[:space:]].*/PermitRootLogin yes/' /etc/ssh/sshd_config",
    "grep -q '^PasswordAuthentication yes' /etc/ssh/sshd_config || echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config",
    # 4. Reload, never restart.  Ubuntu 24.04 is socket-activated: the first connection
    #    starts ssh.service, whose sshd then holds port 22.  Restarting ssh.socket/ssh
    #    while that listener runs orphans it, the socket cannot bind again, and every
    #    later login is reset ("Missing privilege separation directory").  A reload
    #    (SIGHUP) re-reads the config safely in both socket and classic mode; if no
    #    listener runs yet, the next connection reads the new config anyway.
    #    Validate first so a bad edit cannot take SSH down.
    "sshd -t && (systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null) || true",
]

# Start SSH only when nothing serves it yet (the socket on Ubuntu 24.04, the service
# elsewhere). Starting ssh.service next to an active ssh.socket fights over port 22.
SSH_ENSURE_RUNNING = (
    "systemctl is-active --quiet ssh.socket || systemctl is-active --quiet ssh || "
    "systemctl is-active --quiet sshd || systemctl enable --now ssh 2>/dev/null || "
    "systemctl enable --now sshd 2>/dev/null || true"
)


SSH_AUTH_DROPIN_CONTENT = (
    "PasswordAuthentication yes\n"
    "PubkeyAuthentication yes\n"
    "PermitRootLogin yes\n"
    "KbdInteractiveAuthentication no\n"
)

# Full upgrade, run as the last base runcmd step (after SSH and the guest agent are up).
# --force-confold keeps our edited sshd_config when openssh-server is upgraded.
UPGRADE_CMD = (
    "if command -v apt-get >/dev/null 2>&1; then DEBIAN_FRONTEND=noninteractive apt-get -y "
    "-o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold dist-upgrade; "
    "elif command -v dnf >/dev/null 2>&1; then dnf -y upgrade; "
    "elif command -v yum >/dev/null 2>&1; then yum -y update; fi || true"
)


def build_deploy_user_data(hostname: str, username: str, password: Optional[str],
                           ssh_keys: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> str:
    """User-data for a VM deployed from a cloud image (uploaded as the cicustom snippet).

    The snippet replaces Proxmox's generated user-data, so it has to carry everything:
    hostname, user, password, SSH keys. Order matters for how fast the VM is usable:
    cloud-init runs `runcmd` only after the package module, so the package module only
    installs the guest agent and SSH server (seconds), and the slow full upgrade runs
    later from runcmd, once SSH works and the agent reports the VM's IP.
    """
    extra = extra if isinstance(extra, dict) else {}
    user = {
        "name": username,
        "gecos": username,
        "sudo": "ALL=(ALL) NOPASSWD:ALL",
        "groups": "users, admin, sudo",
        "shell": "/bin/bash",
        "lock_passwd": not password,
    }
    keys = [k.strip() for k in (ssh_keys or "").splitlines() if k.strip()]
    if keys:
        user["ssh_authorized_keys"] = keys

    packages = ["qemu-guest-agent", "openssh-server"]
    packages += [p for p in extra.get("extra_packages", []) if p not in packages]

    config: Dict[str, Any] = {
        "hostname": hostname,
        "fqdn": f"{hostname}.local",
        "manage_etc_hosts": True,
        "users": [user],
    }
    if password:
        config["chpasswd"] = {"list": f"{username}:{password}\n", "expire": False}
    config.update({
        "disable_root": False,
        "ssh_pwauth": bool(password),
        # Written early in boot, so password logins work as soon as sshd answers.
        "write_files": [{"path": SSH_AUTH_DROPIN, "permissions": "0644", "content": SSH_AUTH_DROPIN_CONTENT}]
                       + list(extra.get("write_files", [])),
        "package_update": True,
        "package_upgrade": False,
        "packages": packages,
        "runcmd": [
            "systemctl enable --now qemu-guest-agent",
            SSH_ENSURE_RUNNING,
            *SSH_PASSWORD_AUTH_RUNCMD,
            UPGRADE_CMD,
            *extra.get("extra_runcmd", []),
        ],
    })
    return "#cloud-config\n" + yaml.safe_dump(config, default_flow_style=False, sort_keys=False, width=10000)


class CloudInitService:
    """Service for generating cloud-init configurations"""

    @staticmethod
    def generate_user_data(
        hostname: str,
        username: str,
        password: Optional[str] = None,
        ssh_keys: Optional[List[str]] = None,
        packages: Optional[List[str]] = None,
        install_qemu_agent: bool = True,
        timezone: str = "UTC",
        additional_commands: Optional[List[str]] = None,
    ) -> str:
        """
        Generate cloud-init user-data configuration

        Args:
            hostname: VM hostname
            username: Default user username
            password: User password (will be hashed by cloud-init)
            ssh_keys: List of SSH public keys
            packages: Additional packages to install
            install_qemu_agent: Install QEMU guest agent
            timezone: System timezone
            additional_commands: Additional commands to run

        Returns:
            YAML formatted user-data string
        """
        config = {
            "hostname": hostname,
            "fqdn": f"{hostname}.local",
            "manage_etc_hosts": True,
            "timezone": timezone,
            "users": [],
            "ssh_pwauth": True if password else False,
            "disable_root": False if password else True,
            "package_update": True,
            "package_upgrade": True,
            "packages": packages or [],
            "runcmd": additional_commands or [],
        }

        # Configure default user
        user_config = {
            "name": username,
            "groups": ["sudo", "users", "admin"],
            "shell": "/bin/bash",
            "sudo": ["ALL=(ALL) NOPASSWD:ALL"],
        }

        if password:
            # Use chpasswd for plain text password
            config["chpasswd"] = {
                "expire": False,
                "list": [f"{username}:{password}"]
            }
            user_config["lock_passwd"] = False
        else:
            user_config["lock_passwd"] = True

        if ssh_keys:
            user_config["ssh_authorized_keys"] = ssh_keys

        config["users"].append(user_config)

        # Add QEMU guest agent installation
        if install_qemu_agent:
            if "qemu-guest-agent" not in config["packages"]:
                config["packages"].append("qemu-guest-agent")

            # Ensure agent starts on boot
            config["runcmd"].extend([
                "systemctl enable qemu-guest-agent",
                "systemctl start qemu-guest-agent",
            ])

        # Add SSH server if not present
        if "openssh-server" not in config["packages"]:
            config["packages"].append("openssh-server")

        # Ensure SSH is enabled
        config["runcmd"].append(SSH_ENSURE_RUNNING)

        # Make password logins actually work on Ubuntu 22.04/24.04 cloud images
        if password:
            config["runcmd"].extend(SSH_PASSWORD_AUTH_RUNCMD)

        # Generate YAML with cloud-config header
        user_data = "#cloud-config\n" + yaml.dump(
            config, default_flow_style=False, sort_keys=False
        )

        return user_data

    @staticmethod
    def generate_network_config(
        use_dhcp: bool = True,
        ip_address: Optional[str] = None,
        netmask: Optional[str] = None,
        gateway: Optional[str] = None,
        nameservers: Optional[List[str]] = None,
        interface: str = "eth0",
    ) -> str:
        """
        Generate cloud-init network configuration

        Args:
            use_dhcp: Use DHCP for network configuration
            ip_address: Static IP address
            netmask: Network mask
            gateway: Default gateway
            nameservers: DNS nameservers
            interface: Network interface name

        Returns:
            YAML formatted network config string
        """
        if use_dhcp:
            config = {
                "version": 2,
                "ethernets": {
                    interface: {
                        "dhcp4": True,
                        "dhcp6": False,
                    }
                },
            }
        else:
            if not all([ip_address, netmask, gateway]):
                raise ValueError(
                    "Static IP configuration requires ip_address, netmask, and gateway"
                )

            config = {
                "version": 2,
                "ethernets": {
                    interface: {
                        "dhcp4": False,
                        "dhcp6": False,
                        "addresses": [f"{ip_address}/{netmask}"],
                        "gateway4": gateway,
                    }
                },
            }

            if nameservers:
                config["ethernets"][interface]["nameservers"] = {
                    "addresses": nameservers
                }

        return yaml.dump(config, default_flow_style=False, sort_keys=False)

    @staticmethod
    def generate_meta_data(
        instance_id: str,
        hostname: str,
    ) -> str:
        """
        Generate cloud-init meta-data

        Args:
            instance_id: Unique instance identifier
            hostname: VM hostname

        Returns:
            YAML formatted meta-data string
        """
        config = {
            "instance-id": instance_id,
            "local-hostname": hostname,
        }

        return yaml.dump(config, default_flow_style=False, sort_keys=False)

    @staticmethod
    def generate_partition_config(
        disk_device: str = "/dev/sda",
        scheme: str = "single",
    ) -> Dict[str, Any]:
        """
        Generate disk partition configuration for cloud-init

        Args:
            disk_device: Disk device path
            scheme: Partitioning scheme (single or custom)

        Returns:
            Partition configuration dictionary
        """
        if scheme == "single":
            # Single large partition with necessary boot partitions
            return {
                "layout": {
                    "name": "direct",
                    "match": {
                        "serial": "*",
                    },
                },
                "partitions": [
                    {
                        "id": "boot-partition",
                        "type": "partition",
                        "device": disk_device,
                        "size": "512M",
                        "flag": "boot",
                        "grub_device": True,
                    },
                    {
                        "id": "root-partition",
                        "type": "partition",
                        "device": disk_device,
                        "size": "-1",  # Use remaining space
                    },
                ],
                "filesystems": [
                    {
                        "id": "boot-fs",
                        "type": "ext4",
                        "partition": "boot-partition",
                    },
                    {
                        "id": "root-fs",
                        "type": "ext4",
                        "partition": "root-partition",
                    },
                ],
                "mounts": [
                    ["boot-fs", "/boot"],
                    ["root-fs", "/"],
                ],
            }
        else:
            # Custom scheme - can be extended based on requirements
            return {
                "layout": "lvm",
                "partitions": [],
            }

    @staticmethod
    def create_complete_config(
        hostname: str,
        username: str,
        password: Optional[str] = None,
        ssh_keys: Optional[List[str]] = None,
        use_dhcp: bool = True,
        ip_address: Optional[str] = None,
        netmask: Optional[str] = None,
        gateway: Optional[str] = None,
        nameservers: Optional[List[str]] = None,
        packages: Optional[List[str]] = None,
        install_qemu_agent: bool = True,
        partition_scheme: str = "single",
    ) -> Dict[str, str]:
        """
        Create complete cloud-init configuration with user-data, meta-data, and network-config

        Returns:
            Dictionary with 'user_data', 'meta_data', and 'network_config' keys
        """
        instance_id = f"depl0y-{hostname}"

        user_data = CloudInitService.generate_user_data(
            hostname=hostname,
            username=username,
            password=password,
            ssh_keys=ssh_keys,
            packages=packages,
            install_qemu_agent=install_qemu_agent,
        )

        meta_data = CloudInitService.generate_meta_data(
            instance_id=instance_id,
            hostname=hostname,
        )

        network_config = CloudInitService.generate_network_config(
            use_dhcp=use_dhcp,
            ip_address=ip_address,
            netmask=netmask,
            gateway=gateway,
            nameservers=nameservers,
        )

        return {
            "user_data": user_data,
            "meta_data": meta_data,
            "network_config": network_config,
        }
