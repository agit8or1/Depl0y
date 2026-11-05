"""Background scheduler for automated VM checks"""
import json
import logging
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(daemon=True)
_started = False


# ── helpers ──────────────────────────────────────────────────────────────────

# Older BMCs (iDRAC 7 especially) intermittently drop a connect under load, so
# a single miss is not evidence the box is down. Retry before believing it.
_BMC_ATTEMPTS = 3
_BMC_RETRY_DELAY = 2


def _retry_bmc(fn, attempts=_BMC_ATTEMPTS, delay=_BMC_RETRY_DELAY):
    """Call `fn`, retrying transient BMC failures. Re-raises the last error."""
    last = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt + 1 < attempts:
                time.sleep(delay)
    raise last


# BMCs on DHCP get new addresses whenever they lose link or the DHCP server
# restarts, and polling the old address then fails forever. We remember each
# BMC's MAC (from the ARP table, so only on-link BMCs) after a good poll, and
# when it stops answering we sweep its /24 and follow the MAC to its new IP.
# The sweep only opens TCP connections — no credentials go to unknown hosts.
_BMC_SWEEP_INTERVAL = 600  # seconds between sweeps of the same subnet
_bmc_last_sweep: dict = {}


def _arp_table() -> dict:
    """Return {ip: mac} for complete entries in the kernel ARP table."""
    table = {}
    try:
        with open("/proc/net/arp") as f:
            next(f)
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[2] != "0x0" and parts[3] != "00:00:00:00:00:00":
                    table[parts[0]] = parts[3].lower()
    except Exception as exc:
        logger.debug("ARP table read failed: %s", exc)
    return table


def _sweep_subnet(ip: str) -> None:
    """Touch every address in ip's /24 on port 443 so the kernel learns their MACs."""
    import ipaddress
    import socket
    from concurrent.futures import ThreadPoolExecutor

    try:
        net = ipaddress.ip_network(f"{ip}/24", strict=False)
    except ValueError:
        return
    now = time.time()
    if now - _bmc_last_sweep.get(str(net), 0) < _BMC_SWEEP_INTERVAL:
        return
    _bmc_last_sweep[str(net)] = now

    def _touch(addr):
        try:
            socket.create_connection((str(addr), 443), timeout=1).close()
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=64) as pool:
        list(pool.map(_touch, net.hosts()))


def _relocate_moved_bmcs(servers, poll_one):
    """Record the MAC of every BMC that answered; re-point the ones that didn't
    to wherever their MAC now lives, then poll them again at the new address."""
    from app.core.database import SessionLocal
    from app.models.database import ProxmoxHost, PBSServer, StandaloneBMC, ProxmoxNode, SystemSettings
    from app.api.idrac import bmc_status_cache

    models = {"pve": ProxmoxHost, "pbs": PBSServer, "standalone": StandaloneBMC, "pve_node": ProxmoxNode}
    arp = _arp_table()
    db = SessionLocal()
    try:
        lost = []
        for stype, sid, obj in servers:
            key = f"{stype}:{sid}"
            mac_key = f"bmc_mac:{key}"
            row = db.query(SystemSettings).filter(SystemSettings.key == mac_key).first()
            if not bmc_status_cache.get(key, {}).get("stale"):
                mac = arp.get(obj.idrac_hostname)
                if mac and (not row or row.value != mac):
                    if row:
                        row.value = mac
                    else:
                        db.add(SystemSettings(key=mac_key, value=mac,
                                              description=f"Last seen MAC of BMC {key}"))
            elif row and row.value:
                lost.append((stype, sid, obj, row.value))
        db.commit()
        if not lost:
            return

        for _, _, obj, _ in lost:
            _sweep_subnet(obj.idrac_hostname)
        arp = _arp_table()

        for stype, sid, obj, mac in lost:
            old_ip = obj.idrac_hostname
            new_ip = next((ip for ip, m in arp.items() if m == mac and ip != old_ip), None)
            if not new_ip:
                continue
            rec = db.query(models[stype]).filter_by(id=sid).first()
            if not rec or rec.idrac_hostname != old_ip:
                continue
            logger.warning("BMC %s:%s (MAC %s) moved from %s to %s — updating its address",
                           stype, sid, mac, old_ip, new_ip)
            rec.idrac_hostname = new_ip
            db.commit()
            obj.idrac_hostname = new_ip
            poll_one(stype, sid, obj)
    except Exception as exc:
        db.rollback()
        logger.warning("BMC relocation check failed: %s", exc)
    finally:
        db.close()


_BMC_HISTORY_DAYS = 120
_BMC_CACHE_SETTING = "bmc_status_cache"


def _record_bmc_readings(keys):
    """Append one history row per BMC for this poll, prune rows older than
    120 days, and save the whole status cache so a restart starts with the
    last known values instead of an empty page."""
    from datetime import timedelta
    from app.core.database import SessionLocal
    from app.models.database import BmcReading, SystemSettings
    from app.api.idrac import bmc_status_cache

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        for key in keys:
            e = bmc_status_cache.get(key)
            if not e:
                continue
            ok = not e.get("stale")
            db.add(BmcReading(
                bmc_key=key,
                captured_at=now,
                reachable=ok,
                power_state=e.get("power_state") if ok else None,
                health=e.get("health") if ok else None,
                consumed_watts=e.get("consumed_watts") if ok else None,
                max_temp_c=e.get("max_temp_c") if ok else None,
            ))
        db.query(BmcReading).filter(
            BmcReading.captured_at < now - timedelta(days=_BMC_HISTORY_DAYS)
        ).delete(synchronize_session=False)

        blob = json.dumps(bmc_status_cache, default=str)
        row = db.query(SystemSettings).filter(SystemSettings.key == _BMC_CACHE_SETTING).first()
        if row:
            row.value = blob
        else:
            db.add(SystemSettings(key=_BMC_CACHE_SETTING, value=blob,
                                  description="Last BMC status (restored at startup)"))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("BMC history write failed: %s", exc)
    finally:
        db.close()


def _restore_bmc_cache():
    """Load the BMC status saved by the last poll so the page has values
    while the first poll after startup (slow on iDRAC 7) is still running."""
    from app.core.database import SessionLocal
    from app.models.database import SystemSettings
    from app.api.idrac import bmc_status_cache

    db = SessionLocal()
    try:
        row = db.query(SystemSettings).filter(SystemSettings.key == _BMC_CACHE_SETTING).first()
        if row and row.value:
            for key, entry in json.loads(row.value).items():
                if isinstance(entry, dict):
                    bmc_status_cache.setdefault(key, entry)
    except Exception as exc:
        logger.warning("BMC status restore failed: %s", exc)
    finally:
        db.close()


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
                health_reasons = []

                # ── Routing logic ──────────────────────────────────────────
                # One IP per BMC: idrac_hostname is the BMC. Always try both
                # Redfish (HTTPS) and SSH against it — whichever the device
                # supports fills in its piece. Results are merged, never
                # exclusive.
                try_redfish = bool(obj.idrac_hostname)
                # `idrac_use_ssh` is the admin's statement that this address
                # serves an OS shell. BMC-only addresses never will, and each
                # attempt burns a connect timeout out of the poll cycle.
                try_ssh = bool(obj.idrac_hostname) and has_ssh_creds and bool(use_ssh)

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
                        rf_info = _retry_bmc(client.get_system_info)
                        power_state = rf_info.get("power_state")
                        # Prefer component-level current health over the SEL-aware
                        # rollup so stale event-log entries don't keep us at Warning
                        # after a hardware condition has cleared.
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
                    "last_success": datetime.utcnow().isoformat(),
                    "stale": False,
                    "error": None,
                    "max_temp_c": max_temp_c,
                    "consumed_watts": consumed_watts,
                    "firmware_updates": prev.get("firmware_updates"),
                    "health_reasons": health_reasons,
                    "reachable": True,
                    "last_heartbeat": prev.get("last_heartbeat"),
                    "last_heartbeat_ok": prev.get("last_heartbeat_ok"),
                }
            except Exception as e:
                # Keep the last good reading and mark it stale rather than
                # blanking the tile — a flaky BMC that misses one cycle is
                # not the same as a server with no data. `last_success`
                # tells the UI how old the surviving values are.
                prev = bmc_status_cache.get(key, {})
                bmc_status_cache[key] = {
                    **prev,
                    "power_state": prev.get("power_state"),
                    "health": prev.get("health"),
                    "model": prev.get("model"),
                    "last_polled": datetime.utcnow().isoformat(),
                    "last_success": prev.get("last_success"),
                    "stale": True,
                    "error": str(e),
                }

        # Poll all servers in parallel — a slow/unreachable BMC no longer
        # blocks the rest of the cycle.
        if servers:
            with ThreadPoolExecutor(max_workers=min(10, len(servers))) as pool:
                list(pool.map(lambda args: _poll_one(*args), servers))
            _relocate_moved_bmcs(servers, _poll_one)
            _record_bmc_readings([f"{stype}:{sid}" for stype, sid, _ in servers])
    except Exception as e:
        logger.error(f"BMC poll job error: {e}")
    finally:
        db.close()


def run_bmc_heartbeat():
    """Every 30 s: check that each BMC still accepts connections on its
    Redfish port. Only a TCP connect — no login — so it can never add to an
    iDRAC's failed-login count. A BMC that was down and answers again is
    polled right away instead of waiting for the next full poll."""
    import socket
    from concurrent.futures import ThreadPoolExecutor
    from app.core.database import SessionLocal
    from app.models.database import ProxmoxHost, PBSServer, StandaloneBMC, ProxmoxNode
    from app.api.idrac import bmc_status_cache

    db = SessionLocal()
    try:
        _has_idrac = lambda col: col.isnot(None) & (col != "")
        targets = []
        for stype, model, extra in (
            ("pve", ProxmoxHost, None),
            ("pbs", PBSServer, None),
            ("standalone", StandaloneBMC, StandaloneBMC.is_active == True),
            ("pve_node", ProxmoxNode, None),
        ):
            q = db.query(model).filter(_has_idrac(model.idrac_hostname))
            if extra is not None:
                q = q.filter(extra)
            targets += [(f"{stype}:{o.id}", o.idrac_hostname, o.idrac_port or 443) for o in q.all()]
    finally:
        db.close()

    def _alive(t):
        _, host, port = t
        try:
            socket.create_connection((host, port), timeout=3).close()
            return True
        except Exception:
            return False

    if not targets:
        return
    with ThreadPoolExecutor(max_workers=min(16, len(targets))) as pool:
        results = list(pool.map(_alive, targets))

    came_back = False
    now = datetime.utcnow().isoformat()
    for (key, _, _), alive in zip(targets, results):
        entry = bmc_status_cache.get(key)
        if entry is None:
            continue  # not polled yet — the UI shows "Pending first poll"
        was_alive = entry.get("reachable")
        entry["reachable"] = alive
        entry["last_heartbeat"] = now
        if alive:
            entry["last_heartbeat_ok"] = now
            # Only on the down→up transition, so a BMC that answers but
            # rejects our login isn't hammered with polls every 30 s.
            if entry.get("stale") and was_alive is False:
                came_back = True
        else:
            if was_alive:
                logger.warning("BMC %s stopped answering heartbeat", key)
            entry["stale"] = True
            entry.setdefault("error", None)
            if not entry["error"]:
                entry["error"] = "No response from BMC (heartbeat)"
    if came_back:
        try:
            _scheduler.modify_job("bmc_poll", next_run_time=datetime.utcnow())
        except Exception as exc:
            logger.debug("could not trigger BMC poll after heartbeat: %s", exc)


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
    _restore_bmc_cache()
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
        IntervalTrigger(minutes=1),  # was 5min — too slow for offline detection
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
        run_bmc_heartbeat,
        IntervalTrigger(seconds=30),
        id="bmc_heartbeat",
        max_instances=1,
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
