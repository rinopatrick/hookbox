"""Unit tests for database adapter."""

from __future__ import annotations

import datetime as dt

import pytest

from hookbox.adapters.database import Database, RequestData
from hookbox.config import Settings
from hookbox.exceptions import NotFoundError


@pytest.mark.asyncio
async def test_create_hook(db: Database) -> None:
    """Creating a hook stores it in the database."""
    result = await db.create_hook("abc123", name="test hook")
    assert result["id"] == "abc123"
    assert result["name"] == "test hook"
    assert result["created_at"] is not None


@pytest.mark.asyncio
async def test_get_hook(db: Database) -> None:
    """Getting a hook returns its data."""
    await db.create_hook("xyz789", name="my hook")
    result = await db.get_hook("xyz789")
    assert result["id"] == "xyz789"
    assert result["name"] == "my hook"


@pytest.mark.asyncio
async def test_get_hook_not_found(db: Database) -> None:
    """Getting a non-existent hook raises NotFoundError."""
    with pytest.raises(NotFoundError):
        await db.get_hook("nonexistent")


@pytest.mark.asyncio
async def test_delete_hook(db: Database) -> None:
    """Deleting a hook removes it from the database."""
    await db.create_hook("delme", name="to delete")
    await db.delete_hook("delme")
    with pytest.raises(NotFoundError):
        await db.get_hook("delme")


@pytest.mark.asyncio
async def test_store_and_get_request(db: Database) -> None:
    """Storing a request and retrieving it returns consistent data."""
    await db.create_hook("hook1")
    request_data = RequestData(
        hook_id="hook1",
        method="POST",
        path="/webhook",
        query_string="foo=bar",
        headers={"content-type": "application/json"},
        body='{"test": true}',
        content_type="application/json",
        source_ip="127.0.0.1",
    )
    stored = await db.store_request(request_data)
    assert stored["id"] is not None
    assert stored["method"] == "POST"
    assert stored["body"] == '{"test": true}'

    fetched = await db.get_request("hook1", stored["id"])
    assert fetched["method"] == "POST"
    assert fetched["headers"]["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_get_requests_paginated(db: Database) -> None:
    """Requests are returned in paginated form."""
    await db.create_hook("pagehook")
    for i in range(5):
        request_data = RequestData(
            hook_id="pagehook",
            method="POST",
            path=f"/test/{i}",
            query_string="",
            headers={},
            body="",
            content_type="",
            source_ip="",
        )
        await db.store_request(request_data)

    requests, total = await db.get_requests("pagehook", offset=0, limit=3)
    assert total == 5
    assert len(requests) == 3

    requests2, _ = await db.get_requests("pagehook", offset=3, limit=3)
    assert len(requests2) == 2


@pytest.mark.asyncio
async def test_delete_request(db: Database) -> None:
    """Deleting a single request removes it."""
    await db.create_hook("delreq")
    request_data = RequestData(
        hook_id="delreq",
        method="GET",
        path="/",
        query_string="",
        headers={},
        body="",
        content_type="",
        source_ip="",
    )
    stored = await db.store_request(request_data)
    await db.delete_request("delreq", stored["id"])
    with pytest.raises(NotFoundError):
        await db.get_request("delreq", stored["id"])


@pytest.mark.asyncio
async def test_cleanup_expired(db: Database) -> None:
    """Cleanup removes requests older than TTL."""
    test_settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        request_ttl_hours=1,
        cleanup_interval_seconds=3600,
        max_body_size=1024,
    )
    short_db = Database(test_settings)
    await short_db.connect()

    await short_db.create_hook("expirehook")
    request_data = RequestData(
        hook_id="expirehook",
        method="POST",
        path="/",
        query_string="",
        headers={},
        body="expired",
        content_type="",
        source_ip="",
    )
    await short_db.store_request(request_data)

    old_time = (dt.datetime.now() - dt.timedelta(hours=2)).isoformat()
    await short_db.db.execute(
        "UPDATE webhook_requests SET received_at = ? WHERE hook_id = ?",
        (old_time, "expirehook"),
    )
    await short_db.db.commit()

    deleted = await short_db.cleanup_expired()
    assert deleted >= 1
    await short_db.close()


@pytest.mark.asyncio
async def test_body_truncation(db: Database) -> None:
    """Request body is truncated if it exceeds max_body_size."""
    await db.create_hook("trunchook")
    long_body = "x" * 2048
    request_data = RequestData(
        hook_id="trunchook",
        method="POST",
        path="/",
        query_string="",
        headers={},
        body=long_body,
        content_type="",
        source_ip="",
    )
    stored = await db.store_request(request_data)
    assert len(stored["body"]) == 1024
