"""SSH server identity checks for every Paramiko connection depl0y makes.

Each managed host's server key is stored in `ssh_host_keys`. A connection
only proceeds when the server presents an approved key; a different key is
refused before we authenticate (so no password or key signature is sent to
an impostor) and is kept as `pending` for an administrator to review.

A host we have never seen is handled by the `ssh_host_key_policy` setting:

- ``tofu`` (default): the first key seen is approved automatically
  ("trust on first use") and audited. Every later change is refused.
- ``strict``: the first key is stored as pending and the connection is
  refused until an administrator approves it.

Approving a pending key (rotation) replaces the host's approved keys.

OpenSSH command-line calls (ssh/scp/ssh-copy-id) get the same checks through
`openssh_options()`: the server's key is verified against the store first, and
ssh then runs with StrictHostKeyChecking=yes against a known_hosts file built
from the approved keys, so ssh re-checks the key on its own connection.
Hops that run *on* a Proxmox node use the cluster's own per-node keys
(`pve_hop_options()`), the way Proxmox itself connects between nodes.
"""
import base64
import hashlib
import logging
import os
import re
import shlex
import socket
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from typing import List, Optional

import paramiko

logger = logging.getLogger(__name__)

# Refuse SHA-1 RSA signatures ("ssh-rsa") for host keys and our own key auth (CVE-2026-44405,
# no fixed Paramiko release yet). RSA keys still work through rsa-sha2-256/512.
SSH_DISABLED_ALGORITHMS = {"pubkeys": ["ssh-rsa"], "keys": ["ssh-rsa"]}

POLICY_SETTING = "ssh_host_key_policy"
POLICIES = ("tofu", "strict")

KNOWN_HOSTS_FILE = os.getenv("DEPL0Y_SSH_KNOWN_HOSTS", "/var/lib/depl0y/ssh/known_hosts")
_VERIFIED_TTL = 60          # seconds a direct key check is reused for the same host
_verified: dict = {}        # (host, port) -> monotonic time of last successful check
_known_hosts_lock = threading.Lock()
_NODE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$")


class HostKeyError(paramiko.SSHException):
    """The server's identity could not be verified; nothing was authenticated."""

    def __init__(self, message: str, host: str, port: int, fingerprint: str):
        super().__init__(message)
        self.host = host
        self.port = port
        self.fingerprint = fingerprint


class HostKeyChangedError(HostKeyError):
    """The server presented a key other than the approved one."""


class HostKeyNotTrustedError(HostKeyError):
    """Unknown host under the strict policy — waiting for admin approval."""


def fingerprint(key: paramiko.PKey) -> str:
    """OpenSSH-style SHA256 fingerprint ("SHA256:..."), as `ssh-keygen -lf` prints it."""
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


def _hostkey_name(host: str, port: int) -> str:
    # Same naming Paramiko uses when it looks a host up in its HostKeys.
    return host if port == 22 else f"[{host}]:{port}"


def _merged_disabled(extra: Optional[dict]) -> dict:
    """Callers may disable more algorithms, never re-enable the defaults."""
    merged = {k: list(v) for k, v in SSH_DISABLED_ALGORITHMS.items()}
    for k, v in (extra or {}).items():
        merged[k] = sorted(set(merged.get(k, [])) | set(v))
    return merged


def get_policy(db) -> str:
    from app.models.database import SystemSettings
    row = db.query(SystemSettings).filter(SystemSettings.key == POLICY_SETTING).first()
    value = (row.value if row else "") or "tofu"
    return value if value in POLICIES else "tofu"


def _audit(db, action: str, row, user_id: Optional[int] = None, **details):
    from app.api.audit import log_audit_event
    log_audit_event(
        db, action, user_id=user_id, resource_type="ssh_host_key",
        resource_id=row.id if row is not None else None,
        details={"host": row.host, "port": row.port, "key_type": row.key_type,
                 "fingerprint": row.fingerprint, **details} if row is not None else details,
    )


def _record(db, host: str, port: int, key: paramiko.PKey, status: str):
    """Insert or refresh the row for this exact key and return it."""
    from sqlalchemy.exc import IntegrityError
    from app.models.database import SshHostKey

    fp = fingerprint(key)
    q = db.query(SshHostKey).filter_by(host=host, port=port, key_type=key.get_name(), fingerprint=fp)
    row = q.first()
    now = datetime.utcnow()
    if row is None:
        row = SshHostKey(host=host, port=port, key_type=key.get_name(), key_b64=key.get_base64(),
                         fingerprint=fp, status=status, first_seen=now, last_seen=now,
                         approved_at=now if status == "approved" else None)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            # Another thread recorded the same key at the same moment.
            db.rollback()
            row = q.first()
    else:
        row.last_seen = now
        db.commit()
    return row


def _approved_keys(db, host: str, port: int):
    from app.models.database import SshHostKey
    return db.query(SshHostKey).filter_by(host=host, port=port, status="approved").all()


def _trust_unknown(db, host: str, port: int, key: paramiko.PKey):
    """Apply the unknown-host policy to the first key seen for host:port."""
    name = _hostkey_name(host, port)
    fp = fingerprint(key)
    if get_policy(db) == "strict":
        row = _record(db, host, port, key, "pending")
        _audit(db, "ssh_host_key_unknown_rejected", row)
        raise HostKeyNotTrustedError(
            f"SSH host key for {name} is not approved yet ({key.get_name()} {fp}). "
            "Approve it under Settings → SSH host keys.", host, port, fp)
    row = _record(db, host, port, key, "approved")
    if row.status != "approved":
        # A pending row for this exact key already exists — an admin
        # has not approved it, so first use must not approve it either.
        raise HostKeyNotTrustedError(
            f"SSH host key for {name} is pending approval ({fp}).", host, port, fp)
    _audit(db, "ssh_host_key_trusted_first_use", row)
    logger.warning("SSH: trusting %s key %s for %s on first use", key.get_name(), fp, name)


class _PinnedHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """Called by Paramiko only when no approved key exists for the host."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def missing_host_key(self, client, hostname, key):
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            _trust_unknown(db, self.host, self.port, key)
        finally:
            db.close()
        client.get_host_keys().add(hostname, key.get_name(), key)


def ssh_connect(hostname: str, port: int = 22, username: Optional[str] = None,
                password: Optional[str] = None, pkey=None, timeout: float = 30,
                disabled_algorithms: Optional[dict] = None, **kwargs) -> paramiko.SSHClient:
    """Open a Paramiko SSHClient after verifying the server's key.

    Drop-in for a bare ``SSHClient().connect(...)`` that used to accept any
    host key. Raises HostKeyError (a paramiko.SSHException) when the
    server's identity is not approved — before any credentials are sent.
    """
    from app.core.database import SessionLocal

    client = paramiko.SSHClient()
    name = _hostkey_name(hostname, port)
    db = SessionLocal()
    try:
        for row in _approved_keys(db, hostname, port):
            try:
                client.get_host_keys().add(name, row.key_type, paramiko.PKey.from_type_string(
                    row.key_type, base64.b64decode(row.key_b64)))
            except Exception as exc:  # unreadable row: skip it, the host then looks changed
                logger.warning("SSH: cannot load stored key %s for %s: %s", row.id, name, exc)
    finally:
        db.close()
    client.set_missing_host_key_policy(_PinnedHostKeyPolicy(hostname, port))

    try:
        client.connect(hostname, port=port, username=username, password=password, pkey=pkey,
                       timeout=timeout, disabled_algorithms=_merged_disabled(disabled_algorithms),
                       **kwargs)
    except paramiko.BadHostKeyException as exc:
        client.close()
        db = SessionLocal()
        try:
            row = _record(db, hostname, port, exc.key, "pending")
            _audit(db, "ssh_host_key_changed_rejected", row,
                   expected_fingerprint=fingerprint(exc.expected_key))
        finally:
            db.close()
        fp = fingerprint(exc.key)
        logger.error("SSH: host key for %s CHANGED (got %s, expected %s) — refusing to connect",
                     name, fp, fingerprint(exc.expected_key))
        raise HostKeyChangedError(
            f"SSH host key for {name} changed (now {exc.key.get_name()} {fp}). Refusing to "
            "connect. If the change is expected, approve the new key under Settings → SSH host keys.",
            hostname, port, fp) from None
    except Exception:
        client.close()
        raise
    return client


def fetch_host_key(hostname: str, port: int = 22, timeout: float = 10) -> paramiko.PKey:
    """Read a server's host key without authenticating (for explicit enrollment)."""
    sock = socket.create_connection((hostname, port), timeout=timeout)
    transport = paramiko.Transport(sock, disabled_algorithms=SSH_DISABLED_ALGORITHMS)
    try:
        transport.start_client(timeout=timeout)
        return transport.get_remote_server_key()
    finally:
        transport.close()


def enroll_host_key(db, hostname: str, port: int, user_id: int):
    """Fetch a host's key and store it as pending for an admin to compare and approve."""
    key = fetch_host_key(hostname, port)
    row = _record(db, hostname, port, key, "pending")
    if row.status == "pending":
        _audit(db, "ssh_host_key_scanned", row, user_id=user_id)
    return row


def approve_host_key(db, row, user_id: int):
    """Approve `row` and retire every other approved key for that host (rotation)."""
    from app.models.database import SshHostKey
    replaced = (db.query(SshHostKey)
                .filter(SshHostKey.host == row.host, SshHostKey.port == row.port,
                        SshHostKey.status == "approved", SshHostKey.id != row.id).all())
    old = [r.fingerprint for r in replaced]
    for r in replaced:
        db.delete(r)
    row.status = "approved"
    row.approved_at = datetime.utcnow()
    row.approved_by = user_id
    db.commit()
    _verified.clear()
    _audit(db, "ssh_host_key_approved", row, user_id=user_id, replaced_fingerprints=old)
    return row


def delete_host_key(db, row, user_id: int):
    _audit(db, "ssh_host_key_deleted", row, user_id=user_id, status=row.status)
    db.delete(row)
    db.commit()
    _verified.clear()


# ── OpenSSH command-line tools ──────────────────────────────────────────────

def _verify_presented(db, host: str, port: int, keys: List[paramiko.PKey]):
    """Check the key(s) a server offers against the store (same rules as ssh_connect)."""
    approved = _approved_keys(db, host, port)
    if not approved:
        return _trust_unknown(db, host, port, keys[0])
    trusted = {(r.key_type, r.fingerprint): r for r in approved}
    for k in keys:
        row = trusted.get((k.get_name(), fingerprint(k)))
        if row is not None:
            row.last_seen = datetime.utcnow()
            db.commit()
            return
    key = keys[0]
    row = _record(db, host, port, key, "pending")
    _audit(db, "ssh_host_key_changed_rejected", row,
           expected_fingerprint=", ".join(r.fingerprint for r in approved))
    name, fp = _hostkey_name(host, port), fingerprint(key)
    logger.error("SSH: host key for %s CHANGED (got %s) — refusing to connect", name, fp)
    raise HostKeyChangedError(
        f"SSH host key for {name} changed (now {key.get_name()} {fp}). Refusing to connect. "
        "If the change is expected, approve the new key under Settings → SSH host keys.",
        host, port, fp)


_KEYSCAN_ORDER = ("ssh-ed25519", "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521", "ssh-rsa")


def _keyscan_via(jump: str, host: str, port: int) -> List[paramiko.PKey]:
    """Read host's keys with ssh-keyscan run on `jump` (itself verified first)."""
    cmd = shlex.join(["ssh-keyscan", "-T", "5", "-p", str(port), "-t", "ed25519,ecdsa,rsa", host])
    p = subprocess.run(["ssh", *openssh_options(jump), "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                        f"root@{jump}", cmd], capture_output=True, text=True, timeout=30)
    keys = []
    for line in p.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and not line.startswith("#"):
            try:
                keys.append(paramiko.PKey.from_type_string(parts[1], base64.b64decode(parts[2])))
            except Exception:
                continue
    keys.sort(key=lambda k: _KEYSCAN_ORDER.index(k.get_name()) if k.get_name() in _KEYSCAN_ORDER else 99)
    return keys


def ensure_host_key(host: str, port: int = 22, scan_via: Optional[str] = None):
    """Verify host's SSH key against the store before an OpenSSH tool connects.

    Raises HostKeyError if the key changed or is not approved. If the host
    cannot be reached (directly, or through `scan_via`), nothing is raised: ssh
    then fails on its own, because only approved keys are in its known_hosts.
    """
    from app.core.database import SessionLocal
    last = _verified.get((host, port))
    if last and time.monotonic() - last < _VERIFIED_TTL:
        return
    keys = []
    try:
        keys = [fetch_host_key(host, port, timeout=8)]
    except Exception as exc:
        if scan_via and scan_via != host:
            try:
                keys = _keyscan_via(scan_via, host, port)
            except HostKeyError:
                raise
            except Exception as exc2:
                logger.debug("SSH: keyscan of %s via %s failed: %s", host, scan_via, exc2)
        if not keys:
            logger.debug("SSH: could not read host key of %s:%s: %s", host, port, exc)
            return
    db = SessionLocal()
    try:
        _verify_presented(db, host, port, keys)
    finally:
        db.close()
    _verified[(host, port)] = time.monotonic()


def write_known_hosts(path: Optional[str] = None) -> str:
    """Rewrite the OpenSSH known_hosts file from the approved keys; return its path."""
    from app.core.database import SessionLocal
    from app.models.database import SshHostKey
    path = path or KNOWN_HOSTS_FILE
    db = SessionLocal()
    try:
        rows = db.query(SshHostKey).filter(SshHostKey.status == "approved").order_by(SshHostKey.id).all()
        lines = [f"{_hostkey_name(r.host, r.port)} {r.key_type} {r.key_b64}\n" for r in rows]
    finally:
        db.close()
    directory = os.path.dirname(path)
    with _known_hosts_lock:
        os.makedirs(directory, mode=0o700, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".known_hosts.")
        try:
            with os.fdopen(fd, "w") as f:
                f.writelines(lines)
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        except Exception:
            os.unlink(tmp)
            raise
    return path


def _strict_options(path: str) -> List[str]:
    return [
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={path}",
        "-o", "GlobalKnownHostsFile=/dev/null",
        "-o", "UpdateHostKeys=no",
        # Same SHA-1 refusal as SSH_DISABLED_ALGORITHMS; RSA keys use rsa-sha2-*.
        "-o", "HostKeyAlgorithms=-ssh-rsa",
        "-o", "PubkeyAcceptedAlgorithms=-ssh-rsa",
    ]


def openssh_options(host: str, port: int = 22, scan_via: Optional[str] = None) -> List[str]:
    """`-o` options for ssh/scp/ssh-copy-id to `host` with its key verified.

    Raises HostKeyError (before anything connects with credentials) if the key
    changed or is not approved.
    """
    ensure_host_key(host, port, scan_via=scan_via)
    return _strict_options(write_known_hosts())


def proxy_command_options(jump: str) -> List[str]:
    """Reach a host through `jump` with the jump host verified too.

    Used instead of ProxyJump, whose ssh for the jump host does not inherit
    command-line -o options and so would skip these checks.
    """
    inner = ["ssh", *openssh_options(jump), "-o", "BatchMode=yes", "-W", "%h:%p", f"root@{jump}"]
    return ["-o", "ProxyCommand=" + shlex.join(inner)]


def pve_hop_options(node_name: str) -> str:
    """Options (as a shell string) for ssh/scp run on a Proxmox node to reach `node_name`.

    Verifies the target against the cluster's own record of that node's key
    (/etc/pve/nodes/<node>/ssh_known_hosts), as Proxmox does between nodes.
    """
    if not _NODE_NAME_RE.match(node_name or ""):
        raise ValueError(f"invalid Proxmox node name: {node_name!r}")
    return " ".join([
        "-o", "BatchMode=yes",
        "-o", f"HostKeyAlias={node_name}",
        "-o", shlex.quote(f"UserKnownHostsFile=/etc/pve/nodes/{node_name}/ssh_known_hosts"),
        "-o", "GlobalKnownHostsFile=none",
        "-o", "StrictHostKeyChecking=yes",
    ])
