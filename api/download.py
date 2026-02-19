"""File download utilities for CDN content."""

import os
import time
import threading
import concurrent.futures

from .config import resolve_config


def human_bytes(num_bytes):
    """Format byte count as human-readable string."""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.3f} {unit}"
        size /= 1024


class Downloader:
    """Handles parallel file downloads from CDN."""

    def __init__(self, config=None):
        """Initialize downloader with configuration.
        
        Args:
            config: Optional config map for worker counts/chunk sizes/progress interval.
        """
        self._config = resolve_config(config)

    def download_files(self, files, destination, post_download_hook=None):
        """Download CDN files in parallel with optional checkpointing.

        Args:
            files: Iterable of CDN file objects to download.
            destination: Local root directory where files are written.
            post_download_hook: Optional callable(file_obj) for checkpointing per file.

        Returns:
            True on full success, False if any file failed.
        """
        max_workers = self._config["download_max_workers"]
        chunk_size = self._config["download_chunk_size"]
        progress_interval = self._config["download_progress_interval"]
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

        def _worker(file_obj):
            nonlocal finished_count
            success = self._download_single_file(
                file_obj, chunk_size, 
                print_lock=print_lock, 
                progress_interval=progress_interval
            )
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
                print(f"{finished_count}/{len(files_to_download)}: {status} {file_obj.filename} ({human_bytes(file_obj.size)})")
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

    def _download_single_file(self, file, chunk_size, print_lock=None, progress_interval=60):
        """Stream a single CDN file to disk with optional periodic progress.

        Args:
            file: CDN file object with read(), size, filename, is_executable.
            chunk_size: Read chunk size in bytes.
            print_lock: Optional threading.Lock for serialized prints.
            progress_interval: Seconds between progress logs; disable with -1/0.

        Returns:
            True if the file fully downloaded; False otherwise.
        """
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
                except Exception:
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
                    report = f"Progress {file.filename}: {percent:.1f}% ({human_bytes(downloaded)}/{human_bytes(file.size)})"
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
