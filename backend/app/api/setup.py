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

        # SECURITY: Validate hostname to prevent command injection
        import re
        if not re.match(r'^[a-zA-Z0-9._-]+$', proxmox_host):
            raise HTTPException(status_code=400, detail="Invalid hostname format")

        logger.info(f"Starting cloud image setup for host {proxmox_host}")

        # Check if SSH is already configured
        # Backend already runs as depl0y user, no need for sudo -u
        check_ssh = subprocess.run(
            [
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
            ['/usr/bin/which', 'sshpass'],
            capture_output=True
        )

        if check_sshpass.returncode != 0:
            logger.info("Installing sshpass")
            # Use the exact command allowed in sudoers
            install_result = subprocess.run(
                [
                    '/usr/bin/sudo', '/usr/bin/apt-get', 'install', '-y', '-qq', 'sshpass'
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
            # Backend already runs as depl0y user, no need for sudo -u
            subprocess.run(
                [
                    'mkdir', '-p', '/opt/depl0y/.ssh'
                ],
                check=True
            )
            subprocess.run(
                [
                    'ssh-keygen', '-t', 'rsa', '-b', '4096',
                    '-f', ssh_key_path,
                    '-N', '', '-q'
                ],
                check=True
            )

        # Copy SSH key to Proxmox using sshpass
        logger.info(f"Copying SSH key to {proxmox_host}")
        # Backend already runs as depl0y user, no need for sudo -u
        copy_result = subprocess.run(
            [
                '/usr/bin/sshpass', '-p', password,
                '/usr/bin/ssh-copy-id',
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

            # Backend already runs as depl0y user, no need for sudo -u
            # SECURITY: Use proper shell escaping with shlex.quote to prevent command injection
            import shlex
            safe_public_key = shlex.quote(public_key)
            alt_result = subprocess.run(
                [
                    '/usr/bin/sshpass', '-p', password,
                    '/usr/bin/ssh', '-o', 'StrictHostKeyChecking=no',
                    f'root@{proxmox_host}',
                    f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo {safe_public_key} >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && sort -u ~/.ssh/authorized_keys -o ~/.ssh/authorized_keys"
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            if alt_result.returncode != 0:
                raise Exception(f"Failed to copy SSH key: {alt_result.stderr}")

        # Verify SSH access works
        logger.info("Verifying SSH access")
        # Backend already runs as depl0y user, no need for sudo -u
        verify_result = subprocess.run(
            [
                '/usr/bin/ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
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
        # SECURITY: Sanitize node names to prevent command injection
        import re
        node_names = [n.node_name for n in nodes]
        # Validate node names contain only alphanumeric, dots, hyphens, underscores
        for node_name in node_names:
            if not re.match(r'^[a-zA-Z0-9._-]+$', node_name):
                raise HTTPException(status_code=400, detail=f"Invalid node name: {node_name}")

        test_node_1 = node_names[0]
        test_node_2 = node_names[1] if len(node_names) > 1 else node_names[0]

        # Backend already runs as depl0y user, no need for sudo -u
        # SECURITY: Validate hostname to prevent injection
        if not re.match(r'^[a-zA-Z0-9._-]+$', proxmox_host):
            raise HTTPException(status_code=400, detail="Invalid hostname")

        check_result = subprocess.run(
            [
                'ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                '-o', 'StrictHostKeyChecking=no', f'root@{proxmox_host}',
                f'ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no {test_node_2} echo test'
            ],
            capture_output=True,
            text=True,
            timeout=15,
            stderr=subprocess.STDOUT
        )

        if check_result.returncode == 0 and 'test' in check_result.stdout:
            logger.info("Inter-node SSH already configured")
            return {
                "success": True,
                "already_configured": True,
                "message": f"Inter-node SSH is already configured! Nodes can communicate with each other."
            }

        # Set up SSH keys on Proxmox cluster nodes
        logger.info("Setting up SSH keys between nodes...")

        # SECURITY: Build setup script safely without exposing password in shell commands
        # Use shlex.quote to properly escape all variables
        import shlex

        # Build safe node list for the shell script
        safe_node_list = ' '.join([shlex.quote(node) for node in node_names])
        safe_proxmox_host = shlex.quote(proxmox_host)

        # Create a safe setup script that doesn't include the password
        setup_script = f"""#!/bin/bash
set -e

# Generate SSH key on first node if it doesn't exist
if [ ! -f ~/.ssh/id_rsa ]; then
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N '' -q
fi

# Get the public key
PUB_KEY=$(cat ~/.ssh/id_rsa.pub)

# Copy key to all other nodes
for node in {safe_node_list}; do
    ssh-copy-id -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa.pub root@$node 2>/dev/null || true
    ssh -o StrictHostKeyChecking=no root@$node "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo \\"$PUB_KEY\\" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && sort -u ~/.ssh/authorized_keys -o ~/.ssh/authorized_keys" 2>/dev/null || true
done

# Set up reverse keys (each node can SSH to others)
for node in {safe_node_list}; do
    ssh -o StrictHostKeyChecking=no root@$node "ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N '' -q 2>/dev/null || true; ssh-copy-id -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa.pub root@{safe_proxmox_host} 2>/dev/null || true" 2>/dev/null || true
done

echo "SSH_SETUP_COMPLETE"
"""

        # Execute setup via SSH to Proxmox using sshpass
        # SECURITY: Password is passed via -p flag, not in shell command
        result = subprocess.run(
            ['/usr/bin/sshpass', '-p', password, '/usr/bin/ssh',
             '-o', 'StrictHostKeyChecking=no', f'root@{proxmox_host}',
             setup_script],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            raise Exception(f"Failed to setup inter-node SSH: {result.stderr}")

        # Verify connectivity
        logger.info("Verifying inter-node SSH connectivity...")
        # Backend already runs as depl0y user, no need for sudo -u
        # SECURITY: Use argument list instead of shell=True
        verify_result = subprocess.run(
            ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
             '-o', 'StrictHostKeyChecking=no', f'root@{proxmox_host}',
             f'ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no {test_node_2} echo VERIFIED'],
            capture_output=True,
            text=True,
            timeout=15
        )

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
