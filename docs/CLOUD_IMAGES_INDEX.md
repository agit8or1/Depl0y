# Cloud Images Documentation Index

This directory contains all documentation related to the Cloud Images feature in Depl0y.

---

## 📚 Documentation Files

### 1. [CLOUD_IMAGES_QUICKSTART.md](../CLOUD_IMAGES_QUICKSTART.md)
**Best for: First-time users who want to get started quickly**

A concise, one-page guide covering:
- What cloud images are
- 4-step setup process
- How to create your first cloud image VM
- Quick troubleshooting tips

**Time to read:** 3 minutes

---

### 2. [CLOUD_IMAGES_GUIDE.md](../CLOUD_IMAGES_GUIDE.md)
**Best for: Complete understanding and troubleshooting**

Comprehensive 50+ page guide covering:
- Detailed explanation of cloud images
- Step-by-step setup with screenshots
- All available cloud images
- Technical architecture and how it works
- Complete troubleshooting section
- FAQ with 20+ common questions

**Time to read:** 20 minutes

---

### 3. Setup Script
**Location:** `/tmp/enable_cloud_images.sh`

The automated setup script that configures SSH access to Proxmox. Run once to enable all cloud images.

**How to run:**
```bash
sudo /tmp/enable_cloud_images.sh
```

**What it does:**
- Checks if SSH is already configured
- Installs dependencies (sshpass)
- Generates SSH key pair
- Copies public key to Proxmox
- Verifies configuration

---

## 🚀 Quick Links

### For Users

**"I just want to deploy VMs fast!"**
→ Read [CLOUD_IMAGES_QUICKSTART.md](../CLOUD_IMAGES_QUICKSTART.md)

**"I want to understand how this works"**
→ Read [CLOUD_IMAGES_GUIDE.md](../CLOUD_IMAGES_GUIDE.md)

**"Something's not working"**
→ See [Troubleshooting section in CLOUD_IMAGES_GUIDE.md](../CLOUD_IMAGES_GUIDE.md#troubleshooting)

### For Administrators

**"How do I set this up?"**
→ Run `/tmp/enable_cloud_images.sh` (details in [CLOUD_IMAGES_QUICKSTART.md](../CLOUD_IMAGES_QUICKSTART.md))

**"How does the architecture work?"**
→ See [Technical section in CLOUD_IMAGES_GUIDE.md](../CLOUD_IMAGES_GUIDE.md#how-it-works-technical)

**"Where are files stored?"**
- Cloud images: `/var/lib/depl0y/cloud-images/`
- SSH keys: `/opt/depl0y/.ssh/`
- Templates on Proxmox: VM IDs 9001, 9002, 9003, etc.

---

## 🎯 Feature Overview

### What Cloud Images Provide

| Feature | Description | Time Savings |
|---------|-------------|--------------|
| **Fast Deployment** | Pre-configured OS images | 20 min → 30 sec |
| **Auto-Configuration** | Credentials set automatically | 5 min → 0 sec |
| **Template Reuse** | First deploy creates template | One-time cost |
| **API-Only Cloning** | After template, pure API | Instant clones |

### Available Cloud Images

- Ubuntu 24.04 LTS (Noble)
- Ubuntu 22.04 LTS (Jammy)
- Ubuntu 20.04 LTS (Focal)
- Debian 12 (Bookworm)
- Debian 11 (Bullseye)

---

## 📖 Reading Guide

### Scenario 1: New User
1. ✅ Read [CLOUD_IMAGES_QUICKSTART.md](../CLOUD_IMAGES_QUICKSTART.md)
2. ✅ Run setup script: `sudo /tmp/enable_cloud_images.sh`
3. ✅ Create your first VM via web UI
4. ✅ Bookmark [CLOUD_IMAGES_GUIDE.md](../CLOUD_IMAGES_GUIDE.md) for reference

### Scenario 2: Troubleshooting
1. ✅ Check [Quick Troubleshooting in QUICKSTART](../CLOUD_IMAGES_QUICKSTART.md#troubleshooting)
2. ✅ If not resolved, see [Detailed Troubleshooting in GUIDE](../CLOUD_IMAGES_GUIDE.md#troubleshooting)
3. ✅ Check system logs: `sudo journalctl -u depl0y-backend -f`

### Scenario 3: Understanding Architecture
1. ✅ Read [How It Works section in GUIDE](../CLOUD_IMAGES_GUIDE.md#how-it-works-technical)
2. ✅ Review template creation process
3. ✅ Understand template ID system (9000 + cloud_image_id)

---

## 🔧 Key Commands Reference

### Setup
```bash
# Run one-time setup
sudo /tmp/enable_cloud_images.sh

# Verify SSH access
sudo -u depl0y ssh root@pve.example.com "echo test"
```

### Troubleshooting
```bash
# Check backend logs
sudo journalctl -u depl0y-backend -f

# List templates on Proxmox
ssh root@pve.example.com "qm list | grep 900"

# Delete a template (recreates on next deploy)
ssh root@pve.example.com "qm destroy 9001"

# Check cloud image downloads
ls -lh /var/lib/depl0y/cloud-images/
```

### Verification
```bash
# Check SSH status via API
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/cloud-images/ssh-status

# Check template status via API
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/cloud-images/templates/status/1
```

---

## 🎓 Learning Path

### Beginner → Advanced

**Level 1: Basic Usage**
- Read QUICKSTART
- Run setup script
- Create 1 VM with cloud image
- ✅ You can now deploy VMs in 30 seconds!

**Level 2: Understanding**
- Read GUIDE's "What Are Cloud Images?" section
- Read "How to Use Cloud Images" section
- Understand first-time vs subsequent deployments
- ✅ You understand the template system!

**Level 3: Technical Knowledge**
- Read "How It Works (Technical)" section
- Understand architecture diagram
- Learn template creation process
- Learn why SSH is required
- ✅ You can explain cloud images to others!

**Level 4: Expert**
- Read complete FAQ
- Read all troubleshooting scenarios
- Understand database schema
- Know all file locations
- ✅ You can troubleshoot any issue!

---

## 💡 Tips & Best Practices

### For Users
- ✅ Use cloud images for all Linux VMs (fastest)
- ✅ Keep templates (deleting them means re-creating = slow)
- ✅ First deployment per image type takes time (be patient)
- ✅ All subsequent deployments are instant (enjoy!)

### For Administrators
- ✅ Run setup script once during installation
- ✅ Ensure Proxmox has 5+ GB storage free
- ✅ Monitor `/var/lib/depl0y/cloud-images/` size
- ✅ Add setup to installation documentation
- ✅ Test SSH access after Proxmox updates

---

## 📞 Support Resources

### Documentation
- Quick Start: `CLOUD_IMAGES_QUICKSTART.md`
- Full Guide: `CLOUD_IMAGES_GUIDE.md`
- Main README: `README.md`

### System Resources
- Backend logs: `sudo journalctl -u depl0y-backend`
- Setup script: `/tmp/enable_cloud_images.sh`
- Cloud images: `/var/lib/depl0y/cloud-images/`
- SSH keys: `/opt/depl0y/.ssh/`

### Code Locations
- Backend API: `/opt/depl0y/backend/app/api/cloud_images.py`
- Deployment logic: `/opt/depl0y/backend/app/services/deployment.py`
- Frontend UI: `/opt/depl0y/frontend/src/views/Settings.vue`
- Database: `/var/lib/depl0y/db/depl0y.db`

---

## 📊 Feature Comparison

| Feature | Cloud Image | ISO Installation |
|---------|-------------|------------------|
| **First deployment** | 5-10 min | 20-30 min |
| **Subsequent deploys** | 30 sec | 20-30 min |
| **Setup required** | One-time (1 min) | Upload ISO |
| **OS configuration** | Automatic | Manual |
| **Credentials** | Pre-configured | Manual setup |
| **Network** | Auto-configured | Manual setup |
| **Storage used** | 300 MB + template | ISO file (~1 GB) |
| **Best for** | Repeated deployments | Custom configs |

---

**Last Updated:** November 16, 2025
**Version:** 1.0
