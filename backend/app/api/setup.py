"""Setup API endpoints for automated configuration"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.api.auth import get_current_user
from app.models import ProxmoxHost, ProxmoxNode
from app.core.database import get_db
from sqlalchemy.orm import Session
import logging
import subprocess
import os

logger = logging.getLogger(__name__)

router = APIRouter()


class CloudImageSetupRequest(BaseModel):
    proxmox_password: str


class ProxmoxClusterSSHRequest(BaseModel):
    proxmox_password: str


@router.post("/cloud-images/enable")
def enable_cloud_images(
    request: CloudImageSetupRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Automatically enable cloud images by running the setup script
    This sets up SSH access to Proxmox for cloud image template creation
    """
    try:
        # Get Proxmox host
        host = db.query(ProxmoxHost).first()
        if not host:
            raise HTTPException(
                status_code=404,
                detail="No Proxmox host configured. Please add a Proxmox host first."
            )

        proxmox_host = host.hostname
        password = request.proxmox_password

        if not password:
            raise HTTPException(
                status_code=400,
                detail="Proxmox root password is required"
            )

        logger.info(f"Starting cloud image setup for host {proxmox_host}")

        # Check if SSH is already configured
        check_ssh = subprocess.run(
            [
                'sudo', '-u', 'depl0y',
                'ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                '-o', 'StrictHostKeyChecking=no',
                f'root@{proxmox_host}',
                'echo test'
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if check_ssh.returncode == 0:
            logger.info("SSH already configured")
            return {
                "success": True,
                "already_configured": True,
                "message": "SSH access is already configured! Cloud images are ready to use."
            }

        # Install sshpass if not present
        logger.info("Checking for sshpass")
        check_sshpass = subprocess.run(
            ['which', 'sshpass'],
            capture_output=True
        )

        if check_sshpass.returncode != 0:
            logger.info("Installing sshpass")
            install_result = subprocess.run(
                [
                    'sudo', 'DEBIAN_FRONTEND=noninteractive',
                    'apt-get', 'install', '-y', '-qq', 'sshpass'
                ],
                capture_output=True,
                text=True,
                timeout=60
            )
            if install_result.returncode != 0:
                raise Exception(f"Failed to install sshpass: {install_result.stderr}")

        # Generate SSH key if it doesn't exist
        ssh_key_path = '/opt/depl0y/.ssh/id_rsa'
        if not os.path.exists(ssh_key_path):
            logger.info("Generating SSH key")
            subprocess.run(
                [
                    'sudo', '-u', 'depl0y',
                    'mkdir', '-p', '/opt/depl0y/.ssh'
                ],
                check=True
            )
            subprocess.run(
                [
                    'sudo', '-u', 'depl0y',
                    'ssh-keygen', '-t', 'rsa', '-b', '4096',
                    '-f', ssh_key_path,
                    '-N', '', '-q'
                ],
                check=True
            )

        # Copy SSH key to Proxmox using sshpass
        logger.info(f"Copying SSH key to {proxmox_host}")
        copy_result = subprocess.run(
            [
                'sudo', '-u', 'depl0y',
                'sshpass', '-p', password,
                'ssh-copy-id',
                '-o', 'StrictHostKeyChecking=no',
                '-i', f'{ssh_key_path}.pub',
                f'root@{proxmox_host}'
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if copy_result.returncode != 0:
            # Try alternative method
            logger.info("Trying alternative SSH key copy method")
            with open(f'{ssh_key_path}.pub', 'r') as f:
                public_key = f.read().strip()

            alt_result = subprocess.run(
                [
                    'sudo', '-u', 'depl0y',
                    'sshpass', '-p', password,
                    'ssh', '-o', 'StrictHostKeyChecking=no',
                    f'root@{proxmox_host}',
                    f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '{public_key}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && sort -u ~/.ssh/authorized_keys -o ~/.ssh/authorized_keys"
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            if alt_result.returncode != 0:
                raise Exception(f"Failed to copy SSH key: {alt_result.stderr}")

        # Verify SSH access works
        logger.info("Verifying SSH access")
        verify_result = subprocess.run(
            [
                'sudo', '-u', 'depl0y',
                'ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                '-o', 'StrictHostKeyChecking=no',
                f'root@{proxmox_host}',
                'echo SSH_CONFIGURED'
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if verify_result.returncode != 0 or 'SSH_CONFIGURED' not in verify_result.stdout:
            raise Exception(f"SSH verification failed: {verify_result.stderr}")

        logger.info("Cloud image setup completed successfully")

        return {
            "success": True,
            "already_configured": False,
            "message": "SSH access configured successfully! Cloud images are now enabled.",
            "details": {
                "host": proxmox_host,
                "ssh_key": f"{ssh_key_path}.pub"
            }
        }

    except subprocess.TimeoutExpired:
        logger.error("Setup timed out")
        raise HTTPException(
            status_code=408,
            detail="Setup operation timed out. Please check network connectivity to Proxmox."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cloud image setup failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enable cloud images: {str(e)}"
        )


@router.post("/proxmox-cluster-ssh/enable")
def enable_proxmox_cluster_ssh(
    request: ProxmoxClusterSSHRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Set up SSH access between Proxmox cluster nodes
    This allows the deployment system to target specific nodes for template creation
    """
    try:
        # Get Proxmox host
        host = db.query(ProxmoxHost).first()
        if not host:
            raise HTTPException(
                status_code=404,
                detail="No Proxmox host configured. Please add a Proxmox host first."
            )

        # Get all nodes
        nodes = db.query(ProxmoxNode).filter(ProxmoxNode.host_id == host.id).all()
        if len(nodes) < 2:
            return {
                "success": True,
                "already_configured": True,
                "message": "Only one node detected - inter-node SSH not needed for single node setups."
            }

        proxmox_host = host.hostname
        password = request.proxmox_password

        if not password:
            raise HTTPException(
                status_code=400,
                detail="Proxmox root password is required"
            )

        logger.info(f"Starting inter-node SSH setup for Proxmox cluster")

        # Check if inter-node SSH is already working
        node_names = [n.node_name for n in nodes]
        test_node_1 = node_names[0]
        test_node_2 = node_names[1] if len(node_names) > 1 else node_names[0]

        check_cmd = f"sudo -u depl0y ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@{proxmox_host} 'ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no {test_node_2} echo test' 2>&1"
        check_result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=15)

        if check_result.returncode == 0 and 'test' in check_result.stdout:
            logger.info("Inter-node SSH already configured")
            return {
                "success": True,
                "already_configured": True,
                "message": f"Inter-node SSH is already configured! Nodes can communicate with each other."
            }

        # Set up SSH keys on Proxmox cluster nodes
        logger.info("Setting up SSH keys between nodes...")

        setup_script = f"""
# Generate SSH key on first node if it doesn't exist
if [ ! -f ~/.ssh/id_rsa ]; then
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N '' -q
fi

# Get the public key
PUB_KEY=$(cat ~/.ssh/id_rsa.pub)

# Copy key to all other nodes
{' '.join([f'sshpass -p "{password}" ssh-copy-id -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa.pub root@{node} 2>/dev/null || sshpass -p "{password}" ssh -o StrictHostKeyChecking=no root@{node} "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo \\"$PUB_KEY\\" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && sort -u ~/.ssh/authorized_keys -o ~/.ssh/authorized_keys"' for node in node_names])}

# Also set up reverse keys (each node can SSH to others)
{' '.join([f'ssh -o StrictHostKeyChecking=no root@{node} "ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N \\"\\" -q 2>/dev/null || true; ssh-copy-id -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa.pub root@{proxmox_host} 2>/dev/null || true"' for node in node_names])}

echo "SSH_SETUP_COMPLETE"
"""

        # Execute setup via SSH to Proxmox
        cmd = f"sudo -u depl0y sshpass -p '{password}' ssh -o StrictHostKeyChecking=no root@{proxmox_host} '{setup_script}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            raise Exception(f"Failed to setup inter-node SSH: {result.stderr}")

        # Verify connectivity
        logger.info("Verifying inter-node SSH connectivity...")
        verify_cmd = f"sudo -u depl0y ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@{proxmox_host} 'ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no {test_node_2} echo VERIFIED'"
        verify_result = subprocess.run(verify_cmd, shell=True, capture_output=True, text=True, timeout=15)

        if verify_result.returncode != 0 or 'VERIFIED' not in verify_result.stdout:
            raise Exception(f"Inter-node SSH verification failed")

        logger.info("Inter-node SSH setup completed successfully")

        return {
            "success": True,
            "already_configured": False,
            "message": f"Inter-node SSH configured successfully! All {len(nodes)} nodes can now communicate.",
            "details": {
                "nodes": node_names,
                "tested": f"{test_node_1} → {test_node_2}"
            }
        }

    except subprocess.TimeoutExpired:
        logger.error("Setup timed out")
        raise HTTPException(
            status_code=408,
            detail="Setup operation timed out. Please check network connectivity."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Inter-node SSH setup failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enable inter-node SSH: {str(e)}"
        )
