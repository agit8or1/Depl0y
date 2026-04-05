"""
Proxmox Backup Server (PBS) API client service.

Provides PBSService — a class that wraps the PBS HTTP API (port 8007)
using the requests library and token-based authentication.

PBS API token auth header format:
  Authorization: PBSAPIToken={userid}!{tokenid}={secret}
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

    def __init__(self, server: PBSServer):
        self.server = server
        self.base_url = f"https://{server.hostname}:{server.port}/api2/json"
        self.verify_ssl = server.verify_ssl
        self.session = requests.Session()
        self.session.verify = self.verify_ssl
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
            # e.g. "root@pam!mytoken".  PBS auth header = PBSAPIToken=<id>=<secret>
            return {"Authorization": f"PBSAPIToken={server.api_token_id}={secret}"}

        # Fallback: try password auth via the userid!tokenid convention using
        # the stored username and password fields (not recommended for PBS but
        # included for completeness).
        if server.password:
            try:
                password = decrypt_data(server.password)
            except Exception:
                password = server.password
            # PBS does not support HTTP Basic auth — log a warning and return empty
            logger.warning(
                "PBS server '%s' has no API token configured; "
                "password-only auth is not supported by this client.",
                server.name,
            )
        return {}

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

    def get_snapshots(
        self, datastore: str, vmid: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Return backup snapshots in the given datastore.

        Args:
            datastore: Name of the PBS datastore.
            vmid: Optional VM/CT ID to filter results.  When provided, only
                  snapshots whose backup-id matches str(vmid) are returned.

        Returns a list of snapshot dicts, each containing backup-type,
        backup-id, backup-time, size, verification status, etc.
        """
        data = self._get(f"/admin/datastore/{datastore}/snapshots")
        if not data:
            return []

        if vmid is not None:
            target_id = str(vmid)
            data = [
                snap for snap in data
                if str(snap.get("backup-id", "")) == target_id
            ]

        return data
