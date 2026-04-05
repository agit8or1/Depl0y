"""VM Import API - Import VMs from VMware, VirtualBox, Hyper-V and other platforms"""
import json
import logging
import os
import re
import shutil
import subprocess
import time
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from typing import Optional, List

from app.api.auth import require_operator
from app.core.database import SessionLocal, get_db
from app.services import vm_import_service as svc
from sqlalchemy.orm import Session

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


# ---------------------------------------------------------------------------
# New import endpoints
# ---------------------------------------------------------------------------

# Format detection map: extension → (format, recommendations)
_FORMAT_MAP = {
    ".qcow2":  ("qcow2",  ["Ready to import directly via Disk Image tab",
                            "Most efficient format for KVM/QEMU VMs"]),
    ".vmdk":   ("vmdk",   ["Import via Disk Image tab",
                            "Consider converting to qcow2 for better performance",
                            "Use convert-disk endpoint to convert on the Proxmox node"]),
    ".vhd":    ("vhd",    ["Hyper-V disk image",
                            "Convert to qcow2 before importing for best compatibility"]),
    ".vhdx":   ("vhdx",   ["Hyper-V VHDX disk image",
                            "Convert to qcow2 before importing for best compatibility"]),
    ".raw":    ("raw",    ["Raw disk image",
                            "Can be imported directly; qcow2 is preferred for snapshots"]),
    ".img":    ("raw",    ["Raw disk image (IMG)",
                            "Importable directly; rename or convert to qcow2 if needed"]),
    ".ova":    ("ova",    ["VMware/VirtualBox archive containing OVF + VMDK",
                            "Upload via OVA/OVF tab for automatic spec extraction",
                            "The VMDK disk inside will be converted to qcow2 during import"]),
    ".ovf":    ("ovf",    ["OVF descriptor file",
                            "Upload together with its VMDK disk via OVA/OVF tab"]),
    ".iso":    ("iso",    ["CD/DVD ISO image — not a disk image for VM import",
                            "Upload to Proxmox ISO storage and attach to a VM instead"]),
    ".zip":    ("zip",    ["ZIP archive — may contain OVF+VMDK",
                            "Upload via OVA/OVF tab; the server will extract and detect contents"]),
}


class DetectFormatRequest(BaseModel):
    filename: Optional[str] = None
    url: Optional[str] = None


@router.get("/detect-format")
def detect_format(
    filename: Optional[str] = None,
    url: Optional[str] = None,
    current_user=Depends(require_operator),
):
    """
    Detect disk/VM image format from a filename or URL.
    Returns the detected format and import recommendations.
    """
    name = filename or url or ""
    # Strip query strings from URL paths
    name = name.split("?")[0].split("#")[0]
    _, ext = os.path.splitext(name.lower())

    fmt, recommendations = _FORMAT_MAP.get(ext, (
        "unknown",
        [f"Unrecognised extension '{ext}'",
         "Supported: qcow2, vmdk, vhd, vhdx, raw, img, ova, ovf, zip"],
    ))

    return {
        "filename": os.path.basename(name),
        "extension": ext,
        "format": fmt,
        "recommendations": recommendations,
        "supported": fmt != "unknown",
        "direct_import": fmt in ("qcow2", "raw"),
        "needs_conversion": fmt in ("vmdk", "vhd", "vhdx"),
        "is_archive": fmt in ("ova", "zip", "ovf"),
    }


# ---------------------------------------------------------------------------
# From-URL import (downloads directly to Proxmox storage, then creates VM)
# ---------------------------------------------------------------------------

class FromUrlRequest(BaseModel):
    url: str
    proxmox_host_id: int
    node: str          # node name, e.g. "pve"
    storage: str       # Proxmox storage ID, e.g. "local-lvm"
    filename: Optional[str] = None      # override filename on Proxmox side
    checksum: Optional[str] = None
    checksum_algorithm: Optional[str] = None
    # VM creation params
    vm_name: Optional[str] = "imported-vm"
    vmid: Optional[int] = None
    cores: Optional[int] = 2
    memory: Optional[int] = 2048       # MB
    os_type: Optional[str] = "l26"
    network_bridge: Optional[str] = "vmbr0"
    disk_bus: Optional[str] = "scsi"   # scsi|virtio|sata|ide


@router.post("/from-url", status_code=status.HTTP_202_ACCEPTED)
async def import_from_url(
    req: FromUrlRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_operator),
):
    """
    Download a VM image/OVA from a URL directly to Proxmox storage, then
    create a VM using the downloaded disk.

    Steps:
      1. POST /nodes/{node}/storage/{storage}/download-url  (Proxmox API)
      2. Poll the returned UPID until the task finishes
      3. POST /nodes/{node}/qemu  to create the VM with import-from

    Returns: { job_id, upid, status }
    """
    from app.models import ProxmoxHost
    from app.services.proxmox import ProxmoxService

    host = db.query(ProxmoxHost).filter(
        ProxmoxHost.id == req.proxmox_host_id,
        ProxmoxHost.is_active == True,
    ).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")

    job_id = svc.create_import_job()
    job = svc.get_import_job(job_id)
    job["source_type"] = "url"
    job["status"] = "downloading"
    job["status_message"] = f"Queued: downloading from {req.url}"

    background_tasks.add_task(
        _run_from_url_import,
        job_id,
        req.model_dump(),
        host.id,
    )

    return {"job_id": job_id, "status": "downloading",
            "message": "URL import started — poll /{job_id}/progress for updates"}


async def _run_from_url_import(job_id: str, req: dict, host_id: int):
    """Background: download URL → Proxmox storage → create VM."""
    import asyncio
    from app.core.database import SessionLocal
    from app.models import ProxmoxHost
    from app.services.proxmox import ProxmoxService

    job = svc.get_import_job(job_id)
    if not job:
        return

    db = SessionLocal()
    try:
        host = db.query(ProxmoxHost).filter(ProxmoxHost.id == host_id).first()
        if not host:
            job["status"] = "error"
            job["error"] = "Proxmox host not found"
            return

        pve = ProxmoxService(host).proxmox
        node = req["node"]
        storage = req["storage"]

        # 1. Determine filename from URL if not provided
        raw_url = req["url"]
        filename = req.get("filename") or ""
        if not filename:
            url_path = raw_url.split("?")[0].split("#")[0]
            filename = os.path.basename(url_path) or "imported-disk.img"
        # Sanitize
        filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

        # 2. Trigger Proxmox download-url
        job["status_message"] = f"Requesting Proxmox to download: {filename}"
        download_params = {
            "url": raw_url,
            "content": "import",
            "filename": filename,
        }
        if req.get("checksum"):
            download_params["checksum"] = req["checksum"]
        if req.get("checksum_algorithm"):
            download_params["checksum-algorithm"] = req["checksum_algorithm"]

        try:
            dl_result = pve.nodes(node).storage(storage).post(
                "download-url", **download_params
            )
        except Exception as e:
            # Some Proxmox versions expose as a sub-resource path
            try:
                dl_result = pve.nodes(node).storage(storage).__getattr__("download-url").post(
                    **download_params
                )
            except Exception:
                raise e

        download_upid = dl_result if isinstance(dl_result, str) else str(dl_result)
        job["status_message"] = f"Downloading via Proxmox (UPID: {download_upid[:30]}...)"
        job["download_upid"] = download_upid

        # 3. Poll download task
        max_wait = 7200  # 2 hours
        waited = 0
        poll_interval = 5
        while waited < max_wait:
            await asyncio.sleep(poll_interval)
            waited += poll_interval
            try:
                task_status = pve.nodes(node).tasks(download_upid).status.get()
                pct = int(task_status.get("upid_extra", {}).get("progress", 0) or 0)
                job["progress"] = min(50, pct // 2)
                if task_status.get("status") == "stopped":
                    exit_status = task_status.get("exitstatus", "")
                    if exit_status == "OK":
                        break
                    else:
                        raise RuntimeError(f"Download task failed: {exit_status}")
            except RuntimeError:
                raise
            except Exception:
                pass  # ignore transient poll errors

        job["progress"] = 50
        job["status_message"] = f"Download complete. Creating VM from {filename}..."

        # 4. Get next VMID if not provided
        vmid = req.get("vmid") or None
        if not vmid:
            try:
                vmid = int(pve.cluster.nextid.get())
            except Exception:
                vmid = 9000

        vm_name = re.sub(r"[^a-zA-Z0-9_-]", "-", req.get("vm_name") or "imported-vm")[:63] or "imported-vm"
        cores = max(1, int(req.get("cores") or 2))
        memory = max(256, int(req.get("memory") or 2048))
        os_type = req.get("os_type") or "l26"
        bridge = req.get("network_bridge") or "vmbr0"
        bus = req.get("disk_bus") or "scsi"
        _, ext = os.path.splitext(filename.lower())
        fmt_hint = ""
        if ext in (".qcow2",):
            fmt_hint = ",format=qcow2"
        elif ext in (".vmdk",):
            fmt_hint = ",format=vmdk"
        elif ext in (".raw", ".img"):
            fmt_hint = ",format=raw"

        disk_key = f"{bus}0"
        import_volid = f"{storage}:0,import-from={storage}:{filename}{fmt_hint}"

        # 5. Create VM
        job["status"] = "deploying"
        job["status_message"] = f"Creating VM {vm_name} (VMID {vmid})..."
        create_params = {
            "vmid": vmid,
            "name": vm_name,
            "cores": cores,
            "memory": memory,
            "scsihw": "virtio-scsi-pci",
            "ostype": os_type,
            "net0": f"virtio,bridge={bridge}",
            "agent": "1",
            "onboot": 1,
            disk_key: import_volid,
        }
        create_upid = pve.nodes(node).qemu.post(**create_params)

        job["vmid"] = vmid
        job["vm_create_upid"] = str(create_upid)
        job["status"] = "completed"
        job["progress"] = 100
        job["status_message"] = f"VM {vm_name} (VMID {vmid}) created successfully"

    except Exception as e:
        logger.error(f"from-url import job {job_id} failed: {e}", exc_info=True)
        job["status"] = "error"
        job["error"] = str(e)
        job["status_message"] = f"Import failed: {str(e)}"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# From-OVF import (client parses OVF XML, sends config, we create the VM)
# ---------------------------------------------------------------------------

class OvfDisk(BaseModel):
    id: str = ""
    capacity_gb: int = 20
    file_ref: str = ""
    filename: str = ""
    volid: Optional[str] = None   # already-uploaded Proxmox volume ID


class OvfNic(BaseModel):
    name: str = ""
    bridge: str = "vmbr0"


class FromOvfRequest(BaseModel):
    # OVF-extracted config
    vm_name: str = "imported-vm"
    cpu_cores: int = 2
    memory_mb: int = 2048
    os_type: str = "l26"
    disks: List[OvfDisk] = []
    nics: List[OvfNic] = []
    description: str = ""
    # Proxmox target
    proxmox_host_id: int
    node: str
    storage: str
    vmid: Optional[int] = None
    network_bridge: str = "vmbr0"


@router.post("/from-ovf", status_code=status.HTTP_201_CREATED)
def import_from_ovf(
    req: FromOvfRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_operator),
):
    """
    Create a Proxmox VM from an OVF specification parsed on the client side.
    Assumes disk files have already been uploaded to the target Proxmox storage.

    Returns: { vmid, upid }
    """
    from app.models import ProxmoxHost
    from app.services.proxmox import ProxmoxService

    host = db.query(ProxmoxHost).filter(
        ProxmoxHost.id == req.proxmox_host_id,
        ProxmoxHost.is_active == True,
    ).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")

    pve = ProxmoxService(host).proxmox

    # Resolve VMID
    vmid = req.vmid or None
    if not vmid:
        try:
            vmid = int(pve.cluster.nextid.get())
        except Exception:
            vmid = 9000

    vm_name = re.sub(r"[^a-zA-Z0-9_-]", "-", req.vm_name)[:63] or "imported-vm"
    cores = max(1, req.cpu_cores)
    memory = max(256, req.memory_mb)
    os_type = req.os_type or "l26"

    # Build create params
    create_params: dict = {
        "vmid": vmid,
        "name": vm_name,
        "cores": cores,
        "sockets": 1,
        "memory": memory,
        "ostype": os_type,
        "scsihw": "virtio-scsi-pci",
        "agent": "1",
        "onboot": 1,
    }
    if req.description:
        create_params["description"] = req.description[:512]

    # Network interfaces — first NIC uses OVF mapping, rest use bridge from nics list
    if req.nics:
        for i, nic in enumerate(req.nics[:4]):
            bridge = nic.bridge or req.network_bridge or "vmbr0"
            create_params[f"net{i}"] = f"virtio,bridge={bridge}"
    else:
        create_params["net0"] = f"virtio,bridge={req.network_bridge or 'vmbr0'}"

    # Disks — attach by volid if provided
    for i, disk in enumerate(req.disks[:8]):
        if disk.volid:
            bus_key = f"scsi{i}"
            create_params[bus_key] = disk.volid
        elif disk.filename:
            # import-from syntax
            bus_key = f"scsi{i}"
            create_params[bus_key] = (
                f"{req.storage}:{disk.capacity_gb},"
                f"import-from={req.storage}:{disk.filename}"
            )
    if i == 0 and req.disks:
        create_params["boot"] = "order=scsi0"

    try:
        upid = pve.nodes(req.node).qemu.post(**create_params)
        return {"vmid": vmid, "upid": str(upid), "vm_name": vm_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VM creation failed: {str(e)}")


# ---------------------------------------------------------------------------
# Convert-disk (runs qemu-img convert on the Proxmox node via SSH)
# ---------------------------------------------------------------------------

class ConvertDiskRequest(BaseModel):
    proxmox_host_id: int
    node: str
    source_volid: str     # e.g. "local:iso/disk.vmdk"
    target_storage: str   # e.g. "local-lvm"
    target_format: str = "qcow2"   # qcow2|raw
    target_filename: Optional[str] = None


@router.post("/convert-disk", status_code=status.HTTP_202_ACCEPTED)
def convert_disk(
    req: ConvertDiskRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_operator),
):
    """
    Trigger a disk format conversion on a Proxmox node via SSH.
    Converts VMDK/VHD → qcow2 (or raw) using qemu-img, producing a new
    volume in target_storage.

    Returns: { command, note }  — the exact command executed, so the user
    can also run it manually if SSH is not available.
    """
    from app.models import ProxmoxHost
    from app.services import vm_import_service as _svc

    host = db.query(ProxmoxHost).filter(
        ProxmoxHost.id == req.proxmox_host_id,
        ProxmoxHost.is_active == True,
    ).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")

    # Resolve full source path from volid
    # Volid format: "storage:path/file.vmdk"
    parts = req.source_volid.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="source_volid must be 'storage:path/filename'")
    src_storage, src_rel = parts

    # Common storage roots on Proxmox
    storage_roots = {
        "local": "/var/lib/vz",
        "local-lvm": "/dev/pve",
    }
    # Best-effort: guess /var/lib/vz or /mnt/pve/<storage>
    if src_storage in storage_roots:
        src_path = os.path.join(storage_roots[src_storage], src_rel)
    else:
        src_path = f"/mnt/pve/{src_storage}/{src_rel}"

    _, src_ext = os.path.splitext(src_path.lower())
    fmt_map = {".vmdk": "vmdk", ".vhd": "vpc", ".vhdx": "vhdx",
               ".qcow2": "qcow2", ".raw": "raw", ".img": "raw"}
    src_fmt = fmt_map.get(src_ext, "raw")

    target_filename = req.target_filename or (
        re.sub(r"\.[^.]+$", "", os.path.basename(src_path)) + f".{req.target_format}"
    )
    target_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", target_filename)
    dst_path = f"/var/lib/vz/images/{target_filename}"

    cmd = (
        f"qemu-img convert -p -f {src_fmt} -O {req.target_format} "
        f"{src_path} {dst_path}"
    )

    try:
        result = _svc._ssh_run(host.hostname, cmd, timeout=3600)
        if result.returncode == 0:
            return {
                "success": True,
                "command": cmd,
                "output": result.stdout[:500] if result.stdout else "",
                "target_path": dst_path,
                "note": (
                    f"Conversion complete. The converted disk is at {dst_path} on node "
                    f"{req.node}. Use the Disk Image tab to create a VM from it."
                ),
            }
        else:
            return {
                "success": False,
                "command": cmd,
                "error": result.stderr[:500],
                "note": "SSH conversion failed. You can run the command manually on the Proxmox node.",
            }
    except Exception as e:
        return {
            "success": False,
            "command": cmd,
            "error": str(e),
            "note": "Could not reach Proxmox node via SSH. Run the command manually.",
        }
