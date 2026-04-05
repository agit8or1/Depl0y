"""
Database models for Depl0y
"""
from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text, Enum, JSON, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    """User role enumeration"""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class VMStatus(str, enum.Enum):
    """VM status enumeration"""
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    DELETING = "deleting"


class OSType(str, enum.Enum):
    """Operating system type"""
    # Linux Server
    UBUNTU = "ubuntu"
    DEBIAN = "debian"
    CENTOS = "centos"
    ROCKY = "rocky"
    ALMA = "alma"

    # Windows
    WINDOWS_SERVER_2016 = "windows_server_2016"
    WINDOWS_SERVER_2019 = "windows_server_2019"
    WINDOWS_SERVER_2022 = "windows_server_2022"
    WINDOWS_10 = "windows_10"
    WINDOWS_11 = "windows_11"

    # Firewalls
    PFSENSE = "pfsense"
    OPNSENSE = "opnsense"
    SOPHOS = "sophos"
    FORTINET = "fortinet"
    VYOS = "vyos"

    # Other
    FREEBSD = "freebsd"
    TRUENAS = "truenas"
    PROXMOX = "proxmox"
    ESXI = "esxi"
    OTHER = "other"


class User(Base):
    """User model"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.VIEWER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    totp_secret = Column(String(32), nullable=True)  # For 2FA
    totp_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    token_version = Column(Integer, default=0, nullable=False)

    # Relationships
    vms = relationship("VirtualMachine", back_populates="created_by_user")
    audit_logs = relationship("AuditLog", back_populates="user")


class ProxmoxHost(Base):
    """Proxmox VE host configuration"""
    __tablename__ = "proxmox_hosts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    hostname = Column(String(255), nullable=False)
    port = Column(Integer, default=8006, nullable=False)
    username = Column(String(100), nullable=False)
    password = Column(String(255), nullable=True)  # Encrypted (optional if using token)
    api_token_id = Column(String(100), nullable=True)  # e.g., "root@pam!mytoken"
    api_token_secret = Column(String(255), nullable=True)  # Encrypted API token secret
    verify_ssl = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_poll = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # iDRAC / iLO out-of-band management
    idrac_hostname = Column(String(255), nullable=True)
    idrac_port = Column(Integer, default=443, nullable=True)
    idrac_username = Column(String(100), nullable=True)
    idrac_password = Column(String(255), nullable=True)  # Encrypted
    idrac_type = Column(String(20), nullable=True)  # "idrac", "ilo", or None
    idrac_use_ssh = Column(Boolean, default=False, nullable=True)

    # Relationships
    nodes = relationship("ProxmoxNode", back_populates="host", cascade="all, delete-orphan")
    vms = relationship("VirtualMachine", back_populates="proxmox_host")


class ProxmoxNode(Base):
    """Proxmox node (hypervisor) information"""
    __tablename__ = "proxmox_nodes"

    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("proxmox_hosts.id"), nullable=False)
    node_name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=True)
    cpu_cores = Column(Integer, nullable=True)
    cpu_usage = Column(Integer, nullable=True)  # Percentage
    memory_total = Column(Integer, nullable=True)  # Bytes
    memory_used = Column(Integer, nullable=True)  # Bytes
    disk_total = Column(Integer, nullable=True)  # Bytes
    disk_used = Column(Integer, nullable=True)  # Bytes
    uptime = Column(Integer, nullable=True)  # Seconds
    vm_count = Column(Integer, default=0, nullable=True)   # Number of QEMU VMs on this node
    lxc_count = Column(Integer, default=0, nullable=True)  # Number of LXC containers on this node
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)

    # iDRAC / iLO out-of-band management per physical node
    idrac_hostname = Column(String(255), nullable=True)
    idrac_port = Column(Integer, default=443, nullable=True)
    idrac_username = Column(String(100), nullable=True)
    idrac_password = Column(String(255), nullable=True)  # Encrypted
    idrac_type = Column(String(20), nullable=True)  # "idrac", "ilo", or None
    idrac_use_ssh = Column(Boolean, default=False, nullable=True)

    # Relationships
    host = relationship("ProxmoxHost", back_populates="nodes")
    vms = relationship("VirtualMachine", back_populates="node")


class ISOImage(Base):
    """ISO image storage"""
    __tablename__ = "iso_images"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    filename = Column(String(255), unique=True, nullable=False)
    os_type = Column(Enum(OSType), nullable=False)
    version = Column(String(50), nullable=True)
    architecture = Column(String(20), default="amd64", nullable=False)
    file_size = Column(Integer, nullable=True)  # Bytes
    checksum = Column(String(64), nullable=True)  # SHA256
    storage_path = Column(String(500), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)

    # Relationships
    vms = relationship("VirtualMachine", back_populates="iso_image")


class CloudImage(Base):
    """Cloud image storage for pre-installed VM images"""
    __tablename__ = "cloud_images"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    filename = Column(String(255), unique=True, nullable=False)
    os_type = Column(String(50), nullable=False)  # Store as string to avoid enum issues
    version = Column(String(50), nullable=True)
    architecture = Column(String(20), default="amd64", nullable=False)
    file_size = Column(Integer, nullable=True)  # Bytes
    checksum = Column(String(64), nullable=True)  # SHA256
    download_url = Column(String(500), nullable=False)  # Where to download from
    storage_path = Column(String(500), nullable=True)  # Local path once downloaded
    is_downloaded = Column(Boolean, default=False, nullable=False)
    download_progress = Column(Integer, default=0, nullable=False)  # Percentage
    download_status = Column(String(50), default="pending", nullable=False)  # pending, downloading, completed, error
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)

    # Relationships
    vms = relationship("VirtualMachine", back_populates="cloud_image")


class VirtualMachine(Base):
    """Virtual machine deployment records"""
    __tablename__ = "virtual_machines"

    id = Column(Integer, primary_key=True, index=True)
    vmid = Column(Integer, nullable=True)  # Proxmox VMID
    name = Column(String(255), nullable=False)
    hostname = Column(String(255), nullable=False)

    # Proxmox references
    proxmox_host_id = Column(Integer, ForeignKey("proxmox_hosts.id"), nullable=False)
    node_id = Column(Integer, ForeignKey("proxmox_nodes.id"), nullable=True)
    iso_id = Column(Integer, ForeignKey("iso_images.id"), nullable=True)
    cloud_image_id = Column(Integer, ForeignKey("cloud_images.id"), nullable=True)

    # VM specifications
    os_type = Column(Enum(OSType), nullable=False)
    cpu_sockets = Column(Integer, default=1, nullable=False)
    cpu_cores = Column(Integer, nullable=False)
    cpu_type = Column(String(100), default="host", nullable=True)  # CPU type: host, qemu64, kvm64, etc.
    cpu_flags = Column(String(500), nullable=True)  # Additional CPU flags
    cpu_limit = Column(Integer, nullable=True)  # CPU usage limit (0 = unlimited)
    cpu_units = Column(Integer, default=1024, nullable=True)  # CPU weight for scheduler
    numa_enabled = Column(Boolean, default=False, nullable=False)  # NUMA support
    memory = Column(Integer, nullable=False)  # MB
    balloon = Column(Integer, nullable=True)  # Balloon device (0 = disabled, MB)
    shares = Column(Integer, nullable=True)  # Memory shares for scheduler
    disk_size = Column(Integer, nullable=False)  # GB
    storage = Column(String(100), nullable=True)  # Storage pool name for VM disks
    iso_storage = Column(String(100), nullable=True)  # Storage pool name for ISO files
    scsihw = Column(String(50), default="virtio-scsi-pci", nullable=True)  # SCSI controller type

    # Hardware options
    bios_type = Column(String(20), default="seabios", nullable=False)  # seabios or ovmf (UEFI)
    machine_type = Column(String(50), default="pc", nullable=True)  # pc, q35, etc.
    vga_type = Column(String(50), default="std", nullable=False)  # std, virtio, qxl, vmware, cirrus
    boot_order = Column(String(100), default="cdn", nullable=False)  # c=disk, d=cdrom, n=network
    onboot = Column(Boolean, default=True, nullable=False)  # Start VM at boot
    tablet = Column(Boolean, default=True, nullable=False)  # Enable tablet pointer device
    hotplug = Column(String(200), nullable=True)  # Hotplug options: disk,network,usb,memory,cpu
    protection = Column(Boolean, default=False, nullable=False)  # Prevent accidental deletion
    startup_order = Column(Integer, nullable=True)  # Startup order
    startup_up = Column(Integer, nullable=True)  # Startup delay in seconds
    startup_down = Column(Integer, nullable=True)  # Shutdown timeout in seconds
    kvm = Column(Boolean, default=True, nullable=False)  # Enable KVM hardware virtualization
    acpi = Column(Boolean, default=True, nullable=False)  # Enable ACPI
    agent_enabled = Column(Boolean, default=True, nullable=False)  # QEMU guest agent
    description = Column(Text, nullable=True)  # VM description
    tags = Column(String(500), nullable=True)  # VM tags (semicolon-separated)

    # Network configuration
    network_bridge = Column(String(100), nullable=True)  # Primary network bridge
    network_interfaces = Column(JSON, nullable=True)  # Additional network interfaces as JSON array
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6
    gateway = Column(String(45), nullable=True)
    netmask = Column(String(45), nullable=True)
    dns_servers = Column(String(255), nullable=True)

    # Credentials (encrypted)
    username = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    ssh_key = Column(Text, nullable=True)

    # Status and metadata
    status = Column(Enum(VMStatus), default=VMStatus.CREATING, nullable=False)
    status_message = Column(String(500), nullable=True)  # Real-time progress message
    cloud_init_config = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    deployed_at = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # User reference
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    created_by_user = relationship("User", back_populates="vms")
    proxmox_host = relationship("ProxmoxHost", back_populates="vms")
    node = relationship("ProxmoxNode", back_populates="vms")
    iso_image = relationship("ISOImage", back_populates="vms")
    cloud_image = relationship("CloudImage", back_populates="vms")
    update_logs = relationship("UpdateLog", back_populates="vm", cascade="all, delete-orphan")


class UpdateLog(Base):
    """Update history for VMs"""
    __tablename__ = "update_logs"

    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("virtual_machines.id"), nullable=False)
    initiated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(50), nullable=False)  # pending, running, completed, failed
    packages_updated = Column(Integer, default=0, nullable=False)
    output = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    vm = relationship("VirtualMachine", back_populates="update_logs")


class AuditLog(Base):
    """Audit log for tracking user actions"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

class SystemSettings(Base):
    """System-wide settings and configuration"""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ScanType(str, enum.Enum):
    """VM scan type enumeration"""
    OS_UPDATES = "os_updates"
    SECURITY = "security"
    DEPENDENCIES = "dependencies"
    AI_ANALYSIS = "ai_analysis"


class ScanStatus(str, enum.Enum):
    """VM scan status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanSeverity(str, enum.Enum):
    """VM scan severity enumeration"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class VmAgent(Base):
    """Push agent installed on managed Linux VMs"""
    __tablename__ = "vm_agents"

    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("virtual_machines.id"), nullable=True)
    token = Column(String(36), unique=True, nullable=False, index=True)
    hostname = Column(String(255), nullable=True)
    os_info = Column(String(255), nullable=True)
    agent_version = Column(String(50), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    last_seen = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    vm = relationship("VirtualMachine")
    scan_results = relationship("VmScanResult", back_populates="agent", cascade="all, delete-orphan")


class VmScanResult(Base):
    """Scan results reported by VM agents"""
    __tablename__ = "vm_scan_results"

    id = Column(Integer, primary_key=True, index=True)
    vm_agent_id = Column(Integer, ForeignKey("vm_agents.id"), nullable=False)
    scan_type = Column(Enum(ScanType), nullable=False)
    status = Column(Enum(ScanStatus), default=ScanStatus.PENDING, nullable=False)
    result_json = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    severity = Column(Enum(ScanSeverity), default=ScanSeverity.INFO, nullable=False)
    scanned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    agent = relationship("VmAgent", back_populates="scan_results")


class VmScanCache(Base):
    """Cached results of automated or manual update/security checks"""
    __tablename__ = "vm_scan_cache"

    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("virtual_machines.id"), nullable=False)
    scan_type = Column(String(20), nullable=False)   # "updates" or "security"
    result_json = Column(Text, nullable=True)
    scanned_at = Column(DateTime, nullable=True)
    severity = Column(String(20), nullable=True)     # ok / warning / critical
    summary = Column(String(500), nullable=True)

    __table_args__ = (UniqueConstraint("vm_id", "scan_type", name="uq_vm_scan_cache"),)

    vm = relationship("VirtualMachine")


class StandaloneBMC(Base):
    """Standalone iDRAC/iLO entry not tied to a Proxmox host or PBS server"""
    __tablename__ = "standalone_bmc"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500), nullable=True)
    idrac_hostname = Column(String(255), nullable=False)
    idrac_port = Column(Integer, default=443, nullable=False)
    idrac_username = Column(String(100), nullable=False)
    idrac_password = Column(String(255), nullable=False)  # Encrypted
    idrac_type = Column(String(20), nullable=False, default="idrac")  # "idrac" or "ilo"
    idrac_use_ssh = Column(Boolean, default=False, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PBSServer(Base):
    """Proxmox Backup Server configuration"""
    __tablename__ = "pbs_servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    hostname = Column(String(255), nullable=False)
    port = Column(Integer, default=8007, nullable=False)
    username = Column(String(100), nullable=False)  # e.g. "root@pam"
    password = Column(String(255), nullable=True)   # Encrypted
    api_token_id = Column(String(100), nullable=True)
    api_token_secret = Column(String(255), nullable=True)  # Encrypted
    verify_ssl = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # iDRAC / iLO out-of-band management
    idrac_hostname = Column(String(255), nullable=True)
    idrac_port = Column(Integer, default=443, nullable=True)
    idrac_username = Column(String(100), nullable=True)
    idrac_password = Column(String(255), nullable=True)  # Encrypted
    idrac_type = Column(String(20), nullable=True)  # "idrac", "ilo", or None
    idrac_use_ssh = Column(Boolean, default=False, nullable=True)


class ApiKey(Base):
    """API keys for programmatic access"""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)  # bcrypt hash of the key
    key_prefix = Column(String(8), nullable=False)  # first 8 chars for display
    last_used = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    user = relationship("User", backref="api_keys")


class LLMDeployment(Base):
    """LLM deployment record - tracks VMs deployed as LLM inference servers"""
    __tablename__ = "llm_deployments"

    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(Integer, ForeignKey("virtual_machines.id"), nullable=False)
    engine = Column(String(50), nullable=False)       # ollama, llama.cpp
    model = Column(String(100), nullable=False)       # llama3.1:8b, mistral:7b, etc.
    ui_type = Column(String(50), nullable=False)      # open-webui, api-only
    gpu_enabled = Column(Boolean, default=False, nullable=False)
    gpu_type = Column(String(50), nullable=True)      # nvidia, amd
    gpu_device_id = Column(String(100), nullable=True)  # PCI device ID for passthrough
    os_variant = Column(String(50), nullable=False)   # ubuntu2404, ubuntu2204
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    vm = relationship("VirtualMachine")


class Notification(Base):
    """In-app notification for a user"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(20), default="info", nullable=False)  # info/success/warning/error
    read = Column(Boolean, default=False, nullable=False)
    action_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="notifications")


class WebhookDelivery(Base):
    """Delivery log for webhook calls"""
    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    webhook_id = Column(String(36), nullable=False, index=True)  # UUID string from SystemSettings JSON
    event = Column(String(100), nullable=False)
    status_code = Column(Integer, nullable=True)
    success = Column(Boolean, default=False, nullable=False)
    response_body = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TotpBackupCode(Base):
    """Backup codes for TOTP 2FA recovery"""
    __tablename__ = "totp_backup_codes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)

    user = relationship("User", backref="totp_backup_codes")


class RefreshToken(Base):
    """Refresh token store for rotation and revocation"""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User", backref="refresh_tokens")
