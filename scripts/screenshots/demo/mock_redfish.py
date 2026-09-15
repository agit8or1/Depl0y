"""Read-only mock Redfish service (Dell iDRAC + HPE iLO shapes) for the demo.

One process stands in for every BMC; the target server is selected from the
Host header (each BMC address is a loopback alias inside the demo namespace).
All mutating verbs are refused — no power action can ever be executed.
"""
import logging
import sys
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

sys.path.insert(0, __import__("os").path.dirname(__file__))
import fixtures as F  # noqa: E402

logging.basicConfig(level=logging.INFO, format="mock-redfish %(levelname)s %(message)s")
log = logging.getLogger("mock-redfish")
UNMATCHED = set()

app = FastAPI(docs_url=None, redoc_url=None)


def node_for(request: Request):
    host = (request.headers.get("host") or "").split(":")[0]
    hit = F.BMC_BY_IP.get(host)
    if hit:
        return hit
    return next(iter(F.BMC_BY_IP.values()))


def ids(n):
    if n["bmc"] == "ilo":
        return "1", "1", "1"
    return "System.Embedded.1", "iDRAC.Embedded.1", "System.Embedded.1"


def status(health="OK", state="Enabled"):
    return {"Health": health, "HealthRollup": health, "State": state}


# ----------------------------------------------------------------- resources


def service_root(name, n):
    sid, mid, cid = ids(n)
    return {
        "@odata.id": "/redfish/v1", "@odata.type": "#ServiceRoot.v1_5_0.ServiceRoot",
        "Id": "RootService", "Name": "Root Service", "RedfishVersion": "1.13.0",
        "Vendor": "HPE" if n["bmc"] == "ilo" else "Dell",
        "Systems": {"@odata.id": "/redfish/v1/Systems"},
        "Managers": {"@odata.id": "/redfish/v1/Managers"},
        "Chassis": {"@odata.id": "/redfish/v1/Chassis"},
        "UpdateService": {"@odata.id": "/redfish/v1/UpdateService"},
    }


def system(name, n):
    sid, mid, cid = ids(n)
    dimm_total = n["dimms"] * n["dimm_gb"]
    body = {
        "@odata.id": f"/redfish/v1/Systems/{sid}",
        "@odata.type": "#ComputerSystem.v1_12_0.ComputerSystem",
        "Id": sid, "Name": "System", "SystemType": "Physical",
        "Manufacturer": "HPE" if n["bmc"] == "ilo" else "Dell Inc.",
        "Model": n["model"].replace("Dell ", "").replace("HPE ", ""),
        "SerialNumber": n["service_tag"], "SKU": n["service_tag"],
        "PartNumber": "0XY1Z2A00",
        "HostName": f"{name}.example.net",
        "BiosVersion": n["bios"],
        "PowerState": "On",
        "AssetTag": f"ASSET-{name.upper()}",
        "IndicatorLED": "Off",
        "Status": status(n["health"]),
        "ProcessorSummary": {
            "Count": n["sockets"], "Model": n["cpu_model"],
            "LogicalProcessorCount": n["cores"] * 2, "CoreCount": n["cores"],
            "Status": status("OK"),
        },
        "MemorySummary": {
            "TotalSystemMemoryGiB": dimm_total,
            "Status": status("Warning" if n.get("warn_dimm") else "OK"),
        },
        "Processors": {"@odata.id": f"/redfish/v1/Systems/{sid}/Processors"},
        "Memory": {"@odata.id": f"/redfish/v1/Systems/{sid}/Memory"},
        "Storage": {"@odata.id": f"/redfish/v1/Systems/{sid}/Storage"},
        "EthernetInterfaces": {"@odata.id": f"/redfish/v1/Systems/{sid}/EthernetInterfaces"},
        "Boot": {"BootSourceOverrideEnabled": "Disabled", "BootSourceOverrideTarget": "None"},
        "Actions": {"#ComputerSystem.Reset": {
            "target": f"/redfish/v1/Systems/{sid}/Actions/ComputerSystem.Reset",
            "ResetType@Redfish.AllowableValues": [
                "On", "ForceOff", "GracefulShutdown", "ForceRestart",
                "GracefulRestart", "PowerCycle", "Pxe"],
        }},
    }
    if n["bmc"] == "idrac":
        body["Oem"] = {"Dell": {"DellSystem": {
            "SystemPID": n["model"].replace("Dell ", ""),
            "SystemID": 1963, "NodeID": n["service_tag"],
            "ExpressServiceCode": "15738294016",
            "ChassisServiceTag": n["service_tag"],
            "ManagedSystemSize": "2 U",
        }}}
    return body


def manager(name, n):
    sid, mid, cid = ids(n)
    return {
        "@odata.id": f"/redfish/v1/Managers/{mid}",
        "@odata.type": "#Manager.v1_5_0.Manager",
        "Id": mid, "Name": "Manager",
        "ManagerType": "BMC",
        "Manufacturer": "HPE" if n["bmc"] == "ilo" else "Dell Inc.",
        "Model": n["gen"],
        "FirmwareVersion": n["bmc_fw"],
        "DateTime": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "Status": status("OK"),
        "EthernetInterfaces": {"@odata.id": f"/redfish/v1/Managers/{mid}/EthernetInterfaces"},
        "LogServices": {"@odata.id": f"/redfish/v1/Managers/{mid}/LogServices"},
    }


def thermal(name, n):
    base = n["temp"]
    temps = [
        {"Name": "Inlet Temp", "ReadingCelsius": round(base, 1),
         "UpperThresholdCritical": 47, "UpperThresholdNonCritical": 42,
         "Status": status("OK"), "PhysicalContext": "Intake"},
        {"Name": "Exhaust Temp", "ReadingCelsius": round(base + 14.5, 1),
         "UpperThresholdCritical": 75, "UpperThresholdNonCritical": 70,
         "Status": status("OK"), "PhysicalContext": "Exhaust"},
        {"Name": "CPU1 Temp", "ReadingCelsius": round(base + 26, 1),
         "UpperThresholdCritical": 93, "UpperThresholdNonCritical": 88,
         "Status": status("OK"), "PhysicalContext": "CPU"},
        {"Name": "CPU2 Temp", "ReadingCelsius": round(base + 24, 1),
         "UpperThresholdCritical": 93, "UpperThresholdNonCritical": 88,
         "Status": status("OK"), "PhysicalContext": "CPU"},
    ]
    fans = []
    for i in range(1, 7):
        rpm = int(F.wobble(8400, 900, name, "fan", i))
        fans.append({"Name": f"System Board Fan{i}A", "ReadingRPM": rpm,
                     "Reading": rpm, "MinReadingRange": 720, "MaxReadingRange": 18000,
                     "Status": status("OK")})
    return {"@odata.id": f"/redfish/v1/Chassis/{ids(n)[2]}/Thermal",
            "Id": "Thermal", "Name": "Thermal", "Temperatures": temps, "Fans": fans}


def power(name, n):
    w = n["watts"]
    return {
        "@odata.id": f"/redfish/v1/Chassis/{ids(n)[2]}/Power",
        "Id": "Power", "Name": "Power",
        "PowerControl": [{
            "Name": "System Power Control", "PowerConsumedWatts": w,
            "PowerCapacityWatts": 1100, "PowerAllocatedWatts": 1100,
            "PowerMetrics": {"AverageConsumedWatts": w - 9, "MaxConsumedWatts": w + 128,
                             "MinConsumedWatts": max(80, w - 150), "IntervalInMin": 60},
            "Status": status("OK"),
        }],
        "PowerSupplies": [
            {"Name": "PS1 Status", "PowerSupplyType": "AC", "LineInputVoltage": 232,
             "PowerCapacityWatts": 1100, "LastPowerOutputWatts": w // 2,
             "Model": "PWR SPLY,1100W,RDNT", "SerialNumber": "CN17B0AA1X001",
             "FirmwareVersion": "00.24.7A", "Status": status("OK"), "Redundancy": []},
            {"Name": "PS2 Status", "PowerSupplyType": "AC", "LineInputVoltage": 231,
             "PowerCapacityWatts": 1100, "LastPowerOutputWatts": w - w // 2,
             "Model": "PWR SPLY,1100W,RDNT", "SerialNumber": "CN17B0AA1X002",
             "FirmwareVersion": "00.24.7A", "Status": status("OK"), "Redundancy": []},
        ],
    }


_SEL = [
    ("OK", "Critical", "The power input for power supply 2 is lost.", "Power Supply"),
    ("OK", "OK", "Power supply redundancy is restored.", "Power Supply"),
    ("OK", "OK", "The system inlet temperature is within range.", "Temperature"),
    ("OK", "OK", "Log cleared.", "System Event"),
    ("OK", "OK", "Server power-on complete.", "System Event"),
    ("OK", "OK", "Firmware update to iDRAC completed successfully.", "System Event"),
]


def sel(name, n):
    now = int(time.time())
    members = []
    entries = list(_SEL)
    if n.get("warn_dimm"):
        entries.append(("OK", "Warning",
                        f"Correctable memory error rate exceeded for {n['warn_dimm']}.", "Memory"))
    for i, (_h, sev, msg, stype) in enumerate(entries):
        ts = now - 3600 * (len(entries) - i) * 7
        members.append({
            "@odata.id": f"/redfish/v1/Managers/{ids(n)[1]}/LogServices/Sel/Entries/{i+1}",
            "Id": str(i + 1), "Name": "System Event Log Entry",
            "Created": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(ts)),
            "Message": msg, "Severity": sev, "SensorType": stype,
            "EntryType": "SEL", "MessageId": f"IDRAC.2.9.{1000+i}",
        })
    return {"Members": members, "Members@odata.count": len(members),
            "Name": "System Event Log Entries", "Id": "Entries"}


def processors_collection(name, n):
    sid = ids(n)[0]
    return {"Name": "ProcessorsCollection", "Members@odata.count": n["sockets"],
            "Members": [{"@odata.id": f"/redfish/v1/Systems/{sid}/Processors/CPU.Socket.{i}"}
                        for i in range(1, n["sockets"] + 1)]}


def processor(name, n, pid):
    sid = ids(n)[0]
    return {
        "@odata.id": f"/redfish/v1/Systems/{sid}/Processors/{pid}",
        "Id": pid, "Name": pid.replace(".", " "),
        "Manufacturer": "Intel", "Model": n["cpu_model"],
        "ProcessorType": "CPU", "ProcessorArchitecture": "x86",
        "InstructionSet": "x86-64",
        "MaxSpeedMHz": int(float(n["mhz"]) * 1.0) if n["mhz"].isdigit() else 2000,
        "TotalCores": n["cores"] // n["sockets"],
        "TotalThreads": (n["cores"] // n["sockets"]) * 2,
        "Socket": pid.split(".")[-1],
        "Status": status("OK"),
    }


def memory_collection(name, n):
    sid = ids(n)[0]
    slots = []
    letters = "ABCDEFGH"
    for i in range(n["dimms"]):
        slot = f"DIMM.Socket.{letters[i % 2]}{i // 2 + 1}"
        slots.append(slot)
    return {"Name": "MemoryCollection", "Members@odata.count": len(slots),
            "Members": [{"@odata.id": f"/redfish/v1/Systems/{sid}/Memory/{s}"} for s in slots]}


def memory(name, n, mid_):
    sid = ids(n)[0]
    bad = n.get("warn_dimm") == mid_
    return {
        "@odata.id": f"/redfish/v1/Systems/{sid}/Memory/{mid_}",
        "Id": mid_, "Name": mid_.replace(".", " "),
        "Manufacturer": "Hynix Semiconductor",
        "CapacityMiB": n["dimm_gb"] * 1024,
        "OperatingSpeedMhz": 3200, "AllowedSpeedsMHz": [3200],
        "MemoryDeviceType": "DDR4", "MemoryType": "DRAM",
        "RankCount": 2, "BusWidthBits": 72, "DataWidthBits": 64,
        "PartNumber": "HMAA4GR7AJR8N-XN", "SerialNumber": "3E1A2B4C",
        "DeviceLocator": mid_.split(".")[-1],
        "Status": status("Warning" if bad else "OK"),
    }


def storage_collection(name, n):
    sid = ids(n)[0]
    return {"Name": "StorageCollection", "Members@odata.count": 1,
            "Members": [{"@odata.id": f"/redfish/v1/Systems/{sid}/Storage/RAID.Integrated.1-1"}]}


def storage_ctrl(name, n):
    sid = ids(n)[0]
    media, cap, model, count = n["drives"][0]
    ctrl_model = "HPE Smart Array P408i-a SR Gen10" if n["bmc"] == "ilo" else "PERC H745 Front"
    return {
        "@odata.id": f"/redfish/v1/Systems/{sid}/Storage/RAID.Integrated.1-1",
        "Id": "RAID.Integrated.1-1", "Name": "RAID Controller in SL 1",
        "Status": status("OK"),
        "StorageControllers": [{
            "Name": ctrl_model, "Model": ctrl_model, "Manufacturer": "DELL" if n["bmc"] == "idrac" else "HPE",
            "FirmwareVersion": "52.26.0-5179", "SupportedRAIDTypes": ["RAID0", "RAID1", "RAID5", "RAID10"],
            "Status": status("OK"),
        }],
        "Drives": [{"@odata.id":
                    f"/redfish/v1/Systems/{sid}/Storage/RAID.Integrated.1-1/Drives/"
                    f"Disk.Bay.{i}:Enclosure.Internal.0-1:RAID.Integrated.1-1"}
                   for i in range(count)],
    }


def drive(name, n, did):
    sid = ids(n)[0]
    media, cap, model, _count = n["drives"][0]
    bay = did.split(".")[2].split(":")[0]
    return {
        "@odata.id": f"/redfish/v1/Systems/{sid}/Storage/RAID.Integrated.1-1/Drives/{did}",
        "Id": did, "Name": f"Solid State Disk 0:1:{bay}" if media == "SSD" else f"Physical Disk 0:1:{bay}",
        "Model": model, "Manufacturer": "DELL" if n["bmc"] == "idrac" else "HPE",
        "CapacityBytes": cap, "MediaType": media,
        "Protocol": "NVMe" if "NVMe" in model else "SAS",
        "RotationSpeedRPM": None if media == "SSD" else 10000,
        "SerialNumber": f"S5{bay}NNE0R{bay}12{bay}",
        "Revision": "2.3.0", "PredictedMediaLifeLeftPercent": 97 if media == "SSD" else None,
        "Status": status("OK"),
    }


def bmc_nics_collection(name, n):
    mid = ids(n)[1]
    return {"Name": "EthernetInterfaceCollection", "Members@odata.count": 1,
            "Members": [{"@odata.id": f"/redfish/v1/Managers/{mid}/EthernetInterfaces/NIC.1"}]}


def bmc_nic(name, n, iid):
    mid = ids(n)[1]
    ip = n["bmc_ip"]
    net = ip.rsplit(".", 1)[0]
    return {
        "@odata.id": f"/redfish/v1/Managers/{mid}/EthernetInterfaces/{iid}",
        "Id": iid, "Name": "Manager Ethernet Interface",
        "MACAddress": "F4:8E:38:%02X:%02X:%02X" % (
            F._seed(name, "bmc") % 256, F._seed(name, "bmc2") % 256, F._seed(name, "bmc3") % 256),
        "SpeedMbps": 1000, "LinkStatus": "LinkUp", "InterfaceEnabled": True,
        "HostName": f"idrac-{name}", "FQDN": f"idrac-{name}.example.net",
        "IPv4Addresses": [{"Address": ip, "SubnetMask": "255.255.255.0",
                           "Gateway": f"{net}.1", "AddressOrigin": "Static"}],
        "IPv4StaticAddresses": [{"Address": ip, "SubnetMask": "255.255.255.0",
                                 "Gateway": f"{net}.1"}],
        "IPv6Addresses": [], "NameServers": ["203.0.113.2", "198.51.100.2"],
        "DHCPv4": {"DHCPEnabled": False}, "Status": status("OK"),
    }


def firmware_collection(name, n):
    comps = ["BIOS", "iDRAC" if n["bmc"] == "idrac" else "iLO5", "NIC.Integrated.1-1-1",
             "RAID.Integrated.1-1", "Disk.Bay.0", "PSU.Slot.1", "PSU.Slot.2", "CPLD"]
    return {"Name": "FirmwareInventoryCollection", "Members@odata.count": len(comps),
            "Members": [{"@odata.id": f"/redfish/v1/UpdateService/FirmwareInventory/Installed-{c}"}
                        for c in comps]}


_FW_VERSIONS = {
    "NIC.Integrated.1-1-1": ("Intel(R) Ethernet 10G 4P X710 rNDC", "22.5.7"),
    "RAID.Integrated.1-1": ("PERC H745 Front", "52.26.0-5179"),
    "Disk.Bay.0": ("Backplane Firmware", "4.35"),
    "PSU.Slot.1": ("Power Supply 1", "00.24.7A"),
    "PSU.Slot.2": ("Power Supply 2", "00.24.7A"),
    "CPLD": ("System CPLD", "1.1.3"),
}


def firmware(name, n, comp):
    comp = comp.replace("Installed-", "")
    if comp == "BIOS":
        label, ver = "BIOS", n["bios"]
    elif comp in ("iDRAC", "iLO5"):
        label, ver = ("Integrated Dell Remote Access Controller" if comp == "iDRAC"
                      else "HPE iLO 5"), n["bmc_fw"]
    else:
        label, ver = _FW_VERSIONS.get(comp, (comp, "1.0.0"))
    return {
        "@odata.id": f"/redfish/v1/UpdateService/FirmwareInventory/Installed-{comp}",
        "Id": f"Installed-{comp}", "Name": label, "Version": ver,
        "Updateable": True, "ReleaseDate": "2025-11-04T00:00:00Z",
        "Status": status("OK"),
    }


# -------------------------------------------------------------------- router


@app.get("/redfish/v1{rest:path}")
def redfish(rest: str, request: Request):
    name, n = node_for(request)
    sid, mid, cid = ids(n)
    p = ("/redfish/v1" + rest).rstrip("/")
    T = {
        "/redfish/v1": lambda: service_root(name, n),
        f"/redfish/v1/Systems/{sid}": lambda: system(name, n),
        f"/redfish/v1/Managers/{mid}": lambda: manager(name, n),
        f"/redfish/v1/Chassis/{cid}/Thermal": lambda: thermal(name, n),
        f"/redfish/v1/Chassis/{cid}/Power": lambda: power(name, n),
        f"/redfish/v1/Managers/{mid}/LogServices/Sel/Entries": lambda: sel(name, n),
        f"/redfish/v1/Systems/{sid}/LogServices/IML/Entries": lambda: sel(name, n),
        f"/redfish/v1/Systems/{sid}/Processors": lambda: processors_collection(name, n),
        f"/redfish/v1/Systems/{sid}/Memory": lambda: memory_collection(name, n),
        f"/redfish/v1/Systems/{sid}/Storage": lambda: storage_collection(name, n),
        f"/redfish/v1/Systems/{sid}/Storage/RAID.Integrated.1-1": lambda: storage_ctrl(name, n),
        f"/redfish/v1/Managers/{mid}/EthernetInterfaces": lambda: bmc_nics_collection(name, n),
        "/redfish/v1/UpdateService/FirmwareInventory": lambda: firmware_collection(name, n),
    }
    if p in T:
        return JSONResponse(T[p]())

    pre = f"/redfish/v1/Systems/{sid}/"
    if p.startswith(pre + "Processors/"):
        return JSONResponse(processor(name, n, p.rsplit("/", 1)[1]))
    if p.startswith(pre + "Memory/"):
        return JSONResponse(memory(name, n, p.rsplit("/", 1)[1]))
    if p.startswith(pre + "Storage/RAID.Integrated.1-1/Drives/"):
        return JSONResponse(drive(name, n, p.rsplit("/", 1)[1]))
    if p.startswith(f"/redfish/v1/Managers/{mid}/EthernetInterfaces/"):
        return JSONResponse(bmc_nic(name, n, p.rsplit("/", 1)[1]))
    if p.startswith("/redfish/v1/UpdateService/FirmwareInventory/"):
        return JSONResponse(firmware(name, n, p.rsplit("/", 1)[1]))

    if p not in UNMATCHED:
        UNMATCHED.add(p)
        log.info("unmatched GET %s (%s)", p, name)
    return JSONResponse({"error": {"code": "Base.1.0.ResourceMissing"}}, status_code=404)


@app.api_route("/redfish/v1{rest:path}", methods=["POST", "PUT", "PATCH", "DELETE"])
def refuse(rest: str, request: Request):
    log.warning("refused %s %s", request.method, rest)
    return JSONResponse(
        {"error": {"code": "Base.1.0.ActionNotSupported",
                   "@Message.ExtendedInfo": [{"Message": "read-only demo fixture"}]}},
        status_code=403,
    )
