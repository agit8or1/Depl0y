"""Where to SSH for a Proxmox host.

`ProxmoxHost.hostname` is the API address, which is often a public name that reaches
port 8006 through a firewall. Port 22 on that name may go somewhere else entirely (or
nowhere), so SSH uses the LAN address of the cluster node that answers the API instead,
as reported by Proxmox in /cluster/status.
"""
import logging
import time

logger = logging.getLogger(__name__)

_CACHE_TTL = 600   # seconds
_cache = {}        # host id -> (expires, address)


def ssh_address(host) -> str:
    """LAN IP of the node serving `host`'s API; falls back to host.hostname."""
    hit = _cache.get(host.id)
    if hit and hit[0] > time.time():
        return hit[1]
    address = host.hostname
    try:
        from app.services.proxmox import ProxmoxService
        status = ProxmoxService(host).proxmox.cluster.status.get()
        local = next((x for x in status if x.get("type") == "node" and x.get("local") and x.get("ip")), None)
        if local:
            address = local["ip"]
    except Exception as exc:  # noqa: BLE001 - fall back to the API hostname
        logger.warning("Could not look up the node address for %s, using the hostname for SSH: %s",
                       host.hostname, exc)
    _cache[host.id] = (time.time() + _CACHE_TTL, address)
    return address
