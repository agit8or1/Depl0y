"""Single-use tickets for the console WebSockets.

Browsers cannot set an Authorization header on a WebSocket, so the socket URL
has to carry the credential. Instead of the access token (which would then be
written to proxy and server access logs), the page first asks
POST /pve-console/ws-ticket for a ticket. A ticket:

- is 32 random bytes, stored server-side only as its SHA-256;
- is bound to one user (and that user's token_version) and one target
  (kind, host_id, node, vmid);
- expires after TICKET_TTL seconds and is deleted on first use, whether the
  use succeeds or not.

The store is in process memory: depl0y runs a single uvicorn worker, and a
restart simply invalidates outstanding tickets (the page asks for a new one).
"""
import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

TICKET_TTL = 30.0
_MAX_OUTSTANDING = 10_000

Target = Tuple[str, int, str, Optional[int]]   # (kind, host_id, node, vmid)


@dataclass(frozen=True)
class _Entry:
    user_id: int
    token_version: int
    target: Target
    expires: float


_lock = threading.Lock()
_tickets: dict = {}


def _digest(ticket: str) -> str:
    return hashlib.sha256(ticket.encode("utf-8", "replace")).hexdigest()


def _prune(now: float) -> None:
    for k in [k for k, e in _tickets.items() if e.expires <= now]:
        del _tickets[k]


def issue(user_id: int, token_version: int, target: Target) -> str:
    ticket = secrets.token_urlsafe(32)
    now = time.monotonic()
    with _lock:
        _prune(now)
        if len(_tickets) >= _MAX_OUTSTANDING:
            # Drop the oldest rather than refuse service.
            oldest = min(_tickets, key=lambda k: _tickets[k].expires)
            del _tickets[oldest]
        _tickets[_digest(ticket)] = _Entry(user_id, token_version, target, now + TICKET_TTL)
    return ticket


def consume(ticket: Optional[str], target: Target) -> Optional[Tuple[int, int]]:
    """Redeem *ticket* for *target*. Returns (user_id, token_version) or None.

    The ticket is removed even when the target does not match, so a ticket
    can never be tried twice."""
    if not ticket:
        return None
    with _lock:
        entry = _tickets.pop(_digest(ticket), None)
    if entry is None or entry.expires <= time.monotonic() or entry.target != target:
        return None
    return entry.user_id, entry.token_version


def clear() -> None:
    with _lock:
        _tickets.clear()
