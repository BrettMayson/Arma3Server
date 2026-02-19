"""State and index management for incremental sync tracking."""

import os
import hashlib

from .config import STATE_VERSION, COMBINATION_METHOD


def normalize_path(path):
    """Normalize a filesystem path to lowercase forward-slash form."""
    return path.replace("\\", "/").lower()


def content_hash_hex(file_obj):
    """Return the hex content hash from a CDN file object."""
    content_hash = getattr(file_obj, "sha_content", "")
    if isinstance(content_hash, bytes):
        return content_hash.hex()
    return str(content_hash)


def compute_file_hash(local_path, content_hash):
    """Compute stable hash combining normalized path and content hash."""
    digest = hashlib.sha1()
    digest.update(local_path.encode("utf-8"))
    digest.update(b"|")
    digest.update(content_hash.encode("utf-8"))
    return digest.hexdigest()


def combined_mod_hash(file_hashes):
    """Combine individual file hashes deterministically for state header."""
    digest = hashlib.sha1()
    for file_hash in sorted(file_hashes):
        digest.update(file_hash.encode("utf-8"))
    return digest.hexdigest()


class StateManager:
    """Manages index state for depot/workshop items."""

    def __init__(self, index_root):
        """Initialize state manager for a specific index root.
        
        Args:
            index_root: Root folder for indices (e.g., workshop or depot index dir).
        """
        self.index_root = index_root

    def _index_paths(self, item_id):
        """Compute index directories for a given depot/workshop item."""
        mod_dir = os.path.join(self.index_root, str(item_id))
        files_dir = os.path.join(mod_dir, "files")
        state_file = os.path.join(mod_dir, "state.txt")
        return mod_dir, files_dir, state_file

    def ensure_state_header(self, item_id, combined_hash="pending", updated_at=None):
        """Ensure the state.txt header exists for an item index."""
        import time
        mod_dir, files_dir, state_file = self._index_paths(item_id)
        os.makedirs(files_dir, exist_ok=True)

        if os.path.exists(state_file):
            return

        timestamp = updated_at if updated_at is not None else time.time()
        with open(state_file, "w") as f:
            f.write(f"{STATE_VERSION}\n")
            f.write(f"{COMBINATION_METHOD}\n")
            f.write(f"{combined_hash}\n")
            f.write(f"{timestamp}\n")

    def write_file_entry(self, item_id, entry):
        """Write a single file entry checkpoint into the index."""
        _, files_dir, _ = self._index_paths(item_id)
        os.makedirs(files_dir, exist_ok=True)

        entry_path = os.path.join(files_dir, f"{entry['file_hash']}.txt")
        with open(entry_path, "w") as f_entry:
            f_entry.write(f"{entry['path']}\n")
            f_entry.write(f"{entry['file_hash']}\n")
            f_entry.write(f"{entry['content_hash']}\n")
            f_entry.write(f"{entry.get('size', 0)}\n")
            f_entry.write(f"{entry.get('downloaded_at', 0.0)}\n")

    def load_state(self, item_id):
        """Load indexed state for an item if present.

        Args:
            item_id: Workshop ID or depot ID.

        Returns:
            Dict with version/method/combined_hash/files or None if missing/invalid.
        """
        mod_dir, files_dir, state_file = self._index_paths(item_id)

        if not os.path.exists(state_file):
            return None

        try:
            with open(state_file, "r") as f:
                rows = [row.strip() for row in f.readlines()]
        except OSError:
            return None

        if len(rows) < 3:
            return None

        version, method, combined_hash = rows[0], rows[1], rows[2]
        updated_at = float(rows[3]) if len(rows) > 3 and rows[3] else 0.0
        files = []

        if os.path.isdir(files_dir):
            for filename in os.listdir(files_dir):
                entry_path = os.path.join(files_dir, filename)
                try:
                    with open(entry_path, "r") as f:
                        entry_rows = [row.strip() for row in f.readlines()]
                    if len(entry_rows) < 3:
                        continue
                    files.append({
                        "path": entry_rows[0],
                        "file_hash": entry_rows[1],
                        "content_hash": entry_rows[2],
                        "size": int(entry_rows[3]) if len(entry_rows) > 3 and entry_rows[3] else 0,
                        "downloaded_at": float(entry_rows[4]) if len(entry_rows) > 4 and entry_rows[4] else 0.0,
                    })
                except (OSError, ValueError):
                    continue

        return {
            "version": version,
            "method": method,
            "combined_hash": combined_hash,
            "updated_at": updated_at,
            "files": files,
        }

    def save_state(self, item_id, combined_hash, files, updated_at=None):
        """Persist state header and file checkpoints for an item."""
        import time
        mod_dir, files_dir, _ = self._index_paths(item_id)
        os.makedirs(files_dir, exist_ok=True)

        timestamp = updated_at if updated_at is not None else time.time()
        state_file = os.path.join(mod_dir, "state.txt")
        with open(state_file, "w") as f:
            f.write(f"{STATE_VERSION}\n")
            f.write(f"{COMBINATION_METHOD}\n")
            f.write(f"{combined_hash}\n")
            f.write(f"{timestamp}\n")

        keep_hashes = set()
        for entry in files:
            keep_hashes.add(entry["file_hash"])
            entry_path = os.path.join(files_dir, f"{entry['file_hash']}.txt")
            with open(entry_path, "w") as f_entry:
                f_entry.write(f"{entry['path']}\n")
                f_entry.write(f"{entry['file_hash']}\n")
                f_entry.write(f"{entry['content_hash']}\n")
                f_entry.write(f"{entry.get('size', 0)}\n")
                f_entry.write(f"{entry.get('downloaded_at', 0.0)}\n")

        for filename in os.listdir(files_dir):
            if not filename.endswith(".txt"):
                continue
            if filename[:-4] not in keep_hashes:
                try:
                    os.remove(os.path.join(files_dir, filename))
                except OSError:
                    pass
