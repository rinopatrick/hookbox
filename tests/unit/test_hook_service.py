"""Unit tests for hook service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from hookbox.adapters.database import RequestData
from hookbox.exceptions import NotFoundError
from hookbox.services.hook_service import HookService, generate_hook_id

if TYPE_CHECKING:
    from hookbox.adapters.database import Database


@pytest_asyncio.fixture
def svc(db: Database) -> HookService:
    """Create a HookService with test database."""
    return HookService(db, base_url="http://localhost:8080")


def test_generate_hook_id() -> None:
    """Hook ID generation produces 12-char hex strings."""
    hook_id = generate_hook_id()
    assert len(hook_id) == 12
    assert all(c in "0123456789abcdef" for c in hook_id)


def test_generate_hook_id_unique() -> None:
    """Consecutive hook IDs are unique."""
    ids = {generate_hook_id() for _ in range(100)}
    assert len(ids) == 100


@pytest.mark.asyncio
async def test_create_hook(svc: HookService) -> None:
    """Creating a hook returns a valid response with URL."""
    result = await svc.create_hook(name="test")
    assert result.id
    assert len(result.id) == 12
    assert result.url == f"http://localhost:8080/hook/{result.id}"


@pytest.mark.asyncio
async def test_get_hook(svc: HookService) -> None:
    """Getting a hook returns its metadata."""
    created = await svc.create_hook(name="myhook")
    hook = await svc.get_hook(created.id)
    assert hook["id"] == created.id


@pytest.mark.asyncio
async def test_delete_hook(svc: HookService) -> None:
    """Deleting a hook removes it."""
    created = await svc.create_hook()
    await svc.delete_hook(created.id)
    with pytest.raises(NotFoundError):
        await svc.get_hook(created.id)


@pytest.mark.asyncio
async def test_capture_request(svc: HookService) -> None:
    """Capturing a request stores and returns it."""
    created = await svc.create_hook()
    request_data = RequestData(
        hook_id=created.id,
        method="POST",
        path="/webhook",
        query_string="event=push",
        headers={"x-github-event": "push"},
        body='{"ref": "refs/heads/main"}',
        content_type="application/json",
        source_ip="192.168.1.1",
    )
    stored = await svc.capture_request(request_data)
    assert stored["method"] == "POST"
    assert stored["path"] == "/webhook"
    assert stored["source_ip"] == "192.168.1.1"


@pytest.mark.asyncio
async def test_capture_request_hook_not_found(svc: HookService) -> None:
    """Capturing a request for a non-existent hook raises NotFoundError."""
    request_data = RequestData(
        hook_id="nonexistent",
        method="GET",
        path="/",
        query_string="",
        headers={},
        body="",
        content_type="",
        source_ip="",
    )
    with pytest.raises(NotFoundError):
        await svc.capture_request(request_data)


@pytest.mark.asyncio
async def test_get_requests(svc: HookService) -> None:
    """Getting requests returns paginated results."""
    created = await svc.create_hook()
    for i in range(3):
        request_data = RequestData(
            hook_id=created.id,
            method="POST",
            path=f"/{i}",
            query_string="",
            headers={},
            body="",
            content_type="",
            source_ip="",
        )
        await svc.capture_request(request_data)

    requests, total = await svc.get_requests(created.id)
    assert total == 3
    assert len(requests) == 3


@pytest.mark.asyncio
async def test_delete_request(svc: HookService) -> None:
    """Deleting a single request removes it."""
    created = await svc.create_hook()
    request_data = RequestData(
        hook_id=created.id,
        method="POST",
        path="/",
        query_string="",
        headers={},
        body="delete me",
        content_type="",
        source_ip="",
    )
    stored = await svc.capture_request(request_data)
    await svc.delete_request(created.id, stored["id"])
    with pytest.raises(NotFoundError):
        await svc.get_request(created.id, stored["id"])
