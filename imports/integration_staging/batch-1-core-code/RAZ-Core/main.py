"""
RAZ Core v1.0 - Main Entry Point
Ryan A. Wallace's personal AI operating system.

Run: python main.py
     python main.py --mode meeting
     python main.py --overnight
     python main.py --ingest /path/to/files
     python main.py --restore
     python main.py --version
     python main.py --scan-dupes /path/to/dir
"""

import os
import sys
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from system.config_loader import load_config
from system.version_logger import init_version, get_version, print_changelog, log_update
from system.restore_system import create_backup, restore_backup, list_backups
import core.memory_engine as mem


def print_banner(version: str, mode: str = "chat"):
    print()
    print("=" * 60)
    print("  ██████╗  █████╗ ███████╗")
    print("  ██╔══██╗██╔══██╗╚══███╔╝")
    print("  ██████╔╝███████║  ███╔╝ ")
    print("  ██╔══██╗██╔══██║ ███╔╝  ")
    print("  ██║  ██║██║  ██║███████╗")
    print("  ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝")
    print()
    print(f"  RAZ Core v{version} - Personal AI Operating System")
    print(f"  Operator: Ryan A. Wallace | Mode: {mode.upper()}")
    print(f"  Oklahoma City | All domains active")
    print("=" * 60)
    print()


def run_chat(mode: str = "chat"):
    from core.chat import RAZChat
    raz = RAZChat()
    raz.mode = mode
    raz._refresh_system_prompt()
    raz.run()


def run_overnight():
    from modes.overnight_scheduler import run_overnight_cycle, get_morning_report
    print("[RAZ] Running overnight task cycle...")
    mem.init_memory()
    run_overnight_cycle()
    print("\n[RAZ] Morning Report:")
    print(get_morning_report())


def run_ingest(target_path: str):
    from ingestion.ingestor import ingest_file, ingest_directory
    mem.init_memory()
    if os.path.isfile(target_path):
        print(f"[RAZ] Ingesting file: {target_path}")
        result = ingest_file(target_path, memory_engine=mem)
        print(f"  [{result['status'].upper()}] {result['filename']}: {result['reason']}")
    elif os.path.isdir(target_path):
        print(f"[RAZ] Ingesting directory: {target_path}")
        results = ingest_directory(target_path, memory_engine=mem)
        ingested = sum(1 for r in results if r["status"] == "ingested")
        dupes = sum(1 for r in results if r["status"] == "duplicate")
        print(f"\n[RAZ] Done. {ingested} ingested, {dupes} duplicates.")
    else:
        print(f"[RAZ] Path not found: {target_path}")


def run_restore(backup_label: str = None):
    print("[RAZ] Running Emergency Restore System...")
    result = restore_backup(backup_label=backup_label)
    print(result)


def run_scan_dupes(target_path: str):
    from core.duplicate_detector import generate_duplicate_report
    mem.init_memory()
    print(f"[RAZ] Scanning for duplicates in: {target_path}")
    report = generate_duplicate_report(dirpath=target_path, memory_engine=mem)
    print(report)


def main():
    parser = argparse.ArgumentParser(
        description="RAZ Core - Personal AI Operating System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                      Start chat (default)
  python main.py --mode meeting       Start in meeting mode
  python main.py --mode build         Start in build mode
  python main.py --overnight          Run overnight task cycle
  python main.py --ingest /path/dir   Ingest files into memory
  python main.py --restore            Emergency restore last backup
  python main.py --scan-dupes /path   Scan directory for duplicates
  python main.py --backup             Create a manual backup
  python main.py --version            Show version and changelog
        """
    )
    parser.add_argument("--mode", default=None, help="Start in a specific mode: chat, meeting, research, build, overnight")
    parser.add_argument("--overnight", action="store_true", help="Run overnight task cycle")
    parser.add_argument("--ingest", metavar="PATH", help="Ingest a file or directory")
    parser.add_argument("--restore", action="store_true", help="Run emergency restore")
    parser.add_argument("--restore-label", metavar="LABEL", help="Restore a specific backup by label")
    parser.add_argument("--scan-dupes", metavar="PATH", help="Scan directory for duplicate files")
    parser.add_argument("--backup", action="store_true", help="Create a manual backup")
    parser.add_argument("--version", action="store_true", help="Show version and changelog")
    parser.add_argument("--list-backups", action="store_true", help="List available backups")

    args = parser.parse_args()

    # Initialize core systems
    config = load_config()
    version_info = init_version("1.0.0")
    version = version_info.get("version", "1.0.0")
    mem.init_memory()

    # Auto-backup on start if configured
    if config.get("auto_backup_on_start") and not any([
        args.overnight, args.ingest, args.restore, args.scan_dupes,
        args.backup, args.version, args.list_backups
    ]):
        try:
            create_backup()
        except Exception as e:
            print(f"[RAZ] Auto-backup warning: {e}")

    # Route to the right mode
    if args.version:
        print(f"\nRAZ Core v{version}")
        print_changelog(limit=10)
        return

    if args.list_backups:
        backups = list_backups()
        if not backups:
            print("[RAZ] No backups found.")
        else:
            print(f"\n[RAZ] Available backups ({len(backups)}):")
            for b in backups:
                print(f"  {b['label']} | v{b['version']} | {b['timestamp'][:16]} | {b.get('stable', True) and 'STABLE' or 'UNSTABLE'}")
        return

    if args.backup:
        backup_path = create_backup()
        print(f"[RAZ] Backup created: {backup_path}")
        return

    if args.overnight:
        mode_label = "overnight"
        print_banner(version, mode_label)
        run_overnight()
        return

    if args.ingest:
        print_banner(version, "ingestion")
        run_ingest(args.ingest)
        return

    if args.restore:
        run_restore(backup_label=args.restore_label)
        return

    if args.scan_dupes:
        print_banner(version, "scan")
        run_scan_dupes(args.scan_dupes)
        return

    # Default: launch chat
    mode = args.mode or config.get("default_mode", "chat")
    print_banner(version, mode)
    run_chat(mode=mode)


if __name__ == "__main__":
    main()
