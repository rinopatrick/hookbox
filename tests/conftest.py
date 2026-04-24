"""Shared pytest fixtures for Hookbox tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest_asyncio

from hookbox.adapters.database import Database
from hookbox.config import Settings
from hookbox.services.hook_service import HookService

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[Database]:
    """Create a temporary in-memory database for testing."""
    test_settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        request_ttl_hours=24,
        cleanup_interval_seconds=3600,
        max_body_size=1024,
    )
    database = Database(test_settings)
    await database.connect()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def hook_svc(db: Database) -> HookService:
    """Create a HookService instance with test database."""
    return HookService(db, base_url="http://localhost:8080")
