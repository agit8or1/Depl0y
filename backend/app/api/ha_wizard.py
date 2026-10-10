"""Failover wizard API: check a guest, show the (fixed) plan, apply it or undo it.

The decisions live in app.services.ha_failover. Apply/remove run in a background thread
because the first replication or a disk move can take a long time; the wizard polls
GET /ha-wizard/jobs/{job_id}.
"""
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.core.database import get_db
from app.models import ProxmoxHost
from app.services import ha_failover
from app.services.proxmox import ProxmoxService

logger = logging.getLogger(__name__)
router = APIRouter()

_jobs: dict = {}
_jobs_lock = threading.Lock()
_JOB_TTL = 24 * 3600


def _get_host(host_id: int, db: Session) -> ProxmoxHost:
    host = db.query(ProxmoxHost).filter(
        ProxmoxHost.id == host_id, ProxmoxHost.is_active == True
    ).first()
    if not host:
        raise HTTPException(status_code=404, detail="Proxmox host not found")
    return host


def _pve(host: ProxmoxHost):
    return ProxmoxService(host).proxmox


def _vmtype(vmtype: str) -> str:
    if vmtype not in ("qemu", "lxc"):
        raise HTTPException(status_code=400, detail="vmtype must be 'qemu' or 'lxc'")
    return vmtype


def _plan(pve, node, vmtype, vmid):
    try:
        return ha_failover.build_plan(ha_failover.gather_facts(pve, node, vmtype, vmid))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("ha_wizard: planning %s/%s/%s failed: %s", node, vmtype, vmid, exc)
        raise HTTPException(status_code=502, detail=f"Could not read the guest or cluster from Proxmox: {exc}")


@router.get("/{host_id}/guests")
def list_guests(host_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """Every guest with its failover status, for the wizard's first step."""
    pve = _pve(_get_host(host_id, db))
    try:
        cluster = ha_failover.gather_cluster(pve)
        resources = [r for r in pve.cluster.resources.get(type="vm") if not r.get("template")]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not read the cluster from Proxmox: {exc}")
    guests = []
    for r in sorted(resources, key=lambda r: int(r["vmid"])):
        entry = {"vmid": int(r["vmid"]), "name": r.get("name", ""), "node": r["node"], "vmtype": r["type"],
                 "status": r.get("status")}
        if r.get("status") == "unknown" or not cluster["nodes"].get(r["node"], {}).get("online"):
            entry.update(summary="Node offline", state="unknown")
            guests.append(entry)
            continue
        try:
            plan = ha_failover.build_plan(
                ha_failover.gather_facts(pve, r["node"], r["type"], r["vmid"], cluster=cluster, resource=r))
        except Exception as exc:
            entry.update(summary=f"Could not read config: {exc}", state="unknown")
            guests.append(entry)
            continue
        if plan["already_protected"]:
            entry.update(state="protected", summary="Protected by HA")
        elif plan["eligible"]:
            entry.update(state="ready", mode=plan["mode"],
                         summary="Ready: shared storage" if plan["mode"] == "shared" else "Ready: ZFS replication")
        elif plan["move_options"]:
            entry.update(state="movable", summary=f"Needs disks moved to {plan['move_options'][0]['storage']}")
        else:
            fail = next((c["title"] for c in plan["checks"] if c["status"] == "fail"), "Not eligible")
            entry.update(state="blocked", summary=fail)
        guests.append(entry)
    return {"guests": guests,
            "cluster": {"quorate": cluster["quorate"], "nodes": len(cluster["nodes"]),
                        "qdevice": cluster["qdevice"]}}


@router.get("/{host_id}/{node}/{vmtype}/{vmid}/plan")
def get_plan(host_id: int, node: str, vmtype: str, vmid: int,
             db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """Readiness checks and the exact changes the wizard would make."""
    return _plan(_pve(_get_host(host_id, db)), node, _vmtype(vmtype), vmid)


class ApplyRequest(BaseModel):
    move_storage: Optional[str] = None   # move the guest's disks here first (must be one of plan.move_options)


def _start_job(kind: str, description: str, user, target):
    now = time.time()
    with _jobs_lock:
        for jid in [j for j, v in _jobs.items() if now - v["created"] > _JOB_TTL]:
            del _jobs[jid]
        job_id = uuid.uuid4().hex
        _jobs[job_id] = {"id": job_id, "kind": kind, "description": description,
                         "user_id": getattr(user, "id", None), "created": now,
                         "status": "running", "steps": [], "error": None}
    job = _jobs[job_id]

    def progress(text):
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        with _jobs_lock:
            job["steps"].append({"time": stamp, "text": text})
        logger.info("ha_wizard job %s: %s", job_id, text)

    def run():
        try:
            target(progress)
            job["status"] = "done"
        except Exception as exc:  # noqa: BLE001 - report any Proxmox error to the wizard
            logger.error("ha_wizard job %s failed: %s", job_id, exc)
            job["error"] = str(exc)
            job["status"] = "failed"

    threading.Thread(target=run, daemon=True, name=f"ha-wizard-{job_id[:8]}").start()
    return {"job_id": job_id}


@router.post("/{host_id}/{node}/{vmtype}/{vmid}/apply")
def apply(host_id: int, node: str, vmtype: str, vmid: int, body: ApplyRequest = ApplyRequest(),
          db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """Make the guest fail over. The plan is recomputed here; the client only picks a move target."""
    pve = _pve(_get_host(host_id, db))
    vmtype = _vmtype(vmtype)
    plan = _plan(pve, node, vmtype, vmid)
    if plan["already_protected"]:
        raise HTTPException(status_code=409, detail=f"{plan['sid']} is already protected by HA")
    if body.move_storage:
        if body.move_storage not in {o["storage"] for o in plan["move_options"]}:
            raise HTTPException(status_code=400, detail="That storage is not a valid move target for this guest")
    elif not plan["eligible"]:
        raise HTTPException(status_code=400, detail="This guest cannot fail over yet; see the readiness checks")

    def work(progress):
        current = plan
        if body.move_storage:
            ha_failover.move_disks(pve, current, body.move_storage, progress)
            progress("Re-checking the guest after the move")
            current = ha_failover.build_plan(ha_failover.gather_facts(pve, node, vmtype, vmid))
            if not current["eligible"]:
                problems = "; ".join(c["title"] for c in current["checks"] if c["status"] == "fail")
                raise RuntimeError(f"disks moved, but the guest still cannot fail over: {problems}")
        ha_failover.apply_plan(pve, current, progress)

    return _start_job("apply", f"Enable failover for {plan['sid']} ({plan['name']})", current_user, work)


@router.post("/{host_id}/{node}/{vmtype}/{vmid}/remove")
def remove(host_id: int, node: str, vmtype: str, vmid: int,
           db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """Take the guest out of HA again (the guest itself is not touched)."""
    pve = _pve(_get_host(host_id, db))
    plan = _plan(pve, node, _vmtype(vmtype), vmid)
    if not plan["already_protected"]:
        raise HTTPException(status_code=409, detail=f"{plan['sid']} is not an HA resource")
    return _start_job("remove", f"Remove failover for {plan['sid']} ({plan['name']})", current_user,
                      lambda progress: ha_failover.remove_protection(pve, plan, progress))


@router.get("/jobs/{job_id}")
def job_status(job_id: str, current_user=Depends(require_admin)):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found (it may have expired)")
    with _jobs_lock:
        return {k: (list(v) if k == "steps" else v) for k, v in job.items()}
