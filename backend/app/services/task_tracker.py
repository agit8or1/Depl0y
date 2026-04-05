"""Task tracker — keeps an in-memory registry of all Proxmox UPIDs initiated through Depl0y."""
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
        """Return an estimated 0–100 progress percentage for a running task."""
        if task.get("status") != "running":
            return 100.0
        task_type = task.get("task_type", "")
        duration = _TASK_DURATIONS.get(task_type, 60)
        try:
            started = datetime.fromisoformat(task["started_at"])
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        except Exception:
            return 0.0
        pct = min(elapsed / duration * 100, 95.0)
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
            finally:
                db.close()
        except Exception as exc:
            logger.debug("TaskTracker poll error for %s: %s", task.get("upid"), exc)

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
