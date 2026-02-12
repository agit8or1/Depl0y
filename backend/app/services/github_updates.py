"""GitHub update integration service"""
import requests
import logging
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

# GitHub repository configuration
GITHUB_OWNER = "agit8or1"
GITHUB_REPO = "Depl0y"
GITHUB_API_BASE = "https://api.github.com"


class GitHubUpdateService:
    """Service for managing updates from GitHub releases"""

    def __init__(self):
        self.api_url = f"{GITHUB_API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}"

    def get_latest_release(self) -> Optional[Dict[str, Any]]:
        """
        Fetch latest release information from GitHub

        Returns:
            Dict with release info or None if error
        """
        try:
            url = f"{self.api_url}/releases/latest"
            logger.info(f"Fetching latest release from {url}")

            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"Depl0y/{settings.APP_VERSION}"
            }

            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 404:
                logger.warning("No releases found on GitHub")
                return None

            response.raise_for_status()
            release_data = response.json()

            logger.info(f"Found release: {release_data.get('tag_name', 'unknown')}")

            return {
                "version": release_data.get("tag_name", "").lstrip("v"),
                "name": release_data.get("name"),
                "body": release_data.get("body"),  # Release notes
                "published_at": release_data.get("published_at"),
                "html_url": release_data.get("html_url"),
                "tarball_url": release_data.get("tarball_url"),
                "zipball_url": release_data.get("zipball_url"),
                "assets": release_data.get("assets", [])
            }

        except requests.RequestException as e:
            logger.error(f"Failed to fetch GitHub release: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing GitHub release: {e}")
            return None

    def check_for_updates(self) -> Dict[str, Any]:
        """
        Check if updates are available

        Returns:
            Dict with update availability information
        """
        current_version = settings.APP_VERSION
        latest_release = self.get_latest_release()

        if not latest_release:
            return {
                "current_version": current_version,
                "latest_version": current_version,
                "update_available": False,
                "error": "Could not fetch latest release from GitHub"
            }

        latest_version = latest_release["version"]

        # Simple version comparison
        update_available = self._compare_versions(current_version, latest_version)

        result = {
            "current_version": current_version,
            "latest_version": latest_version,
            "update_available": update_available,
            "release_name": latest_release.get("name"),
            "release_notes": latest_release.get("body"),
            "published_at": latest_release.get("published_at"),
            "download_url": latest_release.get("tarball_url"),
            "release_page": latest_release.get("html_url")
        }

        # Check for release assets (pre-built packages)
        assets = latest_release.get("assets", [])
        if assets:
            # Look for a .tar.gz asset
            for asset in assets:
                if asset.get("name", "").endswith(".tar.gz"):
                    result["package_url"] = asset.get("browser_download_url")
                    result["package_size"] = asset.get("size")
                    result["package_name"] = asset.get("name")
                    break

        return result

    def _compare_versions(self, current: str, latest: str) -> bool:
        """
        Compare semantic versions

        Args:
            current: Current version (e.g., "1.3.7")
            latest: Latest version (e.g., "1.3.8")

        Returns:
            True if update is available
        """
        try:
            # Remove 'v' prefix if present
            current = current.lstrip("v")
            latest = latest.lstrip("v")

            # Split into parts
            current_parts = [int(x) for x in current.split(".")]
            latest_parts = [int(x) for x in latest.split(".")]

            # Pad with zeros if needed
            while len(current_parts) < 3:
                current_parts.append(0)
            while len(latest_parts) < 3:
                latest_parts.append(0)

            # Compare
            return latest_parts > current_parts

        except Exception as e:
            logger.error(f"Version comparison error: {e}")
            # If we can't compare, assume update is available if versions differ
            return current != latest

    def download_release(self, download_url: str, destination: str) -> bool:
        """
        Download release package from GitHub

        Args:
            download_url: URL to download from
            destination: Local file path to save to

        Returns:
            True if successful
        """
        try:
            logger.info(f"Downloading release from {download_url}")

            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"Depl0y/{settings.APP_VERSION}"
            }

            response = requests.get(download_url, headers=headers, stream=True, timeout=300)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            logger.info(f"Download size: {total_size} bytes")

            with open(destination, "wb") as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            if downloaded % (1024 * 1024) == 0:  # Log every MB
                                logger.info(f"Download progress: {progress:.1f}%")

            logger.info(f"Download complete: {destination}")
            return True

        except Exception as e:
            logger.error(f"Failed to download release: {e}")
            return False

    def get_all_releases(self, limit: int = 10) -> list:
        """
        Get list of all releases

        Args:
            limit: Maximum number of releases to return

        Returns:
            List of release dicts
        """
        try:
            url = f"{self.api_url}/releases"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"Depl0y/{settings.APP_VERSION}"
            }

            params = {"per_page": limit}
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            releases = response.json()

            return [
                {
                    "version": r.get("tag_name", "").lstrip("v"),
                    "name": r.get("name"),
                    "published_at": r.get("published_at"),
                    "prerelease": r.get("prerelease", False),
                    "draft": r.get("draft", False),
                    "html_url": r.get("html_url")
                }
                for r in releases
            ]

        except Exception as e:
            logger.error(f"Failed to fetch releases list: {e}")
            return []
