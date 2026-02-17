from steam.client import SteamClient
from steam.client.cdn import CDNClient, CDNDepotFile
import os
import hashlib
import json
import time
import sys
import threading
import concurrent.futures

ARMA3_SERVER_APP_ID = 233780
CACHE_DIR = "/arma3/cache"
MANIFEST_CACHE_FILE = os.path.join(CACHE_DIR, "manifests.json")
CACHE_EXPIRY_SECONDS = 5 * 60

WORKSHOP_ROOT = "server/workshop"
DEPOT_ROOT = "server"
INDEX_ROOT = os.path.join(CACHE_DIR, "index")
WORKSHOP_INDEX_DIR = os.path.join(INDEX_ROOT, "workshop")
DEPOT_INDEX_DIR = os.path.join(INDEX_ROOT, "depot")
STATE_VERSION = "1.0"
COMBINATION_METHOD = "file-hash-asc"

CDLC_IDS = {
    "csla": 233793,
    "gm": 233792,
    "vn": 233794,
    "ws": 233795,
    "spe": 233788,
    "rf": 233799,
    "ef": 233798
}

def _get_cdn_client(client, retries=3, base_delay=1.5):
    """Reuse a CDNClient when possible; retry construction on failure."""
    global _CACHED_CDN_CLIENT, _CACHED_STEAM_CLIENT_ID

    if _CACHED_CDN_CLIENT and _CACHED_STEAM_CLIENT_ID == id(client):
        return _CACHED_CDN_CLIENT

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            cdn_client = CDNClient(client)
            _CACHED_CDN_CLIENT = cdn_client
            _CACHED_STEAM_CLIENT_ID = id(client)
            return cdn_client
        except Exception as exc:
            last_error = exc
            print(f"CDNClient init failed (attempt {attempt}/{retries}): {exc}")
            if attempt < retries:
                time.sleep(base_delay * attempt)

    print(f"CDNClient could not be initialized after {retries} attempts; giving up. Last error: {last_error}")
    return None

_CACHED_CDN_CLIENT = None
_CACHED_STEAM_CLIENT_ID = None


def _normalize_path(path):
    return path.replace("\\", "/").lower()


def _content_hash_hex(file_obj):
    content_hash = getattr(file_obj, "sha_content", "")
    if isinstance(content_hash, bytes):
        return content_hash.hex()
    return str(content_hash)


def _compute_file_hash(local_path, content_hash):
    digest = hashlib.sha1()
    digest.update(local_path.encode("utf-8"))
    digest.update(b"|")
    digest.update(content_hash.encode("utf-8"))
    return digest.hexdigest()


def _combined_mod_hash(file_hashes):
    digest = hashlib.sha1()
    for file_hash in sorted(file_hashes):
        digest.update(file_hash.encode("utf-8"))
    return digest.hexdigest()


def _index_paths(index_root, item_id):
    mod_dir = os.path.join(index_root, str(item_id))
    files_dir = os.path.join(mod_dir, "files")
    state_file = os.path.join(mod_dir, "state.txt")
    return mod_dir, files_dir, state_file


def _ensure_state_header(index_root, item_id, combined_hash="pending"):
    mod_dir, files_dir, state_file = _index_paths(index_root, item_id)
    os.makedirs(files_dir, exist_ok=True)

    if os.path.exists(state_file):
        return

    with open(state_file, "w") as f:
        f.write(f"{STATE_VERSION}\n")
        f.write(f"{COMBINATION_METHOD}\n")
        f.write(f"{combined_hash}\n")


def _write_file_entry(index_root, item_id, entry):
    _, files_dir, _ = _index_paths(index_root, item_id)
    os.makedirs(files_dir, exist_ok=True)

    entry_path = os.path.join(files_dir, f"{entry['file_hash']}.txt")
    with open(entry_path, "w") as f_entry:
        f_entry.write(f"{entry['path']}\n")
        f_entry.write(f"{entry['file_hash']}\n")
        f_entry.write(f"{entry['content_hash']}\n")
        f_entry.write(f"{entry.get('size', 0)}\n")
        f_entry.write(f"{entry.get('downloaded_at', 0.0)}\n")


def _load_state(index_root, item_id):
    mod_dir, files_dir, state_file = _index_paths(index_root, item_id)

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
        "files": files,
    }


def _save_state(index_root, item_id, combined_hash, files):
    mod_dir, files_dir, _ = _index_paths(index_root, item_id)
    os.makedirs(files_dir, exist_ok=True)

    state_file = os.path.join(mod_dir, "state.txt")
    with open(state_file, "w") as f:
        f.write(f"{STATE_VERSION}\n")
        f.write(f"{COMBINATION_METHOD}\n")
        f.write(f"{combined_hash}\n")

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


def _build_remote_state(destination_root, files):
    entries = []
    file_map = {}

    for file_obj in files:
        local_path = _normalize_path(os.path.join(destination_root, file_obj.filename))
        content_hash = _content_hash_hex(file_obj)
        file_hash = _compute_file_hash(local_path, content_hash)
        entry = {
            "path": local_path,
            "file_hash": file_hash,
            "content_hash": content_hash,
            "size": getattr(file_obj, "size", 0),
            "file": file_obj,
        }
        entries.append(entry)
        file_map[local_path] = entry

    combined_hash = _combined_mod_hash([entry["file_hash"] for entry in entries])
    return {"combined_hash": combined_hash, "files": entries}, file_map


def _diff_states(remote_state, local_state):
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


def _remove_local_files(entries):
    for entry in entries:
        local_path = os.path.normpath(entry["path"])
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except OSError:
            print(f"Warning: failed to delete {local_path}")


def _sync_content(client, cdn_client, files, destination, index_root, item_id, label):
    if not files:
        print(f"{label} has no files in manifest.")
        return

    remote_state, _ = _build_remote_state(destination, files)
    local_state = _load_state(index_root, item_id)

    _ensure_state_header(index_root, item_id, combined_hash=local_state.get("combined_hash") if local_state else "pending")

    if local_state and (local_state.get("version") != STATE_VERSION or local_state.get("method") != COMBINATION_METHOD):
        print(f"{label} index format changed, ignoring cached state.")
        local_state = None

    if local_state and local_state.get("combined_hash") == remote_state["combined_hash"]:
        print(f"{label} already matches manifest (combined hash {remote_state['combined_hash']}).")
        return

    to_download, to_delete, unchanged = _diff_states(remote_state, local_state)

    print(f"{label}: {len(remote_state['files'])} files in manifest.")
    print(f"  Unchanged: {len(unchanged)} | To download/update: {len(to_download)} | To delete: {len(to_delete)}")

    _remove_local_files(to_delete)
    _remove_local_files(to_download)

    entry_map = {entry["path"]: entry for entry in to_download}

    if to_download:
        def _checkpoint(file_obj):
            path = _normalize_path(file_obj.local)
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
            _write_file_entry(index_root, item_id, checkpoint)

        download_files(
            [entry["file"] for entry in to_download],
            destination=destination,
            post_download_hook=_checkpoint,
        )

    updated_state = _load_state(index_root, item_id) or {}
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

    _save_state(index_root, item_id, remote_state["combined_hash"], persisted_files)
    print(f"{label} synced. Combined hash: {remote_state['combined_hash']}")

def login(username, password):
    client = SteamClient()
    client.login(username, password)
    print("Logged in to Steam as", client.user.name)
    return client

def load_cached_manifests():
    """Load cached manifest data if it exists and is not expired"""
    if not os.path.exists(MANIFEST_CACHE_FILE):
        return None
    
    try:
        with open(MANIFEST_CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
        
        if time.time() - cache_data.get('timestamp', 0) > CACHE_EXPIRY_SECONDS:
            print("Manifest cache expired, will refetch...")
            return None
        
        return cache_data.get('manifests', [])
    except (json.JSONDecodeError, FileNotFoundError):
        print("Cache file corrupted or missing, will refetch...")
        return None

def save_manifests_to_cache(manifests):
    """Save manifest data to cache with timestamp"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    
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
    
    with open(MANIFEST_CACHE_FILE, 'w') as f:
        json.dump(cache_data, f, indent=2)
    
    print(f"Manifest data cached to {MANIFEST_CACHE_FILE}")

def download_depot(client, depot_id):
    cdn_client = _get_cdn_client(client)
    if not cdn_client:
        print("Cannot download depot without CDN client; aborting.")
        return
    
    cached_manifests = load_cached_manifests()
    
    if cached_manifests:
        manifests = cached_manifests
        print("Got manifests from cache for ARMA3 server app ID:", ARMA3_SERVER_APP_ID)
    else:
        print("Fetching fresh manifests from Steam...")
        manifests_obj = cdn_client.get_manifests(ARMA3_SERVER_APP_ID, branch="creatordlc")
        
        save_manifests_to_cache(manifests_obj)
        
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

    files_generator = cdn_client.iter_files(ARMA3_SERVER_APP_ID, branch="creatordlc", filter_func=lambda d_id, depot_info: d_id == target_manifest['depot_id'])
    files = list(files_generator)
    files = [f for f in files if f.is_file]
    print(f"Found {len(files)} files to download")
    _sync_content(
        client,
        cdn_client,
        files,
        destination=DEPOT_ROOT,
        index_root=DEPOT_INDEX_DIR,
        item_id=depot_id,
        label=f"Depot {depot_id}",
    )

def download_workshop(client, workshop_id):
    cdn_client = _get_cdn_client(client)
    if not cdn_client:
        print(f"Cannot download workshop {workshop_id} without CDN client; aborting.")
        return
    workshop_manifest = cdn_client.get_manifest_for_workshop_item(workshop_id)
    files = [f for f in workshop_manifest.iter_files() if f.is_file]
    destination = os.path.join(WORKSHOP_ROOT, str(workshop_id))
    _sync_content(
        client,
        cdn_client,
        files,
        destination=destination,
        index_root=WORKSHOP_INDEX_DIR,
        item_id=workshop_id,
        label=f"Workshop {workshop_id}",
    )

def download_files(files, destination, post_download_hook=None, max_workers=4, chunk_size=4 * 1024 * 1024, progress_interval=120):
    files_to_download = []

    for file in files:
        file.local = os.path.join(destination, file.filename).lower()
        files_to_download.append(file)

    if not files_to_download:
        print("All files already up to date.")
        return True

    print(f"Downloading {len(files_to_download)} files across {max_workers} workers.")

    checkpoint_lock = threading.Lock()
    print_lock = threading.Lock()
    finished_count = 0

    def _human_bytes(num_bytes):
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(num_bytes)
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.3f} {unit}"
            size /= 1024

    def _worker(file_obj):
        nonlocal finished_count
        success = _download_single_file(file_obj, chunk_size, print_lock=print_lock, progress_interval=progress_interval)
        if success and post_download_hook:
            try:
                with checkpoint_lock:
                    post_download_hook(file_obj)
            except Exception:
                with print_lock:
                    print("Warning: checkpoint hook failed; continuing")
        with print_lock:
            finished_count += 1
            status = "downloaded" if success else "failed"
            print(f"{finished_count}/{len(files_to_download)}: {status} {file_obj.filename} ({_human_bytes(file_obj.size)})")
        return success

    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {}
        for file_obj in files_to_download:
            future = executor.submit(_worker, file_obj)
            future_map[future] = file_obj.filename

        for future in concurrent.futures.as_completed(future_map):
            filename = future_map[future]
            try:
                if not future.result():
                    failures.append(filename)
            except Exception as exc:
                with print_lock:
                    print(f"Download crashed for {filename}: {exc}")
                failures.append(filename)

    if failures:
        print(f"Failed downloads: {len(failures)} => {failures}")
        return False

    print("All files downloaded successfully.")
    return True


def _download_single_file(file, chunk_size, print_lock=None, progress_interval=120):
    if file.local and os.path.dirname(file.local) != "":
        os.makedirs(os.path.dirname(file.local), exist_ok=True)

    downloaded = 0
    failed = False
    last_report = time.time()

    with open(file.local, 'wb') as f:
        while downloaded < file.size:
            remaining = file.size - downloaded
            read_size = min(chunk_size, remaining)

            try:
                chunk = file.read(read_size)
            except Exception as exc:
                failed = True
                break

            if not chunk:
                failed = True
                break

            f.write(chunk)
            downloaded += len(chunk)

            now = time.time()
            if progress_interval > 0 and now - last_report >= progress_interval:
                percent = (downloaded / file.size * 100) if file.size else 0.0
                report = f"Progress {file.filename}: {percent:.1f}% ({downloaded}/{file.size} bytes)"
                if print_lock:
                    with print_lock:
                        print(report)
                else:
                    print(report)
                last_report = now

    if failed or downloaded < file.size:
        return False

    if file.is_executable:
        os.chmod(file.local, 0o755)
    return True

if __name__ == "__main__":
    import os
    import sys

    if len(sys.argv) != 3:
        print("Usage: python api.py <username> <password>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    client = login(username, password)
    if client:
        download_depot(client, 233785) # Western Sahara
        download_workshop(client, 463939057)  # Example workshop ID for ACE3 mod
