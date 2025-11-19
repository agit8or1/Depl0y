"""Cloud-init configuration service"""
import yaml
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


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
            "disable_root": True,
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
            user_config["password"] = password
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
        config["runcmd"].extend([
            "systemctl enable ssh",
            "systemctl start ssh",
        ])

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
