"""VM Import API - Import VMs from VMware, VirtualBox, Hyper-V and other platforms"""
import json
import logging
import os
import shutil
import subprocess
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from typing import Optional

from app.api.auth import require_operator
from app.core.database import SessionLocal
from app.services import vm_import_service as svc

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# VMware connection models
# ---------------------------------------------------------------------------

class VMwareConnectRequest(BaseModel):
    hostname: str
    username: str
    password: str
    port: int = 443
    verify_ssl: bool = False


class VMwarePrepareRequest(BaseModel):
    hostname: str
    username: str
    password: str
    port: int = 443
    verify_ssl: bool = False
    moref: str  # VM managed object reference ID


# ---------------------------------------------------------------------------
# VMware endpoints
# ---------------------------------------------------------------------------

@router.post("/vmware/test")
def vmware_test_connection(
    req: VMwareConnectRequest,
    current_user=Depends(require_operator),
):
    """Test connection to an ESXi host or vCenter server."""
    try:
        from app.services import vmware_service
        info = vmware_service.test_connection(
            req.hostname, req.username, req.password, req.port, req.verify_ssl
        )
        return {"success": True, **info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")


@router.post("/vmware/vms")
def vmware_list_vms(
    req: VMwareConnectRequest,
    current_user=Depends(require_operator),
):
    """List all VMs on a VMware ESXi host or vCenter."""
    try:
        from app.services import vmware_service
        vms = vmware_service.list_vms(
            req.hostname, req.username, req.password, req.port, req.verify_ssl
        )
        return {"vms": vms}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to list VMs: {str(e)}")


@router.post("/vmware/prepare", status_code=status.HTTP_201_CREATED)
async def vmware_prepare_import(
    req: VMwarePrepareRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(require_operator),
):
    """
    Start downloading a VM from VMware for import.
    Creates an import job and begins downloading VMDKs in the background.
    Poll /{job_id}/progress until status == 'parsed', then call /{job_id}/deploy.
    """
    job_id = svc.create_import_job()
    import_dir = os.path.join(svc.IMPORT_UPLOAD_DIR, job_id)
    os.makedirs(import_dir, exist_ok=True)

    job = svc.get_import_job(job_id)
    job["import_dir"] = import_dir
    job["status"] = "downloading"
    job["status_message"] = "Connecting to VMware..."
    job["source_type"] = "vmware"

    background_tasks.add_task(
        _run_vmware_download,
        job_id,
        req.hostname,
        req.username,
        req.password,
        req.port,
        req.verify_ssl,
        req.moref,
        import_dir,
    )

    return {"job_id": job_id, "message": "VMware download started"}


async def _run_vmware_download(
    job_id: str,
    hostname: str,
    username: str,
    password: str,
    port: int,
    verify_ssl: bool,
    moref: str,
    import_dir: str,
):
    """Background task: download VMDK files from VMware."""
    from app.services import vmware_service

    job = svc.get_import_job(job_id)
    if not job:
        return

    try:
        vmware_service.download_vm_disks(
            job_id=job_id,
            hostname=hostname,
            username=username,
            password=password,
            port=port,
            verify_ssl=verify_ssl,
            moref=moref,
            import_dir=import_dir,
            job=job,
        )
        # Download complete — mark as parsed so the UI can advance to Review step
        job["status"] = "parsed"
        job["filename"] = f"vmware-import-{moref}"

    except Exception as e:
        logger.error(f"VMware download job {job_id} failed: {e}", exc_info=True)
        job["status"] = "error"
        job["error"] = str(e)
        job["status_message"] = f"Download failed: {str(e)}"
        try:
            shutil.rmtree(import_dir, ignore_errors=True)
        except Exception:
            pass

SUPPORTED_EXTENSIONS = {
    ".ova", ".ovf", ".vmdk", ".vhd", ".vhdx", ".qcow2", ".img", ".raw", ".zip"
}
MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024 * 1024  # 200 GB


class ImportDeployRequest(BaseModel):
    proxmox_host_id: int
    node_id: int
    storage: str
    vm_name: Optional[str] = None
    cpu_cores: Optional[int] = None
    memory_mb: Optional[int] = None
    network_bridge: Optional[str] = "vmbr0"
    os_type: Optional[str] = None
    username: Optional[str] = "administrator"
    password: Optional[str] = ""


@router.get("/")
def list_imports(current_user=Depends(require_operator)):
    """List all active import jobs."""
    return [
        {
            "job_id": j["id"],
            "status": j["status"],
            "progress": j["progress"],
            "status_message": j["status_message"],
            "filename": j.get("filename", ""),
            "file_size_mb": j.get("file_size_mb", 0),
            "specs": j.get("specs"),
            "error": j.get("error"),
        }
        for j in svc.list_import_jobs()
    ]


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_import_file(
    file: UploadFile = File(...),
    current_user=Depends(require_operator),
):
    """
    Upload a VM image file for import.

    Supported formats:
    - OVA (VMware/VirtualBox archive)
    - OVF + VMDK (separate or zipped)
    - VMDK (VMware disk)
    - VHD / VHDX (Hyper-V)
    - QCOW2 / RAW / IMG (QEMU/KVM)
    """
    filename = file.filename or "upload"
    _, ext = os.path.splitext(filename.lower())

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    job_id = svc.create_import_job()
    import_dir = os.path.join(svc.IMPORT_UPLOAD_DIR, job_id)
    os.makedirs(import_dir, exist_ok=True)

    job = svc.get_import_job(job_id)
    job["import_dir"] = import_dir

    try:
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(import_dir, safe_filename)

        total_written = 0
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB chunks
                if not chunk:
                    break
                f.write(chunk)
                total_written += len(chunk)
                if total_written > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413, detail="File too large (max 200 GB)"
                    )

        job["status"] = "parsing"
        job["status_message"] = "Parsing VM specifications..."

        # Parse specs based on file type
        specs: dict = {
            "name": "imported-vm",
            "cpu_cores": 1,
            "memory_mb": 512,
            "disks": [],
            "os_type": "other",
            "description": "",
        }

        if ext == ".ova":
            ovf_path = svc.extract_ova(file_path, import_dir)
            if ovf_path:
                specs = svc.parse_ovf(ovf_path)

        elif ext == ".ovf":
            specs = svc.parse_ovf(file_path)

        elif ext == ".zip":
            try:
                with zipfile.ZipFile(file_path, "r") as zf:
                    zf.extractall(import_dir)
                os.remove(file_path)
                for fname in os.listdir(import_dir):
                    if fname.lower().endswith(".ovf"):
                        specs = svc.parse_ovf(os.path.join(import_dir, fname))
                        break
            except Exception as e:
                logger.warning(f"ZIP extraction failed: {e}")

        elif ext in (".vmdk", ".vhd", ".vhdx", ".qcow2", ".img", ".raw"):
            # Probe with qemu-img for disk size
            try:
                result = subprocess.run(
                    ["qemu-img", "info", "--output=json", file_path],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    info = json.loads(result.stdout)
                    vsz = info.get("virtual-size", 0)
                    disk_gb = max(1, int(vsz // (1024 ** 3)))
                    specs["disks"] = [{
                        "id": "disk0",
                        "capacity_gb": disk_gb,
                        "file_ref": "disk0",
                        "filename": safe_filename,
                    }]
            except Exception as e:
                logger.warning(f"qemu-img info failed: {e}")

        disk_files = svc.find_disk_files(import_dir)

        job["specs"] = specs
        job["disk_files"] = [os.path.basename(d) for d in disk_files]
        job["status"] = "parsed"
        job["status_message"] = "File parsed successfully. Ready to deploy."
        job["progress"] = 0
        job["filename"] = safe_filename
        job["file_size_mb"] = round(total_written / (1024 * 1024), 1)

        return {
            "job_id": job_id,
            "filename": safe_filename,
            "file_size_mb": job["file_size_mb"],
            "specs": specs,
            "disk_files": job["disk_files"],
        }

    except HTTPException:
        shutil.rmtree(import_dir, ignore_errors=True)
        svc.delete_import_job(job_id)
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        shutil.rmtree(import_dir, ignore_errors=True)
        svc.delete_import_job(job_id)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/{job_id}/deploy")
async def deploy_import(
    job_id: str,
    request: ImportDeployRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(require_operator),
):
    """Start deploying an uploaded VM image to Proxmox."""
    job = svc.get_import_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")

    if job["status"] != "parsed":
        raise HTTPException(
            status_code=400,
            detail=f"Import job is in state '{job['status']}', expected 'parsed'",
        )

    job["status"] = "queued"
    job["status_message"] = "Queued for deployment..."

    background_tasks.add_task(
        svc.run_import_job, job_id, request.model_dump(), SessionLocal
    )

    return {"message": "Import deployment started", "job_id": job_id}


@router.get("/{job_id}/progress")
def get_import_progress(job_id: str, current_user=Depends(require_operator)):
    """Get progress of an import job."""
    job = svc.get_import_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")

    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "status_message": job["status_message"],
        "error": job.get("error"),
        "vm_id": job.get("vm_id"),
        "vmid": job.get("vmid"),
        "manual_import_cmd": job.get("manual_import_cmd"),
    }


@router.delete("/{job_id}")
def cancel_import(job_id: str, current_user=Depends(require_operator)):
    """Cancel or clean up an import job."""
    job = svc.get_import_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")

    if job["status"] in ("converting", "deploying", "queued"):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete an in-progress import job. Wait for it to complete or fail.",
        )

    svc.delete_import_job(job_id)
    return {"message": "Import job deleted"}
