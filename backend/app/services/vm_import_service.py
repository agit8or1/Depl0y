"""VM Import Service - handles OVA/OVF/VMDK/VHD/VHDX import from external platforms"""
import os
import re
import json
import time
import shutil
import tarfile
import zipfile
import logging
import subprocess
import asyncio
import uuid
import xml.etree.ElementTree as ET  # kept for type hints (Element) only
from defusedxml.ElementTree import parse as _safe_xml_parse
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

IMPORT_UPLOAD_DIR = "/tmp/depl0y-imports"
os.makedirs(IMPORT_UPLOAD_DIR, exist_ok=True)

# In-memory job store (ephemeral - jobs are cleared on restart)
_import_jobs: Dict[str, Dict[str, Any]] = {}


def create_import_job() -> str:
    job_id = str(uuid.uuid4())
    _import_jobs[job_id] = {
        "id": job_id,
        "status": "uploading",
        "progress": 0,
        "status_message": "Uploading file...",
        "specs": None,
        "error": None,
        "vm_id": None,
        "vmid": None,
        "import_dir": None,
        "disk_files": [],
        "filename": "",
        "file_size_mb": 0,
        "manual_import_cmd": None,
    }
    return job_id


def get_import_job(job_id: str) -> Optional[Dict]:
    return _import_jobs.get(job_id)


def list_import_jobs() -> List[Dict]:
    return list(_import_jobs.values())


def delete_import_job(job_id: str):
    job = _import_jobs.pop(job_id, None)
    if job and job.get("import_dir"):
        shutil.rmtree(job["import_dir"], ignore_errors=True)


# ---------------------------------------------------------------------------
# OVF / OVA parsing helpers
# ---------------------------------------------------------------------------

def _find_by_local(root: ET.Element, local_name: str) -> List[ET.Element]:
    """Find XML elements by local name, ignoring namespaces."""
    return [e for e in root.iter() if e.tag.split("}")[-1] == local_name]


def _attr(elem: ET.Element, local_name: str) -> Optional[str]:
    """Get attribute value by local name, ignoring namespaces."""
    for k, v in elem.attrib.items():
        if k.split("}")[-1] == local_name:
            return v
    return None


def parse_ovf(ovf_path: str) -> Dict[str, Any]:
    """Parse OVF descriptor XML and return a normalized VM spec dict."""
    specs: Dict[str, Any] = {
        "name": "imported-vm",
        "cpu_cores": 1,
        "memory_mb": 512,
        "disks": [],
        "os_type": "other",
        "description": "",
    }
    try:
        tree = _safe_xml_parse(ovf_path)
        root = tree.getroot()

        # VM name
        vs_list = _find_by_local(root, "VirtualSystem")
        if vs_list:
            vs = vs_list[0]
            name_els = _find_by_local(vs, "Name")
            if name_els and name_els[0].text:
                raw = name_els[0].text.strip()
                specs["name"] = re.sub(r"[^a-zA-Z0-9_-]", "-", raw)[:63] or "imported-vm"
            desc_els = _find_by_local(vs, "Description")
            if desc_els and desc_els[0].text:
                specs["description"] = desc_els[0].text.strip()[:500]

        # CPU and Memory from hardware items
        for item in _find_by_local(root, "Item"):
            rtype_el = next(
                (c for c in item if c.tag.split("}")[-1] == "ResourceType"), None
            )
            qty_el = next(
                (c for c in item if c.tag.split("}")[-1] == "VirtualQuantity"), None
            )
            unit_el = next(
                (c for c in item if c.tag.split("}")[-1] == "AllocationUnits"), None
            )
            if rtype_el is None:
                continue
            try:
                rtype = int(rtype_el.text or 0)
            except ValueError:
                continue

            if rtype == 3 and qty_el is not None:  # CPU
                try:
                    specs["cpu_cores"] = max(1, int(qty_el.text or 1))
                except ValueError:
                    pass
            elif rtype == 4 and qty_el is not None:  # Memory
                try:
                    val = int(qty_el.text or 512)
                    units = (unit_el.text or "MB").upper() if unit_el is not None else "MB"
                    if "GIGA" in units or "GIB" in units or " GB" in units:
                        specs["memory_mb"] = val * 1024
                    elif "MEGA" in units or "MIB" in units or " MB" in units:
                        specs["memory_mb"] = max(512, val)
                    elif val > 100_000:
                        # Probably bytes
                        specs["memory_mb"] = max(512, val // (1024 * 1024))
                    else:
                        specs["memory_mb"] = max(512, val)
                except ValueError:
                    pass

        # Build file-id → filename map
        file_map: Dict[str, str] = {}
        for ref in _find_by_local(root, "File"):
            fid = _attr(ref, "id")
            href = _attr(ref, "href")
            if fid and href:
                file_map[fid] = href

        # Disk entries
        for disk_el in _find_by_local(root, "Disk"):
            disk_id = _attr(disk_el, "diskId") or ""
            capacity = _attr(disk_el, "capacity") or "0"
            file_ref = _attr(disk_el, "fileRef") or ""
            cap_units = (_attr(disk_el, "capacityAllocationUnits") or "").upper()

            cap_gb = 20
            try:
                cap_val = int(capacity)
                if "GIGA" in cap_units or "GIB" in cap_units:
                    cap_gb = max(1, cap_val)
                elif "MEGA" in cap_units or "MIB" in cap_units:
                    cap_gb = max(1, cap_val // 1024)
                elif cap_val > 2 * 1024 ** 3:
                    cap_gb = max(1, cap_val // (1024 ** 3))
                elif cap_val > 1000:
                    # Could be MB
                    cap_gb = max(1, cap_val // 1024)
                else:
                    cap_gb = max(1, cap_val)
            except ValueError:
                pass

            specs["disks"].append(
                {
                    "id": disk_id,
                    "capacity_gb": cap_gb,
                    "file_ref": file_ref,
                    "filename": file_map.get(file_ref, ""),
                }
            )

        # OS type detection
        combined = (specs["name"] + " " + specs["description"]).lower()
        if "windows" in combined or "win" in combined:
            specs["os_type"] = "windows"
        elif "ubuntu" in combined:
            specs["os_type"] = "ubuntu"
        elif "debian" in combined:
            specs["os_type"] = "debian"
        elif "centos" in combined:
            specs["os_type"] = "centos"
        elif "rocky" in combined:
            specs["os_type"] = "rocky"
        elif "alma" in combined:
            specs["os_type"] = "alma"
        elif "pfsense" in combined:
            specs["os_type"] = "pfsense"
        elif "opnsense" in combined:
            specs["os_type"] = "opnsense"
        elif "freebsd" in combined:
            specs["os_type"] = "freebsd"

    except Exception as e:
        logger.warning(f"OVF parsing error (using defaults): {e}")

    return specs


def _is_within(base: str, target: str) -> bool:
    """True iff `target` resolves inside `base` (defeats ../ + absolute paths + symlinks)."""
    base = os.path.realpath(base) + os.sep
    resolved = os.path.realpath(target)
    return (resolved + os.sep).startswith(base) or resolved == base.rstrip(os.sep)


def _safe_tar_members(tar: tarfile.TarFile, dest: str):
    """Yield only tar members that resolve inside `dest` and are regular files / dirs.
    Rejects: absolute paths, traversal, symlinks, device files, hardlinks — i.e. classic
    TarSlip vectors that `tarfile.extractall()` would otherwise honour."""
    for m in tar.getmembers():
        if m.name.startswith("/") or ".." in m.name.split("/"):
            logger.warning(f"OVA: rejecting tar member with unsafe name: {m.name!r}")
            continue
        if m.issym() or m.islnk() or m.isdev():
            logger.warning(f"OVA: rejecting non-regular tar member: {m.name!r}")
            continue
        target = os.path.join(dest, m.name)
        if not _is_within(dest, target):
            logger.warning(f"OVA: rejecting tar member escaping dest: {m.name!r}")
            continue
        yield m


def _safe_zip_members(zf: zipfile.ZipFile, dest: str):
    for info in zf.infolist():
        name = info.filename
        if name.startswith("/") or ".." in name.split("/"):
            logger.warning(f"OVA: rejecting zip entry with unsafe name: {name!r}")
            continue
        target = os.path.join(dest, name)
        if not _is_within(dest, target):
            logger.warning(f"OVA: rejecting zip entry escaping dest: {name!r}")
            continue
        yield info


def extract_ova(ova_path: str, extract_dir: str) -> Optional[str]:
    """Extract OVA archive to extract_dir. Returns path to OVF file if found."""
    ovf_path = None
    os.makedirs(extract_dir, exist_ok=True)
    try:
        with tarfile.open(ova_path, "r") as tar:
            safe = list(_safe_tar_members(tar, extract_dir))
            tar.extractall(extract_dir, members=safe)
    except Exception as e:
        logger.warning(f"tarfile extraction failed: {e}. Trying zip...")
        try:
            with zipfile.ZipFile(ova_path, "r") as zf:
                for info in _safe_zip_members(zf, extract_dir):
                    zf.extract(info, extract_dir)
        except Exception as e2:
            logger.warning(f"zipfile extraction also failed: {e2}")
            return None

    for fname in sorted(os.listdir(extract_dir)):
        if fname.lower().endswith(".ovf"):
            ovf_path = os.path.join(extract_dir, fname)
            break

    return ovf_path


# ---------------------------------------------------------------------------
# Disk helpers
# ---------------------------------------------------------------------------

_DISK_EXTENSIONS = (".vmdk", ".vhd", ".vhdx", ".qcow2", ".img", ".raw")


def find_disk_files(directory: str) -> List[str]:
    """Return list of disk image paths inside directory, largest first."""
    disks = []
    for fname in os.listdir(directory):
        fpath = os.path.join(directory, fname)
        if not fname.lower().endswith(_DISK_EXTENSIONS):
            continue
        if not os.path.isfile(fpath):
            continue
        # Skip tiny VMDK descriptor-only files (< 10 KB)
        if fname.lower().endswith(".vmdk") and os.path.getsize(fpath) < 10_240:
            try:
                with open(fpath, "rb") as f:
                    sig = f.read(4)
                # Valid VMDK binary signatures
                if sig not in (b"KDMV", b"COWD", b"\x00\x00\x00\x00"):
                    continue
            except Exception:
                continue
        disks.append(fpath)
    # Sort by size descending so the primary (largest) disk comes first
    disks.sort(key=lambda p: os.path.getsize(p), reverse=True)
    return disks


def _qemu_format(disk_path: str) -> str:
    ext = disk_path.lower()
    if ext.endswith(".vmdk"):
        return "vmdk"
    if ext.endswith(".vhd"):
        return "vpc"
    if ext.endswith(".vhdx"):
        return "vhdx"
    if ext.endswith(".qcow2"):
        return "qcow2"
    # raw / img or unknown → probe with qemu-img
    try:
        result = subprocess.run(
            ["qemu-img", "info", "--output=json", disk_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout).get("format", "raw")
    except Exception:
        pass
    return "raw"


async def convert_disk(src_path: str, dst_path: str, job: Dict) -> None:
    """Convert disk image to qcow2 using qemu-img (async)."""
    src_fmt = _qemu_format(src_path)
    if src_fmt == "qcow2" and src_path == dst_path:
        job["status_message"] = "Disk already in qcow2 format, skipping conversion..."
        return

    job["status_message"] = (
        f"Converting {os.path.basename(src_path)} ({src_fmt} → qcow2)..."
    )
    logger.info(f"qemu-img convert: {src_path} ({src_fmt}) → {dst_path}")

    proc = await asyncio.create_subprocess_exec(
        "qemu-img", "convert",
        "-f", src_fmt, "-O", "qcow2",
        src_path, dst_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        err = stderr.decode().strip() or "unknown error"
        raise RuntimeError(f"qemu-img conversion failed: {err}")
    logger.info("Disk conversion complete.")


def _disk_virtual_size_gb(disk_path: str) -> int:
    """Get virtual disk size in GB using qemu-img info."""
    try:
        result = subprocess.run(
            ["qemu-img", "info", "--output=json", disk_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return max(1, int(info.get("virtual-size", 0) // (1024 ** 3)))
    except Exception:
        pass
    return 20


# ---------------------------------------------------------------------------
# SSH helpers
# ---------------------------------------------------------------------------

def _ssh_run(host_addr: str, command: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a command on a remote host via SSH (key-based auth, no password)."""
    return subprocess.run(
        [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            "-o", f"ConnectTimeout=30",
            f"root@{host_addr}",
            command,
        ],
        capture_output=True, text=True, timeout=timeout,
    )


def _get_node_ip(host_addr: str, node_name: str) -> Optional[str]:
    """Try to discover a cluster node's IP address via corosync config."""
    safe_node = re.sub(r"[^a-zA-Z0-9._-]", "", node_name)
    cmd = (
        f"grep -A3 'name: {safe_node}' /etc/pve/corosync.conf "
        f"| grep ring0_addr | awk '{{print $2}}'"
    )
    result = _ssh_run(host_addr, cmd, timeout=15)
    ip = result.stdout.strip()
    if ip and re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
        return ip
    return None


# ---------------------------------------------------------------------------
# Main import background task
# ---------------------------------------------------------------------------

async def run_import_job(job_id: str, deploy_req: Dict, _db_factory) -> None:
    """Background task: convert disk → upload to Proxmox → create VM."""
    from app.core.database import SessionLocal
    from app.models import ProxmoxHost, ProxmoxNode, VirtualMachine, VMStatus, OSType
    from app.services.proxmox import ProxmoxService
    from app.core.security import encrypt_data, decrypt_data
    import requests

    job = _import_jobs.get(job_id)
    if not job:
        logger.error(f"Import job {job_id} not found")
        return

    import_dir = job.get("import_dir", "")

    try:
        # ------------------------------------------------------------------ #
        # Step 1: Find & validate disk files                                  #
        # ------------------------------------------------------------------ #
        job["status"] = "converting"
        job["progress"] = 5
        job["status_message"] = "Locating disk image files..."

        disk_files = find_disk_files(import_dir)
        if not disk_files:
            raise RuntimeError("No disk image files found in the uploaded archive.")

        primary_disk = disk_files[0]
        logger.info(f"Primary disk: {primary_disk}")

        # ------------------------------------------------------------------ #
        # Step 2: Convert disk to qcow2                                       #
        # ------------------------------------------------------------------ #
        if primary_disk.lower().endswith(".qcow2"):
            converted_disk = primary_disk
        else:
            converted_disk = os.path.join(import_dir, "import-disk.qcow2")
            job["progress"] = 10
            await convert_disk(primary_disk, converted_disk, job)

        job["progress"] = 40
        disk_size_gb = _disk_virtual_size_gb(converted_disk)

        # ------------------------------------------------------------------ #
        # Step 3: Create VM shell in Proxmox                                  #
        # ------------------------------------------------------------------ #
        job["status"] = "deploying"
        job["status_message"] = "Connecting to Proxmox..."

        db = SessionLocal()
        try:
            host = db.query(ProxmoxHost).filter(
                ProxmoxHost.id == deploy_req["proxmox_host_id"]
            ).first()
            if not host:
                raise RuntimeError("Proxmox host not found")

            node = db.query(ProxmoxNode).filter(
                ProxmoxNode.id == deploy_req["node_id"]
            ).first()
            if not node:
                raise RuntimeError("Proxmox node not found")

            proxmox_svc = ProxmoxService(host)

            # Resolve deploy parameters (request overrides parsed OVF specs)
            specs = job.get("specs") or {}
            vm_name = (deploy_req.get("vm_name") or specs.get("name") or "imported-vm").strip()
            vm_name = re.sub(r"[^a-zA-Z0-9_-]", "-", vm_name)[:63] or "imported-vm"
            cpu_cores = max(1, int(deploy_req.get("cpu_cores") or specs.get("cpu_cores") or 1))
            memory_mb = max(256, int(deploy_req.get("memory_mb") or specs.get("memory_mb") or 512))
            storage = deploy_req["storage"]
            network_bridge = deploy_req.get("network_bridge") or "vmbr0"

            # Use OVF disk size if larger
            ovf_disk_gb = specs.get("disks", [{}])[0].get("capacity_gb", 20) if specs.get("disks") else 20
            disk_size_gb = max(disk_size_gb, ovf_disk_gb)

            # Map os_type string → Proxmox ostype
            os_type_str = (deploy_req.get("os_type") or specs.get("os_type") or "other").lower()
            proxmox_ostype = "win10" if "windows" in os_type_str else "l26"

            # Map to DB OSType enum
            os_enum_map = {
                "ubuntu": OSType.UBUNTU,
                "debian": OSType.DEBIAN,
                "centos": OSType.CENTOS,
                "rocky": OSType.ROCKY,
                "alma": OSType.ALMA,
                "windows": OSType.WINDOWS_SERVER_2022,
                "pfsense": OSType.PFSENSE,
                "opnsense": OSType.OPNSENSE,
                "freebsd": OSType.FREEBSD,
            }
            db_os_type = OSType.OTHER
            for key, val in os_enum_map.items():
                if key in os_type_str:
                    db_os_type = val
                    break

            vmid = proxmox_svc.get_next_vmid()
            job["status_message"] = f"Creating VM {vm_name} (VMID {vmid})..."
            job["progress"] = 45

            proxmox_svc.proxmox.nodes(node.node_name).qemu.post(
                vmid=vmid,
                name=vm_name,
                sockets=1,
                cores=cpu_cores,
                memory=memory_mb,
                net0=f"virtio,bridge={network_bridge}",
                scsihw="virtio-scsi-pci",
                agent="1",
                onboot=1,
                ostype=proxmox_ostype,
            )
            time.sleep(2)

            # ---------------------------------------------------------------- #
            # Step 4: Upload converted disk to Proxmox local:iso storage       #
            # ---------------------------------------------------------------- #
            job["progress"] = 50
            disk_filename = f"import-{vmid}-{job_id[:8]}.qcow2"
            job["status_message"] = f"Uploading disk ({os.path.getsize(converted_disk) / (1024**2):.0f} MB) to Proxmox..."

            upload_url = (
                f"https://{host.hostname}:{host.port}/api2/json"
                f"/nodes/{node.node_name}/storage/local/upload"
            )

            # Build auth
            headers: Dict[str, str] = {}
            req_auth = None
            if host.api_token_id and host.api_token_secret:
                try:
                    tok_secret = decrypt_data(host.api_token_secret)
                except Exception:
                    tok_secret = host.api_token_secret
                full_tok = (
                    host.api_token_id
                    if "!" in host.api_token_id
                    else f"{host.username}!{host.api_token_id}"
                )
                headers["Authorization"] = f"PVEAPIToken={full_tok}={tok_secret}"
            else:
                try:
                    pw = decrypt_data(host.password)
                except Exception:
                    pw = host.password
                req_auth = (host.username, pw)

            with open(converted_disk, "rb") as disk_file:
                resp = requests.post(
                    upload_url,
                    auth=req_auth,
                    headers=headers,
                    files={"filename": (disk_filename, disk_file, "application/octet-stream")},
                    data={"content": "iso"},
                    verify=host.verify_ssl,
                    timeout=7200,
                )
            if resp.status_code != 200:
                raise RuntimeError(f"Disk upload failed ({resp.status_code}): {resp.text}")

            job["progress"] = 75
            job["status_message"] = "Importing disk into VM..."

            # ---------------------------------------------------------------- #
            # Step 5: qm importdisk via SSH                                    #
            # ---------------------------------------------------------------- #
            import_path = f"/var/lib/vz/template/iso/{disk_filename}"
            importdisk_cmd = f"qm importdisk {vmid} {import_path} {storage}"

            disk_imported = False
            ssh_result = _ssh_run(host.hostname, importdisk_cmd, timeout=600)

            if ssh_result.returncode == 0:
                disk_imported = True
                logger.info(f"importdisk succeeded: {ssh_result.stdout}")
            else:
                logger.warning(
                    f"SSH to {host.hostname} failed (rc={ssh_result.returncode}): "
                    f"{ssh_result.stderr}. Trying cluster node..."
                )
                node_ip = _get_node_ip(host.hostname, node.node_name)
                if node_ip:
                    hop_cmd = f'ssh -o StrictHostKeyChecking=no root@{node_ip} "{importdisk_cmd}"'
                    ssh_result2 = _ssh_run(host.hostname, hop_cmd, timeout=600)
                    if ssh_result2.returncode == 0:
                        disk_imported = True
                        logger.info(f"importdisk via hop succeeded: {ssh_result2.stdout}")
                    else:
                        logger.warning(f"Hop SSH also failed: {ssh_result2.stderr}")

            if not disk_imported:
                job["manual_import_cmd"] = importdisk_cmd
                logger.warning(
                    "Could not run importdisk via SSH. "
                    f"Manual command: {importdisk_cmd}"
                )

            # ---------------------------------------------------------------- #
            # Step 6: Attach imported disk to VM                               #
            # ---------------------------------------------------------------- #
            if disk_imported:
                job["progress"] = 85
                job["status_message"] = "Configuring VM disk..."
                try:
                    vm_cfg = proxmox_svc.proxmox.nodes(node.node_name).qemu(vmid).config.get()
                    unused = {k: v for k, v in vm_cfg.items() if k.startswith("unused")}
                    if unused:
                        key = sorted(unused.keys())[0]
                        proxmox_svc.proxmox.nodes(node.node_name).qemu(vmid).config.put(
                            scsi0=unused[key],
                            boot="order=scsi0",
                        )
                        logger.info(f"Attached disk {unused[key]} as scsi0 on VM {vmid}")
                except Exception as e:
                    logger.warning(f"Could not attach disk to VM {vmid}: {e}")

                # Cleanup ISO storage copy
                try:
                    _ssh_run(host.hostname, f"rm -f {import_path}", timeout=30)
                except Exception:
                    pass

            # ---------------------------------------------------------------- #
            # Step 7: Save VM to database                                      #
            # ---------------------------------------------------------------- #
            job["progress"] = 90
            job["status_message"] = "Saving VM record..."

            vm_record = VirtualMachine(
                vmid=vmid,
                name=vm_name,
                hostname=vm_name,
                proxmox_host_id=host.id,
                node_id=node.id,
                os_type=db_os_type,
                cpu_sockets=1,
                cpu_cores=cpu_cores,
                memory=memory_mb,
                disk_size=disk_size_gb,
                storage=storage,
                network_bridge=network_bridge,
                username=deploy_req.get("username") or "administrator",
                password=(
                    encrypt_data(deploy_req["password"])
                    if deploy_req.get("password")
                    else None
                ),
                status=VMStatus.STOPPED,
                status_message=(
                    "Imported from external platform"
                    if disk_imported
                    else "Imported (manual disk import required — see manual_import_cmd)"
                ),
            )
            db.add(vm_record)
            db.commit()
            db.refresh(vm_record)

            job["vm_id"] = vm_record.id
            job["vmid"] = vmid
            job["status"] = "completed"
            job["progress"] = 100
            job["status_message"] = (
                "Import completed successfully!"
                if disk_imported
                else f"VM created. Run on Proxmox node: {importdisk_cmd}"
            )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Import job {job_id} failed: {e}", exc_info=True)
        job["status"] = "error"
        job["error"] = str(e)
        job["status_message"] = f"Import failed: {str(e)}"
    finally:
        # Always clean up temp files
        try:
            if import_dir and os.path.exists(import_dir):
                shutil.rmtree(import_dir, ignore_errors=True)
        except Exception:
            pass
