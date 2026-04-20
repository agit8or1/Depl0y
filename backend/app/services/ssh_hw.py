"""SSH-based hardware info — faster alternative to Redfish for host-side data."""
import logging
import json
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)


def _run(client, cmd: str) -> str:
    try:
        _, stdout, _ = client.exec_command(cmd, timeout=15)
        return stdout.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def get_ssh_client(hostname: str, username: str, password: str, port: int = 22):
    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname, port=port, username=username, password=password,
                   timeout=10, allow_agent=False, look_for_keys=False)
    return client


def _parse_lscpu(raw: str) -> dict:
    info = {}
    for line in raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            info[k.strip()] = v.strip()
    return info


def _parse_dmidecode_memory(raw: str) -> list:
    """Parse dmidecode -t memory output into a list of populated DIMM dicts."""
    modules = []
    current = {}
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("Memory Device"):
            if current.get("Size") and current["Size"] != "No Module Installed":
                modules.append(current)
            current = {}
        elif ":" in line:
            k, _, v = line.partition(":")
            current[k.strip()] = v.strip()
    if current.get("Size") and current["Size"] != "No Module Installed":
        modules.append(current)
    result = []
    for i, m in enumerate(modules):
        size_str = m.get("Size", "")
        cap_mib = None
        match = re.match(r"(\d+)\s*(MB|GB|MiB|GiB)", size_str, re.I)
        if match:
            n, unit = int(match.group(1)), match.group(2).upper()
            cap_mib = n if "MB" in unit or "MIB" in unit else n * 1024
        result.append({
            "id": m.get("Locator", f"DIMM{i}"),
            "name": m.get("Bank Locator", m.get("Locator", "")),
            "manufacturer": m.get("Manufacturer", ""),
            "capacity_mib": cap_mib,
            "speed_mhz": int(re.sub(r"\D", "", m.get("Speed", "0") or "0") or 0) or None,
            "type": m.get("Type", ""),
            "part_number": m.get("Part Number", "").strip(),
            "health": "OK",
        })
    return result


def _parse_lsblk(raw: str) -> list:
    try:
        data = json.loads(raw)
    except Exception:
        return []
    drives = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") not in ("disk",):
            continue
        # lsblk -b returns size as integer bytes in JSON
        size_raw = dev.get("size") or 0
        try:
            cap_gb = round(int(size_raw) / 1e9, 1) if size_raw else None
        except (ValueError, TypeError):
            cap_gb = None
        drives.append({
            "id": dev.get("name", ""),
            "name": dev.get("name", ""),
            "model": (dev.get("model") or "").strip(),
            "manufacturer": (dev.get("vendor") or "").strip(),
            "serial": (dev.get("serial") or "").strip(),
            "capacity_gb": cap_gb,
            "media_type": "SSD" if str(dev.get("rota", "1")) in ("0", "false", "False") else "HDD",
            "protocol": (dev.get("tran") or "").upper() or "Unknown",
            "rpm": None,
            "health": "Unknown",
            "state": "Enabled",
        })
    return drives


def _parse_sensors_temp(raw: str):
    """Return max temperature (°C) from sensors -j output, or None."""
    try:
        data = json.loads(raw)
        temps = []
        for adapter_data in data.values():
            if not isinstance(adapter_data, dict):
                continue
            for sensor_data in adapter_data.values():
                if not isinstance(sensor_data, dict):
                    continue
                for key, val in sensor_data.items():
                    if "input" in key and isinstance(val, (int, float)) and 0 < val < 200:
                        temps.append(val)
        return round(max(temps), 1) if temps else None
    except Exception:
        return None


def _parse_hwmon_temp(raw: str):
    """Parse /sys/class/hwmon temp*_input files (millidegrees), return max °C or None."""
    temps = []
    for line in raw.splitlines():
        if ":" in line:
            _, _, val = line.partition(":")
            try:
                t = int(val.strip()) / 1000.0
                # Valid CPU/system temperatures are 1–120 °C; filter bogus sensor values
                if 1.0 <= t <= 120.0:
                    temps.append(t)
            except Exception:
                pass
    return round(max(temps), 1) if temps else None


def _parse_mdstat(raw: str) -> list:
    """Parse /proc/mdstat into a list of RAID array status dicts."""
    arrays = []
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r'^(md\w+)\s*:\s*(\w+)\s+(\w+)\s+(.*)', line)
        if not m:
            continue
        name, state, level, devices = m.groups()
        status_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        health = "OK"
        if state == "inactive":
            health = "Failed"
        elif re.search(r'\[.*_.*\]', status_line):
            health = "Degraded"
        level_label = level.upper()
        if level_label.startswith("RAID"):
            level_label = "RAID " + level_label[4:]
        arrays.append({
            "name": name,
            "level": level_label,
            "state": state,
            "health": health,
            "detail": status_line,
        })
    return arrays


def get_hardware_info(hostname: str, username: str, password: str, port: int = 22) -> Dict[str, Any]:
    client = get_ssh_client(hostname, username, password, port)
    try:
        # Fire the core commands in parallel (8 channels — safely within OpenSSH MaxSessions=10)
        core_cmds = {
            "lscpu":  "lscpu 2>/dev/null",
            "memory": "dmidecode -t memory 2>/dev/null",
            "disks":  "lsblk -J -b -o NAME,SIZE,TYPE,MODEL,SERIAL,VENDOR,ROTA,TRAN 2>/dev/null",
            "bios":   "dmidecode -t bios 2>/dev/null | grep -E 'Version:|Release Date:'",
            "system": "dmidecode -t system 2>/dev/null | grep -E 'Manufacturer:|Product Name:|Serial Number:'",
            "uptime": "uptime -p 2>/dev/null || uptime",
            "kernel": "uname -r",
            "os":     "cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'",
        }
        channels = {}
        for k, cmd in core_cmds.items():
            _, stdout, _ = client.exec_command(cmd, timeout=15)
            channels[k] = stdout
        results = {k: ch.read().decode("utf-8", errors="replace").strip() for k, ch in channels.items()}

        # Run telemetry commands sequentially after core batch to avoid exceeding MaxSessions
        results["temps"]      = _run(client, "sensors -j 2>/dev/null || true")
        results["hwmon"]      = _run(client, "for f in /sys/class/hwmon/hwmon*/temp*_input; do [ -f \"$f\" ] && echo \"$f:$(cat $f)\"; done 2>/dev/null || true")
        results["ipmi_power"] = _run(client, "ipmitool dcmi power reading 2>/dev/null | grep -i 'Instantaneous power reading' | grep -oE '[0-9]+' | head -1 || true")
        results["mdstat"]     = _run(client, "cat /proc/mdstat 2>/dev/null || true")
        # RAPL power: CPU packages + DRAM sub-domains (DRAM is NOT included in package totals)
        # Two samples 1s apart → CPU+DRAM power across all sockets
        results["rapl_power"] = _run(client,
            # Sample 0: sum all package domains + dram sub-domains
            "sample() {"
            " local s=0;"
            " for p in $(ls /sys/class/powercap/ 2>/dev/null | grep -E '^intel-rapl:[0-9]+$');"
            "  do v=$(cat /sys/class/powercap/$p/energy_uj 2>/dev/null); s=$(( s + ${v:-0} )); done;"
            " for d in /sys/class/powercap/intel-rapl:*:*/;"
            "  do n=$(cat ${d}name 2>/dev/null); [ \"$n\" = \"dram\" ] &&"
            "  v=$(cat ${d}energy_uj 2>/dev/null) && s=$(( s + ${v:-0} )); done;"
            " echo $s; };"
            " e0=$(sample); sleep 1; e1=$(sample);"
            " [ $e0 -gt 0 ] && echo $(( (e1 - e0) / 1000000 )) || true"
        )

        # Parse CPU
        cpu_raw = _parse_lscpu(results["lscpu"])
        sockets = int(cpu_raw.get("Socket(s)", "1") or 1)
        cores_per = int(cpu_raw.get("Core(s) per socket", "1") or 1)
        threads_per = int(cpu_raw.get("Thread(s) per core", "1") or 1)
        max_mhz = cpu_raw.get("CPU max MHz") or cpu_raw.get("CPU MHz", "")
        try:
            max_mhz_int = int(float(max_mhz)) if max_mhz else None
        except Exception:
            max_mhz_int = None

        processors = []
        for i in range(sockets):
            processors.append({
                "id": f"CPU{i}",
                "socket": f"CPU {i+1}",
                "model": cpu_raw.get("Model name", ""),
                "manufacturer": cpu_raw.get("Vendor ID", ""),
                "cores": cores_per,
                "threads": cores_per * threads_per,
                "speed_mhz": max_mhz_int,
                "architecture": cpu_raw.get("Architecture", ""),
                "health": "OK",
            })

        # Parse memory
        modules = _parse_dmidecode_memory(results["memory"])

        # Parse disks
        drives = _parse_lsblk(results["disks"])

        # Parse system info
        sys_info = {}
        for line in results["system"].splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                sys_info[k.strip()] = v.strip()

        bios_info = {}
        for line in results["bios"].splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                bios_info[k.strip()] = v.strip()

        os_name = results["os"].strip().strip('"')

        # Temperature: try sensors -j first, fall back to hwmon sysfs
        max_temp_c = _parse_sensors_temp(results.get("temps", ""))
        if max_temp_c is None:
            max_temp_c = _parse_hwmon_temp(results.get("hwmon", ""))

        # Power consumption — ipmitool first, RAPL as fallback
        consumed_watts = None
        ipmi_raw = results.get("ipmi_power", "").strip()
        if ipmi_raw:
            try:
                consumed_watts = int(ipmi_raw)
            except Exception:
                pass
        if consumed_watts is None:
            rapl_raw = results.get("rapl_power", "").strip()
            if rapl_raw:
                try:
                    w = int(rapl_raw)
                    if 1 <= w <= 3000:  # sanity check
                        consumed_watts = w
                except Exception:
                    pass

        # Software RAID status
        raid_arrays = _parse_mdstat(results.get("mdstat", ""))

        return {
            "processors": processors,
            "modules": modules,
            "controllers": [{
                "id": "local",
                "name": "Local Storage",
                "model": "",
                "health": "OK",
                "drives": drives,
            }] if drives else [],
            "system": {
                "manufacturer": sys_info.get("Manufacturer", ""),
                "model": sys_info.get("Product Name", ""),
                "serial": sys_info.get("Serial Number", ""),
                "bios_version": bios_info.get("Version", ""),
                "bios_date": bios_info.get("Release Date", ""),
                "kernel": results["kernel"],
                "os": os_name,
                "uptime": results["uptime"],
            },
            "max_temp_c": max_temp_c,
            "consumed_watts": consumed_watts,
            "raid_arrays": raid_arrays,
        }
    finally:
        client.close()


def get_network_info(hostname: str, username: str, password: str, port: int = 22) -> Dict[str, Any]:
    client = get_ssh_client(hostname, username, password, port)
    try:
        _, stdout, _ = client.exec_command("ip -j addr 2>/dev/null", timeout=10)
        raw = stdout.read().decode("utf-8", errors="replace").strip()
        try:
            ifaces_raw = json.loads(raw)
        except Exception:
            return {"interfaces": []}

        interfaces = []
        for iface in ifaces_raw:
            if iface.get("link_type") == "loopback":
                continue
            ipv4 = [a for a in iface.get("addr_info", []) if a.get("family") == "inet"]
            ipv6 = [a for a in iface.get("addr_info", []) if a.get("family") == "inet6"]
            interfaces.append({
                "id": iface.get("ifname", ""),
                "name": iface.get("ifname", ""),
                "mac_address": iface.get("address", ""),
                "ipv4": [{"Address": a["local"], "SubnetMask": _prefix_to_mask(a["prefixlen"]), "Gateway": ""} for a in ipv4],
                "ipv6": [{"Address": a["local"]} for a in ipv6],
                "speed_mbps": None,
                "dhcp_enabled": False,
                "link_status": "LinkUp" if "UP" in iface.get("flags", []) else "LinkDown",
                "fqdn": hostname,
                "hostname": hostname,
                "name_servers": [],
            })
        return {"interfaces": interfaces, "source": "ssh"}
    finally:
        client.close()


def get_firmware_info(hostname: str, username: str, password: str, port: int = 22) -> Dict[str, Any]:
    """Return firmware inventory gathered via SSH (BIOS, kernel, fwupd, packages)."""
    client = get_ssh_client(hostname, username, password, port)
    try:
        cmds = {
            "bios":    "dmidecode -t bios 2>/dev/null",
            "board":   "dmidecode -t baseboard 2>/dev/null | grep -E 'Manufacturer:|Product Name:|Version:'",
            "kernel":  "uname -r",
            "fwupd":   "fwupdmgr get-devices --json 2>/dev/null || true",
            "pkgs":    "dpkg -l 2>/dev/null | awk '/^ii/{print $2,$3}' | grep -iE 'firmware|microcode|bios|ucode|iwlwifi|ath[0-9]|radeon|nvidia' || rpm -qa --queryformat '%{NAME} %{VERSION}-%{RELEASE}\n' 2>/dev/null | grep -iE 'firmware|microcode|ucode' || true",
        }
        channels = {}
        for k, cmd in cmds.items():
            _, stdout, _ = client.exec_command(cmd, timeout=15)
            channels[k] = stdout
        results = {k: ch.read().decode("utf-8", errors="replace").strip() for k, ch in channels.items()}

        firmware = []

        # BIOS
        bios = {}
        for line in results["bios"].splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                bios[k.strip()] = v.strip()
        if bios.get("Version"):
            firmware.append({
                "id": "bios",
                "name": "BIOS / UEFI",
                "version": bios.get("Version", ""),
                "updateable": False,
                "health": "",
                "release_date": bios.get("Release Date", ""),
            })

        # Baseboard
        board = {}
        for line in results["board"].splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                board[k.strip()] = v.strip()
        if board.get("Version") and board["Version"] not in ("", "None", "N/A"):
            firmware.append({
                "id": "baseboard",
                "name": f"{board.get('Manufacturer', '')} {board.get('Product Name', 'Baseboard')}".strip(),
                "version": board["Version"],
                "updateable": False,
                "health": "",
                "release_date": "",
            })

        # Kernel
        if results["kernel"]:
            firmware.append({
                "id": "kernel",
                "name": "Linux Kernel",
                "version": results["kernel"],
                "updateable": False,
                "health": "",
                "release_date": "",
            })

        # fwupd devices
        fwupd_raw = results["fwupd"].strip()
        if fwupd_raw and fwupd_raw.startswith("{"):
            try:
                fwdata = json.loads(fwupd_raw)
                for dev in fwdata.get("Devices", []):
                    flags = dev.get("Flags", [])
                    updatable = isinstance(flags, list) and any("updatable" in str(f).lower() for f in flags)
                    firmware.append({
                        "id": dev.get("DeviceId", ""),
                        "name": dev.get("Name", ""),
                        "version": dev.get("Version", ""),
                        "updateable": updatable,
                        "health": "",
                        "release_date": "",
                    })
            except Exception:
                pass

        # Firmware packages
        seen = {f["id"] for f in firmware}
        for line in results["pkgs"].splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0] not in seen:
                firmware.append({
                    "id": parts[0],
                    "name": parts[0],
                    "version": parts[1],
                    "updateable": False,
                    "health": "",
                    "release_date": "",
                })

        return {"firmware": firmware, "source": "ssh"}
    finally:
        client.close()


def get_log_entries(hostname: str, username: str, password: str, port: int = 22, limit: int = 100) -> Dict[str, Any]:
    """Return recent system log entries via journalctl (or syslog fallback)."""
    client = get_ssh_client(hostname, username, password, port)
    _PRIO_MAP = {
        "0": "Critical", "1": "Critical", "2": "Critical",
        "3": "Error", "4": "Warning", "5": "OK", "6": "OK", "7": "OK",
    }
    try:
        cmd = (
            f"journalctl -n {limit} --no-pager -o json 2>/dev/null "
            f"|| tail -n {limit} /var/log/syslog 2>/dev/null "
            f"|| tail -n {limit} /var/log/messages 2>/dev/null"
        )
        _, stdout, _ = client.exec_command(cmd, timeout=20)
        raw = stdout.read().decode("utf-8", errors="replace").strip()

        entries = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("{"):
                try:
                    rec = json.loads(line)
                    ts_us = rec.get("__REALTIME_TIMESTAMP")
                    if ts_us:
                        from datetime import datetime, timezone
                        ts = datetime.fromtimestamp(int(ts_us) / 1e6, tz=timezone.utc).isoformat()
                    else:
                        ts = ""
                    prio = str(rec.get("PRIORITY", "6"))
                    svc = rec.get("SYSLOG_IDENTIFIER") or rec.get("_COMM", "kernel")
                    msg = rec.get("MESSAGE", "")
                    if isinstance(msg, list):
                        msg = " ".join(str(c) for c in msg)
                    entries.append({
                        "id": ts,
                        "created": ts,
                        "message": f"[{svc}] {msg}",
                        "severity": _PRIO_MAP.get(prio, "OK"),
                        "sensor_type": "",
                    })
                except Exception:
                    continue
            else:
                # Plain syslog line
                entries.append({
                    "id": line[:20],
                    "created": "",
                    "message": line,
                    "severity": "OK",
                    "sensor_type": "",
                })

        return {"entries": list(reversed(entries)), "source": "ssh"}
    finally:
        client.close()


def run_system_update(hostname: str, username: str, password: str, port: int = 22) -> dict:
    """Run a non-interactive system package update and return the output."""
    client = get_ssh_client(hostname, username, password, port)
    try:
        cmd = (
            "if command -v apt-get >/dev/null 2>&1; then "
            "  DEBIAN_FRONTEND=noninteractive apt-get update -q 2>&1 && "
            "  DEBIAN_FRONTEND=noninteractive apt-get upgrade -y 2>&1; "
            "elif command -v dnf >/dev/null 2>&1; then "
            "  dnf update -y 2>&1; "
            "elif command -v yum >/dev/null 2>&1; then "
            "  yum update -y 2>&1; "
            "elif command -v zypper >/dev/null 2>&1; then "
            "  zypper update -y 2>&1; "
            "else "
            "  echo 'No supported package manager found'; exit 1; "
            "fi"
        )
        _, stdout, stderr = client.exec_command(cmd, timeout=300)
        output = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace").strip()
        exit_code = stdout.channel.recv_exit_status()
        if err:
            output = output + f"\n--- stderr ---\n{err}"
        return {
            "output": output.strip(),
            "success": exit_code == 0,
            "exit_code": exit_code,
        }
    finally:
        client.close()


def test_ssh(hostname: str, username: str, password: str, port: int = 22) -> bool:
    """Return True if SSH connects successfully."""
    client = get_ssh_client(hostname, username, password, port)
    try:
        return True
    finally:
        client.close()


def _prefix_to_mask(prefix: int) -> str:
    mask = (0xFFFFFFFF >> (32 - prefix)) << (32 - prefix)
    return ".".join(str((mask >> (8 * i)) & 0xFF) for i in reversed(range(4)))
