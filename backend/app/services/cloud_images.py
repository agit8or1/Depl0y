"""Cloud Image Download Service"""
import os
import requests
import logging
from sqlalchemy.orm import Session
from app.models import CloudImage
from app.core.config import settings

logger = logging.getLogger(__name__)

# Directory to store downloaded cloud images
CLOUD_IMAGES_DIR = os.path.join(settings.UPLOAD_DIR, "cloud-images")
os.makedirs(CLOUD_IMAGES_DIR, exist_ok=True)


def download_cloud_image_task(image_id: int, db: Session):
    """Download a cloud image from URL with progress tracking"""
    try:
        image = db.query(CloudImage).filter(CloudImage.id == image_id).first()
        if not image:
            logger.error(f"Cloud image {image_id} not found")
            return

        if image.is_downloaded:
            logger.info(f"Cloud image {image.id} already downloaded")
            return

        # Update status
        image.download_status = "downloading"
        image.download_progress = 0
        db.commit()

        logger.info(f"Starting download of {image.name} from {image.download_url}")

        # Download the file
        response = requests.get(image.download_url, stream=True, timeout=30)
        response.raise_for_status()

        # Get file size from headers
        total_size = int(response.headers.get('content-length', 0))
        image.file_size = total_size
        db.commit()

        # Determine file path
        storage_path = os.path.join(CLOUD_IMAGES_DIR, image.filename)
        image.storage_path = storage_path

        # Download with progress tracking
        downloaded = 0
        chunk_size = 8192  # 8KB chunks
        last_progress = 0

        logger.info(f"Downloading {total_size / (1024 * 1024):.1f} MB to {storage_path}")

        with open(storage_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Update progress every 5%
                    if total_size > 0:
                        progress = int((downloaded / total_size) * 100)
                        if progress >= last_progress + 5 or progress == 100:
                            image.download_progress = progress
                            db.commit()
                            logger.info(f"Download progress: {progress}% ({downloaded / (1024 * 1024):.1f} MB)")
                            last_progress = progress

        # Mark as completed
        image.download_status = "completed"
        image.download_progress = 100
        image.is_downloaded = True
        db.commit()

        logger.info(f"Successfully downloaded cloud image: {image.name}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download cloud image: {e}")
        if image:
            image.download_status = "error"
            image.download_progress = 0
            db.commit()
    except Exception as e:
        logger.error(f"Unexpected error during download: {e}")
        if image:
            image.download_status = "error"
            image.download_progress = 0
            db.commit()


def get_cloud_image_path(image_id: int, db: Session) -> str | None:
    """Get the local path of a downloaded cloud image"""
    try:
        image = db.query(CloudImage).filter(CloudImage.id == image_id).first()
        if not image:
            return None

        if not image.is_downloaded or not image.storage_path:
            return None

        if not os.path.exists(image.storage_path):
            logger.warning(f"Cloud image file not found at {image.storage_path}")
            image.is_downloaded = False
            db.commit()
            return None

        return image.storage_path
    except Exception as e:
        logger.error(f"Error getting cloud image path: {e}")
        return None


def create_template_on_node(image_id: int, node_id: int, template_vmid: int, db: Session):
    """Create a cloud image template on a Proxmox node"""
    try:
        from app.models import CloudImage, ProxmoxNode, ProxmoxHost
        from app.services.proxmox import ProxmoxService
        import time

        image = db.query(CloudImage).filter(CloudImage.id == image_id).first()
        if not image:
            logger.error(f"Cloud image {image_id} not found")
            return

        node = db.query(ProxmoxNode).filter(ProxmoxNode.id == node_id).first()
        if not node:
            logger.error(f"Node {node_id} not found")
            return

        host = db.query(ProxmoxHost).filter(ProxmoxHost.id == node.host_id).first()
        if not host:
            logger.error(f"Proxmox host not found for node {node_id}")
            return

        proxmox = ProxmoxService(host)

        logger.info(f"Creating template {template_vmid} for {image.name} on node {node.node_name}")

        # Check if template already exists
        try:
            proxmox.proxmox.nodes(node.node_name).qemu(template_vmid).status.current.get()
            logger.info(f"Template {template_vmid} already exists on {node.node_name}")
            return
        except:
            pass  # Template doesn't exist, create it

        # Step 1: Download cloud image if not already downloaded
        if not image.is_downloaded or not image.storage_path:
            logger.info(f"Downloading cloud image {image.name}")
            download_cloud_image_task(image_id, db)

            # Wait for download to complete
            max_wait = 3600  # 1 hour max
            waited = 0
            while not image.is_downloaded and waited < max_wait:
                time.sleep(5)
                waited += 5
                db.refresh(image)

            if not image.is_downloaded:
                raise Exception(f"Cloud image download timed out after {max_wait} seconds")

        # Step 2: Upload cloud image to Proxmox
        logger.info(f"Uploading cloud image to {node.node_name}")

        # Use Proxmox API to upload to ISO storage
        image_filename = image.filename
        with open(image.storage_path, 'rb') as f:
            # Upload via Proxmox API
            upload_url = f"/nodes/{node.node_name}/storage/local/upload"
            files = {'filename': (image_filename, f)}
            data = {'content': 'iso'}

            proxmox.proxmox.nodes(node.node_name).storage('local').upload.post(
                content='iso',
                filename=f
            )

        logger.info(f"Cloud image uploaded to {node.node_name}:local/iso/{image_filename}")

        # Step 3: Create VM shell
        logger.info(f"Creating VM shell {template_vmid}")
        proxmox.proxmox.nodes(node.node_name).qemu.create(
            vmid=template_vmid,
            name=f"cloud-{image.os_type}-{image.version or 'latest'}",
            memory=2048,
            cores=2,
            sockets=1,
            net0='virtio,bridge=vmbr0',
            scsihw='virtio-scsi-pci',
            ostype='l26' if image.os_type != 'windows' else 'win10',
            agent=1
        )

        time.sleep(2)

        # Step 4: Import disk using qm importdisk (requires SSH/exec)
        # For now, we'll add a note that manual import is needed
        logger.warning(f"Template {template_vmid} created but requires manual disk import")
        logger.warning(f"Run on Proxmox node: qm importdisk {template_vmid} /var/lib/vz/template/iso/{image_filename} local-lvm")

        # Step 5: Configure disk and cloud-init
        proxmox.proxmox.nodes(node.node_name).qemu(template_vmid).config.put(
            scsi0='local-lvm:0,import-from=/var/lib/vz/template/iso/' + image_filename,
            ide2='local-lvm:cloudinit',
            boot='order=scsi0',
            serial0='socket',
            vga='serial0'
        )

        # Step 6: Convert to template
        proxmox.proxmox.nodes(node.node_name).qemu(template_vmid).template.post()

        logger.info(f"Successfully created template {template_vmid} on {node.node_name}")

    except Exception as e:
        logger.error(f"Failed to create template: {e}", exc_info=True)
