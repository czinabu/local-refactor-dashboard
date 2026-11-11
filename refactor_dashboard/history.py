"""Local history of past refactors, stored in a SQLite file under the data dir."""

import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS refactors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    filename TEXT,
    language TEXT NOT NULL,
    instruction TEXT NOT NULL,
    model TEXT,
    original_code TEXT NOT NULL,
    refactored_code TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT ''
)
"""

_LIST_COLUMNS = "id, created_at, source, filename, language, instruction, model, summary"


@dataclass
class HistoryEntry:
    id: int
    created_at: str
    source: str
    filename: str | None
    language: str
    instruction: str
    model: str | None
    original_code: str
    refactored_code: str
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)


class HistoryStore:
    """Small wrapper around a SQLite database of refactor runs."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def add(
        self,
        *,
        source: str,
        language: str,
        instruction: str,
        original_code: str,
        refactored_code: str,
        summary: str = "",
        filename: str | None = None,
        model: str | None = None,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO refactors (created_at, source, filename, language, instruction, model,"
                " original_code, refactored_code, summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    created_at,
                    source,
                    filename,
                    language,
                    instruction,
                    model,
                    original_code,
                    refactored_code,
                    summary,
                ),
            )
            return cur.lastrowid

    def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Newest first, without the (possibly large) code bodies."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT {_LIST_COLUMNS} FROM refactors ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, entry_id: int) -> HistoryEntry | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM refactors WHERE id = ?", (entry_id,)).fetchone()
        return HistoryEntry(**dict(row)) if row else None

    def delete(self, entry_id: int) -> bool:
        with closing(self._connect()) as conn, conn:
            return conn.execute("DELETE FROM refactors WHERE id = ?", (entry_id,)).rowcount > 0

    def clear(self) -> int:
        with closing(self._connect()) as conn, conn:
            return conn.execute("DELETE FROM refactors").rowcount


def get_history_store() -> HistoryStore | None:
    """FastAPI dependency; returns None when history is turned off in settings."""
    settings = get_settings()
    if not settings.history_enabled:
        return None
    return HistoryStore(settings.history_db_path)
