from steam.client import SteamClient
from steam.client.cdn import CDNClient, CDNDepotFile
import os
import hashlib
import json
import time
import sys

ARMA3_SERVER_APP_ID = 233780
CACHE_DIR = "cache"
MANIFEST_CACHE_FILE = os.path.join(CACHE_DIR, "manifests.json")
CACHE_EXPIRY_SECONDS = 5 * 60

CDLC_IDS = {
    "csla": 233793,
    "gm": 233792,
    "vn": 233794,
    "ws": 233795,
    "spe": 233788,
    "rf": 233799,
    "ef": 233798
}

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
    cdn_client = CDNClient(client)
    
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
    download_files(client, cdn_client, files, destination="server/")

def download_workshop(client, workshop_id):
    cdn_client = CDNClient(client)
    workshop_manifest = cdn_client.get_manifest_for_workshop_item(workshop_id)
    files_generator = workshop_manifest.iter_files()
    files = list(files_generator)
    files = [f for f in files if f.is_file]
    print(f"Found {len(files)} files to download")
    download_files(client, cdn_client, files, destination=f"server/workshop/{workshop_id}/")

def download_files(client, cdn_client, files, destination):
    print(f"Verifying {len(files)} files...")
    files_to_download = []
    
    for i, file in enumerate(files):
        file.local = os.path.join(destination, file.filename).lower()

        if os.path.exists(file.local):
            with open(file.local, 'rb') as f:
                existing_hash = hashlib.sha1(f.read()).hexdigest()
                expected_hash = file.sha_content.hex() if isinstance(file.sha_content, bytes) else file.sha_content
                if existing_hash == expected_hash:
                    if file.is_executable:
                        os.chmod(file.local, 0o755)
                    continue
        files_to_download.append(file)
    
    print(f"Need to download {len(files_to_download)} files...")
    
    for i, file in enumerate(files_to_download):
        print(f"Downloading {i+1}/{len(files_to_download)}: {file.filename} ({file.size} bytes)")
        _download_single_file(file)
            
    print("All files downloaded successfully.")

def _download_single_file(file):
    if file.local and os.path.dirname(file.local) != "":
        os.makedirs(os.path.dirname(file.local), exist_ok=True)
    
    chunk_size = 1024 * 1024  # 1MB chunks
    downloaded = 0
    failed = False
    
    with open(file.local, 'wb') as f:
        while downloaded < file.size:
            remaining = file.size - downloaded
            read_size = min(chunk_size, remaining)

            chunk = file.read(read_size)
            if not chunk:
                break
            
            f.write(chunk)
            downloaded += len(chunk)
            
            if downloaded % (10 * 1024 * 1024) == 0:
                percent = (downloaded / file.size) * 100
                print(f"  Progress: {percent:.1f}% ({downloaded}/{file.size} bytes)")
                
    if failed:
        print(f"Failed to download {file.filename}")
    else:
        if file.is_executable:
            os.chmod(file.local, 0o755)
        print(f"✓ Downloaded {file.filename}")

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
