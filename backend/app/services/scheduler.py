"""Background scheduler for automated VM checks"""
import json
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(daemon=True)
_started = False


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_setting(db, key, default=None):
    from app.models import SystemSettings
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    return row.value if row else default


def _upsert_cache(db, vm_id: int, scan_type: str, result: dict, severity: str, summary: str):
    from app.models import VmScanCache
    cache = (
        db.query(VmScanCache)
        .filter(VmScanCache.vm_id == vm_id, VmScanCache.scan_type == scan_type)
        .first()
    )
    if cache:
        cache.result_json = json.dumps(result)
        cache.scanned_at = datetime.utcnow()
        cache.severity = severity
        cache.summary = summary
    else:
        cache = VmScanCache(
            vm_id=vm_id,
            scan_type=scan_type,
            result_json=json.dumps(result),
            scanned_at=datetime.utcnow(),
            severity=severity,
            summary=summary,
        )
        db.add(cache)
    db.commit()


# ── scheduled jobs ────────────────────────────────────────────────────────────

def run_auto_update_checks():
    """Check for OS updates on all managed VMs that have SSH credentials."""
    from app.core.database import SessionLocal
    from app.models import VirtualMachine
    from app.services.updates import UpdateService

    db = SessionLocal()
    try:
        if _get_setting(db, "auto_update_check_enabled", "false") != "true":
            return

        vms = (
            db.query(VirtualMachine)
            .filter(
                VirtualMachine.ip_address.isnot(None),
                VirtualMachine.password.isnot(None),
            )
            .all()
        )

        service = UpdateService(db)
        for vm in vms:
            try:
                result = service.check_updates(vm.id)
                if result:
                    _upsert_cache(
                        db, vm.id, "updates", result,
                        severity="warning" if result["updates_available"] > 0 else "ok",
                        summary=f"{result['updates_available']} update(s) available",
                    )
                    logger.debug(f"Auto update check VM {vm.id}: {result['updates_available']} updates")
            except Exception as e:
                logger.error(f"Auto update check failed for VM {vm.id}: {e}")

    except Exception as e:
        logger.error(f"Auto update check job error: {e}")
    finally:
        db.close()


def run_auto_security_scans():
    """Run security scans on all managed VMs that have SSH credentials."""
    from app.core.database import SessionLocal
    from app.models import VirtualMachine
    from app.services.updates import UpdateService

    db = SessionLocal()
    try:
        if _get_setting(db, "auto_security_scan_enabled", "false") != "true":
            return

        vms = (
            db.query(VirtualMachine)
            .filter(
                VirtualMachine.ip_address.isnot(None),
                VirtualMachine.password.isnot(None),
            )
            .all()
        )

        service = UpdateService(db)
        for vm in vms:
            try:
                result = service.scan_security(vm.id)
                if "error" not in result:
                    sec = result.get("os_updates", {}).get("security_updates", 0)
                    failed = result.get("failed_ssh_attempts", 0)
                    _upsert_cache(
                        db, vm.id, "security", result,
                        severity=result.get("severity", "ok"),
                        summary=f"{sec} security updates, {failed} failed SSH logins",
                    )
                    logger.debug(f"Auto security scan VM {vm.id}: severity={result.get('severity')}")
            except Exception as e:
                logger.error(f"Auto security scan failed for VM {vm.id}: {e}")

    except Exception as e:
        logger.error(f"Auto security scan job error: {e}")
    finally:
        db.close()


def run_proxmox_node_poll():
    """Poll all active Proxmox hosts to refresh node disk/CPU/RAM stats in the DB."""
    from app.core.database import SessionLocal
    from app.models.database import ProxmoxHost
    from app.services.proxmox import poll_proxmox_resources

    db = SessionLocal()
    try:
        hosts = db.query(ProxmoxHost).filter(ProxmoxHost.is_active == True).all()
        for host in hosts:
            try:
                poll_proxmox_resources(db, host.id)
            except Exception as e:
                logger.error(f"Node poll failed for host {host.name}: {e}")
    except Exception as e:
        logger.error(f"Proxmox node poll job error: {e}")
    finally:
        db.close()


def run_bmc_poll():
    """Poll all configured BMC servers every 2 minutes and update status cache."""
    from app.core.database import SessionLocal
    from app.models.database import ProxmoxHost, PBSServer, StandaloneBMC
    from app.core.security import decrypt_data
    from app.services.idrac import RedfishClient
    from app.api.idrac import bmc_status_cache

    db = SessionLocal()
    try:
        servers = []
        for h in db.query(ProxmoxHost).filter(ProxmoxHost.idrac_hostname.isnot(None)).all():
            servers.append(("pve", h.id, h))
        for s in db.query(PBSServer).filter(PBSServer.idrac_hostname.isnot(None)).all():
            servers.append(("pbs", s.id, s))
        for b in db.query(StandaloneBMC).filter(StandaloneBMC.is_active == True).all():
            servers.append(("standalone", b.id, b))

        for stype, sid, obj in servers:
            key = f"{stype}:{sid}"
            try:
                pw = decrypt_data(obj.idrac_password)
                use_ssh = getattr(obj, "idrac_use_ssh", False)

                if use_ssh:
                    # SSH mode: connect via SSH to the host (not the BMC address)
                    from app.services.ssh_hw import get_hardware_info, test_ssh
                    # PVE hosts SSH to their main hostname; PBS/standalone SSH to idrac_hostname
                    ssh_host = getattr(obj, "hostname", None) or obj.idrac_hostname
                    hw = get_hardware_info(ssh_host, obj.idrac_username, pw)
                    sys_info = hw.get("system", {})
                    bmc_status_cache[key] = {
                        "power_state": "On",
                        "health": "OK",
                        "model": sys_info.get("model", ""),
                        "last_polled": datetime.utcnow().isoformat(),
                        "error": None,
                        "max_temp_c": None,
                        "consumed_watts": None,
                    }
                else:
                    # Redfish / BMC mode
                    client = RedfishClient(
                        hostname=obj.idrac_hostname,
                        username=obj.idrac_username,
                        password=pw,
                        port=obj.idrac_port or 443,
                        bmc_type=obj.idrac_type or "idrac",
                    )
                    info = client.get_system_info()
                    max_temp_c = None
                    consumed_watts = None
                    try:
                        thermal = client.get_thermal()
                        temps = [t.get("reading_celsius") for t in thermal.get("temperatures", []) if t.get("reading_celsius") is not None]
                        if temps:
                            max_temp_c = max(temps)
                    except Exception:
                        pass
                    try:
                        power = client.get_power_usage()
                        consumed_watts = (power.get("power_control") or [{}])[0].get("consumed_watts")
                    except Exception:
                        pass
                    bmc_status_cache[key] = {
                        "power_state": info.get("power_state"),
                        "health": info.get("health"),
                        "model": info.get("model"),
                        "last_polled": datetime.utcnow().isoformat(),
                        "error": None,
                        "max_temp_c": max_temp_c,
                        "consumed_watts": consumed_watts,
                    }
            except Exception as e:
                bmc_status_cache[key] = {
                    "power_state": None,
                    "health": None,
                    "model": None,
                    "last_polled": datetime.utcnow().isoformat(),
                    "error": str(e),
                }
    except Exception as e:
        logger.error(f"BMC poll job error: {e}")
    finally:
        db.close()


# ── public API ────────────────────────────────────────────────────────────────

def start_scheduler(update_hours: int = 24, scan_hours: int = 24):
    """Start the background scheduler (idempotent)."""
    global _started
    if _started:
        return
    _scheduler.add_job(
        run_auto_update_checks,
        IntervalTrigger(hours=update_hours),
        id="auto_update_checks",
        max_instances=1,
    )
    _scheduler.add_job(
        run_auto_security_scans,
        IntervalTrigger(hours=scan_hours),
        id="auto_security_scans",
        max_instances=1,
    )
    _scheduler.add_job(
        run_proxmox_node_poll,
        IntervalTrigger(minutes=5),
        id="proxmox_node_poll",
        max_instances=1,
        next_run_time=datetime.utcnow(),  # run immediately on startup
    )
    _scheduler.add_job(
        run_bmc_poll,
        IntervalTrigger(minutes=2),
        id="bmc_poll",
        max_instances=1,
        next_run_time=datetime.utcnow(),  # run immediately on startup
    )
    _scheduler.start()
    _started = True
    logger.info(f"Scheduler started — update checks every {update_hours}h, security scans every {scan_hours}h, node poll every 5m, BMC poll every 2m")


def reschedule(update_hours: int = 24, scan_hours: int = 24):
    """Replace scheduled jobs with new intervals."""
    if not _started:
        return
    for job_id in ("auto_update_checks", "auto_security_scans"):
        try:
            _scheduler.remove_job(job_id)
        except Exception:
            pass
    _scheduler.add_job(
        run_auto_update_checks,
        IntervalTrigger(hours=update_hours),
        id="auto_update_checks",
        max_instances=1,
    )
    _scheduler.add_job(
        run_auto_security_scans,
        IntervalTrigger(hours=scan_hours),
        id="auto_security_scans",
        max_instances=1,
    )
    logger.info(f"Rescheduled — update checks every {update_hours}h, security scans every {scan_hours}h")
    # bmc_poll is always 2 minutes, no need to reschedule it
