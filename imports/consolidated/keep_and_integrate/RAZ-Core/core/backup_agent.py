"""
RAZ Core - Backup Agent
Creates timestamped zip archives of folders.
Supports local destinations and OneDrive paths.
"""

import os
import zipfile
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from system.config_loader import load_config
    from system.storage_layout import get_backup_dir
except Exception:
    load_config = dict
    get_backup_dir = None


def _get_default_dest() -> str:
    """Return the configured backup destination or a default inside BASE_DIR."""
    try:
        cfg = load_config()
        if get_backup_dir is not None:
            return get_backup_dir(cfg)
        dest = cfg.get("backup_dest", "")
        if dest:
            return dest
    except Exception:
        pass
    return os.path.join(BASE_DIR, "backups")


def run_backup(source: str, dest: str = None) -> str:
    """
    Zip-compress 'source' (file or folder) and save to 'dest' directory.
    Returns a status string.
    """
    source = os.path.expandvars(os.path.expanduser(source.strip()))

    if not os.path.exists(source):
        return f"Source not found: {source}"

    dest_dir = (dest or _get_default_dest()).strip()
    os.makedirs(dest_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.basename(source.rstrip("/\\"))
    archive_name = f"{base_name}_backup_{ts}.zip"
    archive_path = os.path.join(dest_dir, archive_name)

    try:
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isfile(source):
                zf.write(source, base_name)
                file_count = 1
            else:
                file_count = 0
                for root, dirs, files in os.walk(source):
                    # Skip hidden dirs and __pycache__
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
                    for fname in files:
                        full = os.path.join(root, fname)
                        arcname = os.path.relpath(full, os.path.dirname(source))
                        zf.write(full, arcname)
                        file_count += 1

        size_mb = os.path.getsize(archive_path) / 1_000_000
        return (
            f"Backup complete.\n"
            f"  Source: {source}\n"
            f"  Archive: {archive_path}\n"
            f"  Files: {file_count} | Size: {size_mb:.2f} MB"
        )
    except Exception as e:
        return f"Backup failed: {e}"


def list_backups(dest: str = None) -> str:
    """List existing backups in the destination folder."""
    dest_dir = (dest or _get_default_dest()).strip()
    if not os.path.isdir(dest_dir):
        return f"No backup directory found at: {dest_dir}"
    archives = sorted(
        [f for f in os.listdir(dest_dir) if f.endswith(".zip")],
        reverse=True
    )
    if not archives:
        return f"No backups found in {dest_dir}"
    lines = [f"Backups in {dest_dir}:"]
    for name in archives[:20]:
        full = os.path.join(dest_dir, name)
        size_mb = os.path.getsize(full) / 1_000_000
        lines.append(f"  {name}  ({size_mb:.2f} MB)")
    return "\n".join(lines)
