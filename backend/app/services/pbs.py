"""
Proxmox Backup Server (PBS) API client service.

Provides PBSService — a class that wraps the PBS HTTP API (port 8007)
using the requests library and token-based authentication.

PBS API token auth header format:
  Authorization: PBSAPIToken={userid}!{tokenid}:{secret}
"""
import logging
from typing import Any, Dict, List, Optional

import requests
import urllib3

from app.core.security import decrypt_data
from app.models.database import PBSServer

logger = logging.getLogger(__name__)

# Suppress InsecureRequestWarning for self-signed PBS certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class PBSService:
    """Client for the Proxmox Backup Server REST API."""

    # Ticket cache (per hostname): (expires_epoch, ticket, csrf_token)
    _ticket_cache: Dict[str, tuple] = {}

    def __init__(self, server: PBSServer):
        self.server = server
        self.base_url = f"https://{server.hostname}:{server.port}/api2/json"
        self.verify_ssl = server.verify_ssl
        self.session = requests.Session()
        self.session.verify = self.verify_ssl
        self._uses_ticket = False
        self.session.headers.update(self._build_auth_header())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_auth_header(self) -> Dict[str, str]:
        """Build the Authorization header for PBS token auth."""
        server = self.server
        if server.api_token_id and server.api_token_secret:
            try:
                secret = decrypt_data(server.api_token_secret)
            except Exception:
                secret = server.api_token_secret

            # api_token_id is expected to be in the form "{userid}!{tokenid}",
            # e.g. "root@pam!mytoken".  PBS auth header = PBSAPIToken=<id>:<secret>
            return {"Authorization": f"PBSAPIToken={server.api_token_id}:{secret}"}

        # Ticket-based (password) auth. PBS issues a ticket + CSRFPreventionToken
        # at /access/ticket that is valid for ~2 hours. We cache it per host and
        # attach it as a cookie + CSRF header on subsequent requests.
        if server.password and server.username:
            try:
                password = decrypt_data(server.password)
            except Exception:
                password = server.password
            ticket, csrf = self._get_or_refresh_ticket(server.username, password)
            if ticket and csrf:
                self._uses_ticket = True
                self.session.cookies.set("PBSAuthCookie", ticket)
                return {"CSRFPreventionToken": csrf}
            logger.warning("PBS %s: ticket auth failed", server.name)
        return {}

    def _get_or_refresh_ticket(self, username: str, password: str) -> tuple:
        """Return (ticket, csrf_token), fetching a fresh ticket if the cache
        has expired. PBS tickets last 2 hours; we refresh after 100 minutes."""
        import time
        key = f"{self.server.hostname}:{self.server.port}:{username}"
        now = time.time()
        cached = PBSService._ticket_cache.get(key)
        if cached and cached[0] > now + 60:
            return cached[1], cached[2]
        url = f"{self.base_url}/access/ticket"
        try:
            resp = requests.post(
                url,
                data={"username": username, "password": password},
                verify=self.verify_ssl,
                timeout=30,
            )
            resp.raise_for_status()
            data = (resp.json() or {}).get("data") or {}
            ticket = data.get("ticket")
            csrf = data.get("CSRFPreventionToken")
            if ticket and csrf:
                PBSService._ticket_cache[key] = (now + 100 * 60, ticket, csrf)
                return ticket, csrf
        except Exception as e:
            logger.warning("PBS %s: ticket request failed: %s", self.server.name, e)
        return None, None

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Perform a GET request against the PBS API and return the 'data' field."""
        url = f"{self.base_url}{path}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get("data")
        except requests.exceptions.SSLError as exc:
            logger.error("SSL error connecting to PBS %s: %s", self.server.hostname, exc)
            raise
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error to PBS %s: %s", self.server.hostname, exc)
            raise
        except requests.exceptions.HTTPError as exc:
            logger.error(
                "HTTP %s from PBS %s at %s: %s",
                exc.response.status_code,
                self.server.hostname,
                path,
                exc,
            )
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        """
        Test connectivity to the PBS instance.

        Returns True if the PBS API responds successfully, False otherwise.
        """
        try:
            data = self._get("/version")
            if data and "version" in data:
                logger.info(
                    "Connected to PBS '%s' (version %s)",
                    self.server.name,
                    data.get("version"),
                )
                return True
            # Some PBS versions return the version at a different path
            data = self._get("/nodes/localhost/status")
            return data is not None
        except Exception as exc:
            logger.error(
                "PBS connection test failed for '%s': %s", self.server.name, exc
            )
            return False

    def get_datastores(self) -> List[Dict[str, Any]]:
        """
        Return all datastores configured on this PBS instance, including
        usage statistics (total, used, available bytes and backup counts).
        """
        data = self._get("/admin/datastore")
        if not data:
            return []
        return data  # Each entry already contains usage stats from PBS

    def get_datastore_usage(self, datastore: str) -> Dict[str, Any]:
        """
        Return usage statistics for a specific datastore.

        Includes total/used/available bytes and GC/prune status.
        """
        data = self._get(f"/admin/datastore/{datastore}/status")
        return data or {}

    def get_groups(self, datastore: str) -> List[Dict[str, Any]]:
        """
        Return all backup groups in the given datastore.

        Each group entry contains: backup-type, backup-id, last-backup,
        backup-count, owner, etc.
        """
        data = self._get(f"/admin/datastore/{datastore}/groups")
        if not data:
            return []
        return data

    def _post(self, path: str, data: Optional[Dict[str, Any]] = None) -> Any:
        """Perform a POST request against the PBS API and return the 'data' field."""
        url = f"{self.base_url}{path}"
        try:
            response = self.session.post(url, json=data or {}, timeout=30)
            response.raise_for_status()
            body = response.json()
            return body.get("data") if isinstance(body, dict) else body
        except requests.exceptions.SSLError as exc:
            logger.error("SSL error connecting to PBS %s: %s", self.server.hostname, exc)
            raise
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error to PBS %s: %s", self.server.hostname, exc)
            raise
        except requests.exceptions.HTTPError as exc:
            logger.error(
                "HTTP %s from PBS %s at %s: %s",
                exc.response.status_code,
                self.server.hostname,
                path,
                exc,
            )
            raise

    def _delete(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Perform a DELETE request against the PBS API and return the 'data' field."""
        url = f"{self.base_url}{path}"
        try:
            response = self.session.delete(url, params=params, timeout=30)
            response.raise_for_status()
            try:
                body = response.json()
                return body.get("data") if isinstance(body, dict) else body
            except Exception:
                return None
        except requests.exceptions.SSLError as exc:
            logger.error("SSL error connecting to PBS %s: %s", self.server.hostname, exc)
            raise
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error to PBS %s: %s", self.server.hostname, exc)
            raise
        except requests.exceptions.HTTPError as exc:
            logger.error(
                "HTTP %s from PBS %s at %s: %s",
                exc.response.status_code,
                self.server.hostname,
                path,
                exc,
            )
            raise

    def get_snapshots(
        self,
        datastore: str,
        vmid: Optional[int] = None,
        backup_type: Optional[str] = None,
        backup_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return backup snapshots in the given datastore.

        Args:
            datastore: Name of the PBS datastore.
            vmid: Optional VM/CT ID to filter results.  When provided, only
                  snapshots whose backup-id matches str(vmid) are returned.
            backup_type: Optional backup type filter (vm, ct, host).
            backup_id: Optional backup-id string filter.

        Returns a list of snapshot dicts, each containing backup-type,
        backup-id, backup-time, size, verification status, etc.
        """
        params: Dict[str, Any] = {}
        if backup_type:
            params["backup-type"] = backup_type
        if backup_id:
            params["backup-id"] = backup_id

        data = self._get(f"/admin/datastore/{datastore}/snapshots", params=params or None)
        if not data:
            return []

        if vmid is not None:
            target_id = str(vmid)
            data = [
                snap for snap in data
                if str(snap.get("backup-id", "")) == target_id
            ]

        return data

    def verify_snapshot(
        self,
        datastore: str,
        backup_type: str,
        backup_id: str,
        backup_time: int,
    ) -> Any:
        """
        Start a verification job for a specific snapshot.

        Returns the UPID task identifier.
        """
        return self._post(
            f"/admin/datastore/{datastore}/verify",
            {
                "backup-type": backup_type,
                "backup-id": backup_id,
                "backup-time": backup_time,
            },
        )

    def forget_snapshot(
        self,
        datastore: str,
        backup_type: str,
        backup_id: str,
        backup_time: int,
    ) -> Any:
        """
        Permanently delete (forget) a specific snapshot.

        PBS DELETE /admin/datastore/{datastore}/snapshots accepts the
        backup-type / backup-id / backup-time as query parameters.
        """
        return self._delete(
            f"/admin/datastore/{datastore}/snapshots",
            params={
                "backup-type": backup_type,
                "backup-id": backup_id,
                "backup-time": backup_time,
            },
        )

    def prune(
        self,
        datastore: str,
        backup_type: str,
        backup_id: str,
        prune_options: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Prune old snapshots for a specific backup group according to the
        provided keep-* options.

        prune_options may include: keep-last, keep-daily, keep-weekly,
        keep-monthly, keep-yearly, keep-hourly.
        """
        payload: Dict[str, Any] = {
            "backup-type": backup_type,
            "backup-id": backup_id,
        }
        if prune_options:
            payload.update(prune_options)
        return self._post(f"/admin/datastore/{datastore}/prune", payload)

    def list_tasks(self, datastore: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Return tasks from the PBS node.

        Args:
            datastore: Optional datastore name to filter tasks.
        """
        params: Dict[str, Any] = {}
        if datastore:
            params["store"] = datastore
        data = self._get("/nodes/localhost/tasks", params=params or None)
        if not data:
            return []
        return data

    def get_sync_jobs(self) -> List[Dict[str, Any]]:
        """
        Return all jobs configured on this PBS instance:
        sync, pull, verify, and prune jobs.
        """
        jobs: List[Dict[str, Any]] = []
        for job_type, path in (
            ("sync", "/config/sync"),
            ("pull", "/config/pull"),
            ("verify", "/config/verify"),
            ("prune", "/config/prune"),
        ):
            try:
                data = self._get(path)
                if data:
                    for item in data:
                        item.setdefault("job-type", job_type)
                        # Normalise id field
                        if "id" not in item and "job-id" in item:
                            item["id"] = item["job-id"]
                        # Merge admin (runtime) status for verify/sync jobs
                        jobs.append(item)
            except Exception as exc:
                logger.warning("Could not fetch %s jobs from PBS '%s': %s", job_type, self.server.name, exc)

        # Enrich verify/sync jobs with last-run info from admin endpoints
        admin_map: Dict[str, Dict] = {}
        for admin_path in ("/admin/sync", "/admin/verify"):
            try:
                for item in (self._get(admin_path) or []):
                    admin_map[item.get("id", "")] = item
            except Exception:
                pass
        for job in jobs:
            admin = admin_map.get(job.get("id", ""))
            if admin:
                for key in ("last-run-endtime", "last-run-state", "last-run-upid", "next-run"):
                    if key in admin and key not in job:
                        job[key] = admin[key]

        return jobs

    def run_sync_job(self, job_id: str) -> Any:
        """
        Trigger a sync job to run immediately.

        PBS: POST /api2/json/config/sync/{job-id}/run
        Returns the UPID of the started task.
        """
        return self._post(f"/config/sync/{job_id}/run")

    def get_tapes(self) -> Dict[str, Any]:
        """
        Return tape library info: drives, changers, and media inventory.

        PBS exposes these at /tape/drive, /tape/changer, and
        /tape/changer/{changer}/inventory (requires a changer to be configured).
        Returns a summary dict so the frontend has a single endpoint to call.
        """
        result: Dict[str, Any] = {"drives": [], "changers": [], "media": []}
        for key, path in (("drives", "/tape/drive"), ("changers", "/tape/changer")):
            try:
                data = self._get(path)
                if isinstance(data, list):
                    result[key] = data
            except Exception:
                pass

        # Fetch inventory from each changer
        for changer in result["changers"]:
            name = changer.get("name") or changer.get("id")
            if not name:
                continue
            try:
                inv = self._get(f"/tape/changer/{name}/inventory")
                if isinstance(inv, list):
                    result["media"].extend(inv)
            except Exception:
                pass

        return result

    def get_task_log(self, upid: str) -> List[str]:
        """
        Return the log lines for a given task UPID.

        PBS returns an array of {n, t} objects where 'n' is the line number
        and 't' is the text.  We return the text lines for convenience.
        """
        import urllib.parse
        encoded = urllib.parse.quote(upid, safe="")
        data = self._get(f"/nodes/localhost/tasks/{encoded}/log")
        if not data:
            return []
        if isinstance(data, list):
            # Each item is {"n": linenum, "t": text} or just a string
            lines = []
            for item in data:
                if isinstance(item, dict):
                    lines.append(item.get("t", ""))
                else:
                    lines.append(str(item))
            return lines
        return [str(data)]

    # ------------------------------------------------------------------
    # Task status / recent tasks
    # ------------------------------------------------------------------

    def get_task_status(self, upid: str) -> Dict[str, Any]:
        """Return the PBS task status dict for a given UPID."""
        import urllib.parse
        encoded = urllib.parse.quote(upid, safe="")
        data = self._get(f"/nodes/localhost/tasks/{encoded}/status")
        return data or {}

    def list_recent_tasks(
        self,
        since_epoch: int,
        types: Optional[List[str]] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Return recent PBS tasks whose endtime is >= since_epoch.

        PBS /nodes/localhost/tasks accepts 'since', 'running' and 'typefilter'
        parameters. We request both running and finished tasks.
        """
        tasks: List[Dict[str, Any]] = []
        params: Dict[str, Any] = {
            "since": since_epoch,
            "limit": limit,
        }
        try:
            data = self._get("/nodes/localhost/tasks", params=params) or []
            tasks.extend(data)
        except Exception as exc:
            logger.warning("PBS list_recent_tasks failed for '%s': %s", self.server.name, exc)

        if types:
            def _match(task):
                worker = (task.get("worker_type") or task.get("type") or "").lower()
                return any(t.lower() in worker for t in types)
            tasks = [t for t in tasks if _match(t)]
        return tasks

    # ------------------------------------------------------------------
    # APT / package update helpers
    # ------------------------------------------------------------------

    def apt_list_updates(self) -> List[Dict[str, Any]]:
        """Return pending package updates from PBS (GET /nodes/localhost/apt/update)."""
        data = self._get("/nodes/localhost/apt/update")
        if not data:
            return []
        return data

    def apt_refresh_updates(self) -> str:
        """Trigger apt-get update on the PBS node. Returns UPID of the task."""
        upid = self._post("/nodes/localhost/apt/update")
        return upid

    def apt_upgrade(self, packages: Optional[List[str]] = None) -> str:
        """Trigger apt-get dist-upgrade on PBS. Returns UPID of the task.

        If 'packages' is provided, PBS's apt.upgrade endpoint will upgrade
        only those packages.
        """
        payload: Dict[str, Any] = {}
        if packages:
            payload["packages"] = " ".join(packages)
        upid = self._post("/nodes/localhost/apt/upgrade", payload or None)
        return upid
