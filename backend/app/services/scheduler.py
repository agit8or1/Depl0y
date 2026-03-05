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
    _scheduler.start()
    _started = True
    logger.info(f"Scheduler started — update checks every {update_hours}h, security scans every {scan_hours}h")


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
