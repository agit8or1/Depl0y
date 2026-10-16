"""HA-ZFS wizard API: survey the replicated ZFS storage, then apply the suggestions the user picks.

The analysis lives in app.services.hazfs. Apply only accepts suggestions from this host's
latest survey (matched by id and fingerprint), so what runs is exactly what the user reviewed.
Jobs run in the background and are polled through GET /ha-wizard/jobs/{job_id}.
"""
import logging
import threading
import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.api.ha_wizard import _get_host, _pve, _start_job
from app.core.database import get_db
from app.services import hazfs
from app.services.host_ssh import ssh_address

logger = logging.getLogger(__name__)
router = APIRouter()

_SURVEY_TTL = 30 * 60
_surveys: dict = {}            # host id -> {"time", "facts", "result"}
_busy: set = set()             # host ids with a job running
_lock = threading.Lock()


@router.get("/{host_id}/survey")
def survey(host_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """Read every node and return its status, the suggested changes and notes."""
    host = _get_host(host_id, db)
    pve = _pve(host)
    try:
        facts = hazfs.gather(pve, jump=ssh_address(host))
    except Exception as exc:
        logger.error("hazfs survey of host %s failed: %s", host_id, exc)
        raise HTTPException(status_code=502, detail=f"Could not read the cluster: {exc}")
    result = hazfs.suggest(facts)
    with _lock:
        _surveys[host_id] = {"time": time.time(), "facts": facts, "result": result}
        result["busy"] = host_id in _busy
    return result


class Choice(BaseModel):
    id: str
    fingerprint: str


class ApplyRequest(BaseModel):
    suggestions: List[Choice]


@router.post("/{host_id}/apply")
def apply(host_id: int, body: ApplyRequest, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """Apply suggestions from the latest survey. Refuses anything the user has not just seen."""
    host = _get_host(host_id, db)
    if not body.suggestions:
        raise HTTPException(status_code=400, detail="Pick at least one change")
    with _lock:
        cached = _surveys.get(host_id)
        if not cached or time.time() - cached["time"] > _SURVEY_TTL:
            raise HTTPException(status_code=409, detail="The survey is out of date; check the cluster again")
        if host_id in _busy:
            raise HTTPException(status_code=409, detail="Changes are already being applied to this cluster")
        by_id = {s["id"]: s for s in cached["result"]["suggestions"]}
        chosen = []
        for c in body.suggestions:
            s = by_id.get(c.id)
            if not s or s["fingerprint"] != c.fingerprint:
                raise HTTPException(status_code=409, detail="The suggestions changed; check the cluster again")
            chosen.append(s)
        chosen.sort(key=lambda s: cached["result"]["suggestions"].index(s))
        facts = cached["facts"]
        _busy.add(host_id)
        del _surveys[host_id]      # every apply needs a fresh survey afterwards
    pve = _pve(host)
    jump = ssh_address(host)

    def work(progress):
        try:
            hazfs.apply(pve, facts, chosen, progress, jump=jump)
        finally:
            with _lock:
                _busy.discard(host_id)

    n = len(chosen)
    return _start_job("hazfs", f"Apply {n} HA-ZFS change{'s' if n != 1 else ''}", current_user, work)
