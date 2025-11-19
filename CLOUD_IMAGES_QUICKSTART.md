# Cloud Images - Quick Start Guide

## What Are Cloud Images?

Cloud images let you deploy VMs in **30 seconds** instead of 20 minutes. No manual OS installation needed!

---

## One-Time Setup (Takes 1 Minute)

### Step 1: Check Status in Web UI

Go to **Settings** → Look for **"Cloud Image Setup"** section

- **Green box (✅)**: Already configured! Skip to "Using Cloud Images" below.
- **Yellow box (⚠️)**: Setup needed. Continue to Step 2.

### Step 2: Run Setup Script

**IMPORTANT:** Run this script **ON YOUR DEPL0Y SERVER** (not on Proxmox!)

**Option A: Copy from Web UI**
1. Click the **"Copy"** button in Settings page
2. SSH to your **Depl0y server** (hostname: `deploy`)
3. Paste and run the command

**Option B: Manual Command**

SSH to your **Depl0y server** and run:

```bash
sudo /tmp/enable_cloud_images.sh
```

**If you're already logged into the Depl0y server:**
Just run the command directly - no need to SSH anywhere!

### Step 3: Enter Password

When prompted, enter your **Proxmox root password**:

```
Password: [your-proxmox-root-password]
```

(Password won't be displayed as you type - this is normal)

### Step 4: Done!

You'll see:

```
✅ SUCCESS!

Cloud images are now fully configured!
```

Go back to **Settings** in web UI and click **"Re-check Status"** to verify.

---

## Using Cloud Images

### Create a VM:

1. Go to **"Create VM"** in web UI
2. Select **"Cloud Image (Fast)"** installation method
3. Choose a cloud image:
   - Ubuntu 24.04 LTS
   - Ubuntu 22.04 LTS
   - Ubuntu 20.04 LTS
   - Debian 12
   - Debian 11
4. Configure CPU, RAM, disk size
5. Enter your desired **username** and **password**
6. Click **"Create VM"**

### Deployment Times:

- **First time using a cloud image**: 5-10 minutes (creates template)
- **Every time after that**: 30 seconds ⚡

---

## Troubleshooting

### Error: "SSH access not configured"

**Fix:** Run the setup script again:
```bash
sudo /tmp/enable_cloud_images.sh
```

### Setup script fails with "Permission denied"

**Possible causes:**
- Wrong password
- SSH password auth disabled on Proxmox

**Fix:** Try password again, or manually enable SSH password authentication on Proxmox.

### VM boots but no OS

**Cause:** Template is missing or corrupt

**Fix:** Delete and recreate template:
```bash
ssh root@pve.example.com "qm destroy 9001"
```
Then create a new VM - template will be recreated.

### Can't login to VM

**Cause:** Cloud-init didn't configure credentials

**Fix:** Check cloud-init logs via Proxmox console:
```bash
sudo cat /var/log/cloud-init.log
```

---

## Get Help

- **Full documentation**: `CLOUD_IMAGES_GUIDE.md`
- **Check logs**: `sudo journalctl -u depl0y-backend -f`
- **Verify SSH**: `sudo -u depl0y ssh root@pve.example.com "echo test"`
- **Check templates**: `ssh root@pve.example.com "qm list | grep 900"`

---

## Summary

✅ **One-time setup**: 1 minute
✅ **Maintenance**: Zero
✅ **Deployment time**: 30 seconds
✅ **Manual installation**: Never again

**Questions?** See full guide: `CLOUD_IMAGES_GUIDE.md`
