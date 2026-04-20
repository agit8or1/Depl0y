"""Dell firmware catalog checker — compares installed BIOS/iDRAC versions against Dell's catalog."""
import gzip
import logging
import os
import time
import xml.etree.ElementTree as ET
from urllib.request import urlretrieve

logger = logging.getLogger(__name__)

CATALOG_URL = "https://downloads.dell.com/catalog/Catalog.xml.gz"
CATALOG_CACHE_PATH = "/tmp/dell_firmware_catalog.xml.gz"
CATALOG_TTL_SECONDS = 86400  # 24 hours

# In-memory parsed catalog: {system_id_hex: {"bios": (version, date), "idrac": (version, date)}}
_catalog: dict = {}
_catalog_mtime: float = 0


def _load_catalog() -> dict:
    """Download (if stale) and parse the Dell firmware catalog. Returns parsed dict."""
    global _catalog, _catalog_mtime

    now = time.time()
    # Use in-memory cache first
    if _catalog and (now - _catalog_mtime) < CATALOG_TTL_SECONDS:
        return _catalog

    # Download if disk cache is missing or stale
    needs_dl = not os.path.exists(CATALOG_CACHE_PATH)
    if not needs_dl:
        try:
            needs_dl = (now - os.path.getmtime(CATALOG_CACHE_PATH)) > CATALOG_TTL_SECONDS
        except OSError:
            needs_dl = True

    if needs_dl:
        logger.info("Downloading Dell firmware catalog from %s", CATALOG_URL)
        try:
            urlretrieve(CATALOG_URL, CATALOG_CACHE_PATH + ".tmp")
            os.replace(CATALOG_CACHE_PATH + ".tmp", CATALOG_CACHE_PATH)
            logger.info("Dell firmware catalog downloaded successfully")
        except Exception as exc:
            logger.error("Failed to download Dell firmware catalog: %s", exc)
            # Use stale cache if available
            if not os.path.exists(CATALOG_CACHE_PATH):
                return {}

    # Parse catalog with streaming XML (memory efficient)
    parsed: dict = {}
    try:
        with gzip.open(CATALOG_CACHE_PATH, "rb") as fh:
            for event, elem in ET.iterparse(fh, events=["end"]):
                local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if local == "SoftwareComponent":
                    _parse_component(elem, parsed)
                    elem.clear()
    except Exception as exc:
        logger.error("Failed to parse Dell firmware catalog: %s", exc)
        return {}

    _catalog = parsed
    _catalog_mtime = now
    logger.info("Dell firmware catalog parsed — %d system entries", len(parsed))
    return parsed


def _parse_component(elem, result: dict) -> None:
    """Extract BIOS/iDRAC version info from a SoftwareComponent XML element."""
    # Only care about BIOS and firmware (iDRAC)
    comp_type_elem = elem.find("ComponentType")
    if comp_type_elem is None:
        return
    comp_type = comp_type_elem.get("value", "")
    if comp_type not in ("BIOS", "FRMW"):
        return

    # Component display name (English)
    name_elem = elem.find('.//Name/Display[@lang="en"]')
    name = (name_elem.text or "").upper() if name_elem is not None else ""

    if "BIOS" in name:
        fw_type = "bios"
    elif "IDRAC" in name or "LIFECYCLE CONTROLLER" in name or "BMC" in name:
        fw_type = "idrac"
    else:
        return

    version = elem.get("version", "")
    release_date = elem.get("releaseDate", "")
    if not version:
        return

    # Each component lists supported system IDs
    for model_elem in elem.findall(".//SupportedSystems/Brand/Model"):
        sys_id_raw = model_elem.get("systemID", "")
        if not sys_id_raw:
            continue
        # Normalise: the catalog uses decimal (e.g. "1575"); convert to hex
        try:
            sys_id = hex(int(sys_id_raw))
        except ValueError:
            sys_id = sys_id_raw.lower()

        entry = result.setdefault(sys_id, {})
        existing = entry.get(fw_type)
        if existing is None or _is_newer(version, existing[0]):
            entry[fw_type] = (version, release_date)


def _is_newer(v1: str, v2: str) -> bool:
    """Return True if version string v1 is strictly newer than v2."""
    def _parts(v):
        parts = []
        for seg in v.replace("-", ".").split("."):
            try:
                parts.append(int(seg))
            except ValueError:
                parts.append(seg)
        return parts
    try:
        return _parts(v1) > _parts(v2)
    except Exception:
        return False


def check_updates(system_id: str, bios_version: str, idrac_version: str) -> dict:
    """
    Check if newer BIOS or iDRAC firmware is available for the given system.

    Args:
        system_id: Dell system ID as hex string (e.g. '0x0627'), or decimal string.
        bios_version: Installed BIOS version string.
        idrac_version: Installed iDRAC firmware version string.

    Returns:
        {
            "bios":  {"installed": ..., "available": ..., "release_date": ...} or None,
            "idrac": {"installed": ..., "available": ..., "release_date": ...} or None,
            "checked_at": ISO timestamp,
        }
    """
    from datetime import datetime
    result = {"bios": None, "idrac": None, "checked_at": datetime.utcnow().isoformat()}

    if not system_id:
        return result

    # Normalise system_id to hex
    try:
        norm_id = hex(int(system_id, 16))
    except Exception:
        try:
            norm_id = hex(int(system_id))
        except Exception:
            norm_id = system_id.lower()

    catalog = _load_catalog()
    entry = catalog.get(norm_id, {})

    if bios_version and "bios" in entry:
        latest, date = entry["bios"]
        if _is_newer(latest, bios_version):
            result["bios"] = {
                "installed": bios_version,
                "available": latest,
                "release_date": date,
            }

    if idrac_version and "idrac" in entry:
        latest, date = entry["idrac"]
        if _is_newer(latest, idrac_version):
            result["idrac"] = {
                "installed": idrac_version,
                "available": latest,
                "release_date": date,
            }

    return result
