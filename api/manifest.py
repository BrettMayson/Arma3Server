"""Manifest caching for Steam CDN operations."""

import os
import json
import time

from .config import CACHE_DIR, MANIFEST_CACHE_FILE, CACHE_EXPIRY_SECONDS


class ManifestCache:
    """Handles caching of Steam CDN manifest data."""

    def __init__(self, cache_file=None, expiry_seconds=None):
        """Initialize manifest cache.
        
        Args:
            cache_file: Path to cache file (default: MANIFEST_CACHE_FILE).
            expiry_seconds: Cache expiry in seconds (default: CACHE_EXPIRY_SECONDS).
        """
        self.cache_file = cache_file or MANIFEST_CACHE_FILE
        self.expiry_seconds = expiry_seconds or CACHE_EXPIRY_SECONDS

    def load(self):
        """Load cached manifest data if present and fresh.

        Returns:
            List of cached manifest dicts or None if missing/expired/corrupt.
        """
        if not os.path.exists(self.cache_file):
            return None
        
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            if time.time() - cache_data.get('timestamp', 0) > self.expiry_seconds:
                print("Manifest cache expired, will refetch...")
                return None
            
            return cache_data.get('manifests', [])
        except (json.JSONDecodeError, FileNotFoundError):
            print("Cache file corrupted or missing, will refetch...")
            return None

    def save(self, manifests):
        """Save manifest data to cache with timestamp.

        Args:
            manifests: Iterable of manifest objects from CDNClient.get_manifests.
        """
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        
        manifest_data = []
        for manifest in manifests:
            manifest_data.append({
                'name': manifest.name,
                'gid': manifest.gid,
                'depot_id': manifest.depot_id
            })
        
        cache_data = {
            'timestamp': time.time(),
            'manifests': manifest_data
        }
        
        with open(self.cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        print(f"Manifest data cached to {self.cache_file}")
