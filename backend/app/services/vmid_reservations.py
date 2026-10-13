"""VMID reservations for deploys and imports that run at the same time.

Proxmox's /cluster/nextid only reports the lowest VMID not in use *right now*. A deploy asks for
it early but only creates the VM later (after building a template, uploading an image, ...), so
two deploys started together got the same VMID and the second failed with "config file already
exists". Every allocation goes through reserve_vmid(), which hands out each VMID once while it is
held. All deploys run as threads of the one backend process, so an in-process lock is enough.
"""
import threading
import time

_lock = threading.Lock()
_held = {}   # vmid -> expiry (epoch seconds)

DEFAULT_TTL = 3 * 3600   # backstop if a holder never releases (a deploy can take a long time)


def reserve_vmid(pve, ttl: int = DEFAULT_TTL) -> int:
    """Return a VMID that is free in the cluster and not held by another deploy, and hold it."""
    with _lock:
        now = time.time()
        for vmid, expiry in list(_held.items()):
            if expiry <= now:
                del _held[vmid]
        in_use = {int(r["vmid"]) for r in pve.cluster.resources.get(type="vm") if r.get("vmid") is not None}
        vmid = int(pve.cluster.nextid.get())
        while vmid in _held or vmid in in_use:
            vmid += 1
        _held[vmid] = now + ttl
        return vmid


def release_vmid(vmid) -> None:
    """Give a VMID back (once its VM exists in Proxmox, or the deploy gave up)."""
    if vmid is None:
        return
    with _lock:
        _held.pop(int(vmid), None)
