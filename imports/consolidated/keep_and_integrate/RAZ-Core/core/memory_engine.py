"""
RAZ Core - Memory Engine
Handles all persistent memory: facts, sessions, projects, user profile.
Storage: SQLite (local-first, no cloud dependency)
"""

import sqlite3
import json
import os
import sys
import shutil
import glob
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_db_path() -> str:
    """
    Resolve a writable SQLite path for both source runs and packaged EXE runs.
    PyInstaller onefile extracts code to a temp folder, which is not suitable for
    persistent writable app data.
    """
    env_override = os.getenv("RAZ_MEMORY_DB", "").strip()
    if env_override:
        return os.path.abspath(os.path.expanduser(os.path.expandvars(env_override)))

    if getattr(sys, "frozen", False):
        local_app_data = os.getenv("LOCALAPPDATA", "")
        if local_app_data:
            return os.path.join(local_app_data, "RAZ-Core", "memory", "raz_memory.db")
        return os.path.join(os.path.dirname(sys.executable), "memory", "raz_memory.db")

    return os.path.join(BASE_DIR, "memory", "raz_memory.db")


DB_PATH = _resolve_db_path()


def _legacy_db_candidates() -> list:
    candidates = []

    # Explicit override path for one-off recovery.
    env_legacy = os.getenv("RAZ_LEGACY_DB", "").strip()
    if env_legacy:
        candidates.append(os.path.abspath(os.path.expanduser(os.path.expandvars(env_legacy))))

    # Common source-run location in this repo.
    candidates.append(os.path.join(BASE_DIR, "memory", "raz_memory.db"))

    # Folder near installed executable.
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), "memory", "raz_memory.db"))

        # Search likely OneDrive source trees for legacy RAZ-Core DBs.
        one_drive_root = os.getenv("OneDrive", "").strip()
        if not one_drive_root:
            user_profile = os.path.expanduser("~")
            guessed = os.path.join(user_profile, "OneDrive")
            if os.path.isdir(guessed):
                one_drive_root = guessed
        if one_drive_root and os.path.isdir(one_drive_root):
            pattern = os.path.join(one_drive_root, "**", "RAZ-Core", "memory", "raz_memory.db")
            try:
                for idx, found_path in enumerate(glob.iglob(pattern, recursive=True)):
                    candidates.append(found_path)
                    if idx >= 24:
                        break
            except Exception:
                pass

    # Remove duplicates while preserving order.
    seen = set()
    unique = []
    for p in candidates:
        ap = os.path.abspath(p)
        if ap not in seen:
            seen.add(ap)
            unique.append(ap)
    return unique


def _restore_legacy_db_if_needed():
    """
    If current DB is missing or tiny, restore from the largest available legacy DB.
    This protects users from appearing to lose entries after install path changes.
    """
    current_size = 0
    if os.path.exists(DB_PATH):
        try:
            current_size = os.path.getsize(DB_PATH)
        except OSError:
            current_size = 0

    # If DB already has meaningful size, assume it is valid.
    if current_size > 512000:
        return

    best_path = None
    best_size = current_size
    for candidate in _legacy_db_candidates():
        if not os.path.exists(candidate):
            continue
        if os.path.abspath(candidate) == os.path.abspath(DB_PATH):
            continue
        try:
            size = os.path.getsize(candidate)
        except OSError:
            continue
        if size > best_size:
            best_size = size
            best_path = candidate

    if best_path:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        shutil.copy2(best_path, DB_PATH)
        print(f"[MEMORY] Restored legacy DB from {best_path} -> {DB_PATH}")


def get_connection():
    _restore_legacy_db_if_needed()
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_memory():
    """Create all memory tables if they don't exist."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            source TEXT,
            confidence REAL DEFAULT 1.0,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            started_at TEXT,
            ended_at TEXT,
            mode TEXT DEFAULT 'chat',
            summary TEXT,
            decisions TEXT,
            action_items TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            domain TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ingested_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            file_hash TEXT UNIQUE NOT NULL,
            size_bytes INTEGER,
            content_preview TEXT,
            tags TEXT,
            ingested_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'normal',
            scheduled_for TEXT,
            completed_at TEXT,
            created_at TEXT,
            project TEXT
        )
    """)

    conn.commit()
    conn.close()
    print(f"[MEMORY] Database initialized at {DB_PATH}")


# --- FACTS ---

def save_fact(category: str, key: str, value: str, source: str = "user", confidence: float = 1.0):
    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM facts WHERE category=? AND key=?", (category, key))
    existing = c.fetchone()
    if existing:
        c.execute(
            "UPDATE facts SET value=?, source=?, confidence=?, updated_at=? WHERE id=?",
            (value, source, confidence, now, existing["id"])
        )
    else:
        c.execute(
            "INSERT INTO facts (category, key, value, source, confidence, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (category, key, value, source, confidence, now, now)
        )
    conn.commit()
    conn.close()


def get_facts(category: str = None) -> list:
    conn = get_connection()
    c = conn.cursor()
    if category:
        c.execute("SELECT * FROM facts WHERE category=? ORDER BY category, key", (category,))
    else:
        c.execute("SELECT * FROM facts ORDER BY category, key")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def search_facts(query: str) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM facts WHERE key LIKE ? OR value LIKE ? OR category LIKE ?",
        (f"%{query}%", f"%{query}%", f"%{query}%")
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# --- SESSIONS ---

def start_session(session_id: str, mode: str = "chat") -> str:
    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO sessions (session_id, started_at, mode) VALUES (?,?,?)",
        (session_id, now, mode)
    )
    conn.commit()
    conn.close()
    return session_id


def end_session(session_id: str, summary: str = "", decisions: list = None, action_items: list = None):
    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE sessions SET ended_at=?, summary=?, decisions=?, action_items=? WHERE session_id=?",
        (
            now,
            summary,
            json.dumps(decisions or []),
            json.dumps(action_items or []),
            session_id
        )
    )
    conn.commit()
    conn.close()


def save_message(session_id: str, role: str, content: str):
    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)",
        (session_id, role, content, now)
    )
    conn.commit()
    conn.close()


def get_session_messages(session_id: str) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT role, content, timestamp FROM messages WHERE session_id=? ORDER BY id ASC",
        (session_id,)
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_recent_sessions(limit: int = 10) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# --- PROJECTS ---

def save_project(name: str, description: str = "", domain: str = "", status: str = "active", notes: str = ""):
    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM projects WHERE name=?", (name,))
    existing = c.fetchone()
    if existing:
        c.execute(
            "UPDATE projects SET description=?, domain=?, status=?, notes=?, updated_at=? WHERE id=?",
            (description, domain, status, notes, now, existing["id"])
        )
    else:
        c.execute(
            "INSERT INTO projects (name, description, domain, status, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (name, description, domain, status, notes, now, now)
        )
    conn.commit()
    conn.close()


def get_projects(status: str = None) -> list:
    conn = get_connection()
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM projects WHERE status=? ORDER BY name", (status,))
    else:
        c.execute("SELECT * FROM projects ORDER BY name")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# --- TASKS ---

def save_task(title: str, description: str = "", priority: str = "normal",
              scheduled_for: str = None, project: str = None) -> int:
    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO tasks (title, description, priority, scheduled_for, created_at, project) VALUES (?,?,?,?,?,?)",
        (title, description, priority, scheduled_for, now, project)
    )
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_tasks(status: str = "pending") -> list:
    conn = get_connection()
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM tasks WHERE status=? ORDER BY priority, created_at", (status,))
    else:
        c.execute("SELECT * FROM tasks ORDER BY priority, created_at")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def complete_task(task_id: int):
    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE tasks SET status='completed', completed_at=? WHERE id=?", (now, task_id))
    conn.commit()
    conn.close()


def get_task_by_id(task_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def log_followup_issue(user_request: str, reason: str, context: str = "",
                       source_device: str = "unknown", priority: str = "high") -> dict:
    """
    Create a durable follow-up task whenever RAZ could not complete an action.
    This is designed to be synced between devices by exporting/importing task bundles.
    """
    user_request = (user_request or "").strip() or "(no request text captured)"
    reason = (reason or "incomplete execution").strip()
    context = (context or "").strip()
    title = f"[FOLLOW-UP] {user_request[:90]}"
    description = (
        f"Reason: {reason}\n"
        f"Source Device: {source_device}\n"
        f"Context: {context}\n"
        f"Captured: {datetime.now().isoformat()}"
    )

    task_id = save_task(
        title=title,
        description=description,
        priority=priority,
        project="followups"
    )

    # Store a compact memory fact for quick recall/search.
    save_fact(
        "followups",
        f"task_{task_id}",
        f"{reason} | request={user_request[:180]} | device={source_device}",
        source="system"
    )

    return {
        "task_id": task_id,
        "title": title,
        "reason": reason,
        "source_device": source_device,
    }


def get_followup_tasks(status: str = "pending", limit: int = 50) -> list:
    conn = get_connection()
    c = conn.cursor()
    if status:
        c.execute(
            """
            SELECT * FROM tasks
            WHERE project='followups' AND status=?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (status, limit),
        )
    else:
        c.execute(
            """
            SELECT * FROM tasks
            WHERE project='followups'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def export_sync_bundle(file_path: str) -> dict:
    """Export pending follow-up tasks and recent facts for PC/tablet sync."""
    payload = {
        "exported_at": datetime.now().isoformat(),
        "followup_tasks": get_followup_tasks(status="pending", limit=500),
        "followup_facts": get_facts("followups"),
    }
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return {
        "ok": True,
        "path": file_path,
        "tasks": len(payload["followup_tasks"]),
        "facts": len(payload["followup_facts"]),
    }


def import_sync_bundle(file_path: str) -> dict:
    """Import follow-up tasks from another device without duplicating exact matches."""
    if not os.path.exists(file_path):
        return {"ok": False, "error": f"File not found: {file_path}"}

    with open(file_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    incoming_tasks = payload.get("followup_tasks", [])
    incoming_facts = payload.get("followup_facts", [])

    conn = get_connection()
    c = conn.cursor()

    added_tasks = 0
    for t in incoming_tasks:
        title = t.get("title", "")
        description = t.get("description", "")
        c.execute(
            "SELECT id FROM tasks WHERE title=? AND description=? AND project='followups'",
            (title, description),
        )
        if c.fetchone() is None:
            c.execute(
                """
                INSERT INTO tasks (title, description, status, priority, scheduled_for, completed_at, created_at, project)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    title,
                    description,
                    t.get("status", "pending"),
                    t.get("priority", "high"),
                    t.get("scheduled_for"),
                    t.get("completed_at"),
                    t.get("created_at") or datetime.now().isoformat(),
                    "followups",
                ),
            )
            added_tasks += 1

    conn.commit()
    conn.close()

    added_facts = 0
    for fct in incoming_facts:
        category = fct.get("category", "followups")
        key = fct.get("key", "")
        value = fct.get("value", "")
        if not key:
            continue
        save_fact(category, key, value, source=fct.get("source", "sync"))
        added_facts += 1

    return {
        "ok": True,
        "path": file_path,
        "tasks_added": added_tasks,
        "facts_processed": added_facts,
    }


# --- INGESTED FILES ---

def record_ingested_file(filename: str, filepath: str, file_hash: str,
                          size_bytes: int, content_preview: str = "", tags: list = None):
    now = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM ingested_files WHERE file_hash=?", (file_hash,))
    existing = c.fetchone()
    if existing:
        conn.close()
        return False, "duplicate"
    c.execute(
        "INSERT INTO ingested_files (filename, filepath, file_hash, size_bytes, content_preview, tags, ingested_at) VALUES (?,?,?,?,?,?,?)",
        (filename, filepath, file_hash, size_bytes, content_preview[:500], json.dumps(tags or []), now)
    )
    conn.commit()
    conn.close()
    return True, "new"


def get_ingested_files() -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM ingested_files ORDER BY ingested_at DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def check_file_duplicate(file_hash: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM ingested_files WHERE file_hash=?", (file_hash,))
    found = c.fetchone() is not None
    conn.close()
    return found


if __name__ == "__main__":
    init_memory()
    print("[MEMORY] Test: saving a fact...")
    save_fact("profile", "name", "Ryan A. Wallace", source="system")
    save_fact("profile", "location", "Oklahoma City", source="system")
    save_fact("business", "hyperbaric_plus", "Wellness business focused on hyperbaric air therapy", source="system")
    save_fact("business", "hyperbarics_for_heroes", "Nonprofit supporting veterans and first responders with hyperbaric therapy", source="system")
    save_fact("business", "lonely_floater", "Artist development and media project", source="system")
    save_fact("business", "aveek_music", "Music artist project managed by Ryan", source="system")
    facts = get_facts("profile")
    print(f"[MEMORY] Facts loaded: {len(facts)}")
    for f in facts:
        print(f"  {f['category']}/{f['key']}: {f['value']}")
    print("[MEMORY] Engine verified.")
