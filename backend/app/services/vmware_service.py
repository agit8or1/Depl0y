"""VMware ESXi / vCenter integration for direct VM import via pyVmomi."""
import re
import ssl
import logging
import os
import time
from typing import Dict, Any, List, Optional

import requests
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SSL / connection helpers
# ---------------------------------------------------------------------------

def _make_ssl_context(verify_ssl: bool) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _connect(hostname: str, username: str, password: str, port: int, verify_ssl: bool):
    """Return a connected SmartConnect ServiceInstance."""
    ctx = _make_ssl_context(verify_ssl)
    return SmartConnect(
        host=hostname, user=username, pwd=password,
        port=port, sslContext=ctx,
    )


# ---------------------------------------------------------------------------
# Public API: test connection
# ---------------------------------------------------------------------------

def test_connection(
    hostname: str, username: str, password: str,
    port: int = 443, verify_ssl: bool = False,
) -> Dict[str, Any]:
    """
    Test credentials against ESXi / vCenter.
    Returns dict with name, version, api_type ('VirtualCenter' or 'HostAgent').
    Raises on failure.
    """
    si = _connect(hostname, username, password, port, verify_ssl)
    try:
        about = si.content.about
        return {
            "full_name": about.fullName,
            "version": about.version,
            "build": about.build,
            "api_type": about.apiType,  # 'VirtualCenter' or 'HostAgent'
        }
    finally:
        Disconnect(si)


# ---------------------------------------------------------------------------
# Public API: list VMs
# ---------------------------------------------------------------------------

def _os_from_guest_id(guest_id: str) -> str:
    """Map VMware guestId string to our OS type string."""
    g = (guest_id or "").lower()
    if "windows" in g or "win" in g:
        return "windows"
    if "ubuntu" in g:
        return "ubuntu"
    if "debian" in g:
        return "debian"
    if "centos" in g:
        return "centos"
    if "rhel" in g or "redhat" in g:
        return "centos"
    if "rocky" in g:
        return "rocky"
    if "alma" in g:
        return "alma"
    if "freebsd" in g:
        return "freebsd"
    if "pfsense" in g:
        return "pfsense"
    if "opnsense" in g:
        return "opnsense"
    return "other"


def list_vms(
    hostname: str, username: str, password: str,
    port: int = 443, verify_ssl: bool = False,
) -> List[Dict[str, Any]]:
    """Return list of VMs on the ESXi host / vCenter."""
    si = _connect(hostname, username, password, port, verify_ssl)
    try:
        content = si.RetrieveContent()
        container = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )
        result = []
        for vm in container.view:
            try:
                cfg = vm.config
                hw = cfg.hardware
                disks = []
                for device in hw.device:
                    if isinstance(device, vim.vm.device.VirtualDisk):
                        cap_kb = getattr(device, "capacityInKB", 0)
                        cap_gb = max(1, int(cap_kb / (1024 * 1024)))
                        backing = getattr(device.backing, "fileName", "")
                        disks.append({
                            "label": device.deviceInfo.label,
                            "capacity_gb": cap_gb,
                            "backing": backing,
                        })
                result.append({
                    "moref": vm._moId,
                    "name": vm.name,
                    "cpu_cores": hw.numCPU,
                    "memory_mb": hw.memoryMB,
                    "os": cfg.guestFullName or "Unknown",
                    "guest_id": cfg.guestId or "",
                    "os_type": _os_from_guest_id(cfg.guestId or ""),
                    "power_state": str(vm.runtime.powerState),
                    "disks": disks,
                    "total_disk_gb": sum(d["capacity_gb"] for d in disks),
                })
            except Exception as e:
                logger.warning(f"Skipping VM {getattr(vm, 'name', '?')}: {e}")
        container.Destroy()
        return result
    finally:
        Disconnect(si)


# ---------------------------------------------------------------------------
# VMDK download helpers
# ---------------------------------------------------------------------------

def _parse_vmdk_extents(descriptor_text: str) -> List[str]:
    """
    Parse a VMDK descriptor file and return the extent file names (relative paths).
    Handles monolithic-sparse, monolithic-flat, and 2GB-extent variants.
    """
    extents = []
    for line in descriptor_text.splitlines():
        line = line.strip()
        # Lines look like: RW 204800 SPARSE "vm-flat.vmdk"
        # or:              RW 204800 FLAT   "vm-flat.vmdk" 0
        m = re.match(r'^(?:RW|RDONLY|NOACCESS)\s+\d+\s+\S+\s+"([^"]+)"', line)
        if m:
            extents.append(m.group(1))
    return extents


def _vmdk_folder(vmdk_path: str) -> str:
    """Return the folder prefix of a datastore VMDK path."""
    idx = vmdk_path.rfind("/")
    return vmdk_path[:idx + 1] if idx >= 0 else ""


def _datastore_url(hostname: str, port: int, dc_path: str, ds_name: str, file_path: str) -> str:
    return (
        f"https://{hostname}:{port}/folder"
        f"/{requests.utils.quote(file_path, safe='/')}"
        f"?dcPath={requests.utils.quote(dc_path)}"
        f"&dsName={requests.utils.quote(ds_name)}"
    )


def _get_datacenter_path(content, vm) -> str:
    """Walk the inventory tree upward from the VM to find the Datacenter name."""
    obj = vm.parent
    while obj is not None:
        if isinstance(obj, vim.Datacenter):
            return obj.name
        obj = getattr(obj, "parent", None)
    return "ha-datacenter"  # ESXi standalone default


def _download_file(
    url: str,
    dest_path: str,
    auth: tuple,
    verify_ssl: bool,
    job: Dict,
    total_so_far: int,
    grand_total: int,
    label: str = "",
) -> int:
    """
    Stream-download a file from VMware datastore HTTP.
    Returns bytes downloaded. Updates job progress (0-55% range).
    """
    with requests.get(url, auth=auth, verify=verify_ssl, stream=True, timeout=30) as resp:
        resp.raise_for_status()
        file_size = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        start_time = time.time()

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=4 * 1024 * 1024):  # 4 MB chunks
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                total_so_far += len(chunk)

                elapsed = max(0.1, time.time() - start_time)
                speed_mbs = (downloaded / (1024 * 1024)) / elapsed
                pct_file = (downloaded / file_size * 100) if file_size else 0

                if grand_total > 0:
                    overall_pct = min(55, int((total_so_far / grand_total) * 55))
                    job["progress"] = overall_pct

                mb_done = downloaded / (1024 * 1024)
                mb_total = file_size / (1024 * 1024) if file_size else 0
                job["status_message"] = (
                    f"Downloading {label}: {mb_done:.0f} / {mb_total:.0f} MB"
                    f" ({speed_mbs:.1f} MB/s)"
                )

    return downloaded


# ---------------------------------------------------------------------------
# Public API: download + prepare VM for import
# ---------------------------------------------------------------------------

def download_vm_disks(
    job_id: str,
    hostname: str,
    username: str,
    password: str,
    port: int,
    verify_ssl: bool,
    moref: str,
    import_dir: str,
    job: Dict,
) -> None:
    """
    Connect to VMware, find VM by moref, download its VMDK(s) to import_dir.
    Populates job['specs'] and job['disk_files'].
    Caller should set job status to 'parsed' on success.
    Raises RuntimeError on failure.
    """
    auth = (username, password)

    si = _connect(hostname, username, password, port, verify_ssl)
    try:
        content = si.RetrieveContent()
        vm = content.searchIndex.FindByMOID(moref)
        if vm is None:
            raise RuntimeError(f"VM with MOREF {moref!r} not found on {hostname}")

        cfg = vm.config
        hw = cfg.hardware
        dc_path = _get_datacenter_path(content, vm)

        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", vm.name)[:63] or "imported-vm"

        disk_devices: List[vim.vm.device.VirtualDisk] = [
            d for d in hw.device if isinstance(d, vim.vm.device.VirtualDisk)
        ]
        if not disk_devices:
            raise RuntimeError("No virtual disks found on this VM")

        # Build specs
        specs = {
            "name": safe_name,
            "cpu_cores": hw.numCPU,
            "memory_mb": hw.memoryMB,
            "os_type": _os_from_guest_id(cfg.guestId or ""),
            "description": f"Imported from VMware ({hostname}): {vm.name}",
            "disks": [],
        }

        # Calculate total download size estimate (all flat VMDKs)
        total_bytes_estimate = sum(
            getattr(d, "capacityInKB", 0) * 1024 for d in disk_devices
        )

        bytes_downloaded = 0
        downloaded_disk_paths = []

        for disk_idx, disk in enumerate(disk_devices):
            backing_file = getattr(disk.backing, "fileName", "")
            if not backing_file:
                logger.warning(f"Disk {disk_idx} has no backing file, skipping")
                continue

            # Parse "[dsname] folder/vm.vmdk"
            m = re.match(r"\[([^\]]+)\]\s*(.*)", backing_file)
            if not m:
                logger.warning(f"Could not parse backing: {backing_file!r}")
                continue

            ds_name = m.group(1)
            vmdk_rel_path = m.group(2)
            vmdk_folder = _vmdk_folder(vmdk_rel_path)
            cap_kb = getattr(disk, "capacityInKB", 0)
            cap_gb = max(1, int(cap_kb / (1024 * 1024)))

            specs["disks"].append({
                "id": f"disk{disk_idx}",
                "capacity_gb": cap_gb,
                "file_ref": f"disk{disk_idx}",
                "filename": os.path.basename(vmdk_rel_path),
            })

            # ----------------------------------------------------------------
            # Step A: Download the VMDK descriptor
            # ----------------------------------------------------------------
            desc_url = _datastore_url(hostname, port, dc_path, ds_name, vmdk_rel_path)
            local_desc = os.path.join(import_dir, f"disk{disk_idx}.vmdk")

            job["status_message"] = f"Downloading VMDK descriptor for disk {disk_idx + 1}..."
            logger.info(f"Downloading descriptor: {desc_url} → {local_desc}")

            try:
                resp = requests.get(
                    desc_url, auth=auth, verify=verify_ssl, timeout=30
                )
                resp.raise_for_status()
            except requests.HTTPError as e:
                raise RuntimeError(
                    f"Failed to download VMDK descriptor from {hostname}: {e}"
                )

            descriptor_text = resp.text
            with open(local_desc, "w", encoding="utf-8") as f:
                f.write(descriptor_text)

            # ----------------------------------------------------------------
            # Step B: Find extent files from the descriptor
            # ----------------------------------------------------------------
            extent_filenames = _parse_vmdk_extents(descriptor_text)

            if not extent_filenames:
                # Fallback: try the conventional -flat.vmdk name
                base = os.path.splitext(os.path.basename(vmdk_rel_path))[0]
                extent_filenames = [f"{base}-flat.vmdk"]
                logger.info(f"No extents parsed; trying fallback: {extent_filenames}")

            # ----------------------------------------------------------------
            # Step C: Download each extent file
            # ----------------------------------------------------------------
            for ext_filename in extent_filenames:
                ext_rel_path = vmdk_folder + ext_filename
                ext_url = _datastore_url(hostname, port, dc_path, ds_name, ext_rel_path)
                local_ext = os.path.join(import_dir, ext_filename)

                logger.info(f"Downloading extent: {ext_url} → {local_ext}")
                label = f"disk {disk_idx + 1}/{len(disk_devices)} ({ext_filename})"

                try:
                    chunk_bytes = _download_file(
                        ext_url, local_ext, auth, verify_ssl,
                        job, bytes_downloaded, total_bytes_estimate, label,
                    )
                    bytes_downloaded += chunk_bytes
                except requests.HTTPError as e:
                    if e.response is not None and e.response.status_code == 404:
                        # Extent file not found — might be a thin/sparse disk with no flat file
                        # Try the descriptor file itself as a stream-optimized VMDK
                        logger.warning(
                            f"Extent {ext_filename!r} not found (404). "
                            "Trying descriptor as standalone VMDK."
                        )
                        # The descriptor-only VMDK might itself be a stream-optimized vmdk
                        # qemu-img can handle this
                        downloaded_disk_paths.append(local_desc)
                        break
                    else:
                        raise RuntimeError(f"Failed to download extent {ext_filename}: {e}")

                downloaded_disk_paths.append(local_ext)

            # If we successfully downloaded extents, the descriptor is enough for qemu-img
            # (qemu-img reads the descriptor and resolves relative extent paths)
            if downloaded_disk_paths and downloaded_disk_paths[-1] != local_desc:
                # Make sure desc is in the list for qemu-img
                pass

    finally:
        Disconnect(si)

    job["specs"] = specs
    job["disk_files"] = [os.path.basename(p) for p in downloaded_disk_paths]
    job["progress"] = 55
    job["status_message"] = "Download complete. Ready for conversion and deployment."
