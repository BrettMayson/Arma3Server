"""Configuration constants and utilities for the Steam API module."""

import os

# Steam app constants
ARMA3_SERVER_APP_ID = 233780
SESSION_RESET_THRESHOLD = 3  # Consecutive failures before full session reset

# Cache paths
CACHE_DIR = "/arma3/cache"
MANIFEST_CACHE_FILE = os.path.join(CACHE_DIR, "manifests.json")
CACHE_EXPIRY_SECONDS = 5 * 60

# Content paths
WORKSHOP_ROOT = "server/workshop"
DEPOT_ROOT = "server"
INDEX_ROOT = os.path.join(CACHE_DIR, "index")
WORKSHOP_INDEX_DIR = os.path.join(INDEX_ROOT, "workshop")
DEPOT_INDEX_DIR = os.path.join(INDEX_ROOT, "depot")

# State versioning
STATE_VERSION = "1.0"
COMBINATION_METHOD = "file-hash-asc"

# Default configuration values
DEFAULT_CONFIG = {
    "cdn_client_retries": 3,
    "cdn_client_base_delay": 1.5,
    "cdn_op_retries": 3,
    "cdn_op_base_delay": 1.5,
    "download_max_workers": 4,
    "download_chunk_size": 4 * 1024 * 1024,
    "download_progress_interval": 60,
}

# Creator DLC depot IDs
CDLC_IDS = {
    "csla": 233793,
    "gm": 233792,
    "vn": 233794,
    "ws": 233795,
    "spe": 233788,
    "rf": 233799,
    "ef": 233798
}


def resolve_config(config=None):
    """Merge caller config with defaults without mutating inputs.
    
    Args:
        config: Optional config dict to merge with defaults.
        
    Returns:
        Merged config dict.
    """
    merged = DEFAULT_CONFIG.copy()
    if config:
        merged.update({k: v for k, v in config.items() if v is not None})
    return merged
