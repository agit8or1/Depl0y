# User Guide

Complete guide to using Depl0y for VM deployment and management.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Dashboard](#dashboard)
3. [Managing Virtual Machines](#managing-virtual-machines)
4. [Proxmox Hosts](#proxmox-hosts)
5. [ISO Management](#iso-management)
6. [User Management](#user-management)
7. [Settings](#settings)
8. [Best Practices](#best-practices)

## Getting Started

### First Login

1. Navigate to your Depl0y installation URL
2. Enter your username and password
3. If 2FA is enabled, enter your authentication code
4. Click "Login"

### User Roles

Depl0y supports three user roles:

- **Admin**: Full access to all features, including user management
- **Operator**: Can create, modify, and delete VMs; manage hosts and ISOs
- **Viewer**: Read-only access to view VMs and infrastructure

## Dashboard

The dashboard provides an overview of your infrastructure:

### Key Metrics
- **Total VMs**: Number of virtual machines
- **Running VMs**: Currently active VMs
- **Stopped VMs**: Inactive VMs
- **Active Hosts**: Connected Proxmox hosts

### Resource Usage
- **CPU Cores**: Total and used CPU cores across all nodes
- **Memory**: Total and used RAM
- **Disk Space**: Total and used storage

### Quick Actions
- Deploy New VM
- Manage Hosts
- Upload ISO

## Managing Virtual Machines

### Creating a Linux VM

1. Navigate to **Virtual Machines** > **Create VM**

2. **Basic Configuration**:
   - Name: Friendly name for the VM
   - Hostname: System hostname
   - OS Type: Ubuntu, Debian, CentOS, Rocky, or Alma

3. **Select Infrastructure**:
   - Proxmox Host: Choose your Proxmox server
   - Node: Select specific node/hypervisor
   - ISO Image: (Optional) Select installation ISO

4. **Resource Allocation**:
   - CPU Cores: Number of virtual CPUs (1-64)
   - Memory: RAM in MB (512-131072)
   - Disk Size: Storage in GB (10-2000)

5. **Network Configuration**:
   - **DHCP** (recommended for simple setups):
     - Leave IP fields blank
   - **Static IP**:
     - IP Address: e.g., 192.168.1.100
     - Netmask: e.g., 24 or 255.255.255.0
     - Gateway: e.g., 192.168.1.1
     - DNS Servers: e.g., 8.8.8.8,8.8.4.4

6. **Credentials**:
   - Username: Default user account name
   - Password: User password
   - SSH Key: (Optional) Public SSH key for authentication

7. Click **Deploy**

The system will:
- Create the VM in Proxmox
- Configure cloud-init
- Install QEMU guest agent
- Set up networking
- Create user account
- Enable SSH server

### Creating a Windows VM

1. Follow steps 1-4 above, selecting Windows OS type

2. **Important**: Windows VMs require manual installation:
   - The VM will be created and configured
   - Connect via VNC from Proxmox
   - Complete Windows installation manually
   - Install VirtIO drivers from the second CD-ROM
   - Install QEMU guest agent manually

### VM Operations

**Start a VM**:
1. Go to Virtual Machines
2. Find your VM in the list
3. Click the ▶️ Start button

**Stop a VM**:
1. Click the ⏹️ Stop button
2. Confirm the action

**View VM Details**:
1. Click on the VM name
2. View configuration, status, and logs

**Delete a VM**:
1. Stop the VM first
2. Click the 🗑️ Delete button
3. Confirm deletion
4. The VM will be removed from both Depl0y and Proxmox

### Managing Updates (Linux only)

**Check for Updates**:
1. Open VM details
2. Click "Check Updates"
3. View available packages

**Install Updates**:
1. Click "Install Updates"
2. Monitor progress
3. View update log when complete

**Update History**:
- View all past updates in the Updates tab
- See package counts and status
- Review update output and errors

## Proxmox Hosts

### Adding a Proxmox Host

1. Navigate to **Proxmox Hosts**
2. Click **Add Host**
3. Fill in details:
   - **Name**: Friendly identifier
   - **Hostname**: IP address or FQDN
   - **Port**: 8006 (default)
   - **Username**: root@pam or API user
   - **Password**: Proxmox password
   - **Verify SSL**: Disable for self-signed certs
4. Click **Test Connection**
5. Click **Add** if successful

### Polling Resources

Depl0y polls Proxmox hosts to gather resource information:

**Manual Poll**:
1. Click the 🔄 Poll button
2. Wait for resources to update

**Automatic Polling**:
- Configured in settings (default: every 60 seconds)
- Updates node resources and status

### Viewing Nodes

1. Select a Proxmox host
2. Click "View Nodes"
3. See all hypervisors in the cluster with:
   - CPU usage
   - Memory usage
   - Disk usage
   - Uptime

## ISO Management

### Uploading ISOs

1. Navigate to **ISO Images**
2. Click **Upload ISO**
3. Fill in information:
   - **Name**: Descriptive name
   - **OS Type**: Operating system
   - **Version**: OS version (optional)
   - **Architecture**: amd64 (default)
4. Select the ISO file
5. Click **Upload**

The system will:
- Upload the file
- Calculate SHA256 checksum
- Store metadata
- Make it available for VM deployment

**Note**: Large ISOs may take time to upload. Maximum size: 10GB (configurable).

### Verifying ISOs

1. Find the ISO in the list
2. Click "Verify"
3. The system checks the SHA256 checksum
4. View verification result

### Deleting ISOs

1. Click the 🗑️ Delete button
2. Confirm deletion
3. The ISO file will be removed

## User Management

*(Admin only)*

### Creating Users

1. Navigate to **Users**
2. Click **Create User**
3. Fill in details:
   - Username
   - Email
   - Password
   - Role: Admin, Operator, or Viewer
4. Click **Create**

### Editing Users

1. Click on a user
2. Click **Edit**
3. Update email, role, or active status
4. Click **Save**

### Deleting Users

1. Click the 🗑️ Delete button
2. Confirm deletion

**Note**: You cannot delete your own account.

## Settings

### Changing Password

1. Navigate to **Settings**
2. Enter current password
3. Enter new password (minimum 8 characters)
4. Confirm new password
5. Click **Change Password**

### Enabling 2FA

1. Navigate to **Settings**
2. Click **Enable 2FA**
3. Scan QR code with authenticator app (Google Authenticator, Authy, etc.)
4. Enter verification code
5. Click **Verify**

**Important**: Save backup codes in case you lose access to your authenticator.

### Disabling 2FA

1. Navigate to **Settings**
2. Enter 2FA code
3. Click **Disable 2FA**

## Best Practices

### Security

1. **Use Strong Passwords**
   - Minimum 12 characters
   - Mix of letters, numbers, symbols
   - Unique for each account

2. **Enable 2FA**
   - Required for admin accounts
   - Recommended for all users

3. **Regular Updates**
   - Keep Depl0y updated
   - Apply security patches promptly

4. **Limit Access**
   - Use viewer role for monitoring only
   - Grant operator/admin sparingly

### VM Deployment

1. **Plan Resources**
   - Don't over-allocate CPU and RAM
   - Leave headroom on nodes

2. **Use DHCP Initially**
   - Easier troubleshooting
   - Switch to static IPs later if needed

3. **Test Deployments**
   - Try a small VM first
   - Verify networking and access
   - Then deploy production VMs

4. **Regular Backups**
   - Backup VMs in Proxmox
   - Test restore procedures

### Maintenance

1. **Monitor Resources**
   - Check dashboard regularly
   - Watch for resource constraints

2. **Update VMs**
   - Schedule regular update windows
   - Test updates on non-critical VMs first

3. **Clean Up**
   - Delete unused VMs
   - Remove old ISOs
   - Audit user accounts

4. **Documentation**
   - Document your VM inventory
   - Note special configurations
   - Keep credentials secure

## Keyboard Shortcuts

- `Ctrl/Cmd + K`: Quick search (coming soon)
- `Ctrl/Cmd + /`: Help (coming soon)

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting Guide](TROUBLESHOOTING.md)
2. Review logs: `docker-compose logs -f`
3. Open an issue on GitHub
4. Join community discussions

## Next Steps

- [API Documentation](API.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Contributing](../CONTRIBUTING.md)
