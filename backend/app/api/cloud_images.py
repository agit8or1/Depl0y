"""Cloud Images API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from app.core.database import get_db
from app.models import CloudImage
from app.api.auth import get_current_user
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter()


class CloudImageResponse(BaseModel):
    id: int
    name: str
    filename: str
    os_type: str
    version: str | None
    architecture: str
    file_size: int | None
    download_url: str
    is_downloaded: bool
    download_progress: int
    download_status: str
    is_available: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=List[CloudImageResponse])
def list_cloud_images(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """List all available cloud images"""
    try:
        images = db.query(CloudImage).filter(CloudImage.is_available == True).all()
        return images
    except Exception as e:
        logger.error(f"Failed to list cloud images: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/fetch-latest")
def fetch_latest_cloud_images(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Fetch the latest cloud image information from upstream sources and update existing images"""
    try:
        import requests
        import re
        from datetime import datetime

        updated_images = []
        errors = []

        # Get all existing cloud images
        images = db.query(CloudImage).filter(CloudImage.is_available == True).all()

        for image in images:
            try:
                updated = False
                old_version = image.version
                old_url = image.download_url

                # Ubuntu cloud images
                if image.os_type == 'ubuntu' and 'ubuntu' in image.download_url.lower():
                    # Extract version from existing URL or use stored version
                    version_match = re.search(r'(\d+\.\d+)', image.download_url)
                    if version_match:
                        version = version_match.group(1)

                        # Check for new URL format
                        base_url = f"https://cloud-images.ubuntu.com/releases/{version}/release/"
                        try:
                            response = requests.head(base_url + image.filename, timeout=10)
                            if response.status_code == 200:
                                new_url = base_url + image.filename
                                if new_url != image.download_url:
                                    image.download_url = new_url
                                    updated = True
                        except:
                            pass

                # Debian cloud images
                elif image.os_type == 'debian' and 'debian' in image.download_url.lower():
                    # Try to get latest release URL
                    try:
                        # Debian uses a "latest" symlink for current release
                        if 'latest' in image.download_url:
                            # URL is already using latest, just verify it's accessible
                            response = requests.head(image.download_url, timeout=10, allow_redirects=True)
                            if response.status_code == 200:
                                # Update version if we can determine it from redirect
                                if 'debian-' in response.url:
                                    version_match = re.search(r'debian-(\d+)', response.url)
                                    if version_match and version_match.group(1) != image.version:
                                        image.version = version_match.group(1)
                                        updated = True
                    except:
                        pass

                # Rocky Linux cloud images
                elif image.os_type == 'rocky' and 'rocky' in image.download_url.lower():
                    # Rocky Linux has versioned releases
                    version_match = re.search(r'rocky[/-](\d+)', image.download_url, re.IGNORECASE)
                    if version_match:
                        version = version_match.group(1)
                        # Check if URL is still valid
                        try:
                            response = requests.head(image.download_url, timeout=10)
                            if response.status_code != 200:
                                # Try to construct new URL
                                base_url = f"https://download.rockylinux.org/pub/rocky/{version}/images/x86_64/"
                                response = requests.head(base_url + image.filename, timeout=10)
                                if response.status_code == 200:
                                    image.download_url = base_url + image.filename
                                    updated = True
                        except:
                            pass

                if updated:
                    db.commit()
                    updated_images.append({
                        "name": image.name,
                        "old_version": old_version,
                        "new_version": image.version,
                        "old_url": old_url,
                        "new_url": image.download_url
                    })
                    logger.info(f"Updated cloud image: {image.name}")

            except Exception as e:
                error_msg = f"Failed to update {image.name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

        return {
            "message": f"Checked {len(images)} cloud images",
            "updated_count": len(updated_images),
            "updated_images": updated_images,
            "errors": errors if errors else None
        }

    except Exception as e:
        logger.error(f"Failed to fetch latest cloud images: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{image_id}/download")
def download_cloud_image(
    image_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Trigger download of a cloud image"""
    try:
        image = db.query(CloudImage).filter(CloudImage.id == image_id).first()
        if not image:
            raise HTTPException(status_code=404, detail="Cloud image not found")

        if image.is_downloaded:
            return {"message": "Cloud image already downloaded", "image": image}

        # Import here to avoid circular dependency
        from app.services.cloud_images import download_cloud_image_task

        # Start download in background
        background_tasks.add_task(download_cloud_image_task, image_id, db)

        return {"message": "Download started", "image_id": image_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start download: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{image_id}/progress")
def get_download_progress(
    image_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Get download progress for a cloud image"""
    try:
        image = db.query(CloudImage).filter(CloudImage.id == image_id).first()
        if not image:
            raise HTTPException(status_code=404, detail="Cloud image not found")

        return {
            "id": image.id,
            "name": image.name,
            "download_progress": image.download_progress,
            "download_status": image.download_status,
            "is_downloaded": image.is_downloaded
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get download progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CloudImageCreate(BaseModel):
    name: str
    filename: str
    os_type: str
    version: str | None = None
    architecture: str = "amd64"
    checksum: str | None = None
    download_url: str


class CloudImageUpdate(BaseModel):
    name: str | None = None
    filename: str | None = None
    os_type: str | None = None
    version: str | None = None
    architecture: str | None = None
    checksum: str | None = None
    download_url: str | None = None
    is_available: bool | None = None


@router.post("/", response_model=CloudImageResponse)
def create_cloud_image(
    image_data: CloudImageCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Create a new cloud image entry"""
    try:
        # Check if filename already exists
        existing = db.query(CloudImage).filter(CloudImage.filename == image_data.filename).first()
        if existing:
            raise HTTPException(status_code=400, detail="Cloud image with this filename already exists")

        new_image = CloudImage(
            name=image_data.name,
            filename=image_data.filename,
            os_type=image_data.os_type,
            version=image_data.version,
            architecture=image_data.architecture,
            checksum=image_data.checksum,
            download_url=image_data.download_url,
            download_status="pending",
            is_downloaded=False
        )

        db.add(new_image)
        db.commit()
        db.refresh(new_image)

        logger.info(f"Created new cloud image: {new_image.name}")
        return new_image
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create cloud image: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{image_id}", response_model=CloudImageResponse)
def update_cloud_image(
    image_id: int,
    image_data: CloudImageUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Update a cloud image entry"""
    try:
        image = db.query(CloudImage).filter(CloudImage.id == image_id).first()
        if not image:
            raise HTTPException(status_code=404, detail="Cloud image not found")

        # Update fields if provided
        if image_data.name is not None:
            image.name = image_data.name
        if image_data.filename is not None:
            image.filename = image_data.filename
        if image_data.os_type is not None:
            image.os_type = image_data.os_type
        if image_data.version is not None:
            image.version = image_data.version
        if image_data.architecture is not None:
            image.architecture = image_data.architecture
        if image_data.checksum is not None:
            image.checksum = image_data.checksum
        if image_data.download_url is not None:
            image.download_url = image_data.download_url
        if image_data.is_available is not None:
            image.is_available = image_data.is_available

        db.commit()
        db.refresh(image)

        logger.info(f"Updated cloud image: {image.name}")
        return image
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update cloud image: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{image_id}")
def delete_cloud_image(
    image_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Delete a cloud image"""
    try:
        image = db.query(CloudImage).filter(CloudImage.id == image_id).first()
        if not image:
            raise HTTPException(status_code=404, detail="Cloud image not found")

        # Delete the file if it exists
        if image.storage_path and os.path.exists(image.storage_path):
            try:
                os.remove(image.storage_path)
                logger.info(f"Deleted cloud image file: {image.storage_path}")
            except Exception as e:
                logger.warning(f"Failed to delete cloud image file: {e}")

        db.delete(image)
        db.commit()

        logger.info(f"Deleted cloud image: {image.name}")
        return {"message": "Cloud image deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete cloud image: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/setup-script")
def get_template_setup_script(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Get the shell script to setup cloud image templates on Proxmox"""
    # Get first 3 cloud images for the script
    images = db.query(CloudImage).filter(CloudImage.is_available == True).limit(3).all()

    script_lines = [
        "#!/bin/bash",
        "# Cloud Image Template Setup Script for Proxmox",
        "# Run this script on your Proxmox node as root",
        "",
        "set -e",
        "",
        "echo '============================================'",
        "echo 'Setting up cloud image templates...'",
        "echo '============================================'",
        "",
    ]

    for idx, image in enumerate(images):
        template_id = 9000 + idx
        script_lines.extend([
            f"# {image.name}",
            f"if ! qm status {template_id} &>/dev/null; then",
            f"  echo 'Creating template {template_id}: {image.name}'",
            f"  wget -q -O /var/lib/vz/template/iso/{image.filename} '{image.download_url}'",
            f"  qm create {template_id} --name '{image.name.lower().replace(' ', '-')}' --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0",
            f"  qm importdisk {template_id} /var/lib/vz/template/iso/{image.filename} local-lvm",
            f"  qm set {template_id} --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-{template_id}-disk-0",
            f"  qm set {template_id} --ide2 local-lvm:cloudinit",
            f"  qm set {template_id} --boot order=scsi0",
            f"  qm set {template_id} --serial0 socket --vga serial0",
            f"  qm set {template_id} --agent enabled=1",
            f"  qm template {template_id}",
            f"  echo '✓ Template {template_id} created'",
            "else",
            f"  echo 'Template {template_id} already exists'",
            "fi",
            "",
        ])

    script_lines.extend([
        "echo '============================================'",
        "echo 'Template setup complete!'",
        "echo 'You can now use cloud images in Depl0y'",
        "echo '============================================'",
    ])

    return {
        "script": "\n".join(script_lines)
    }


@router.get("/templates/status/{node_id}")
def check_templates_on_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Check which cloud image templates exist on a Proxmox node"""
    try:
        from app.models import ProxmoxNode, ProxmoxHost
        from app.services.proxmox import ProxmoxService

        node = db.query(ProxmoxNode).filter(ProxmoxNode.id == node_id).first()
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")

        host = db.query(ProxmoxHost).filter(ProxmoxHost.id == node.host_id).first()
        if not host:
            raise HTTPException(status_code=404, detail="Proxmox host not found")

        proxmox = ProxmoxService(host)

        # Check templates 9000-9010
        template_status = {}
        for i in range(9000, 9011):
            try:
                proxmox.proxmox.nodes(node.node_name).qemu(i).status.current.get()
                template_status[i] = True
            except:
                template_status[i] = False

        return {
            "node_id": node_id,
            "node_name": node.node_name,
            "templates": template_status
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SetupTemplatesRequest(BaseModel):
    node_id: int
    cloud_image_ids: List[int]


@router.post("/setup-templates")
def setup_templates_automated(
    request: SetupTemplatesRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Automatically setup cloud image templates on a Proxmox node"""
    try:
        from app.models import ProxmoxNode, ProxmoxHost
        from app.services.cloud_images import create_template_on_node

        node = db.query(ProxmoxNode).filter(ProxmoxNode.id == request.node_id).first()
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")

        host = db.query(ProxmoxHost).filter(ProxmoxHost.id == node.host_id).first()
        if not host:
            raise HTTPException(status_code=404, detail="Proxmox host not found")

        # Validate all cloud images exist
        for image_id in request.cloud_image_ids:
            image = db.query(CloudImage).filter(CloudImage.id == image_id).first()
            if not image:
                raise HTTPException(status_code=404, detail=f"Cloud image {image_id} not found")

        # Start template creation in background
        for image_id in request.cloud_image_ids:
            template_vmid = 9000 + (image_id - 1)
            background_tasks.add_task(
                create_template_on_node,
                image_id,
                request.node_id,
                template_vmid,
                db
            )

        return {
            "message": f"Template setup started for {len(request.cloud_image_ids)} cloud images on node {node.node_name}",
            "node_id": request.node_id,
            "node_name": node.node_name,
            "cloud_image_ids": request.cloud_image_ids
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start template setup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ssh-status")
def check_ssh_status(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Check if SSH access is configured for Proxmox hosts"""
    try:
        import subprocess
        from app.models import ProxmoxHost

        # Get the first Proxmox host
        host = db.query(ProxmoxHost).first()
        if not host:
            return {
                "configured": False,
                "message": "No Proxmox host configured"
            }

        # Test SSH connection
        try:
            # Try to run a simple command via SSH
            result = subprocess.run(
                [
                    'ssh',
                    '-o', 'BatchMode=yes',
                    '-o', 'ConnectTimeout=5',
                    '-o', 'StrictHostKeyChecking=no',
                    f'root@{host.hostname}',
                    'echo SSH_KEY_CONFIGURED'
                ],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and 'SSH_KEY_CONFIGURED' in result.stdout:
                return {
                    "configured": True,
                    "message": "SSH access is configured",
                    "host": host.hostname
                }
            else:
                return {
                    "configured": False,
                    "message": "SSH access not configured. Please run the setup script.",
                    "host": host.hostname
                }
        except subprocess.TimeoutExpired:
            return {
                "configured": False,
                "message": "SSH connection timed out",
                "host": host.hostname
            }
        except Exception as ssh_error:
            logger.warning(f"SSH check failed: {ssh_error}")
            return {
                "configured": False,
                "message": "SSH access not configured",
                "host": host.hostname
            }
    except Exception as e:
        logger.error(f"Failed to check SSH status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


