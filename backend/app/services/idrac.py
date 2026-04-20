"""iDRAC / iLO out-of-band management via Redfish API."""
import ssl
import requests
from requests.adapters import HTTPAdapter
import logging
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Disable insecure HTTPS warnings for BMC connections (self-signed certs are the norm)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class _LegacyTLSAdapter(HTTPAdapter):
    """HTTPAdapter that handles legacy BMC TLS (iDRAC 7/8, iLO 3/4).

    OpenSSL 3.0 requires OP_LEGACY_SERVER_CONNECT for servers that use
    unsafe legacy renegotiation (common on older iDRAC firmware).
    """
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.minimum_version = ssl.TLSVersion.TLSv1
        except AttributeError:
            ctx.options &= ~(ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1)
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        # Required for iDRAC 7 (and other older BMCs) on OpenSSL 3.0+
        if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
            ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
        kwargs["ssl_context"] = ctx
        super().init_poolmanager(*args, **kwargs)

# ── Dell PCI subsystem device ID → PowerEdge model name ──────────────────
# Source: PCI IDs database + Dell product datasheets. Used to identify server
# model when iDRAC Redfish Model field is blank (common on 13G / iDRAC 8).
_DELL_PCI_SUBSYS_MODEL = {
    "0x048c": "PowerEdge R910",
    "0x04de": "PowerEdge R720",
    "0x04f7": "PowerEdge R720xd",
    "0x0503": "PowerEdge R420",
    "0x0505": "PowerEdge R620",
    "0x0511": "PowerEdge T320",
    "0x0512": "PowerEdge T420",
    "0x051f": "PowerEdge R520",
    "0x052c": "PowerEdge M620",
    "0x0539": "PowerEdge R820",
    "0x053b": "PowerEdge R320",
    "0x0554": "PowerEdge R220",
    "0x05d2": "PowerEdge R430",
    "0x05d3": "PowerEdge R530",
    "0x0601": "PowerEdge R230",
    "0x0602": "PowerEdge R330",
    "0x0617": "PowerEdge R630",
    "0x0618": "PowerEdge R730",
    "0x0619": "PowerEdge R930",
    "0x0627": "PowerEdge R730xd",
    "0x0628": "PowerEdge M630",
    "0x0640": "PowerEdge R230",
    "0x06b7": "PowerEdge R440",
    "0x06bb": "PowerEdge R540",
    "0x06ba": "PowerEdge R640",
    "0x06b9": "PowerEdge R740",
    "0x06bc": "PowerEdge R740xd",
    "0x06c8": "PowerEdge R940",
    "0x0704": "PowerEdge R650",
    "0x0705": "PowerEdge R750",
    "0x0706": "PowerEdge R750xs",
    "0x0738": "PowerEdge R660",
    "0x073a": "PowerEdge R760",
}


def lookup_dell_model_from_pci(subsys_device_id: str) -> str:
    """Return PowerEdge model name for a Dell PCI subsystem device ID, or ''."""
    return _DELL_PCI_SUBSYS_MODEL.get(subsys_device_id.lower(), "")


# ── Redfish paths differ slightly between vendors ──────────────────────────
_PATHS = {
    "idrac": {
        "system": "/redfish/v1/Systems/System.Embedded.1",
        "manager": "/redfish/v1/Managers/iDRAC.Embedded.1",
        "reset_action": "/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset",
        "sel": "/redfish/v1/Managers/iDRAC.Embedded.1/LogServices/Sel/Entries",
        "thermal": "/redfish/v1/Chassis/System.Embedded.1/Thermal",
        "power": "/redfish/v1/Chassis/System.Embedded.1/Power",
    },
    "ilo": {
        "system": "/redfish/v1/Systems/1",
        "manager": "/redfish/v1/Managers/1",
        "reset_action": "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
        "sel": "/redfish/v1/Systems/1/LogServices/IML/Entries",
        "thermal": "/redfish/v1/Chassis/1/Thermal",
        "power": "/redfish/v1/Chassis/1/Power",
    },
}

_RESET_TYPES = {
    "on": "On",
    "off": "ForceOff",
    "graceful_off": "GracefulShutdown",
    "reset": "ForceRestart",
    "graceful_reset": "GracefulRestart",
    "power_cycle": "PowerCycle",
    "pxe": "Pxe",
}


class RedfishClient:
    """Simple Redfish HTTP client for iDRAC and iLO BMCs."""

    def __init__(
        self,
        hostname: str,
        username: str,
        password: str,
        port: int = 443,
        bmc_type: str = "idrac",  # "idrac" or "ilo"
        timeout: int = 20,
    ):
        self.base_url = f"https://{hostname}:{port}"
        self.username = username
        self.password = password
        self.timeout = timeout
        self.bmc_type = bmc_type if bmc_type in _PATHS else "idrac"
        self.paths = _PATHS[self.bmc_type]
        self.session = requests.Session()
        self.session.verify = False
        self.session.auth = (username, password)
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        # Mount legacy TLS adapter for all HTTPS — handles iDRAC 7 (TLS 1.0) transparently
        _adapter = _LegacyTLSAdapter()
        self.session.mount("https://", _adapter)

    def _get(self, path: str) -> Dict[str, Any]:
        url = self.base_url + path
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> Dict[str, Any]:
        url = self.base_url + path
        resp = self.session.post(url, json=body, timeout=self.timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": "ok", "http_status": resp.status_code}

    def test_connection(self) -> bool:
        """Return True if the BMC responds to a Redfish version check."""
        try:
            data = self._get("/redfish/v1")
            return "RedfishVersion" in data or "Name" in data
        except Exception as e:
            logger.warning(f"Redfish connection test failed: {e}")
            return False

    def get_system_info(self) -> Dict[str, Any]:
        """Return condensed system info: model, power state, BIOS version, etc."""
        data = self._get(self.paths["system"])
        # Older iDRAC 8 (13G) returns Model/Manufacturer as ' ' (whitespace)
        model = (data.get("Model") or "").strip()
        manufacturer = (data.get("Manufacturer") or "").strip()
        # NOTE: SKU is the 7-char Dell Express Service Code (e.g. "CVPVS52"), not a model name.
        # Do NOT use it as a model fallback — it is misleading.
        # Try manager endpoint for manufacturer and generation hint
        if not model or not manufacturer:
            try:
                mgr = self._get(self.paths["manager"])
                if not manufacturer:
                    manufacturer = (mgr.get("Manufacturer") or "Dell").strip()
                if not model:
                    # mgr.get("Model") returns e.g. "13G Monolithic", "14G Monolithic"
                    # Convert generation label → "Dell PowerEdge (13G)" style fallback
                    mgr_model = (mgr.get("Model") or "").strip()
                    import re as _re
                    gen_m = _re.match(r'^(\d+G)', mgr_model)
                    if gen_m:
                        model = f"Dell PowerEdge ({gen_m.group(1)})"
                    elif mgr_model and not mgr_model[0].isdigit():
                        model = mgr_model  # e.g. "iDRAC8" from some versions
            except Exception:
                pass
        return {
            "manufacturer": manufacturer,
            "model": model,
            "serial_number": (data.get("SerialNumber") or "").strip(),
            "bios_version": data.get("BiosVersion", ""),
            "power_state": data.get("PowerState", "Unknown"),
            "health": data.get("Status", {}).get("Health", "Unknown"),
            "state": data.get("Status", {}).get("State", "Unknown"),
            "processor_count": data.get("ProcessorSummary", {}).get("Count", None),
            "processor_model": data.get("ProcessorSummary", {}).get("Model", ""),
            "memory_total_gb": round(
                (data.get("MemorySummary", {}).get("TotalSystemMemoryGiB") or 0), 1
            ),
            "hostname": data.get("HostName", ""),
        }

    def get_power_state(self) -> str:
        """Return current power state (On / Off / Unknown)."""
        data = self._get(self.paths["system"])
        return data.get("PowerState", "Unknown")

    def power_action(self, action: str) -> Dict[str, Any]:
        """
        Execute a power action.
        action: on | off | graceful_off | reset | graceful_reset | pxe
        """
        reset_type = _RESET_TYPES.get(action)
        if not reset_type:
            raise ValueError(f"Unknown power action '{action}'. Valid: {list(_RESET_TYPES)}")
        return self._post(self.paths["reset_action"], {"ResetType": reset_type})

    def get_event_log(self, limit: int = 50) -> list:
        """Return the most recent system event log entries."""
        data = self._get(self.paths["sel"])
        members = data.get("Members", [])
        entries = []
        for m in members[-limit:]:
            entries.append({
                "id": m.get("Id", ""),
                "created": m.get("Created", ""),
                "message": m.get("Message", m.get("Name", "")),
                "severity": m.get("Severity", ""),
                "sensor_type": m.get("SensorType", ""),
            })
        return list(reversed(entries))  # newest first

    def get_thermal(self) -> Dict[str, Any]:
        """Return temperature readings and fan status."""
        try:
            data = self._get(self.paths["thermal"])
            temps = []
            for t in data.get("Temperatures", []):
                if t.get("Status", {}).get("State") == "Enabled":
                    temps.append({
                        "name": t.get("Name", ""),
                        "reading_celsius": t.get("ReadingCelsius"),
                        "upper_threshold_critical": t.get("UpperThresholdCritical"),
                        "health": t.get("Status", {}).get("Health", ""),
                    })
            fans = []
            for f in data.get("Fans", []):
                fans.append({
                    "name": f.get("Name", f.get("FanName", "")),
                    "reading_rpm": f.get("ReadingRPM", f.get("Reading")),
                    "health": f.get("Status", {}).get("Health", ""),
                })
            return {"temperatures": temps, "fans": fans}
        except Exception as e:
            logger.warning(f"Failed to get thermal data: {e}")
            return {"temperatures": [], "fans": []}

    def get_power_usage(self) -> Dict[str, Any]:
        """Return current power consumption in watts."""
        try:
            data = self._get(self.paths["power"])
            readings = []
            for ctrl in data.get("PowerControl", []):
                readings.append({
                    "name": ctrl.get("Name", ""),
                    "consumed_watts": ctrl.get("PowerConsumedWatts"),
                    "capacity_watts": ctrl.get("PowerCapacityWatts"),
                })
            return {"power_control": readings}
        except Exception as e:
            logger.warning(f"Failed to get power usage: {e}")
            return {"power_control": []}

    def clear_sel(self) -> Dict[str, Any]:
        """Clear the iDRAC/iLO System Event Log. Stale SEL entries keep the
        rollup Status.Health at Warning even after the condition clears, so
        operators routinely clear this after resolving hardware events."""
        # Try modern Redfish action path first
        action_path = f"{self.paths['manager']}/LogServices/Sel/Actions/LogService.ClearLog"
        try:
            url = self.base_url + action_path
            resp = self.session.post(url, json={}, timeout=self.timeout)
            if resp.status_code in (200, 202, 204):
                return {"status": "ok", "method": "redfish", "http_status": resp.status_code}
            # iDRAC 7 often rejects the Redfish action — fall through to racadm
            logger.info(f"Redfish SEL clear rejected ({resp.status_code}); trying OEM endpoint")
        except Exception as e:
            logger.warning(f"Redfish SEL clear errored: {e}")
        # Dell OEM fallback
        try:
            oem = "/redfish/v1/Managers/iDRAC.Embedded.1/LogServices/Sel/Actions/Oem/DellLogService.ClearLog"
            resp = self.session.post(self.base_url + oem, json={}, timeout=self.timeout)
            if resp.status_code in (200, 202, 204):
                return {"status": "ok", "method": "redfish-oem", "http_status": resp.status_code}
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"OEM SEL clear failed: {e}")
            raise

    def compute_current_health(self) -> Dict[str, Any]:
        """Compute overall health from *current* component state only, bypassing
        the rollup Status.Health which reflects stale SEL entries.

        Returns {health, reasons: [str]} where health is OK / Warning / Critical.
        """
        reasons: list[str] = []
        worst = "OK"

        def _rank(h):
            return {"Critical": 2, "Warning": 1, "OK": 0}.get(h, 0)

        def _consider(h, label):
            nonlocal worst
            if h in ("Warning", "Critical") and _rank(h) > _rank(worst):
                worst = h
            if h in ("Warning", "Critical"):
                reasons.append(f"{label}: {h}")

        # Power supplies
        try:
            p = self._get(self.paths["power"])
            for ps in p.get("PowerSupplies", []) or []:
                h = (ps.get("Status") or {}).get("Health") or ""
                _consider(h, ps.get("Name") or "PSU")
        except Exception:
            pass
        # Thermal (fans + temps) — Warning only if currently above threshold
        try:
            t = self._get(self.paths["thermal"])
            for f in t.get("Fans", []) or []:
                h = (f.get("Status") or {}).get("Health") or ""
                _consider(h, f.get("Name") or f.get("FanName") or "Fan")
            for tp in t.get("Temperatures", []) or []:
                h = (tp.get("Status") or {}).get("Health") or ""
                _consider(h, tp.get("Name") or "Temp")
        except Exception:
            pass
        # Processors
        try:
            procs = self._get(self.paths["system"] + "/Processors")
            for m in procs.get("Members") or []:
                try:
                    data = self._get(m.get("@odata.id", "").replace(self.base_url, "") or "")
                    h = (data.get("Status") or {}).get("Health") or ""
                    _consider(h, data.get("Name") or "CPU")
                except Exception:
                    pass
        except Exception:
            pass
        # Memory — only summary, individual DIMM checks are expensive
        try:
            sys_data = self._get(self.paths["system"])
            mh = (sys_data.get("MemorySummary") or {}).get("Status", {}).get("HealthRollup")
            _consider(mh or "", "Memory")
        except Exception:
            pass
        return {"health": worst, "reasons": reasons}

    def get_sensors(self) -> Dict[str, Any]:
        """Return a unified IPMI-style sensor table combining thermal and power readings."""
        sensors = []
        # Temperature sensors from /Thermal
        try:
            thermal = self._get(self.paths["thermal"])
            for t in thermal.get("Temperatures", []):
                state = t.get("Status", {}).get("State", "")
                if state not in ("Enabled", ""):
                    continue
                health = t.get("Status", {}).get("Health", "OK") or "OK"
                reading = t.get("ReadingCelsius")
                crit = t.get("UpperThresholdCritical")
                warn = t.get("UpperThresholdNonCritical")
                # Derive status from health or threshold proximity
                if health == "Critical" or (crit and reading is not None and reading >= crit):
                    status = "Critical"
                elif health == "Warning" or (warn and reading is not None and reading >= warn):
                    status = "Warning"
                else:
                    status = "OK"
                sensors.append({
                    "name": t.get("Name", ""),
                    "reading": reading,
                    "unit": "°C",
                    "status": status,
                    "type": "Temperature",
                    "upper_critical": crit,
                    "upper_warning": warn,
                })
            for f in thermal.get("Fans", []):
                health = f.get("Status", {}).get("Health", "OK") or "OK"
                reading = f.get("ReadingRPM", f.get("Reading"))
                status = "Critical" if health == "Critical" else ("Warning" if health == "Warning" else "OK")
                sensors.append({
                    "name": f.get("Name", f.get("FanName", "")),
                    "reading": reading,
                    "unit": "RPM",
                    "status": status,
                    "type": "Fan",
                    "upper_critical": None,
                    "upper_warning": None,
                })
        except Exception as e:
            logger.warning(f"Sensor fetch (thermal) failed: {e}")

        # Power readings from /Power
        try:
            power = self._get(self.paths["power"])
            for psu in power.get("PowerSupplies", []):
                health = psu.get("Status", {}).get("Health", "OK") or "OK"
                status = "Critical" if health == "Critical" else ("Warning" if health == "Warning" else "OK")
                reading = psu.get("PowerOutputWatts", psu.get("LastPowerOutputWatts"))
                sensors.append({
                    "name": psu.get("Name", psu.get("MemberId", "PSU")),
                    "reading": reading,
                    "unit": "W",
                    "status": status,
                    "type": "Power Supply",
                    "upper_critical": psu.get("PowerCapacityWatts"),
                    "upper_warning": None,
                })
            for v in power.get("Voltages", []):
                health = v.get("Status", {}).get("Health", "OK") or "OK"
                status = "Critical" if health == "Critical" else ("Warning" if health == "Warning" else "OK")
                sensors.append({
                    "name": v.get("Name", ""),
                    "reading": v.get("ReadingVolts"),
                    "unit": "V",
                    "status": status,
                    "type": "Voltage",
                    "upper_critical": v.get("UpperThresholdCritical"),
                    "upper_warning": v.get("UpperThresholdNonCritical"),
                })
        except Exception as e:
            logger.warning(f"Sensor fetch (power) failed: {e}")

        return {"sensors": sensors}

    def _patch(self, path: str, body: dict) -> Dict[str, Any]:
        url = self.base_url + path
        resp = self.session.patch(url, json=body, timeout=self.timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": "ok", "http_status": resp.status_code}

    def get_manager_info(self) -> Dict[str, Any]:
        """Return iDRAC/iLO manager info: firmware version, model."""
        data = self._get(self.paths["manager"])
        return {
            "firmware_version": data.get("FirmwareVersion", ""),
            "model": data.get("Model", ""),
            "name": data.get("Name", ""),
            "health": data.get("Status", {}).get("Health", ""),
            "id": data.get("Id", ""),
        }

    def get_dell_system_id(self) -> str:
        """Return Dell system ID (hex string like '0x0627') from Redfish OEM data, or ''."""
        try:
            data = self._get(self.paths["system"])
            # Dell iDRAC 8/9 expose SystemID in Oem.Dell.DellSystem
            oem_dell = (data.get("Oem") or {}).get("Dell") or {}
            dell_sys = oem_dell.get("DellSystem") or {}
            raw = dell_sys.get("SystemID")
            if raw is not None:
                return hex(int(raw))
        except Exception:
            pass
        return ""

    def _fetch_all(self, urls: list, parse_fn) -> list:
        """Fetch multiple URLs in parallel and parse each result."""
        results = []
        with ThreadPoolExecutor(max_workers=min(len(urls), 8)) as ex:
            futures = {ex.submit(self._get, url): url for url in urls}
            for fut in as_completed(futures):
                try:
                    item = parse_fn(fut.result())
                    if item is not None:
                        results.append(item)
                except Exception:
                    pass
        return results

    def get_network_interfaces(self) -> Dict[str, Any]:
        """Return BMC ethernet interface configurations."""
        path = self.paths["manager"] + "/EthernetInterfaces"
        data = self._get(path)
        urls = [m["@odata.id"] for m in data.get("Members", []) if m.get("@odata.id")]

        def parse(iface):
            return {
                "id": iface.get("Id", ""),
                "name": iface.get("Name", ""),
                "mac_address": iface.get("MACAddress", ""),
                "ipv4": iface.get("IPv4Addresses", []),
                "ipv4_static": iface.get("IPv4StaticAddresses", []),
                "ipv6": iface.get("IPv6Addresses", []),
                "speed_mbps": iface.get("SpeedMbps"),
                "dhcp_enabled": iface.get("DHCPv4", {}).get("DHCPEnabled", False),
                "link_status": iface.get("LinkStatus", ""),
                "fqdn": iface.get("FQDN", ""),
                "hostname": iface.get("HostName", ""),
                "name_servers": iface.get("NameServers", []),
            }

        return {"interfaces": sorted(self._fetch_all(urls, parse), key=lambda x: x["id"])}

    def patch_network_interface(self, iface_id: str, config: dict) -> Dict[str, Any]:
        """Update a BMC network interface (IP, gateway, DNS, DHCP)."""
        path = self.paths["manager"] + f"/EthernetInterfaces/{iface_id}"
        return self._patch(path, config)

    def get_processors(self) -> Dict[str, Any]:
        """Return CPU details."""
        path = self.paths["system"] + "/Processors"
        data = self._get(path)
        urls = [m["@odata.id"] for m in data.get("Members", []) if m.get("@odata.id")]

        def parse(proc):
            if proc.get("Status", {}).get("State") == "Absent":
                return None
            return {
                "id": proc.get("Id", ""),
                "model": proc.get("Model", ""),
                "manufacturer": proc.get("Manufacturer", ""),
                "cores": proc.get("TotalCores"),
                "threads": proc.get("TotalThreads"),
                "speed_mhz": proc.get("MaxSpeedMHz"),
                "socket": proc.get("Socket", ""),
                "architecture": proc.get("ProcessorArchitecture", ""),
                "health": proc.get("Status", {}).get("Health", ""),
            }

        return {"processors": sorted(self._fetch_all(urls, parse), key=lambda x: x["id"])}

    def get_memory_modules(self) -> Dict[str, Any]:
        """Return memory DIMM details."""
        path = self.paths["system"] + "/Memory"
        data = self._get(path)
        urls = [m["@odata.id"] for m in data.get("Members", []) if m.get("@odata.id")]

        def parse(mem):
            if mem.get("Status", {}).get("State") in ("Absent", None):
                return None
            cap = mem.get("CapacityMiB")
            if not cap:
                return None
            return {
                "id": mem.get("Id", ""),
                "name": mem.get("Name", ""),
                "manufacturer": mem.get("Manufacturer", ""),
                "capacity_mib": cap,
                "speed_mhz": mem.get("OperatingSpeedMhz"),
                "type": mem.get("MemoryDeviceType", ""),
                "part_number": mem.get("PartNumber", ""),
                "health": mem.get("Status", {}).get("Health", ""),
            }

        return {"modules": sorted(self._fetch_all(urls, parse), key=lambda x: x["id"])}

    def get_storage(self) -> Dict[str, Any]:
        """Return storage controllers and physical drives."""
        path = self.paths["system"] + "/Storage"
        data = self._get(path)
        ctrl_urls = [m["@odata.id"] for m in data.get("Members", []) if m.get("@odata.id")]
        controllers = []

        for ctrl_url in ctrl_urls:
            try:
                ctrl = self._get(ctrl_url)
                ctrl_info = ctrl.get("StorageControllers", [{}])
                ctrl_model = ctrl_info[0].get("Model", "") if ctrl_info else ctrl.get("Name", "")
                drive_urls = [d["@odata.id"] for d in ctrl.get("Drives", []) if d.get("@odata.id")]

                def parse_drive(drive):
                    cap = drive.get("CapacityBytes", 0)
                    return {
                        "id": drive.get("Id", ""),
                        "name": drive.get("Name", ""),
                        "model": drive.get("Model", ""),
                        "manufacturer": drive.get("Manufacturer", ""),
                        "capacity_gb": round(cap / 1e9, 1) if cap else None,
                        "media_type": drive.get("MediaType", ""),
                        "protocol": drive.get("Protocol", ""),
                        "rpm": drive.get("RotationSpeedRPM"),
                        "serial": drive.get("SerialNumber", ""),
                        "health": drive.get("Status", {}).get("Health", ""),
                        "state": drive.get("Status", {}).get("State", ""),
                    }

                drives = sorted(self._fetch_all(drive_urls, parse_drive), key=lambda x: x["id"])
                controllers.append({
                    "id": ctrl.get("Id", ""),
                    "name": ctrl.get("Name", ""),
                    "model": ctrl_model,
                    "health": ctrl.get("Status", {}).get("Health", ""),
                    "drives": drives,
                })
            except Exception:
                pass

        return {"controllers": controllers}

    def get_firmware_inventory(self) -> Dict[str, Any]:
        """Return firmware inventory for all components."""
        try:
            data = self._get("/redfish/v1/UpdateService/FirmwareInventory")
        except Exception:
            return {"firmware": []}
        urls = [m["@odata.id"] for m in data.get("Members", []) if m.get("@odata.id")]

        def parse(fw):
            return {
                "id": fw.get("Id", ""),
                "name": fw.get("Name", ""),
                "version": fw.get("Version", ""),
                "updateable": fw.get("Updateable", False),
                "health": fw.get("Status", {}).get("Health", ""),
                "release_date": fw.get("ReleaseDate", ""),
            }

        items = self._fetch_all(urls, parse)
        return {"firmware": sorted(items, key=lambda x: x["name"])}
