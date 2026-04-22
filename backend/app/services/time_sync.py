"""Time sync audit + remediation for PVE nodes, PBS servers, and iDRAC/BMCs.

Probes each target for:
  - reported wall clock (for drift calculation vs. the deploy host)
  - NTP state (enabled / servers)
  - timezone

Provides a one-shot fix that enables NTP and optionally writes a server override.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.security import decrypt_data
from app.models.database import (
    ProxmoxHost,
    ProxmoxNode,
    PBSServer,
    StandaloneBMC,
    SystemSettings,
)

logger = logging.getLogger(__name__)


DEFAULT_NTP_SERVER = "pool.ntp.org"
DEFAULT_DRIFT_THRESHOLD_SECONDS = 300


# ── data model ──────────────────────────────────────────────────────────────

@dataclass
class TimeTarget:
    kind: str
    id: int
    label: str
    address: str
    reported_time_utc: Optional[str] = None
    deploy_time_utc: Optional[str] = None
    drift_seconds: Optional[float] = None
    ntp_enabled: Optional[bool] = None
    ntp_servers: Optional[List[str]] = None
    timezone: Optional[str] = None
    error: Optional[str] = None
    # Extras for UI
    sub_kind: Optional[str] = None  # e.g. "pve_host"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── helpers ─────────────────────────────────────────────────────────────────

def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _now_epoch() -> float:
    return time.time()


def _safe_decrypt(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    try:
        return decrypt_data(val)
    except Exception:
        return val


def _strip_realm(username: Optional[str]) -> Optional[str]:
    """Strip @pam / @pve / etc. from a PVE/PBS username for SSH use."""
    if not username:
        return None
    return username.split("@", 1)[0]


def get_setting(db: Session, key: str, default: str) -> str:
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    return row.value if row and row.value is not None else default


def set_setting(db: Session, key: str, value: str, description: Optional[str] = None) -> None:
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if row:
        row.value = value
        if description and not row.description:
            row.description = description
    else:
        row = SystemSettings(key=key, value=value, description=description or "")
        db.add(row)
    db.commit()


def _parse_timedatectl(raw: str) -> Dict[str, Any]:
    """Parse `timedatectl status` output into a dict.

    Returns keys: ntp_enabled (bool|None), ntp_active (bool|None), timezone, time_epoch (int|None).
    """
    out: Dict[str, Any] = {
        "ntp_enabled": None,
        "ntp_active": None,
        "timezone": None,
    }
    for line in raw.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip().lower()
        v = v.strip()
        if k in ("ntp service", "network time on", "systemd-timesyncd.service active"):
            if v.lower() in ("active", "yes", "true", "running"):
                out["ntp_active"] = True
            elif v.lower() in ("inactive", "no", "false", "not started", "stopped", "n/a"):
                out["ntp_active"] = False
        elif k in ("ntp enabled", "ntp synchronized", "system clock synchronized"):
            # "NTP enabled: yes/no" (older) or "System clock synchronized: yes"
            if v.lower() in ("yes", "true", "active"):
                out["ntp_enabled"] = True
            elif v.lower() in ("no", "false", "inactive"):
                # Only set to False if we haven't seen an explicit True elsewhere
                if out["ntp_enabled"] is None:
                    out["ntp_enabled"] = False
        elif k == "time zone":
            # "Time zone: America/New_York (EDT, -0400)"
            out["timezone"] = v.split(" ")[0]
    return out


_BAD_SRV_TOKENS = ("error", "invalid", "command", "cmdstat", "status_tag", "unrecognized")


def _looks_like_hostname(s: str) -> bool:
    """True if s is plausibly a hostname/IP (not a CLI error echo)."""
    if not s or len(s) > 253:
        return False
    low = s.lower()
    if any(t in low for t in _BAD_SRV_TOKENS):
        return False
    # Must contain at least one letter or digit, and only valid hostname chars
    return bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9.\-_:]*$", s))


def _parse_chrony_sources(raw: str) -> List[str]:
    """Extract server names from `chronyc sources` output."""
    servers: List[str] = []
    # Lines start with ^* ^+ ^- ^? — the second column is the source name
    for line in raw.splitlines():
        line = line.strip()
        if not line or not line.startswith(("^", "#")):
            continue
        parts = line.split()
        if len(parts) >= 2:
            src = parts[1]
            if _looks_like_hostname(src) and src not in servers:
                servers.append(src)
    return servers


def _parse_chronyc_tracking(raw: str) -> Optional[str]:
    """Return the reference name from `chronyc tracking` if present."""
    for line in raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            if k.strip().lower() == "reference id":
                # "Reference ID    : 0A010101 (ntp1.example.com)"
                m = re.search(r"\(([^)]+)\)", v)
                if m:
                    return m.group(1).strip()
    return None


def _ssh_collect_host_time(hostname: str, username: str, password: str, port: int = 22) -> Dict[str, Any]:
    """Run the time/NTP probe commands over SSH. Raises on connection failure."""
    from app.services.ssh_hw import get_ssh_client

    client = get_ssh_client(hostname, username, password, port)
    try:
        cmds = {
            "epoch": "date +%s",
            "iso": "date -u +%Y-%m-%dT%H:%M:%SZ",
            "tdctl": "timedatectl status 2>/dev/null || true",
            "chrony_sources": "chronyc sources 2>/dev/null || true",
            "chrony_tracking": "chronyc tracking 2>/dev/null || true",
            "chrony_conf_servers": (
                "cat /etc/chrony/chrony.conf /etc/chrony.conf /etc/chrony/conf.d/*.conf 2>/dev/null "
                "| grep -E '^\\s*(server|pool)\\s+' | awk '{print $2}' | sort -u"
            ),
            "timesyncd_servers": (
                "cat /etc/systemd/timesyncd.conf 2>/dev/null | grep -E '^\\s*NTP=' "
                "| sed 's/NTP=//'"
            ),
        }
        results: Dict[str, str] = {}
        for k, cmd in cmds.items():
            try:
                _, stdout, _ = client.exec_command(cmd, timeout=15)
                results[k] = stdout.read().decode("utf-8", errors="replace").strip()
            except Exception as e:
                logger.debug("ssh time probe %s failed on %s: %s", k, hostname, e)
                results[k] = ""

        tdctl = _parse_timedatectl(results.get("tdctl", ""))

        # Figure out NTP enabled — prefer explicit status, fall back to timesyncd/chrony active
        ntp_enabled = tdctl["ntp_enabled"]
        if ntp_enabled is None and tdctl["ntp_active"] is not None:
            ntp_enabled = tdctl["ntp_active"]

        # Gather server list
        chrony_servers = _parse_chrony_sources(results.get("chrony_sources", ""))
        # Fall back to configured server lines if chronyc didn't produce anything
        if not chrony_servers:
            conf = results.get("chrony_conf_servers", "").strip().splitlines()
            chrony_servers = [s.strip() for s in conf if _looks_like_hostname(s.strip())]
        if not chrony_servers:
            ts = results.get("timesyncd_servers", "").strip()
            if ts:
                chrony_servers = [s for s in ts.split() if _looks_like_hostname(s)]

        # Reported wall clock
        reported_iso = results.get("iso", "").strip()
        if reported_iso:
            # normalise to +00:00 offset
            reported_iso = reported_iso.replace("Z", "+00:00")
        try:
            reported_epoch = int(results.get("epoch", "0") or "0")
        except ValueError:
            reported_epoch = 0

        # If we got no Linux-style output at all (likely iDRAC SSH CLI), bail
        is_unix_shell = reported_epoch > 1000000000  # any date >= 2001 means bash+date
        if not is_unix_shell:
            return {
                "reported_iso": None,
                "reported_epoch": None,
                "ntp_enabled": None,
                "ntp_servers": None,
                "timezone": None,
                "not_unix_shell": True,
            }

        return {
            "reported_iso": reported_iso or None,
            "reported_epoch": reported_epoch or None,
            "ntp_enabled": ntp_enabled,
            "ntp_servers": chrony_servers or None,
            "timezone": tdctl.get("timezone"),
        }
    finally:
        try:
            client.close()
        except Exception:
            pass


def _epoch_to_iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(microsecond=0).isoformat()


# ── collectors per target kind ──────────────────────────────────────────────

def _collect_pve_node(db: Session, node: ProxmoxNode, host: ProxmoxHost) -> TimeTarget:
    label = node.node_name or f"node-{node.id}"
    address = node.idrac_hostname or host.hostname or ""
    deploy_epoch = _now_epoch()
    tgt = TimeTarget(
        kind="pve_node",
        id=node.id,
        label=label,
        address=address,
        deploy_time_utc=_epoch_to_iso(deploy_epoch),
    )

    # Step 1: use the Proxmox API to get the node's wall clock (authoritative, doesn't need SSH)
    try:
        from app.services.proxmox import ProxmoxService
        svc = ProxmoxService(host)
        t = svc.proxmox.nodes(node.node_name).time.get()
        # PVE returns {'time', 'timezone', 'localtime'} — all integers
        node_epoch = int(t.get("time") or 0)
        tgt.timezone = t.get("timezone")
        if node_epoch:
            tgt.reported_time_utc = _epoch_to_iso(node_epoch)
            tgt.drift_seconds = float(node_epoch - deploy_epoch)
    except Exception as e:
        tgt.error = f"Proxmox API time query failed: {e}"

    # Step 2: if SSH creds exist (idrac_use_ssh + idrac_*), gather NTP state. Otherwise leave unknown.
    if getattr(node, "idrac_use_ssh", False) and node.idrac_hostname and node.idrac_username and node.idrac_password:
        pw = _safe_decrypt(node.idrac_password)
        try:
            ssh = _ssh_collect_host_time(node.idrac_hostname, node.idrac_username, pw)
            if ssh.get("not_unix_shell"):
                # SSH succeeded but target is not a Linux shell (probably iDRAC CLI).
                # Leave NTP state unknown and note that remediation requires OS SSH.
                pass
            else:
                tgt.ntp_enabled = ssh.get("ntp_enabled")
                tgt.ntp_servers = ssh.get("ntp_servers")
                if not tgt.timezone:
                    tgt.timezone = ssh.get("timezone")
                # Prefer SSH wall clock if the PVE API query failed
                if tgt.reported_time_utc is None and ssh.get("reported_epoch"):
                    tgt.reported_time_utc = _epoch_to_iso(ssh["reported_epoch"])
                    tgt.drift_seconds = float(ssh["reported_epoch"] - deploy_epoch)
                tgt.error = None
        except Exception as e:
            # Keep any earlier error so the UI can show something
            extra = f"SSH probe failed: {e}"
            tgt.error = f"{tgt.error}; {extra}" if tgt.error else extra
    # if ssh not available, ntp_enabled stays None
    return tgt


def _collect_pbs(pbs: PBSServer) -> TimeTarget:
    label = pbs.name or pbs.hostname
    address = pbs.hostname
    deploy_epoch = _now_epoch()
    tgt = TimeTarget(
        kind="pbs",
        id=pbs.id,
        label=label,
        address=address,
        deploy_time_utc=_epoch_to_iso(deploy_epoch),
    )

    # PBS only reliably exposes time via SSH. Use its username/password.
    if not pbs.password or not pbs.username:
        tgt.error = "PBS SSH requires username + password (not an API token)"
        return tgt

    pw = _safe_decrypt(pbs.password)
    ssh_user = _strip_realm(pbs.username)
    try:
        ssh = _ssh_collect_host_time(pbs.hostname, ssh_user, pw)
        tgt.ntp_enabled = ssh.get("ntp_enabled")
        tgt.ntp_servers = ssh.get("ntp_servers")
        tgt.timezone = ssh.get("timezone")
        if ssh.get("reported_epoch"):
            tgt.reported_time_utc = _epoch_to_iso(ssh["reported_epoch"])
            tgt.drift_seconds = float(ssh["reported_epoch"] - deploy_epoch)
    except Exception as e:
        tgt.error = f"SSH probe failed: {e}"
    return tgt


def _collect_bmc(kind: str, sid: int, label: str, address: str, username: str,
                 password_encrypted: str, port: int, bmc_type: str) -> TimeTarget:
    deploy_epoch = _now_epoch()
    tgt = TimeTarget(
        kind=kind,
        id=sid,
        label=label,
        address=address,
        deploy_time_utc=_epoch_to_iso(deploy_epoch),
    )
    pw = _safe_decrypt(password_encrypted)
    if not (address and username and pw):
        tgt.error = "BMC credentials not configured"
        return tgt

    try:
        from app.services.idrac import RedfishClient
        client = RedfishClient(
            hostname=address,
            username=username,
            password=pw,
            port=port or 443,
            bmc_type=bmc_type or "idrac",
            timeout=15,
        )

        # DateTime + offset live on the Manager endpoint
        try:
            mgr = client._get(client.paths["manager"])
            dt_str = mgr.get("DateTime") or ""
            offset = mgr.get("DateTimeLocalOffset") or ""
            if dt_str:
                # Parse ISO 8601 with offset — fromisoformat handles "2024-01-01T12:00:00+00:00"
                try:
                    parsed = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    bmc_epoch = parsed.timestamp()
                    tgt.reported_time_utc = parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()
                    tgt.drift_seconds = float(bmc_epoch - deploy_epoch)
                except Exception:
                    tgt.reported_time_utc = dt_str
            if offset:
                tgt.timezone = offset
        except Exception as e:
            tgt.error = f"Manager endpoint read failed: {e}"

        # Dell iDRAC NTP config is under Attributes
        if (bmc_type or "idrac") == "idrac":
            try:
                attr_wrap = client._get(client.paths["manager"] + "/Attributes")
                attrs = attr_wrap.get("Attributes", attr_wrap) or {}
                enable = attrs.get("NTPConfigGroup.1.NTPEnable")
                if enable is not None:
                    tgt.ntp_enabled = str(enable).lower() in ("enabled", "true", "1")
                servers: List[str] = []
                for key in ("NTPConfigGroup.1.NTP1", "NTPConfigGroup.1.NTP2", "NTPConfigGroup.1.NTP3"):
                    val = attrs.get(key)
                    if val and str(val).strip():
                        servers.append(str(val).strip())
                if servers:
                    tgt.ntp_servers = servers
            except Exception as e:
                # Keep the read error as a sub-note but don't overwrite a full error
                logger.debug("BMC NTP attribute read failed for %s: %s", address, e)
    except Exception as e:
        tgt.error = f"Redfish connect failed: {e}"
    return tgt


# ── public collection ────────────────────────────────────────────────────────

def collect_all(db: Session) -> List[TimeTarget]:
    """Probe every configured PVE node, PBS server, and BMC in parallel."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    jobs: List[Any] = []  # list of (callable,) tuples

    # Build one closure per target so each runs against stable captured values.
    # ORM objects are detached before passing into workers to avoid session
    # contention across threads.
    nodes = db.query(ProxmoxNode).all()
    host_by_id: Dict[int, ProxmoxHost] = {
        h.id: h for h in db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()  # noqa: E712
    }

    def _pve_node_job(node, host):
        def _run():
            try:
                return _collect_pve_node(db, node, host)
            except Exception as e:
                return TimeTarget(
                    kind="pve_node", id=node.id,
                    label=node.node_name or f"node-{node.id}",
                    address=host.hostname if host else "",
                    error=str(e), deploy_time_utc=_now_utc_iso(),
                )
        return _run

    for node in nodes:
        host = host_by_id.get(node.host_id)
        if not host:
            continue
        jobs.append(_pve_node_job(node, host))

    # PBS servers (time via SSH)
    for pbs in db.query(PBSServer).filter(PBSServer.is_active == True).all():  # noqa: E712
        def _pbs_job(pbs=pbs):
            try:
                return _collect_pbs(pbs)
            except Exception as e:
                return TimeTarget(
                    kind="pbs", id=pbs.id, label=pbs.name, address=pbs.hostname,
                    error=str(e), deploy_time_utc=_now_utc_iso(),
                )
        jobs.append(_pbs_job)

    # iDRACs: per-node
    for node in db.query(ProxmoxNode).filter(ProxmoxNode.idrac_hostname.isnot(None)).all():
        def _bmc_node_job(node=node):
            try:
                return _collect_bmc(
                    kind="bmc_node", sid=node.id,
                    label=f"{node.node_name} iDRAC",
                    address=node.idrac_hostname,
                    username=node.idrac_username or "",
                    password_encrypted=node.idrac_password or "",
                    port=node.idrac_port or 443,
                    bmc_type=node.idrac_type or "idrac",
                )
            except Exception as e:
                return TimeTarget(
                    kind="bmc_node", id=node.id,
                    label=f"{node.node_name} iDRAC",
                    address=node.idrac_hostname or "",
                    error=str(e), deploy_time_utc=_now_utc_iso(),
                )
        jobs.append(_bmc_node_job)

    # iDRACs: per-PBS
    for pbs in db.query(PBSServer).filter(PBSServer.idrac_hostname.isnot(None)).all():
        def _bmc_pbs_job(pbs=pbs):
            try:
                return _collect_bmc(
                    kind="bmc_pbs", sid=pbs.id,
                    label=f"{pbs.name} iDRAC",
                    address=pbs.idrac_hostname,
                    username=pbs.idrac_username or "",
                    password_encrypted=pbs.idrac_password or "",
                    port=pbs.idrac_port or 443,
                    bmc_type=pbs.idrac_type or "idrac",
                )
            except Exception as e:
                return TimeTarget(
                    kind="bmc_pbs", id=pbs.id,
                    label=f"{pbs.name} iDRAC",
                    address=pbs.idrac_hostname or "",
                    error=str(e), deploy_time_utc=_now_utc_iso(),
                )
        jobs.append(_bmc_pbs_job)

    # Standalone BMCs
    for b in db.query(StandaloneBMC).filter(StandaloneBMC.is_active == True).all():  # noqa: E712
        def _bmc_standalone_job(b=b):
            try:
                return _collect_bmc(
                    kind="bmc_standalone", sid=b.id,
                    label=b.name,
                    address=b.idrac_hostname,
                    username=b.idrac_username or "",
                    password_encrypted=b.idrac_password or "",
                    port=b.idrac_port or 443,
                    bmc_type=b.idrac_type or "idrac",
                )
            except Exception as e:
                return TimeTarget(
                    kind="bmc_standalone", id=b.id,
                    label=b.name, address=b.idrac_hostname or "",
                    error=str(e), deploy_time_utc=_now_utc_iso(),
                )
        jobs.append(_bmc_standalone_job)

    if not jobs:
        return []

    targets: List[TimeTarget] = []
    # Cap parallelism so we don't exhaust SSH/BMC limits or sockets.
    with ThreadPoolExecutor(max_workers=min(12, len(jobs))) as pool:
        futures = [pool.submit(fn) for fn in jobs]
        for fut in as_completed(futures):
            try:
                targets.append(fut.result())
            except Exception as e:
                logger.warning("time_sync collect job failed: %s", e)

    # Sort stably: by kind then label
    targets.sort(key=lambda t: (t.kind, t.label.lower()))
    return targets


# ── remediation ─────────────────────────────────────────────────────────────

def _ssh_enable_ntp(hostname: str, username: str, password: str,
                    ntp_server: Optional[str]) -> List[str]:
    """Enable systemd NTP + restart chrony/timesyncd. Optionally append a server override.
    Returns list of action log strings.
    """
    from app.services.ssh_hw import get_ssh_client

    actions: List[str] = []
    client = get_ssh_client(hostname, username, password)
    try:
        def _run(cmd: str, label: str) -> str:
            try:
                _, stdout, stderr = client.exec_command(cmd, timeout=30)
                out = stdout.read().decode("utf-8", errors="replace").strip()
                err = stderr.read().decode("utf-8", errors="replace").strip()
                rc = stdout.channel.recv_exit_status()
                actions.append(f"{label} (rc={rc}): {out or err or 'ok'}"[:400])
                return out
            except Exception as e:
                actions.append(f"{label} errored: {e}")
                return ""

        _run("timedatectl set-ntp true", "timedatectl set-ntp true")
        # Restart the daemon that actually runs — try chrony first, then systemd-timesyncd
        _run(
            "systemctl restart chrony 2>/dev/null "
            "|| systemctl restart chronyd 2>/dev/null "
            "|| systemctl restart systemd-timesyncd 2>/dev/null",
            "restart ntp daemon",
        )

        if ntp_server and ntp_server.strip() and ntp_server.strip() != DEFAULT_NTP_SERVER:
            safe_server = re.sub(r"[^A-Za-z0-9.\-:_]", "", ntp_server.strip())
            if safe_server:
                drop_in = (
                    f"mkdir -p /etc/chrony/conf.d && "
                    f"echo 'server {safe_server} iburst' > /etc/chrony/conf.d/depl0y-ntp.conf && "
                    f"systemctl restart chrony 2>/dev/null "
                    f"|| systemctl restart chronyd 2>/dev/null "
                    f"|| (mkdir -p /etc/systemd/timesyncd.conf.d && "
                    f"echo -e '[Time]\\nNTP={safe_server}' > /etc/systemd/timesyncd.conf.d/depl0y-ntp.conf && "
                    f"systemctl restart systemd-timesyncd)"
                )
                _run(drop_in, f"write override for {safe_server}")

        # Step the clock immediately if chrony is active
        _run("chronyc -a makestep 2>/dev/null || true", "chronyc makestep")
    finally:
        try:
            client.close()
        except Exception:
            pass
    return actions


def _bmc_enable_ntp(kind: str, obj: Any, ntp_server: str) -> List[str]:
    """Configure NTP on a Dell iDRAC via Redfish Attributes PATCH."""
    from app.services.idrac import RedfishClient

    actions: List[str] = []
    pw = _safe_decrypt(obj.idrac_password)
    client = RedfishClient(
        hostname=obj.idrac_hostname,
        username=obj.idrac_username,
        password=pw,
        port=obj.idrac_port or 443,
        bmc_type=obj.idrac_type or "idrac",
        timeout=20,
    )
    body = {
        "Attributes": {
            "NTPConfigGroup.1.NTPEnable": "Enabled",
            "NTPConfigGroup.1.NTP1": ntp_server,
        }
    }
    try:
        client._patch(client.paths["manager"] + "/Attributes", body)
        actions.append(f"PATCH iDRAC Attributes NTPEnable=Enabled NTP1={ntp_server}")
    except Exception as e:
        actions.append(f"PATCH iDRAC Attributes failed: {e}")
        raise
    return actions


def fix_target(db: Session, kind: str, target_id: int,
               ntp_server: Optional[str] = None) -> Dict[str, Any]:
    """Apply the NTP remediation for a single target. Returns a result dict."""
    ntp_server = (ntp_server or DEFAULT_NTP_SERVER).strip() or DEFAULT_NTP_SERVER
    result: Dict[str, Any] = {
        "kind": kind,
        "id": target_id,
        "status": "error",
        "actions": [],
        "target": None,
        "error": None,
    }

    try:
        if kind == "pve_node":
            node = db.query(ProxmoxNode).filter(ProxmoxNode.id == target_id).first()
            if not node:
                raise ValueError("PVE node not found")
            if not (getattr(node, "idrac_use_ssh", False) and node.idrac_hostname
                    and node.idrac_username and node.idrac_password):
                raise ValueError(
                    "This node has no SSH credentials (set idrac_use_ssh + SSH creds "
                    "on the node to enable remediation)"
                )
            pw = _safe_decrypt(node.idrac_password)
            actions = _ssh_enable_ntp(node.idrac_hostname, node.idrac_username, pw, ntp_server)
            result.update(status="ok", actions=actions, target=node.node_name)

        elif kind == "pbs":
            pbs = db.query(PBSServer).filter(PBSServer.id == target_id).first()
            if not pbs:
                raise ValueError("PBS server not found")
            if not (pbs.password and pbs.username):
                raise ValueError("PBS SSH requires username + password")
            pw = _safe_decrypt(pbs.password)
            user = _strip_realm(pbs.username)
            actions = _ssh_enable_ntp(pbs.hostname, user, pw, ntp_server)
            result.update(status="ok", actions=actions, target=pbs.name)

        elif kind == "bmc_node":
            node = db.query(ProxmoxNode).filter(ProxmoxNode.id == target_id).first()
            if not node or not node.idrac_hostname:
                raise ValueError("BMC node not found")
            actions = _bmc_enable_ntp(kind, node, ntp_server)
            result.update(status="ok", actions=actions, target=f"{node.node_name} iDRAC")

        elif kind == "bmc_pbs":
            pbs = db.query(PBSServer).filter(PBSServer.id == target_id).first()
            if not pbs or not pbs.idrac_hostname:
                raise ValueError("PBS BMC not found")
            actions = _bmc_enable_ntp(kind, pbs, ntp_server)
            result.update(status="ok", actions=actions, target=f"{pbs.name} iDRAC")

        elif kind == "bmc_standalone":
            b = db.query(StandaloneBMC).filter(StandaloneBMC.id == target_id).first()
            if not b:
                raise ValueError("Standalone BMC not found")
            actions = _bmc_enable_ntp(kind, b, ntp_server)
            result.update(status="ok", actions=actions, target=b.name)

        else:
            raise ValueError(f"Unknown target kind '{kind}'")
    except Exception as e:
        result["error"] = str(e)
        logger.warning("fix_target(%s/%s) failed: %s", kind, target_id, e)
    return result


# ── drift alerting job ──────────────────────────────────────────────────────

def check_drift_and_alert(db: Session, threshold_seconds: Optional[int] = None) -> Dict[str, int]:
    """Scheduled job — collect all targets, fire alerts on drift or disabled NTP.
    Auto-acks prior alerts when the problem clears.
    """
    from app.services.alert_engine import alert_engine
    from app.models.alert_models import AlertEvent
    from sqlalchemy import and_

    if threshold_seconds is None:
        try:
            threshold_seconds = int(get_setting(
                db, "time_sync.drift_threshold_seconds", str(DEFAULT_DRIFT_THRESHOLD_SECONDS),
            ))
        except (TypeError, ValueError):
            threshold_seconds = DEFAULT_DRIFT_THRESHOLD_SECONDS

    summary = {"total": 0, "drifting": 0, "ntp_off": 0, "alerts": 0, "resolved": 0}
    targets = collect_all(db)
    summary["total"] = len(targets)

    for t in targets:
        is_drifting = (
            t.drift_seconds is not None
            and abs(t.drift_seconds) > threshold_seconds
        )
        is_ntp_off = t.ntp_enabled is False
        rule_key = f"time_sync:{t.kind}:{t.id}"

        if is_drifting or is_ntp_off:
            title = f"Time drift on {t.label}" if is_drifting else f"NTP disabled on {t.label}"
            drift_str = f"{t.drift_seconds:+.1f}s" if t.drift_seconds is not None else "unknown"
            parts = [f"Target: {t.label} ({t.address})", f"Kind: {t.kind}"]
            if is_drifting:
                parts.append(f"Drift: {drift_str} (threshold {threshold_seconds}s)")
                summary["drifting"] += 1
            if is_ntp_off:
                parts.append("NTP is disabled")
                summary["ntp_off"] += 1
            msg = " | ".join(parts)
            severity = "warning" if is_ntp_off and not is_drifting else "critical" if is_drifting and abs(t.drift_seconds or 0) > 3600 else "warning"
            alert_engine._fire_builtin(
                db, rule_key, severity, title, msg,
                cooldown_minutes=60, action_url="/time-sync",
            )
            summary["alerts"] += 1
        else:
            # Auto-ack any open alert for this target
            try:
                open_evts = db.query(AlertEvent).filter(
                    and_(AlertEvent.rule_key == rule_key, AlertEvent.acknowledged == False)  # noqa: E712
                ).all()
                if open_evts:
                    now = datetime.utcnow()
                    for e in open_evts:
                        e.acknowledged = True
                        e.acknowledged_at = now
                    db.commit()
                    summary["resolved"] += len(open_evts)
            except Exception:
                db.rollback()

    return summary
