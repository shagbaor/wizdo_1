"""SQLite storage for link numbers, group settings, and processed messages.

All writes for one message happen inside a single "BEGIN IMMEDIATE"
transaction, which locks the database for writing. That makes number
allocation atomic: two links can never get the same number, even if two
copies of the bot (or two threads) write at the same moment.
"""

import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from links import DEFAULT_FORMAT, FoundLink

DUPLICATE_NEW = "new"  # a repeated URL gets a fresh number (default)
DUPLICATE_IGNORE = "ignore"  # a repeated URL is not numbered again
DUPLICATE_MODES = (DUPLICATE_NEW, DUPLICATE_IGNORE)

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id         INTEGER PRIMARY KEY,
    last_number     INTEGER NOT NULL DEFAULT 0,
    format          TEXT    NOT NULL DEFAULT '#{n} {url}',
    duplicate_mode  TEXT    NOT NULL DEFAULT 'new',
    delete_original INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    number      INTEGER NOT NULL,
    url         TEXT    NOT NULL,
    url_key     TEXT    NOT NULL,
    sender_id   INTEGER,
    message_id  INTEGER NOT NULL,
    created_at  TEXT    NOT NULL,
    UNIQUE (chat_id, number)
);
CREATE INDEX IF NOT EXISTS links_by_key ON links (chat_id, url_key);

CREATE TABLE IF NOT EXISTS processed_messages (
    chat_id     INTEGER NOT NULL,
    message_id  INTEGER NOT NULL,
    PRIMARY KEY (chat_id, message_id)
);
"""


@dataclass(frozen=True)
class ChatSettings:
    format: str
    duplicate_mode: str
    delete_original: bool


@dataclass(frozen=True)
class RecordedLink:
    url: str
    number: int
    is_new: bool  # False when duplicates are ignored and the URL already had a number


@dataclass(frozen=True)
class StoredLink:
    number: int
    url: str
    created_at: str


class Database:
    def __init__(self, path: str):
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)
        # isolation_level=None lets us control transactions explicitly.
        self._conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            # WAL + FULL sync: crash-safe writes that survive power loss.
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.execute("PRAGMA busy_timeout=10000")
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def integrity_ok(self) -> bool:
        with self._lock:
            row = self._conn.execute("PRAGMA quick_check").fetchone()
        return row is not None and row[0] == "ok"

    def _transaction(self):
        return _Transaction(self._conn, self._lock)

    @staticmethod
    def _ensure_chat(conn: sqlite3.Connection, chat_id: int) -> None:
        conn.execute("INSERT OR IGNORE INTO chats (chat_id) VALUES (?)", (chat_id,))

    # ----- recording links -------------------------------------------------

    def record_message(
        self,
        chat_id: int,
        message_id: int,
        sender_id: int | None,
        links: list[FoundLink],
    ) -> list[RecordedLink] | None:
        """Number the links of one message.

        Returns None if this message was already processed (so it is never
        numbered twice), otherwise one RecordedLink per link, in order.
        """
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._transaction() as conn:
            already = conn.execute(
                "INSERT OR IGNORE INTO processed_messages (chat_id, message_id) VALUES (?, ?)",
                (chat_id, message_id),
            ).rowcount == 0
            if already:
                return None

            self._ensure_chat(conn, chat_id)
            row = conn.execute(
                "SELECT last_number, duplicate_mode FROM chats WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
            last_number, duplicate_mode = row["last_number"], row["duplicate_mode"]

            results: list[RecordedLink] = []
            for link in links:
                if duplicate_mode == DUPLICATE_IGNORE:
                    existing = conn.execute(
                        "SELECT number FROM links WHERE chat_id = ? AND url_key = ? "
                        "ORDER BY number LIMIT 1",
                        (chat_id, link.key),
                    ).fetchone()
                    if existing:
                        results.append(RecordedLink(link.url, existing["number"], False))
                        continue
                last_number += 1
                conn.execute(
                    "INSERT INTO links (chat_id, number, url, url_key, sender_id, message_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (chat_id, last_number, link.url, link.key, sender_id, message_id, now),
                )
                results.append(RecordedLink(link.url, last_number, True))

            conn.execute(
                "UPDATE chats SET last_number = ? WHERE chat_id = ?", (last_number, chat_id)
            )
            return results

    # ----- reading ---------------------------------------------------------

    def count(self, chat_id: int) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM links WHERE chat_id = ?", (chat_id,)
            ).fetchone()
        return row[0]

    def last_number(self, chat_id: int) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT last_number FROM chats WHERE chat_id = ?", (chat_id,)
            ).fetchone()
        return row[0] if row else 0

    def last_links(self, chat_id: int, limit: int) -> list[StoredLink]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT number, url, created_at FROM links WHERE chat_id = ? "
                "ORDER BY number DESC LIMIT ?",
                (chat_id, limit),
            ).fetchall()
        return [StoredLink(r["number"], r["url"], r["created_at"]) for r in reversed(rows)]

    def get_link(self, chat_id: int, number: int) -> StoredLink | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT number, url, created_at FROM links WHERE chat_id = ? AND number = ?",
                (chat_id, number),
            ).fetchone()
        return StoredLink(row["number"], row["url"], row["created_at"]) if row else None

    def search(self, chat_id: int, keyword: str, limit: int = 20) -> list[StoredLink]:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self._lock:
            rows = self._conn.execute(
                "SELECT number, url, created_at FROM links "
                "WHERE chat_id = ? AND url LIKE ? ESCAPE '\\' "
                "ORDER BY number DESC LIMIT ?",
                (chat_id, f"%{escaped}%", limit),
            ).fetchall()
        return [StoredLink(r["number"], r["url"], r["created_at"]) for r in reversed(rows)]

    # ----- settings --------------------------------------------------------

    def get_settings(self, chat_id: int) -> ChatSettings:
        with self._lock:
            row = self._conn.execute(
                "SELECT format, duplicate_mode, delete_original FROM chats WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        if row is None:
            return ChatSettings(DEFAULT_FORMAT, DUPLICATE_NEW, False)
        return ChatSettings(row["format"], row["duplicate_mode"], bool(row["delete_original"]))

    def _set(self, chat_id: int, column: str, value) -> None:
        # column names come from the fixed list below, never from users
        with self._transaction() as conn:
            self._ensure_chat(conn, chat_id)
            conn.execute(f"UPDATE chats SET {column} = ? WHERE chat_id = ?", (value, chat_id))

    def set_format(self, chat_id: int, template: str) -> None:
        self._set(chat_id, "format", template)

    def set_duplicate_mode(self, chat_id: int, mode: str) -> None:
        if mode not in DUPLICATE_MODES:
            raise ValueError(f"unknown duplicate mode: {mode}")
        self._set(chat_id, "duplicate_mode", mode)

    def set_delete_original(self, chat_id: int, enabled: bool) -> None:
        self._set(chat_id, "delete_original", int(enabled))

    # ----- maintenance -----------------------------------------------------

    def reset(self, chat_id: int) -> int:
        """Delete this group's links and restart numbering at 1. Returns links removed."""
        with self._transaction() as conn:
            removed = conn.execute("DELETE FROM links WHERE chat_id = ?", (chat_id,)).rowcount
            conn.execute("UPDATE chats SET last_number = 0 WHERE chat_id = ?", (chat_id,))
        return removed

    def migrate_chat(self, old_chat_id: int, new_chat_id: int) -> None:
        """Move data when Telegram upgrades a group to a supergroup (its ID changes)."""
        with self._transaction() as conn:
            if conn.execute("SELECT 1 FROM chats WHERE chat_id = ?", (new_chat_id,)).fetchone():
                return  # already migrated
            for table in ("chats", "links", "processed_messages"):
                conn.execute(
                    f"UPDATE {table} SET chat_id = ? WHERE chat_id = ?",
                    (new_chat_id, old_chat_id),
                )


class _Transaction:
    """Context manager: BEGIN IMMEDIATE ... COMMIT, or ROLLBACK on any error."""

    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock):
        self._conn = conn
        self._lock = lock

    def __enter__(self) -> sqlite3.Connection:
        self._lock.acquire()
        try:
            self._conn.execute("BEGIN IMMEDIATE")
        except BaseException:
            self._lock.release()
            raise
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                self._conn.execute("COMMIT")
            else:
                self._conn.execute("ROLLBACK")
        finally:
            self._lock.release()
