# Cloud Images - Complete Guide

## Table of Contents
1. [What Are Cloud Images?](#what-are-cloud-images)
2. [Why Use Cloud Images?](#why-use-cloud-images)
3. [One-Time Setup](#one-time-setup)
4. [How to Use Cloud Images](#how-to-use-cloud-images)
5. [Available Cloud Images](#available-cloud-images)
6. [How It Works (Technical)](#how-it-works-technical)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## What Are Cloud Images?

Cloud images are pre-configured, ready-to-deploy operating system disk images. Instead of manually installing an OS (which takes 15-20 minutes), cloud images allow you to:

- **Deploy VMs in 30 seconds** (after initial template creation)
- **Automatically configure credentials** (username/password)
- **Auto-configure networking** (DHCP or static IP)
- **Skip manual OS installation** completely

Think of it like cloning a pre-installed OS with your custom settings applied automatically.

---

## Why Use Cloud Images?

### Traditional ISO Installation:
- Upload ISO file (~1GB download)
- Create VM
- Boot from ISO
- Click through installation wizard
- Wait 15-20 minutes
- **Total time: 20-30 minutes per VM**

### Cloud Image Installation:
- Select cloud image
- Configure CPU, RAM, disk, credentials
- Click "Create VM"
- **First time: 5-10 minutes** (creates reusable template)
- **Every time after: 30 seconds** ⚡

**100x faster after the first deployment!**

---

## One-Time Setup

Cloud images require SSH access to your Proxmox server for initial template creation. This is a **ONE-TIME** setup that takes about 1 minute.

### Step 1: Check if Setup is Needed

Open Depl0y web UI and go to **Settings** page. Look for the "Cloud Image Setup" section:

- **Green box (✅)**: Setup already complete! You're good to go.
- **Yellow box (⚠️)**: Setup required. Continue to Step 2.

### Step 2: Run the Setup Script

The setup script is already on your Depl0y server at `/tmp/enable_cloud_images.sh`.

**⚠️ IMPORTANT: Run this script ON YOUR DEPL0Y SERVER (not on Proxmox!)**

The script is located on your Depl0y server at `/tmp/enable_cloud_images.sh`. It will automatically connect to Proxmox to set up SSH access.

**Method 1: Copy from Web UI (Recommended)**

1. In the Settings page, click the **"Copy"** button next to the setup command
2. SSH into your **Depl0y server** (the server where Depl0y is installed):
   ```bash
   ssh administrator@your-depl0y-server
   # Or: ssh administrator@deploy
   ```
3. Paste and run the command:
   ```bash
   sudo /tmp/enable_cloud_images.sh
   ```

**Method 2: Manual Command**

If you're already logged into your Depl0y server, just run:
```bash
sudo /tmp/enable_cloud_images.sh
```

**What Happens:**
1. Script runs **on Depl0y server** (where you run the command)
2. Generates SSH keys **on Depl0y server**
3. Prompts you for **Proxmox root password**
4. Uses SSH to copy the key **from Depl0y to Proxmox**
5. Verifies connection works

### Step 3: Enter Proxmox Password

The script will prompt you:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Please enter the ROOT PASSWORD for Proxmox server: pve.example.com
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Password:
```

**Enter your Proxmox root password** (the password will not be displayed as you type for security).

### Step 4: Wait for Completion

The script will:
1. ✓ Check if `sshpass` is installed (installs if needed)
2. ✓ Generate SSH key pair (if not exists)
3. ✓ Copy SSH public key to Proxmox
4. ✓ Verify SSH connection works

You'll see:
```
╔════════════════════════════════════════════════════════════╗
║                    ✅ SUCCESS!                             ║
╚════════════════════════════════════════════════════════════╝

Cloud images are now fully configured!

🎉 What happens now:
   • Go to the web UI and create a VM
   • Select any cloud image (Ubuntu, Debian, etc.)
   • Click 'Create VM'
   • The system will automatically:
     - Download the cloud image to Proxmox (first time only)
     - Create a bootable template (first time only)
     - Clone and deploy your VM with your credentials
     - Start the VM ready to use!

   First deployment per cloud image: ~5-10 minutes
   All subsequent deployments: ~30 seconds

✨ Everything is automatic from now on!
```

### Step 5: Verify in Web UI

1. Go back to **Settings** page in Depl0y web UI
2. Click **"Re-check Status"** button
3. You should see a **green success box**: "Cloud Images Enabled! ✅"

**Setup is complete!** You never have to do this again.

---

## How to Use Cloud Images

### Creating Your First Cloud Image VM

1. **Go to Create VM Page**
   - Click "Create VM" in the navigation menu

2. **Basic Configuration**
   - **Name**: Enter a name for your VM (e.g., "ubuntu-web-01")
   - **Datacenter**: Select your Proxmox datacenter
   - **Node**: Select which Proxmox node to deploy on

3. **Installation Method**
   - Select **"Cloud Image (Fast)"**
   - Choose a cloud image from the dropdown:
     - Ubuntu 24.04 LTS
     - Ubuntu 22.04 LTS
     - Ubuntu 20.04 LTS
     - Debian 12
     - Debian 11

4. **Resources**
   - **CPU Cores**: 2 (or more)
   - **Memory (RAM)**: 2048 MB (or more)
   - **Disk Size**: 20 GB (or more)

5. **Storage & Network**
   - **Storage Pool**: Select where to store the VM disk
   - **Network Bridge**: Select network (usually vmbr0)

6. **Cloud-Init Configuration**
   - **Username**: Your desired username (e.g., "admin", "ubuntu")
   - **Password**: Your desired password
   - **SSH Public Key** (optional): Paste your SSH public key for key-based auth
   - **IP Configuration**: Choose DHCP or Static IP

7. **Advanced Options** (optional)
   - CPU Type
   - BIOS (SeaBIOS or UEFI)
   - VGA Type
   - Boot Order

8. **Click "Create VM"**

### What Happens Next?

**First Time Using This Cloud Image:**
- Status: "Setting up cloud image (first time - takes ~5 min)..."
- The system automatically:
  1. Downloads the cloud image to Depl0y server (~300-700 MB)
  2. Uploads it to Proxmox via SSH
  3. Creates a VM template on Proxmox
  4. Clones the template to create your VM
  5. Configures cloud-init with your credentials
  6. Starts the VM

**Time: 5-10 minutes** ⏱️

**Every Time After (Same Cloud Image):**
- Status: "Cloning template..."
- The system automatically:
  1. Clones existing template (instant!)
  2. Configures cloud-init with your credentials
  3. Starts the VM

**Time: 30 seconds** ⚡

### Accessing Your VM

Once the VM is created and started:

**SSH Access:**
```bash
ssh username@vm-ip-address
```

**Console Access:**
- Click on the VM in Depl0y
- Click "Console" button
- Login with your configured username/password

---

## Available Cloud Images

**NEW in v1.2.2:** Cloud images are now **auto-populated**! Simply click "Fetch Latest" in the Cloud Images page to automatically add all available images.

### Ubuntu

| Image | Version | Use Case | LTS Until |
|-------|---------|----------|-----------|
| Ubuntu 24.04 LTS | Noble Numbat | Latest features | April 2029 |
| Ubuntu 22.04 LTS | Jammy Jellyfish | Stable production | April 2027 |
| Ubuntu 20.04 LTS | Focal Fossa | Legacy apps | April 2025 |

### Debian

| Image | Version | Use Case |
|-------|---------|----------|
| Debian 12 | Bookworm | Latest stable |
| Debian 11 | Bullseye | Previous stable |

### Rocky Linux

| Image | Version | Use Case |
|-------|---------|----------|
| Rocky Linux 9 | Latest | RHEL 9 compatible |
| Rocky Linux 8 | Stable | RHEL 8 compatible |

**All 7 images above are automatically added** when you click "Fetch Latest" in the Cloud Images page.

**Need more cloud images?** You can manually add additional images using the "+ Add Cloud Image" button.

---

## How It Works (Technical)

### Architecture Overview

```
┌─────────────────┐
│  Depl0y Server  │
│                 │
│  1. Downloads   │──────┐
│     cloud image │      │
└─────────────────┘      │
                         │ SCP Upload
                         ▼
                  ┌─────────────────┐
                  │ Proxmox Server  │
                  │                 │
                  │  2. Import disk │
                  │  3. Convert to  │
                  │     template    │
                  │                 │
                  │  Template ID:   │
                  │  9001, 9002...  │
                  └─────────────────┘
                         │
                         │ Clone via API
                         ▼
                  ┌─────────────────┐
                  │   New VM        │
                  │   + Cloud-init  │
                  │   configured    │
                  └─────────────────┘
```

### Template ID System

Cloud images are converted to Proxmox templates with predictable IDs:

- Template ID = `9000 + cloud_image_id`
- Ubuntu 24.04 (id=1) → Template 9001
- Ubuntu 22.04 (id=2) → Template 9002
- Debian 12 (id=3) → Template 9003
- etc.

### Template Creation Process

**First VM deployment from a cloud image:**

1. **Download** (Depl0y server):
   ```bash
   wget https://cloud-images.ubuntu.com/.../ubuntu-24.04-server-cloudimg-amd64.img
   # Stored in: /var/lib/depl0y/cloud-images/
   ```

2. **Upload to Proxmox** (via SSH):
   ```bash
   scp ubuntu-24.04-server-cloudimg-amd64.img root@pve.example.com:/tmp/
   ```

3. **Create Template VM** (via SSH on Proxmox):
   ```bash
   # Create empty VM
   qm create 9001 --name Ubuntu-24.04-LTS --memory 2048 --cores 2 \
     --net0 virtio,bridge=vmbr0 --ostype l26 --scsihw virtio-scsi-pci

   # Import cloud image as disk
   qm importdisk 9001 /tmp/ubuntu-24.04-server-cloudimg-amd64.img local-lvm --format qcow2

   # Configure disk and boot
   qm set 9001 --scsi0 local-lvm:vm-9001-disk-0
   qm set 9001 --boot order=scsi0

   # Add cloud-init drive
   qm set 9001 --ide2 local-lvm:cloudinit

   # Convert to template
   qm template 9001
   ```

4. **Clone Template** (via Proxmox API):
   ```python
   proxmox.nodes(node).qemu(9001).clone.post(
       newid=vm_id,
       name=vm_name,
       full=1,  # Full clone
       storage=storage
   )
   ```

5. **Configure Cloud-init** (via Proxmox API):
   ```python
   proxmox.nodes(node).qemu(vm_id).config.set(
       ciuser=username,
       cipassword=password,
       ipconfig0=network_config,
       sshkeys=ssh_public_key
   )
   ```

### Subsequent Deployments

**All VMs after the first:**
- **Skip steps 1-3** (template already exists!)
- **Only run steps 4-5** (clone + configure)
- **Result**: 30-second deployments

### Why SSH is Required

The `qm importdisk` command does not have a Proxmox API endpoint. It can only be executed via SSH on the Proxmox server. This is why SSH setup is required for the **first** deployment of each cloud image type.

**After template creation:**
- All operations use pure Proxmox API
- No SSH required for VM cloning
- Fast and efficient deployments

### Security

- **SSH Key Authentication**: Password-free after setup
- **Public Key Only**: Only public key stored on Proxmox
- **No Password Storage**: Proxmox password never stored in database
- **Template Isolation**: Templates separate from user VMs
- **Cloud-init Encryption**: Credentials encrypted in transit

---

## Troubleshooting

### Error: "SSH access not configured"

**Symptoms:**
```
Error: SSH access not configured. Please run this ONE-TIME setup command:

    sudo /tmp/enable_cloud_images.sh

After that, cloud images will deploy automatically!
```

**Solution:**
1. SSH to your Depl0y server
2. Run: `sudo /tmp/enable_cloud_images.sh`
3. Enter your Proxmox root password when prompted
4. Wait for "✅ SUCCESS!" message
5. Try creating the VM again

### SSH Setup Script Fails

**Error: "Permission denied (publickey,password)"**

**Possible Causes:**
- Wrong Proxmox password
- SSH password authentication disabled on Proxmox

**Solution 1: Verify Password**
```bash
# Test SSH with password manually
ssh root@pve.example.com
# If this fails with your password, reset Proxmox root password
```

**Solution 2: Enable Password Auth (if disabled)**

On your Proxmox server, edit SSH config:
```bash
sudo nano /etc/ssh/sshd_config
```

Find and change:
```
PasswordAuthentication yes
```

Restart SSH:
```bash
sudo systemctl restart sshd
```

Then run the setup script again.

**Solution 3: Manual SSH Key Setup**

If the automated script fails, set up SSH manually:

1. On Depl0y server:
   ```bash
   sudo -u depl0y ssh-keygen -t rsa -b 4096 -f /opt/depl0y/.ssh/id_rsa -N ""
   sudo -u depl0y cat /opt/depl0y/.ssh/id_rsa.pub
   ```

2. Copy the public key output

3. On Proxmox server:
   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   nano ~/.ssh/authorized_keys
   # Paste the public key, save and exit
   chmod 600 ~/.ssh/authorized_keys
   ```

4. Test from Depl0y server:
   ```bash
   sudo -u depl0y ssh root@pve.example.com "echo test"
   ```

### VM Created But Won't Boot

**Symptoms:**
- VM starts but no OS loads
- Black screen or BIOS errors
- "No bootable device" error

**Cause:**
Template doesn't exist or is corrupt.

**Solution:**
Delete the template and let it recreate:

1. Check which template exists:
   ```bash
   ssh root@pve.example.com "qm list | grep 900"
   ```

2. Delete the problematic template:
   ```bash
   # For Ubuntu 24.04 (template 9001)
   ssh root@pve.example.com "qm destroy 9001"
   ```

3. Try creating the VM again - template will be recreated automatically

### Cloud-init Not Working

**Symptoms:**
- Can't login with configured credentials
- Default username/password required
- Network not configured

**Cause:**
Cloud-init configuration failed or not applied.

**Solution:**

1. Check cloud-init logs on the VM:
   ```bash
   # Login via console with default credentials
   sudo cat /var/log/cloud-init.log
   sudo cat /var/log/cloud-init-output.log
   ```

2. Verify cloud-init config in Proxmox:
   ```bash
   ssh root@pve.example.com "qm cloudinit dump <vmid> user"
   ```

3. Manually set cloud-init (if needed):
   ```bash
   # Via Proxmox UI:
   # VM → Cloud-Init → Edit settings
   ```

### Template Creation Stuck

**Symptoms:**
- Status shows "Setting up cloud image..." for 20+ minutes
- No progress

**Cause:**
- Network issue downloading cloud image
- Proxmox storage full
- SSH connection lost

**Check Logs:**
```bash
sudo journalctl -u depl0y-backend -f --no-pager
```

**Solutions:**

1. **Check download progress:**
   ```bash
   ls -lh /var/lib/depl0y/cloud-images/
   # If file is growing, download is in progress
   ```

2. **Check Proxmox storage:**
   ```bash
   ssh root@pve.example.com "df -h"
   # Ensure storage has 5+ GB free
   ```

3. **Check SSH connection:**
   ```bash
   sudo -u depl0y ssh root@pve.example.com "echo test"
   ```

4. **Restart the deployment:**
   - Delete the partially created template
   - Try creating the VM again

### Check Templates on Proxmox

List all templates:
```bash
ssh root@pve.example.com "qm list | grep 900"
```

Example output:
```
9001  Ubuntu-24.04-LTS  0     2048        0.00            0
9002  Ubuntu-22.04-LTS  0     2048        0.00            0
```

Delete a template:
```bash
ssh root@pve.example.com "qm destroy 9001"
```

### Verify SSH Status from Command Line

**Test SSH access:**
```bash
sudo -u depl0y ssh -o BatchMode=yes -o ConnectTimeout=5 \
  -o StrictHostKeyChecking=no root@pve.example.com "echo test"
```

**If successful, you'll see:**
```
test
```

**If not configured:**
```
Permission denied (publickey,password).
```

---

## FAQ

### Q: Do I need to run the setup script for every VM?
**A:** No! The setup script is run **once** per Depl0y installation. After that, all cloud image deployments are automatic.

### Q: Do I need to run the setup script for each cloud image?
**A:** No! One setup enables **all** cloud images. The first deployment of each cloud image type takes 5-10 minutes to create the template, then all subsequent deployments are 30 seconds.

### Q: What if I add a new Proxmox node?
**A:** The SSH key is configured per Proxmox host, not per node. If you add a node to an existing cluster, no new setup is needed. If you add a completely new Proxmox host/cluster, you'll need to run the setup script once for that new host.

### Q: Can I use cloud images and ISO images?
**A:** Yes! Both installation methods work side-by-side. Use cloud images for quick deployments, ISOs for custom installations or distros without cloud images.

### Q: Where are cloud images stored?
**A:**
- **Depl0y server**: `/var/lib/depl0y/cloud-images/` (original downloads)
- **Proxmox server**: Imported as disks in configured storage (e.g., local-lvm)

### Q: How much disk space do cloud images use?
**A:**
- **Download**: 300-700 MB per cloud image
- **Template on Proxmox**: 2-3 GB per template
- **Cloned VMs**: Your configured disk size (20+ GB recommended)

### Q: Can I customize the cloud images?
**A:** Cloud images are standard upstream images from Ubuntu/Debian. You can:
- Customize credentials (via cloud-init)
- Customize network (via cloud-init)
- Add SSH keys (via cloud-init)
- Install software after deployment (via Ansible, scripts, etc.)

If you need pre-customized images, consider using Packer to build custom images.

### Q: What happens if template creation fails?
**A:** The deployment will fail with an error message. Check the logs, fix the issue (usually SSH or storage), and try again. The system will automatically retry template creation.

### Q: Can I delete templates?
**A:** Yes, but if you delete a template, the next VM deployment for that cloud image will take 5-10 minutes to recreate the template. Templates are safe to delete if you need to free space.

### Q: How do I add more cloud images?
**A:** Cloud images are defined in the database. You can:
1. Contact your Depl0y administrator
2. Submit a feature request
3. Manually add via database (advanced users)

### Q: Does cloud-init work on all images?
**A:** Yes! All official Ubuntu and Debian cloud images have cloud-init pre-installed and configured. That's what makes them "cloud images."

### Q: Can I use Windows cloud images?
**A:** Windows doesn't have official cloud images like Linux. For Windows VMs, use the traditional ISO installation method. You can create custom Windows templates manually in Proxmox.

### Q: What if I don't want to give Proxmox root SSH access?
**A:** SSH root access is required for the `qm importdisk` command during template creation. This is a Proxmox limitation. For security:
- SSH uses key-based auth (no password storage)
- SSH only used during template creation
- All subsequent operations use Proxmox API
- You can disable SSH after all templates are created (though you'll need to re-enable for new cloud image types)

### Q: How do I know which template ID corresponds to which cloud image?
**A:** Template ID = 9000 + cloud_image_id. You can check cloud image IDs in the database or via the API. Common mappings:
- 9001: Ubuntu 24.04 LTS
- 9002: Ubuntu 22.04 LTS
- 9003: Ubuntu 20.04 LTS
- 9004: Debian 12
- 9005: Debian 11

---

## Additional Resources

### Check System Logs
```bash
# Backend logs
sudo journalctl -u depl0y-backend -f --no-pager

# Last 50 lines
sudo journalctl -u depl0y-backend -n 50 --no-pager
```

### Test SSH Manually
```bash
# As depl0y user
sudo -u depl0y ssh root@pve.example.com "qm list"

# Check SSH key
sudo -u depl0y cat /opt/depl0y/.ssh/id_rsa.pub
```

### View Cloud Images in Database
```bash
sudo -u depl0y sqlite3 /var/lib/depl0y/db/depl0y.db "SELECT id, name, filename, is_downloaded FROM cloud_images WHERE is_available=1;"
```

### File Locations
- **Setup script**: `/tmp/enable_cloud_images.sh`
- **Cloud image downloads**: `/var/lib/depl0y/cloud-images/`
- **SSH keys**: `/opt/depl0y/.ssh/`
- **Backend code**: `/opt/depl0y/backend/app/services/deployment.py`
- **Database**: `/var/lib/depl0y/db/depl0y.db`

---

## Support

If you encounter issues not covered in this guide:

1. **Check logs**: `sudo journalctl -u depl0y-backend -f`
2. **Verify SSH**: `sudo -u depl0y ssh root@pve.example.com "echo test"`
3. **Check templates**: `ssh root@pve.example.com "qm list | grep 900"`
4. **Contact support** or submit a bug report via the web UI

---

**Happy deploying!** 🚀
