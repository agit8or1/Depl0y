"""IP ban/allow list and GeoIP middleware"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import status
import ipaddress
import logging
import time
import urllib.request
import json
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory GeoIP cache — uses ip-api.com (free, no key, no file)
_geoip_cache: dict = {}  # {ip: {"code": str|None, "ts": float}}
_CACHE_TTL = 86400  # 24 hours


def _get_country(ip: str) -> Optional[str]:
    """Return ISO 3166-1 alpha-2 country code via ip-api.com with 24h caching."""
    now = time.time()
    cached = _geoip_cache.get(ip)
    if cached and (now - cached["ts"]) < _CACHE_TTL:
        return cached["code"]
    code = None
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,countryCode"
        req = urllib.request.Request(url, headers={"User-Agent": "depl0y/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "success":
                code = data.get("countryCode")
    except Exception as e:
        logger.debug(f"GeoIP lookup failed for {ip}: {e}")
    _geoip_cache[ip] = {"code": code, "ts": now}
    return code


def _ip_matches(client_ip: str, entry_ip: str) -> bool:
    """Check whether client_ip matches a single IP or CIDR range."""
    try:
        network = ipaddress.ip_network(entry_ip, strict=False)
        return ipaddress.ip_address(client_ip) in network
    except ValueError:
        return False


def _is_private(ip: str) -> bool:
    """Return True for loopback/private/link-local addresses."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_loopback or addr.is_private or addr.is_link_local
    except ValueError:
        return False


def _get_setting(db, key: str, default: str) -> str:
    from app.models.database import SystemSettings
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    return row.value if row else default


class IPFilterMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces IP ban/allow list and GeoIP country rules."""

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        # Skip filtering for loopback / health checks
        if client_ip in ("unknown", "127.0.0.1", "::1") or _is_private(client_ip):
            return await call_next(request)

        # Only import DB here so we don't create circular imports at module load
        from app.core.database import SessionLocal
        from app.models.security import IPBanList, GeoIPRule

        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)

            # ── 1. IP Ban / Allow list ──────────────────────────────────────
            ip_list_mode = _get_setting(db, "ip_list_mode", "blacklist")
            active_entries = (
                db.query(IPBanList)
                .filter(
                    IPBanList.is_active == True,
                    (IPBanList.expires_at == None) | (IPBanList.expires_at > now),
                )
                .all()
            )

            ban_entries = [e for e in active_entries if e.list_type == "ban"]
            allow_entries = [e for e in active_entries if e.list_type == "allow"]

            # Blacklist mode: deny if in ban list
            if ip_list_mode == "blacklist":
                for entry in ban_entries:
                    if _ip_matches(client_ip, entry.ip_address):
                        logger.warning(f"Blocked banned IP: {client_ip} (rule: {entry.ip_address})")
                        return JSONResponse(
                            status_code=status.HTTP_403_FORBIDDEN,
                            content={"detail": "Access denied"},
                        )

            # Whitelist mode: deny if NOT in allow list
            elif ip_list_mode == "whitelist":
                matched = any(_ip_matches(client_ip, e.ip_address) for e in allow_entries)
                if not matched:
                    logger.warning(f"Blocked non-whitelisted IP: {client_ip}")
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Access denied"},
                    )

            # ── 2. GeoIP filtering ──────────────────────────────────────────
            geoip_enabled = _get_setting(db, "geoip_enabled", "false")
            if geoip_enabled.lower() == "true":
                geoip_mode = _get_setting(db, "geoip_mode", "blacklist")
                country_code = _get_country(client_ip)

                if country_code:
                    active_rules = (
                        db.query(GeoIPRule)
                        .filter(GeoIPRule.is_active == True)
                        .all()
                    )
                    block_codes = {r.country_code for r in active_rules if r.action == "block"}
                    allow_codes = {r.country_code for r in active_rules if r.action == "allow"}

                    if geoip_mode == "blacklist":
                        if country_code in block_codes:
                            logger.warning(
                                f"Blocked IP {client_ip} from blocked country {country_code}"
                            )
                            return JSONResponse(
                                status_code=status.HTTP_403_FORBIDDEN,
                                content={"detail": "Access denied from your region"},
                            )
                    elif geoip_mode == "whitelist":
                        if allow_codes and country_code not in allow_codes:
                            logger.warning(
                                f"Blocked IP {client_ip} - country {country_code} not in whitelist"
                            )
                            return JSONResponse(
                                status_code=status.HTTP_403_FORBIDDEN,
                                content={"detail": "Access denied from your region"},
                            )
        finally:
            db.close()

        return await call_next(request)
