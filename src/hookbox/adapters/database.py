"""SQLite database adapter with async support."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import aiosqlite

from hookbox.exceptions import NotFoundError, StorageError

if TYPE_CHECKING:
    from hookbox.config import Settings


@dataclass(frozen=True)
class RequestData:
    """Structured data for a captured webhook request."""

    hook_id: str
    method: str
    path: str
    query_string: str
    headers: dict[str, str]
    body: str
    content_type: str
    source_ip: str


logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS hooks (
    id TEXT PRIMARY KEY,
    name TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hook_id TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL DEFAULT '/',
    query_string TEXT NOT NULL DEFAULT '',
    headers TEXT NOT NULL DEFAULT '{}',
    body TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL DEFAULT '',
    source_ip TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL,
    FOREIGN KEY (hook_id) REFERENCES hooks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_requests_hook_id ON webhook_requests(hook_id);
CREATE INDEX IF NOT EXISTS idx_requests_received_at ON webhook_requests(received_at);
"""


class Database:
    """Async SQLite database adapter for Hookbox.

    Handles connection lifecycle, schema initialization, and all CRUD
    operations for hooks and webhook requests.
    """

    def __init__(self, settings: Settings) -> None:
        self._db_path = str(settings.db_path)
        self._ttl_hours = settings.request_ttl_hours
        self._max_body_size = settings.max_body_size
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open database connection and initialize schema."""
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        logger.info("Database initialized at %s", self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Return active database connection or raise."""
        if self._db is None:
            msg = "Database not connected. Call connect() first."
            raise StorageError(msg)
        return self._db

    async def create_hook(
        self, hook_id: str, name: str | None = None
    ) -> dict[str, Any]:
        """Insert a new hook into the database.

        Args:
            hook_id: Unique identifier for the hook.
            name: Optional human-readable name.

        Returns:
            Dictionary with hook data.
        """
        now = datetime.now().isoformat()
        await self.db.execute(
            "INSERT INTO hooks (id, name, created_at) VALUES (?, ?, ?)",
            (hook_id, name, now),
        )
        await self.db.commit()
        return {"id": hook_id, "name": name, "created_at": now}

    async def get_hook(self, hook_id: str) -> dict[str, Any]:
        """Retrieve a hook by ID.

        Args:
            hook_id: Hook identifier.

        Returns:
            Dictionary with hook data.

        Raises:
            NotFoundError: If hook does not exist.
        """
        cursor = await self.db.execute(
            "SELECT id, name, created_at FROM hooks WHERE id = ?",
            (hook_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            msg = f"Hook '{hook_id}' not found"
            raise NotFoundError(msg)
        return {"id": row[0], "name": row[1], "created_at": row[2]}

    async def delete_hook(self, hook_id: str) -> None:
        """Delete a hook and all its requests.

        Args:
            hook_id: Hook identifier.

        Raises:
            NotFoundError: If hook does not exist.
        """
        existing = await self.get_hook(hook_id)
        if existing is None:
            msg = f"Hook '{hook_id}' not found"
            raise NotFoundError(msg)
        await self.db.execute(
            "DELETE FROM webhook_requests WHERE hook_id = ?", (hook_id,)
        )
        await self.db.execute("DELETE FROM hooks WHERE id = ?", (hook_id,))
        await self.db.commit()

    async def store_request(self, request_data: RequestData) -> dict[str, Any]:
        """Store a captured webhook request.

        Args:
            request_data: Structured request capture data.

        Returns:
            Dictionary with the stored request data including its ID.
        """
        truncated_body = (
            request_data.body[: self._max_body_size]
            if len(request_data.body) > self._max_body_size
            else request_data.body
        )
        headers_json = json.dumps(request_data.headers)
        now = datetime.now().isoformat()

        cursor = await self.db.execute(
            """INSERT INTO webhook_requests
            (hook_id, method, path, query_string, headers, body, content_type, source_ip, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request_data.hook_id,
                request_data.method,
                request_data.path,
                request_data.query_string,
                headers_json,
                truncated_body,
                request_data.content_type,
                request_data.source_ip,
                now,
            ),
        )
        await self.db.commit()
        return {
            "id": cursor.lastrowid,
            "hook_id": request_data.hook_id,
            "method": request_data.method,
            "path": request_data.path,
            "query_string": request_data.query_string,
            "headers": request_data.headers,
            "body": truncated_body,
            "content_type": request_data.content_type,
            "source_ip": request_data.source_ip,
            "received_at": now,
        }

    async def get_requests(
        self,
        hook_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Retrieve paginated requests for a hook.

        Args:
            hook_id: Hook identifier.
            offset: Pagination offset.
            limit: Page size.

        Returns:
            Tuple of (request list, total count).
        """
        count_cursor = await self.db.execute(
            "SELECT COUNT(*) FROM webhook_requests WHERE hook_id = ?",
            (hook_id,),
        )
        total = (await count_cursor.fetchone())[0]

        cursor = await self.db.execute(
            """SELECT id, hook_id, method, path, query_string, headers, body,
                      content_type, source_ip, received_at
               FROM webhook_requests
               WHERE hook_id = ?
               ORDER BY received_at DESC
               LIMIT ? OFFSET ?""",
            (hook_id, limit, offset),
        )
        rows = await cursor.fetchall()
        requests = [self._row_to_dict(row) for row in rows]
        return requests, total

    async def get_request(self, hook_id: str, request_id: int) -> dict[str, Any]:
        """Retrieve a single request.

        Args:
            hook_id: Hook identifier.
            request_id: Request ID.

        Returns:
            Dictionary with request data.

        Raises:
            NotFoundError: If request does not exist.
        """
        cursor = await self.db.execute(
            """SELECT id, hook_id, method, path, query_string, headers, body,
                      content_type, source_ip, received_at
               FROM webhook_requests
               WHERE hook_id = ? AND id = ?""",
            (hook_id, request_id),
        )
        row = await cursor.fetchone()
        if row is None:
            msg = f"Request {request_id} not found for hook '{hook_id}'"
            raise NotFoundError(msg)
        return self._row_to_dict(row)

    async def delete_request(self, hook_id: str, request_id: int) -> None:
        """Delete a single request.

        Args:
            hook_id: Hook identifier.
            request_id: Request ID.

        Raises:
            NotFoundError: If request does not exist.
        """
        cursor = await self.db.execute(
            "DELETE FROM webhook_requests WHERE hook_id = ? AND id = ?",
            (hook_id, request_id),
        )
        await self.db.commit()
        if cursor.rowcount == 0:
            msg = f"Request {request_id} not found for hook '{hook_id}'"
            raise NotFoundError(msg)

    async def cleanup_expired(self) -> int:
        """Delete requests older than the configured TTL.

        Returns:
            Number of deleted requests.
        """
        cutoff = (datetime.now() - timedelta(hours=self._ttl_hours)).isoformat()
        cursor = await self.db.execute(
            "DELETE FROM webhook_requests WHERE received_at < ?",
            (cutoff,),
        )
        await self.db.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info("Cleaned up %d expired requests", deleted)
        return deleted

    @staticmethod
    def _row_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
        """Convert a database row tuple to a dictionary."""
        keys = [
            "id",
            "hook_id",
            "method",
            "path",
            "query_string",
            "headers",
            "body",
            "content_type",
            "source_ip",
            "received_at",
        ]
        result = dict(zip(keys, row, strict=True))
        if isinstance(result.get("headers"), str):
            result["headers"] = json.loads(result["headers"])
        return result
