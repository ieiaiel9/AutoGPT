"""SQLite FTS5 full-text search memory store.

Extracted from AutoGPT permanent_memory/sqlite3_store.py.
Session-based memory with full-text search via SQLite's FTS5 extension.

Drop-in enhancement for RAZ-Core's memory_engine.py — add FTS5 search
alongside the existing facts/messages tables.
"""

import os
import sqlite3


class FTS5Memory:
    """Session-aware full-text search memory using SQLite FTS5."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.path.join(os.getcwd(), "memory", "fts_memory.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        try:
            self.conn = sqlite3.connect(self.db_path)
        except Exception:
            self.db_path = ":memory:"
            self.conn = sqlite3.connect(self.db_path)

        self.conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts "
            "USING FTS5(session, key, content)"
        )
        self.conn.commit()

        row = self.conn.execute("SELECT MAX(session) FROM memory_fts").fetchone()
        self.session_id = (row[0] or 0) + 1

    def _next_key(self) -> int:
        row = self.conn.execute(
            "SELECT MAX(key) FROM memory_fts WHERE session = ?",
            (self.session_id,)
        ).fetchone()
        return (int(row[0]) + 1) if row[0] is not None else 0

    def add(self, text: str) -> None:
        """Store text in the current session."""
        key = self._next_key()
        self.conn.execute(
            "INSERT INTO memory_fts(session, key, content) VALUES (?, ?, ?)",
            (self.session_id, key, text)
        )
        self.conn.commit()

    def search(self, query: str, limit: int = 10) -> list[str]:
        """Full-text search across all sessions. Returns matching content blocks."""
        # Escape special FTS5 characters
        safe_query = query.replace('"', '""')
        rows = self.conn.execute(
            'SELECT content FROM memory_fts WHERE memory_fts MATCH ? LIMIT ?',
            (f'"{safe_query}"', limit)
        ).fetchall()
        return [r[0] for r in rows]

    def get_session(self, session_id: int | None = None) -> list[str]:
        """Get all content from a session."""
        sid = session_id if session_id is not None else self.session_id
        rows = self.conn.execute(
            "SELECT content FROM memory_fts WHERE session = ? ORDER BY key",
            (sid,)
        ).fetchall()
        return [r[0] for r in rows]

    def delete(self, key: int, session_id: int | None = None) -> None:
        """Delete a specific memory entry."""
        sid = session_id if session_id is not None else self.session_id
        self.conn.execute(
            "DELETE FROM memory_fts WHERE session = ? AND key = ?",
            (sid, key)
        )
        self.conn.commit()

    def get_stats(self) -> dict:
        """Return basic stats about the memory store."""
        total = self.conn.execute("SELECT COUNT(*) FROM memory_fts").fetchone()[0]
        sessions = self.conn.execute(
            "SELECT COUNT(DISTINCT session) FROM memory_fts"
        ).fetchone()[0]
        return {"total_entries": total, "total_sessions": sessions, "current_session": self.session_id}

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()
