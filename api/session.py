"""Steam session management with automatic retry and session reset."""

import os
import time
import threading

from steam.client import SteamClient
from steam.client.cdn import CDNClient

from .config import (
    SESSION_RESET_THRESHOLD,
    ARMA3_SERVER_APP_ID,
    DEPOT_ROOT,
    DEPOT_INDEX_DIR,
    WORKSHOP_ROOT,
    WORKSHOP_INDEX_DIR,
    resolve_config,
)
from .manifest import ManifestCache
from .sync import ContentSyncer


# Module-level CDN client cache
_cached_cdn_client = None
_cached_steam_client_id = None


def _get_cdn_client(client, config=None):
    """Return a cached CDNClient or build one with retries.

    Args:
        client: Authenticated SteamClient instance.
        config: Config map containing cdn_client_retries/base_delay.

    Returns:
        CDNClient or None if construction failed after retries.
    """
    global _cached_cdn_client, _cached_steam_client_id

    resolved = resolve_config(config)
    retries = resolved["cdn_client_retries"]
    base_delay = resolved["cdn_client_base_delay"]

    if _cached_cdn_client and _cached_steam_client_id == id(client):
        return _cached_cdn_client

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            cdn_client = CDNClient(client)
            _cached_cdn_client = cdn_client
            _cached_steam_client_id = id(client)
            return cdn_client
        except Exception as exc:
            last_error = exc
            print(f"CDNClient init failed (attempt {attempt}/{retries}): {exc}")
            if attempt < retries:
                time.sleep(base_delay * attempt)

    print(f"CDNClient could not be initialized after {retries} attempts; giving up. Last error: {last_error}")
    return None


def _clear_cdn_cache():
    """Clear the cached CDN client."""
    global _cached_cdn_client, _cached_steam_client_id
    _cached_cdn_client = None
    _cached_steam_client_id = None


class SteamSession:
    """Facade wrapping Steam and CDN clients with automatic session reset on consecutive failures.
    
    After SESSION_RESET_THRESHOLD consecutive failures, performs a full session reset
    (new SteamClient, new login, new CDNClient) to recover from transient Steam API issues.
    """

    def __init__(self, username, password, config=None):
        """Initialize session with credentials but don't connect yet.
        
        Args:
            username: Steam username.
            password: Steam password.
            config: Optional config map for retry/download tuning.
        """
        self._username = username
        self._password = password
        self._config = config
        self._client = None
        self._cdn_client = None
        self._consecutive_failures = 0
        self._lock = threading.Lock()

    def _reset_session(self):
        """Perform full session reset: new SteamClient, login, and CDNClient."""
        print("Performing full Steam session reset...")
        self._client = None
        self._cdn_client = None
        self._consecutive_failures = 0
        _clear_cdn_cache()
        self._ensure_connected()

    def _ensure_connected(self):
        """Ensure Steam client is logged in and CDN client is available."""
        if self._client is None:
            self._client = SteamClient()
            self._client.login(self._username, self._password)
            print("Logged in to Steam as", self._client.user.name)
        
        if self._cdn_client is None:
            resolved = resolve_config(self._config)
            self._cdn_client = _get_cdn_client(self._client, resolved)
            if self._cdn_client is None:
                raise RuntimeError("Failed to initialize CDN client")

    def _record_success(self):
        """Record a successful operation, resetting failure counter."""
        with self._lock:
            self._consecutive_failures = 0

    def _record_failure(self):
        """Record a failed operation, potentially triggering session reset.
        
        Returns:
            True if session was reset and caller should retry.
        """
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= SESSION_RESET_THRESHOLD:
                print(f"Hit {self._consecutive_failures} consecutive failures, resetting session...")
                self._reset_session()
                return True
            return False

    def _execute_cdn_op(self, op_name, func, *args, **kwargs):
        """Execute a CDN operation with retry and session reset logic.
        
        Args:
            op_name: Label for logging.
            func: Callable that takes (cdn_client, *args, **kwargs).
            *args: Positional args for the callable.
            **kwargs: Keyword args for the callable.
            
        Returns:
            The callable result.
            
        Raises:
            RuntimeError: if all attempts including session resets failed.
        """
        resolved = resolve_config(self._config)
        retries = resolved["cdn_op_retries"]
        base_delay = resolved["cdn_op_base_delay"]
        
        # Allow up to 2 full session resets
        max_session_resets = 2
        session_reset_count = 0
        
        while session_reset_count <= max_session_resets:
            self._ensure_connected()
            last_error = None
            
            for attempt in range(1, retries + 1):
                try:
                    result = func(self._cdn_client, *args, **kwargs)
                    self._record_success()
                    return result
                except Exception as exc:
                    last_error = exc
                    print(f"{op_name} failed (attempt {attempt}/{retries}): {exc}")
                    
                    should_retry = self._record_failure()
                    if should_retry:
                        session_reset_count += 1
                        print(f"Session reset #{session_reset_count}, retrying {op_name}...")
                        break  # Break inner loop to restart with new session
                    
                    if attempt < retries:
                        time.sleep(base_delay * attempt)
            else:
                # Exhausted retries without session reset trigger
                raise RuntimeError(f"{op_name} failed after {retries} attempts: {last_error}")
        
        raise RuntimeError(f"{op_name} failed after {max_session_resets} session resets: {last_error}")

    def get_manifests(self, app_id, branch="creatordlc"):
        """Get manifests for an app from CDN.
        
        Args:
            app_id: Steam app ID.
            branch: Branch name.
            
        Returns:
            List of manifest objects.
        """
        return self._execute_cdn_op(
            "get_manifests",
            lambda cdn, *a, **kw: cdn.get_manifests(*a, **kw),
            app_id,
            branch=branch,
        )

    def iter_files(self, app_id, branch="creatordlc", filter_func=None):
        """Iterate files for an app from CDN.
        
        Args:
            app_id: Steam app ID.
            branch: Branch name.
            filter_func: Optional filter function for depots.
            
        Returns:
            List of file objects.
        """
        return self._execute_cdn_op(
            "iter_files",
            lambda cdn, *a, **kw: list(cdn.iter_files(*a, **kw)),
            app_id,
            branch=branch,
            filter_func=filter_func,
        )

    def get_manifest_for_workshop_item(self, workshop_id):
        """Get manifest for a workshop item.
        
        Args:
            workshop_id: Workshop item ID.
            
        Returns:
            Manifest object for the workshop item.
        """
        return self._execute_cdn_op(
            "get_manifest_for_workshop_item",
            lambda cdn, wid: cdn.get_manifest_for_workshop_item(wid),
            workshop_id,
        )

    @property 
    def client(self):
        """Return underlying SteamClient."""
        self._ensure_connected()
        return self._client

    @property
    def user(self):
        """Return Steam user info."""
        self._ensure_connected()
        return self._client.user

    def download_depot(self, depot_id):
        """Sync a depot by manifest with automatic retry/reset.

        Args:
            depot_id: Depot ID to sync.
        """
        resolved_config = resolve_config(self._config)
        manifest_cache = ManifestCache()
        cached_manifests = manifest_cache.load()
        
        if cached_manifests:
            manifests = cached_manifests
            print("Got manifests from cache for ARMA3 server app ID:", ARMA3_SERVER_APP_ID)
        else:
            print("Fetching fresh manifests from Steam...")
            manifests_obj = self.get_manifests(ARMA3_SERVER_APP_ID, branch="creatordlc")
            
            manifest_cache.save(manifests_obj)
            
            manifests = []
            for manifest in manifests_obj:
                manifests.append({
                    'name': manifest.name,
                    'gid': manifest.gid,
                    'depot_id': manifest.depot_id
                })
        
        target_manifest = next((m for m in manifests if m['depot_id'] == depot_id), None)
        if not target_manifest:
            print(f"No manifest found for depot ID {depot_id}")
            return
        
        print(f"Downloading Manifest ID: {target_manifest['gid']}, Depot ID: {target_manifest['depot_id']}")

        files = self.iter_files(
            ARMA3_SERVER_APP_ID,
            branch="creatordlc",
            filter_func=lambda d_id, depot_info: d_id == target_manifest['depot_id'],
        )
        files = [f for f in files if f.is_file]
        print(f"Found {len(files)} files to download")
        
        syncer = ContentSyncer(DEPOT_INDEX_DIR, config=resolved_config)
        syncer.sync(files, DEPOT_ROOT, depot_id, f"Depot {depot_id}")

    def download_workshop(self, workshop_id):
        """Sync a workshop item by manifest with indexed incremental updates.

        Args:
            workshop_id: Workshop ID to sync.
        """
        resolved_config = resolve_config(self._config)
        workshop_manifest = self.get_manifest_for_workshop_item(workshop_id)
        files = [f for f in workshop_manifest.iter_files() if f.is_file]
        destination = os.path.join(WORKSHOP_ROOT, str(workshop_id))
        
        syncer = ContentSyncer(WORKSHOP_INDEX_DIR, config=resolved_config)
        syncer.sync(files, destination, workshop_id, f"Workshop {workshop_id}")

    @staticmethod
    def login(username, password, config=None):
        """Log in to Steam and return a connected SteamSession.

        Args:
            username: Steam username.
            password: Steam password.
            config: Optional config map for retry/download tuning.

        Returns:
            Connected SteamSession instance.
        """
        session = SteamSession(username, password, config=config)
        session._ensure_connected()
        return session
