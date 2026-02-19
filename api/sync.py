"""Content synchronization using manifest diffs and state tracking."""

import os
import time

from .config import STATE_VERSION, COMBINATION_METHOD, resolve_config
from .state import (
    StateManager, 
    normalize_path, 
    content_hash_hex, 
    compute_file_hash, 
    combined_mod_hash
)
from .download import Downloader


def build_remote_state(destination_root, files):
    """Build remote manifest state for downstream diffing.
    
    Args:
        destination_root: Local root where files should land.
        files: Iterable of CDN file objects.
        
    Returns:
        Tuple of (state_dict, file_map).
    """
    entries = []
    file_map = {}

    for file_obj in files:
        local_path = normalize_path(os.path.join(destination_root, file_obj.filename))
        content_hash = content_hash_hex(file_obj)
        file_hash = compute_file_hash(local_path, content_hash)
        entry = {
            "path": local_path,
            "file_hash": file_hash,
            "content_hash": content_hash,
            "size": getattr(file_obj, "size", 0),
            "file": file_obj,
        }
        entries.append(entry)
        file_map[local_path] = entry

    combined = combined_mod_hash([entry["file_hash"] for entry in entries])
    return {"combined_hash": combined, "files": entries}, file_map


def diff_states(remote_state, local_state):
    """Compare remote vs local state into download/delete/unchanged buckets.
    
    Args:
        remote_state: State dict from build_remote_state.
        local_state: State dict from StateManager.load_state or None.
        
    Returns:
        Tuple of (to_download, to_delete, unchanged) lists.
    """
    remote_map = {entry["path"]: entry for entry in remote_state.get("files", [])}
    local_files = local_state.get("files", []) if local_state else []
    local_map = {entry["path"]: entry for entry in local_files}

    to_download = []
    to_delete = []
    unchanged = []

    for path, remote_entry in remote_map.items():
        local_entry = local_map.get(path)
        if not local_entry or local_entry.get("file_hash") != remote_entry["file_hash"]:
            to_download.append(remote_entry)
        else:
            unchanged.append(remote_entry)

    for path, local_entry in local_map.items():
        if path not in remote_map:
            to_delete.append(local_entry)

    return to_download, to_delete, unchanged


def remove_local_files(entries):
    """Delete local files listed in entries, ignoring errors.
    
    Args:
        entries: List of file entry dicts with 'path' key.
    """
    for entry in entries:
        local_path = os.path.normpath(entry["path"])
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except OSError:
            print(f"Warning: failed to delete {local_path}")


class ContentSyncer:
    """Handles incremental content synchronization."""

    def __init__(self, index_root, config=None):
        """Initialize syncer with index root and config.
        
        Args:
            index_root: Root folder for index state.
            config: Optional config map.
        """
        self.state_manager = StateManager(index_root)
        self._config = resolve_config(config)

    def sync(self, files, destination, item_id, label):
        """Incrementally sync a depot/workshop set using manifest diffs and cached index.

        Args:
            files: Iterable of CDN file objects from the manifest.
            destination: Local root where files should land.
            item_id: Depot or workshop ID used for index names.
            label: Human-readable label for logging.
        """
        if not files:
            print(f"{label} has no files in manifest.")
            return

        remote_state, _ = build_remote_state(destination, files)
        local_state = self.state_manager.load_state(item_id)

        self.state_manager.ensure_state_header(
            item_id, 
            combined_hash=local_state.get("combined_hash") if local_state else "pending"
        )

        if local_state and (local_state.get("version") != STATE_VERSION or 
                           local_state.get("method") != COMBINATION_METHOD):
            print(f"{label} index format changed, ignoring cached state.")
            local_state = None

        if local_state and local_state.get("combined_hash") == remote_state["combined_hash"]:
            short_hash = remote_state["combined_hash"][:7]
            updated_at = local_state.get("updated_at", 0)
            if updated_at:
                from datetime import datetime
                date_str = datetime.fromtimestamp(updated_at).strftime("%Y-%m-%d %H:%M")
                print(f"{label} is up-to-date (commit {short_hash}, last updated {date_str}).")
            else:
                print(f"{label} is up-to-date (commit {short_hash}).")
            return

        to_download, to_delete, unchanged = diff_states(remote_state, local_state)

        print(f"{label}: {len(remote_state['files'])} files in manifest.")
        print(f"  Unchanged: {len(unchanged)} | To download/update: {len(to_download)} | To delete: {len(to_delete)}")

        remove_local_files(to_delete)
        remove_local_files(to_download)

        entry_map = {entry["path"]: entry for entry in to_download}

        if to_download:
            def _checkpoint(file_obj):
                path = normalize_path(file_obj.local)
                entry = entry_map.get(path)
                if not entry:
                    return
                checkpoint = {
                    "path": entry["path"],
                    "file_hash": entry["file_hash"],
                    "content_hash": entry["content_hash"],
                    "size": entry.get("size", 0),
                    "downloaded_at": time.time(),
                }
                self.state_manager.write_file_entry(item_id, checkpoint)

            downloader = Downloader(config=self._config)
            downloader.download_files(
                [entry["file"] for entry in to_download],
                destination=destination,
                post_download_hook=_checkpoint,
            )

        updated_state = self.state_manager.load_state(item_id) or {}
        local_map = {entry["path"]: entry for entry in updated_state.get("files", [])}
        now = time.time()
        persisted_files = []

        for entry in remote_state["files"]:
            previous = local_map.get(entry["path"])
            timestamp = previous.get("downloaded_at") if previous and previous.get("file_hash") == entry["file_hash"] else now
            persisted_files.append({
                "path": entry["path"],
                "file_hash": entry["file_hash"],
                "content_hash": entry["content_hash"],
                "size": entry.get("size", 0),
                "downloaded_at": timestamp,
            })

        self.state_manager.save_state(item_id, remote_state["combined_hash"], persisted_files)
        print(f"{label} synced (commit {remote_state['combined_hash'][:7]}).")
