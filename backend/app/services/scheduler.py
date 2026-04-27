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
    from app.models.database import ProxmoxHost, PBSServer, StandaloneBMC, ProxmoxNode
    from app.core.security import decrypt_data
    from app.services.idrac import RedfishClient, lookup_dell_model_from_pci
    from app.api.idrac import bmc_status_cache

    db = SessionLocal()
    try:
        servers = []
        # `.isnot(None)` only excludes SQL NULL — empty strings sneak through.
        # Filter both NULL and "" so VMs / placeholders aren't polled.
        _has_idrac = lambda col: col.isnot(None) & (col != "")
        for h in db.query(ProxmoxHost).filter(_has_idrac(ProxmoxHost.idrac_hostname)).all():
            servers.append(("pve", h.id, h))
        for s in db.query(PBSServer).filter(_has_idrac(PBSServer.idrac_hostname)).all():
            servers.append(("pbs", s.id, s))
        for b in db.query(StandaloneBMC).filter(StandaloneBMC.is_active == True).all():
            servers.append(("standalone", b.id, b))
        for n in db.query(ProxmoxNode).filter(_has_idrac(ProxmoxNode.idrac_hostname)).all():
            servers.append(("pve_node", n.id, n))

        # Drop cache entries that no longer correspond to a configured BMC
        # (e.g. PBS rows whose iDRAC was cleared because the box is a VM).
        valid_keys = {f"{stype}:{sid}" for stype, sid, _ in servers}
        for stale in [k for k in bmc_status_cache if k not in valid_keys]:
            bmc_status_cache.pop(stale, None)

        # Expunge ORM objects so they're safe to pass into worker threads.
        # Each worker creates its own DB session for PCI-lookup queries.
        for _, _, _obj in servers:
            db.expunge(_obj)

        from concurrent.futures import ThreadPoolExecutor

        def _poll_one(stype, sid, obj):
            key = f"{stype}:{sid}"
            try:
                pw = decrypt_data(obj.idrac_password)
                use_ssh = getattr(obj, "idrac_use_ssh", False)
                has_ssh_creds = bool(obj.idrac_username and pw)

                rf_info = None
                max_temp_c = None
                consumed_watts = None
                power_state = None
                health = None
                model = None
                serial_number = None
                idrac_fw_version = None
                bios_version = None
                dell_system_id = None

                # ── Routing logic ──────────────────────────────────────────
                # One IP per BMC: idrac_hostname is the BMC. Always try both
                # Redfish (HTTPS) and SSH against it — whichever the device
                # supports fills in its piece. Results are merged, never
                # exclusive.
                try_redfish = bool(obj.idrac_hostname)
                try_ssh = bool(obj.idrac_hostname) and has_ssh_creds

                # ── Try Redfish (HTTPS) ────────────────────────────────────
                if try_redfish:
                    try:
                        client = RedfishClient(
                            hostname=obj.idrac_hostname,
                            username=obj.idrac_username,
                            password=pw,
                            port=obj.idrac_port or 443,
                            bmc_type=obj.idrac_type or "idrac",
                        )
                        rf_info = client.get_system_info()
                        power_state = rf_info.get("power_state")
                        # Prefer component-level current health over the SEL-aware
                        # rollup so stale event-log entries don't keep us at Warning
                        # after a hardware condition has cleared.
                        health_reasons = []
                        try:
                            cur = client.compute_current_health()
                            health = cur.get("health") or rf_info.get("health")
                            health_reasons = cur.get("reasons") or []
                        except Exception:
                            health = rf_info.get("health")
                        model = rf_info.get("model")
                        serial_number = rf_info.get("serial_number")
                        bios_version = rf_info.get("bios_version") or None
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
                        try:
                            mgr = client.get_manager_info()
                            idrac_fw_version = mgr.get("firmware_version")
                        except Exception:
                            pass
                        try:
                            dell_system_id = client.get_dell_system_id()
                        except Exception:
                            pass
                    except Exception:
                        pass  # Redfish unavailable

                # ── Try OS SSH ──────────────────────────────────────────────
                # PBS: SSH is the only source (no BMC/Redfish)
                # pve_node/pve/standalone with use_ssh: run alongside Redfish,
                # filling in any values Redfish didn't provide
                if try_ssh:
                    try:
                        from app.services.ssh_hw import get_hardware_info
                        hw = get_hardware_info(obj.idrac_hostname, obj.idrac_username, pw)
                        sys_info = hw.get("system", {})
                        if power_state is None:
                            power_state = "On"
                        if health is None:
                            health = "OK"
                        if model is None:
                            model = sys_info.get("model", "")
                        if serial_number is None:
                            serial_number = sys_info.get("serial", "")
                        if idrac_fw_version is None:
                            bv = sys_info.get("bios_version", "")
                            bd = sys_info.get("bios_date", "")
                            if bv:
                                idrac_fw_version = f"BIOS {bv}" + (f" ({bd})" if bd else "")
                        if max_temp_c is None:
                            max_temp_c = hw.get("max_temp_c")
                        if consumed_watts is None:
                            consumed_watts = hw.get("consumed_watts")
                    except Exception as ssh_e:
                        logger.warning(f"OS SSH failed for {stype}:{sid} ({obj.idrac_hostname}): {ssh_e}")

                if power_state is None and health is None:
                    raise RuntimeError("No Redfish or SSH data could be collected")

                # ── PCI subsystem lookup for generic/blank Dell model ───────
                # When Redfish returns blank or "Dell PowerEdge (NNG)" (13G/12G iDRAC),
                # query the Proxmox PCI device list and match the Dell subsystem ID.
                # Apply PCI lookup for both pve (host) and pve_node entries —
                # depl0y can poll the cluster for either, and we want the same
                # model-resolution fallback in both paths.
                if stype in ("pve_node", "pve") and (not model or model.startswith("Dell PowerEdge (")):
                    _pci_db = SessionLocal()
                    try:
                        from proxmoxer import ProxmoxAPI
                        from app.core.security import decrypt_data as _dec
                        from app.models.database import ProxmoxNode
                        if stype == "pve_node":
                            node_name = getattr(obj, "node_name", None)
                            host = _pci_db.query(ProxmoxHost).filter_by(id=obj.host_id).first()
                        else:
                            host = obj
                            n = _pci_db.query(ProxmoxNode).filter_by(host_id=obj.id).order_by(ProxmoxNode.id).first()
                            node_name = n.node_name if n else None
                        if node_name and host:
                            # Parse token user + name from api_token_id (e.g. "root@pam!depl0y")
                            _api_token_id = host.api_token_id or ""
                            if "!" in _api_token_id:
                                _token_user, _token_name = _api_token_id.split("!", 1)
                            else:
                                _token_user = host.username or "root@pam"
                                _token_name = _api_token_id or "depl0y"
                            try:
                                _token_secret = _dec(host.api_token_secret) if host.api_token_secret else None
                            except Exception:
                                _token_secret = host.api_token_secret
                            px = ProxmoxAPI(
                                host.hostname,
                                user=_token_user,
                                token_name=_token_name,
                                token_value=_token_secret,
                                verify_ssl=False,
                            )
                            pci_list = px.nodes(node_name).hardware.pci.get()
                            dell_subsys_seen = []
                            for dev in pci_list:
                                if dev.get("subsystem_vendor") == "0x1028":  # Dell
                                    sub_dev = dev.get("subsystem_device", "")
                                    if sub_dev:
                                        dell_subsys_seen.append(sub_dev)
                                    found = lookup_dell_model_from_pci(sub_dev)
                                    if found:
                                        model = found
                                        if not dell_system_id and sub_dev:
                                            try:
                                                dell_system_id = hex(int(sub_dev, 16))
                                            except Exception:
                                                pass
                                        break
                            if (not model or model.startswith("Dell PowerEdge (")) and dell_subsys_seen:
                                # We saw Dell PCI devices but none matched our table —
                                # log the IDs so we can extend `_DELL_PCI_SUBSYS_MODEL`.
                                logger.info(
                                    "BMC %s: Dell PCI subsys IDs %s not in lookup; model stays as %r",
                                    key, sorted(set(dell_subsys_seen)), model,
                                )
                    except Exception as exc:
                        logger.debug("PCI model lookup failed for %s: %s", key, exc)
                    finally:
                        _pci_db.close()

                # Manual model override — iDRAC 7 / older BMCs don't expose
                # Model via Redfish at all. The admin can store an override in
                # `system_settings` under the key `model_override:<key>` (e.g.
                # `model_override:pve_node:1`), and we apply it as the highest-
                # priority model source. Auto-detected value is preserved as
                # `auto_model` so the UI can still show what Redfish reports.
                auto_model = model
                try:
                    from app.models.database import SystemSettings
                    _ov_db = SessionLocal()
                    try:
                        ov_row = _ov_db.query(SystemSettings).filter(
                            SystemSettings.key == f"model_override:{key}"
                        ).first()
                        if ov_row and (ov_row.value or "").strip():
                            model = ov_row.value.strip()
                    finally:
                        _ov_db.close()
                except Exception as exc:
                    logger.debug("model override lookup failed for %s: %s", key, exc)

                # Preserve existing firmware_updates if already checked
                prev = bmc_status_cache.get(key, {})
                bmc_status_cache[key] = {
                    "power_state": power_state,
                    "health": health,
                    "model": model,
                    "auto_model": auto_model,
                    "serial_number": serial_number,
                    "idrac_fw_version": idrac_fw_version,
                    "bios_version": bios_version,
                    "dell_system_id": dell_system_id or prev.get("dell_system_id"),
                    "last_polled": datetime.utcnow().isoformat(),
                    "error": None,
                    "max_temp_c": max_temp_c,
                    "consumed_watts": consumed_watts,
                    "firmware_updates": prev.get("firmware_updates"),
                    "health_reasons": health_reasons,
                }
            except Exception as e:
                bmc_status_cache[key] = {
                    "power_state": None,
                    "health": None,
                    "model": None,
                    "last_polled": datetime.utcnow().isoformat(),
                    "error": str(e),
                }

        # Poll all servers in parallel — a slow/unreachable BMC no longer
        # blocks the rest of the cycle.
        if servers:
            with ThreadPoolExecutor(max_workers=min(10, len(servers))) as pool:
                list(pool.map(lambda args: _poll_one(*args), servers))
    except Exception as e:
        logger.error(f"BMC poll job error: {e}")
    finally:
        db.close()


def run_node_metric_snapshot():
    """Every 5 min: capture a NodeMetricSnapshot row for each known node.
    Prunes snapshots older than 30 days.
    """
    from datetime import timedelta
    from app.core.database import SessionLocal
    from app.models.database import ProxmoxNode, NodeMetricSnapshot

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=30)
        try:
            db.query(NodeMetricSnapshot).filter(NodeMetricSnapshot.captured_at < cutoff).delete()
            db.commit()
        except Exception as exc:
            logger.warning("metric snapshot prune failed: %s", exc)
            db.rollback()

        nodes = db.query(ProxmoxNode).all()
        for n in nodes:
            try:
                mem_pct = None
                if n.memory_total and n.memory_used is not None and n.memory_total > 0:
                    mem_pct = round((n.memory_used / n.memory_total) * 100, 2)
                disk_pct = None
                if n.disk_total and n.disk_used is not None and n.disk_total > 0:
                    disk_pct = round((n.disk_used / n.disk_total) * 100, 2)
                snap = NodeMetricSnapshot(
                    node_id=n.id,
                    captured_at=datetime.utcnow(),
                    cpu_pct=float(n.cpu_usage) if n.cpu_usage is not None else None,
                    memory_pct=mem_pct,
                    disk_pct=disk_pct,
                    vm_count=n.vm_count or 0,
                    lxc_count=n.lxc_count or 0,
                )
                db.add(snap)
            except Exception as exc:
                logger.warning("failed to capture snapshot for node %s: %s", n.node_name, exc)
        db.commit()
    except Exception as exc:
        logger.error("run_node_metric_snapshot failed: %s", exc)
    finally:
        db.close()


def run_time_sync_drift_check():
    """Hourly: audit clocks/NTP on PVE nodes, PBS, and BMCs; alert on drift."""
    from app.core.database import SessionLocal
    from app.services.time_sync import check_drift_and_alert

    db = SessionLocal()
    try:
        summary = check_drift_and_alert(db)
        logger.info(
            "Time sync drift check: total=%d drifting=%d ntp_off=%d alerts=%d resolved=%d",
            summary.get("total", 0),
            summary.get("drifting", 0),
            summary.get("ntp_off", 0),
            summary.get("alerts", 0),
            summary.get("resolved", 0),
        )
    except Exception as exc:
        logger.error("run_time_sync_drift_check failed: %s", exc)
    finally:
        db.close()


def run_ai_report_schedules():
    """Every 5 min: find due ReportSchedules and trigger generation."""
    from app.core.database import SessionLocal
    from app.models.database import ReportSchedule
    from app.services.ai_reports import report_service

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        due = (
            db.query(ReportSchedule)
            .filter(ReportSchedule.enabled == True)  # noqa: E712
            .filter(ReportSchedule.next_run_at.isnot(None))
            .filter(ReportSchedule.next_run_at <= now)
            .all()
        )
        for sched in due:
            try:
                title = f"{sched.name} ({sched.report_type})"
                run = report_service.generate_report(
                    db,
                    user=None,
                    report_type=sched.report_type,
                    scope_type=sched.scope_type,
                    scope_ref=sched.scope_ref,
                    title=title,
                    run_async=True,
                )
                sched.last_run_at = now
                # advance next_run_at
                from datetime import timedelta
                if sched.cadence == "daily":
                    sched.next_run_at = now + timedelta(days=1)
                elif sched.cadence == "weekly":
                    sched.next_run_at = now + timedelta(days=7)
                elif sched.cadence == "monthly":
                    sched.next_run_at = now + timedelta(days=30)
                else:
                    sched.next_run_at = now + timedelta(hours=1)
                db.commit()
                logger.info("AI schedule %s (#%d) fired → report_run %d", sched.name, sched.id, run.id)
            except Exception as exc:
                logger.error("failed to run AI schedule %d: %s", sched.id, exc)
                db.rollback()
    finally:
        db.close()


def run_firmware_update_check():
    """Daily job: check BIOS/iDRAC firmware against Dell catalog for all polled servers."""
    from app.api.idrac import bmc_status_cache
    from app.services.firmware_check import check_updates

    servers = list(bmc_status_cache.items())
    if not servers:
        logger.debug("Firmware update check: no servers in cache yet")
        return

    updated = 0
    for key, entry in servers:
        if entry.get("error"):
            continue
        system_id = entry.get("dell_system_id") or ""
        bios_ver = entry.get("bios_version") or ""
        idrac_ver = entry.get("idrac_fw_version") or ""
        if not system_id:
            continue
        try:
            fw_updates = check_updates(system_id, bios_ver, idrac_ver)
            bmc_status_cache[key] = {**entry, "firmware_updates": fw_updates}
            updated += 1
            if fw_updates.get("bios") or fw_updates.get("idrac"):
                logger.info(
                    "Firmware updates available for %s: BIOS=%s iDRAC=%s",
                    key,
                    fw_updates.get("bios", {}).get("available") if fw_updates.get("bios") else "current",
                    fw_updates.get("idrac", {}).get("available") if fw_updates.get("idrac") else "current",
                )
        except Exception as exc:
            logger.error("Firmware check failed for %s: %s", key, exc)

    logger.info("Firmware update check complete — %d/%d servers checked", updated, len(servers))


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
    bmc_minutes = _get_bmc_poll_minutes()
    _scheduler.add_job(
        run_bmc_poll,
        IntervalTrigger(minutes=bmc_minutes),
        id="bmc_poll",
        max_instances=1,
        next_run_time=datetime.utcnow(),  # run immediately on startup
    )
    _scheduler.add_job(
        run_firmware_update_check,
        IntervalTrigger(hours=24),
        id="firmware_update_check",
        max_instances=1,
    )
    _scheduler.add_job(
        run_node_metric_snapshot,
        IntervalTrigger(minutes=5),
        id="ai_node_metric_snapshot",
        max_instances=1,
        next_run_time=datetime.utcnow(),
    )
    _scheduler.add_job(
        run_ai_report_schedules,
        IntervalTrigger(minutes=5),
        id="ai_report_schedules",
        max_instances=1,
    )
    _scheduler.add_job(
        run_time_sync_drift_check,
        IntervalTrigger(hours=1),
        id="time_sync_drift_check",
        max_instances=1,
    )
    _scheduler.start()
    _started = True
    logger.info(f"Scheduler started — update checks every {update_hours}h, security scans every {scan_hours}h, node poll every 5m, BMC poll every 2m, firmware check every 24h")


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


# Allowed BMC poll intervals in minutes — keep in sync with the frontend selector.
_BMC_POLL_ALLOWED_MIN = (1, 2, 5, 10)


def _get_bmc_poll_minutes() -> int:
    """Read the configured BMC poll interval from system_settings (default 2)."""
    try:
        from app.core.database import SessionLocal
        from app.models.database import SystemSettings
        db = SessionLocal()
        try:
            row = db.query(SystemSettings).filter(SystemSettings.key == "bmc_poll_interval_minutes").first()
            if row and row.value:
                v = int(row.value)
                if v in _BMC_POLL_ALLOWED_MIN:
                    return v
        finally:
            db.close()
    except Exception as exc:
        logger.debug("BMC poll interval lookup failed (using default): %s", exc)
    return 2


def reschedule_bmc_poll(minutes: int) -> None:
    """Replace the BMC poll job with a new interval. Caller must ensure value
    is in `_BMC_POLL_ALLOWED_MIN`."""
    if not _started:
        return
    if minutes not in _BMC_POLL_ALLOWED_MIN:
        raise ValueError(f"Invalid BMC poll interval {minutes} — must be one of {_BMC_POLL_ALLOWED_MIN}")
    try:
        _scheduler.remove_job("bmc_poll")
    except Exception:
        pass
    _scheduler.add_job(
        run_bmc_poll,
        IntervalTrigger(minutes=minutes),
        id="bmc_poll",
        max_instances=1,
        next_run_time=datetime.utcnow(),
    )
    logger.info("BMC poll rescheduled to every %d min", minutes)
