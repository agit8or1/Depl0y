"""iDRAC / iLO out-of-band management via Redfish API."""
import requests
import logging
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Disable insecure HTTPS warnings for BMC connections (self-signed certs are the norm)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
        timeout: int = 10,
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
        # Fall back to SKU (service tag) if model is blank — better than nothing
        if not model:
            model = (data.get("SKU") or data.get("PartNumber") or "").strip()
        # Try manager endpoint as last resort to get at least the iDRAC generation
        if not model or not manufacturer:
            try:
                mgr = self._get(self.paths["manager"])
                if not manufacturer:
                    manufacturer = (mgr.get("Manufacturer") or "Dell").strip()
                if not model:
                    mgr_model = (mgr.get("Model") or "").strip()
                    if mgr_model:
                        model = mgr_model
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
