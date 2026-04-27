"""Task tracker — keeps an in-memory registry of all Proxmox UPIDs initiated through Depl0y."""
import re
import threading
import logging
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Estimated durations (seconds) per task type — used for progress estimation
_TASK_DURATIONS = {
    "qmcreate": 120,
    "qmdestroy": 30,
    "qmstart": 15,
    "qmstop": 20,
    "qmshutdown": 30,
    "qmreboot": 30,
    "qmreset": 10,
    "qmsuspend": 10,
    "qmresume": 10,
    "qmmigrate": 300,
    "qmclone": 120,
    "qmsnapshot": 30,
    "qmrollback": 60,
    "vzdump": 600,
    "vzsnapshot": 30,
    "vzstart": 15,
    "vzstop": 20,
    "vzshutdown": 30,
    "vzreboot": 30,
    "vzmigrate": 300,
    "vzclone": 120,
    "vzrestore": 300,
    "download": 120,
    "imgcopy": 60,
}


class TaskTracker:
    """Tracks all Proxmox task UPIDs initiated through Depl0y.

    Thread-safe in-memory registry. A background poller thread calls the
    Proxmox API every 5 s to update the status of running tasks.
    """

    def __init__(self, max_history: int = 500):
        self._tasks: dict[str, dict] = {}       # upid → task_info
        self._history: deque = deque(maxlen=max_history)
        # Progress cache for tasks not registered through depl0y (e.g. a
        # migration started directly from the Proxmox UI). Keyed by UPID →
        # (timestamp, pct). TTL keeps us from hammering PVE on every UI poll.
        self._ext_progress: dict[str, tuple[float, float]] = {}
        self._ext_progress_ttl = 8.0  # seconds
        self._lock = threading.Lock()
        self._poll_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ── Public API ────────────────────────────────────────────────────────────

    def register(
        self,
        upid: str,
        host_id: int,
        node: str,
        description: str,
        user_id: int | None = None,
        vmid: int | None = None,
        task_type: str | None = None,
    ) -> dict:
        """Register a new task UPID and return the task_info dict."""
        now = datetime.now(timezone.utc)
        task_info = {
            "upid": upid,
            "host_id": host_id,
            "node": node,
            "description": description,
            "user_id": user_id,
            "vmid": vmid,
            "task_type": task_type or self._infer_type(upid),
            "status": "running",
            "exit_status": None,
            "registered_at": now.isoformat(),
            "started_at": now.isoformat(),
            "finished_at": None,
        }
        with self._lock:
            self._tasks[upid] = task_info
        self._ensure_poller_running()
        return task_info

    def update_status(self, upid: str, status: str, exit_status: str | None = None) -> None:
        """Update task status (called by background poller or manually)."""
        with self._lock:
            task = self._tasks.get(upid)
            if task is None:
                return
            task["status"] = status
            if exit_status is not None:
                task["exit_status"] = exit_status
            if status != "running" and task["finished_at"] is None:
                task["finished_at"] = datetime.now(timezone.utc).isoformat()
                # Move completed task to history
                self._history.appendleft(dict(task))
                del self._tasks[upid]

    def get_running(self) -> list[dict]:
        """Return all currently running tasks."""
        with self._lock:
            return [dict(t) for t in self._tasks.values()]

    def get_history(self, limit: int = 50, user_id: int | None = None) -> list[dict]:
        """Return recent completed tasks, optionally filtered by user."""
        with self._lock:
            items = list(self._history)
        if user_id is not None:
            items = [t for t in items if t.get("user_id") == user_id]
        return items[:limit]

    def get_task(self, upid: str) -> dict | None:
        """Return a single task by UPID (running or history)."""
        with self._lock:
            if upid in self._tasks:
                return dict(self._tasks[upid])
            for t in self._history:
                if t["upid"] == upid:
                    return dict(t)
        return None

    def estimate_progress(self, task: dict) -> float:
        """Return an estimated 0–100 progress percentage for a running task.

        Prefers real progress parsed from the Proxmox task log (cached by the
        background poller in `task["log_progress"]`). Falls back to a
        time-based estimate when the log doesn't yet contain a percentage.
        The time-based estimate is capped at 60% so it can't lie past the
        halfway mark — actual progress parsed from the log is what pushes
        the bar higher.
        """
        if task.get("status") != "running":
            return 100.0
        lp = task.get("log_progress")
        if isinstance(lp, (int, float)) and 0 <= lp <= 100:
            return round(float(lp), 1)
        task_type = task.get("task_type", "")
        duration = _TASK_DURATIONS.get(task_type, 60)
        try:
            started = datetime.fromisoformat(task["started_at"])
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        except Exception:
            return 0.0
        # Without real log data we can't trust the remaining half.
        pct = min(elapsed / duration * 100, 60.0)
        return round(pct, 1)

    # ── Background poller ─────────────────────────────────────────────────────

    def _ensure_poller_running(self) -> None:
        with self._lock:
            if self._poll_thread is not None and self._poll_thread.is_alive():
                return
            self._stop_event.clear()
            t = threading.Thread(target=self._poll_loop, daemon=True, name="task-tracker-poller")
            self._poll_thread = t
        t.start()
        logger.debug("TaskTracker background poller started")

    def _poll_loop(self) -> None:
        """Poll Proxmox every 5 s to update running task statuses."""
        while not self._stop_event.wait(5.0):
            with self._lock:
                running = list(self._tasks.values())
            if not running:
                logger.debug("TaskTracker: no running tasks — poller exiting")
                return
            for task in running:
                self._poll_one(task)

    def _poll_one(self, task: dict) -> None:
        try:
            from app.core.database import SessionLocal
            from app.models import ProxmoxHost
            from app.services.proxmox import ProxmoxService

            db = SessionLocal()
            try:
                host = db.query(ProxmoxHost).filter(
                    ProxmoxHost.id == task["host_id"],
                    ProxmoxHost.is_active == True,
                ).first()
                if host is None:
                    return
                pve = ProxmoxService(host).proxmox
                result = pve.nodes(task["node"]).tasks(task["upid"]).status.get()
                status = result.get("status", "unknown")
                exit_status = result.get("exitstatus")
                if status != "running":
                    self.update_status(task["upid"], status, exit_status)
                    return

                # Still running — try to parse real progress from the task log.
                try:
                    log_tail = pve.nodes(task["node"]).tasks(task["upid"]).log.get(
                        start=0, limit=200,
                    )
                    pct = self._parse_log_progress(log_tail, task.get("task_type", ""))
                    if pct is not None:
                        with self._lock:
                            t = self._tasks.get(task["upid"])
                            if t is not None:
                                # Monotonic — never let parsed progress move backwards
                                prev = t.get("log_progress") or 0.0
                                t["log_progress"] = max(prev, pct)
                except Exception as e:
                    logger.debug("TaskTracker progress parse for %s: %s", task.get("upid"), e)
            finally:
                db.close()
        except Exception as exc:
            logger.debug("TaskTracker poll error for %s: %s", task.get("upid"), exc)

    # Interactive / shell-style tasks have no meaningful progress
    _NO_PROGRESS_TYPES = frozenset({
        "vncshell", "vncproxy", "spiceshell", "spiceproxy", "termproxy",
    })

    def progress_for_external(self, upid: str, host_id: int, node: str, started_at_ts: float | None, task_type: str) -> float | None:
        """Compute a live progress % for a task NOT registered through depl0y.
        Used for tasks pulled straight from Proxmox's cluster/node task list
        (source=proxmox). Fetches the task log with a short TTL cache and
        parses the actual percentage out, falling back to a conservative
        time-based estimate. Returns None for interactive/shell tasks where
        progress is not meaningful.
        """
        if task_type in self._NO_PROGRESS_TYPES:
            return None
        import time
        now = time.time()
        # TTL-cached parsed progress
        cached = self._ext_progress.get(upid)
        if cached and (now - cached[0]) < self._ext_progress_ttl:
            return round(float(cached[1]), 1)

        prev = self._ext_progress.get(upid, (0.0, 0.0))[1]
        parsed = None
        try:
            from app.core.database import SessionLocal
            from app.models import ProxmoxHost
            from app.services.proxmox import ProxmoxService
            db = SessionLocal()
            try:
                host = db.query(ProxmoxHost).filter(
                    ProxmoxHost.id == host_id,
                    ProxmoxHost.is_active == True,
                ).first()
                if host is not None:
                    pve = ProxmoxService(host).proxmox
                    log_tail = pve.nodes(node).tasks(upid).log.get(start=0, limit=200)
                    parsed = self._parse_log_progress(log_tail, task_type)
            finally:
                db.close()
        except Exception as exc:
            logger.debug("external progress fetch failed for %s: %s", upid, exc)

        if parsed is not None:
            value = max(parsed, prev)  # monotonic
        elif prev > 0:
            value = prev  # keep last known good — don't fall back to time-based once log gave a real number
        elif started_at_ts:
            try:
                elapsed = now - float(started_at_ts)
            except Exception:
                elapsed = 0.0
            duration = _TASK_DURATIONS.get(task_type, 60)
            value = min(elapsed / duration * 100, 60.0)
        else:
            value = 0.0
        self._ext_progress[upid] = (now, value)
        return round(float(value), 1)

    def prune_ext_progress(self, keep_upids: set[str]) -> None:
        """Drop entries for tasks that are no longer running to keep the cache small."""
        for upid in list(self._ext_progress.keys()):
            if upid not in keep_upids:
                self._ext_progress.pop(upid, None)

    @staticmethod
    def _parse_log_progress(log_entries, task_type: str) -> float | None:
        """Extract a real progress percentage from a Proxmox task log tail.

        Proxmox emits percentages in several forms depending on the task:
        - `migration status: mem X% total Y% ...`
        - `transferred: 1.5 GiB of 8 GiB (18.75%)`
        - `transferred X bytes of Y bytes (Z%)` in live migration memory passes
        - `xfer  1500 MB  32%` in vzdump restore / backup
        - `INFO: transferred: X / Y bytes (Z%)`
        Returns the highest percentage found in the last 50 log lines, or None.
        """
        if not log_entries:
            return None
        # Proxmox log API returns a list of {n, t} dicts (line number, text)
        lines = []
        if isinstance(log_entries, list):
            lines = [(e.get("t") if isinstance(e, dict) else str(e)) for e in log_entries[-50:]]
        elif isinstance(log_entries, dict):
            lines = [(e.get("t") if isinstance(e, dict) else str(e)) for e in (log_entries.get("data") or [])[-50:]]
        highest = None
        pct_re = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
        for line in lines:
            if not line:
                continue
            for m in pct_re.finditer(line):
                try:
                    v = float(m.group(1))
                except ValueError:
                    continue
                if 0 <= v <= 100:
                    if highest is None or v > highest:
                        highest = v
        return highest

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _infer_type(upid: str) -> str:
        """Extract the task type from a UPID string.
        UPID format: UPID:<node>:<pid_hex>:<start_hex>:<starttime_hex>:<type>:<vmid>:<user>@<realm>:
        """
        try:
            parts = upid.split(":")
            if len(parts) >= 7:
                return parts[5]
        except Exception:
            pass
        return "unknown"


# Singleton instance
task_tracker = TaskTracker()
