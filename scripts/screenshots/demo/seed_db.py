"""Seed the demo database: admin user, version marker, synthetic audit history."""
import json
import os
import pathlib
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.environ.get("DEMO_REPO", "/home/administrator/depl0y") + "/backend")

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models import (User, UserRole, SystemSettings, AuditLog,  # noqa: E402
                        CloudImage, ISOImage, OSType)
from app.core.security import get_password_hash  # noqa: E402

import app.models.database  # noqa: E402,F401
import app.models.security  # noqa: E402,F401
import app.models.alert_models  # noqa: E402,F401

init_db()
db = SessionLocal()

user = db.query(User).filter(User.username == "admin").first()
if not user:
    user = User(username="admin", email="ops@example.net",
                hashed_password=get_password_hash(os.environ["DEMO_ADMIN_PASSWORD"]),
                role=UserRole.ADMIN, is_active=True, totp_enabled=False)
    db.add(user)
    db.commit()
    db.refresh(user)

# Derive the demo version from the repo rather than hardcoding it, so the
# version in the sidebar of every screenshot tracks the real release.
_pkg = pathlib.Path(os.environ.get("DEMO_REPO", "/home/administrator/depl0y")) / "frontend/package.json"
_version = json.loads(_pkg.read_text())["version"]

for k, v in [("app_version", os.environ.get("DEMO_VERSION", _version)),
             ("bmc_poll_interval_minutes", "5")]:
    row = db.query(SystemSettings).filter(SystemSettings.key == k).first()
    if row:
        row.value = v
    else:
        db.add(SystemSettings(key=k, value=v))
db.commit()

ACTIONS = [
    ("vm_snapshot_create", "vm", 103, "POST", "/api/v1/pve-vm/1/east-01/103/snapshots"),
    ("vm_start", "vm", 126, "POST", "/api/v1/pve-vm/1/east-03/126/start"),
    ("backup_job_run", "backup", 1, "POST", "/api/v1/backup/run"),
    ("idrac_firmware_check", "bmc", 3, "GET", "/api/v1/idrac/3/firmware"),
    ("vm_config_update", "vm", 117, "PUT", "/api/v1/pve-vm/1/east-02/117/config"),
    ("host_poll", "proxmox_host", 2, "POST", "/api/v1/proxmox/2/poll"),
    ("vm_migrate", "vm", 206, "POST", "/api/v1/pve-vm/2/west-01/206/migrate"),
    ("user_login", "auth", None, "POST", "/api/v1/auth/login"),
    ("vm_clone", "vm", 301, "POST", "/api/v1/pve-vm/3/lab-01/301/clone"),
    ("firewall_rule_create", "firewall", 101, "POST", "/api/v1/pve-vm/1/east-01/101/firewall/rules"),
    ("vm_stop", "vm", 215, "POST", "/api/v1/pve-vm/2/west-02/215/stop"),
    ("storage_scan", "storage", 1, "GET", "/api/v1/proxmox/nodes/1/storage"),
    ("idrac_poll", "bmc", None, "POST", "/api/v1/idrac/poll"),
    ("cloud_image_deploy", "vm", 302, "POST", "/api/v1/deploy/cloud-image"),
    ("vm_snapshot_delete", "vm", 112, "DELETE", "/api/v1/pve-vm/1/east-02/112/snapshots/old"),
    ("settings_update", "settings", None, "PUT", "/api/v1/system/settings"),
    ("vm_update_check", "vm", 101, "POST", "/api/v1/updates/101/check"),
    ("node_tasks_view", "node", 2, "GET", "/api/v1/pve-node/1/east-02/tasks"),
]

if db.query(AuditLog).count() == 0:
    now = datetime.utcnow()
    for i, (action, rtype, rid, method, path) in enumerate(ACTIONS):
        db.add(AuditLog(
            user_id=user.id, action=action, resource_type=rtype, resource_id=rid,
            ip_address="203.0.113.9", http_method=method, request_path=path,
            response_status=200, duration_ms=40 + i * 7, success=True,
            timestamp=now - timedelta(minutes=9 * (i + 1)),
        ))
    db.commit()

# ── Cloud image catalogue (demo rows; nothing is downloaded) ───────────────
CLOUD_IMAGES = [
    ("Ubuntu 24.04 LTS (Noble)", "noble-server-cloudimg-amd64.img", "ubuntu", "24.04",
     620_756_992, "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"),
    ("Ubuntu 22.04 LTS (Jammy)", "jammy-server-cloudimg-amd64.img", "ubuntu", "22.04",
     679_477_248, "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"),
    ("Debian 12 (Bookworm)", "debian-12-generic-amd64.qcow2", "debian", "12",
     351_272_960, "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2"),
    ("Rocky Linux 9", "Rocky-9-GenericCloud-Base.latest.x86_64.qcow2", "rocky", "9",
     1_186_988_032, "https://download.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud-Base.latest.x86_64.qcow2"),
]
if db.query(CloudImage).count() == 0:
    for name, filename, os_type, version, size, url in CLOUD_IMAGES:
        db.add(CloudImage(
            name=name, filename=filename, os_type=os_type, version=version,
            architecture="amd64", file_size=size, download_url=url,
            storage_path=f"/var/lib/depl0y/cloud-images/{filename}",
            is_downloaded=True, download_progress=100, download_status="completed",
            is_available=True))
    db.commit()

ISOS = [
    ("Ubuntu Server 24.04.1 LTS", "ubuntu-24.04.1-live-server-amd64.iso", OSType.UBUNTU,
     "24.04.1", 2_663_383_040),
    ("Debian 12.7 netinst", "debian-12.7.0-amd64-netinst.iso", OSType.DEBIAN,
     "12.7.0", 659_030_016),
    ("Rocky Linux 9.4 minimal", "Rocky-9.4-x86_64-minimal.iso", OSType.ROCKY,
     "9.4", 1_694_498_816),
]
if db.query(ISOImage).count() == 0:
    for name, filename, os_type, version, size in ISOS:
        db.add(ISOImage(
            name=name, filename=filename, os_type=os_type, version=version,
            architecture="amd64", file_size=size,
            storage_path=f"/var/lib/depl0y/isos/{filename}",
            uploaded_by=user.id, is_available=True))
    db.commit()

print(f"seeded: user={user.username} audit={db.query(AuditLog).count()} "
      f"cloud_images={db.query(CloudImage).count()} isos={db.query(ISOImage).count()}")
db.close()
