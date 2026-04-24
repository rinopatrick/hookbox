"""Integration tests for FastAPI routes."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from hookbox.api.routes import app, db as app_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db() -> None:
    """Ensure the app database is connected before each test."""
    if app_db._db is None:
        await app_db.connect()
    yield
    await app_db.close()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Create an async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    """Health endpoint returns healthy status."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_create_hook(client: AsyncClient) -> None:
    """Creating a hook returns ID and URL."""
    resp = await client.post("/hook")
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "url" in data
    assert len(data["id"]) == 12


@pytest.mark.asyncio
async def test_create_hook_with_name(client: AsyncClient) -> None:
    """Creating a hook with a name includes it in the response."""
    resp = await client.post("/hook?name=myhook")
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data


@pytest.mark.asyncio
async def test_catch_webhook_post(client: AsyncClient) -> None:
    """POST to a hook endpoint captures the request."""
    create_resp = await client.post("/hook")
    hook_id = create_resp.json()["id"]

    resp = await client.post(
        f"/hook/{hook_id}",
        json={"event": "test", "data": "hello"},
        headers={"X-Custom": "value"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_requests(client: AsyncClient) -> None:
    """GET requests for a hook returns stored requests."""
    create_resp = await client.post("/hook")
    hook_id = create_resp.json()["id"]

    await client.post(f"/hook/{hook_id}", json={"test": 1})
    await client.post(f"/hook/{hook_id}", json={"test": 2})

    resp = await client.get(f"/hook/{hook_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["requests"]) == 2


@pytest.mark.asyncio
async def test_catch_webhook_with_path(client: AsyncClient) -> None:
    """POST to a hook with sub-path captures the full path."""
    create_resp = await client.post("/hook")
    hook_id = create_resp.json()["id"]

    resp = await client.post(f"/hook/{hook_id}/sub/path", json={"deep": True})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_hook(client: AsyncClient) -> None:
    """Deleting a hook removes it."""
    create_resp = await client.post("/hook")
    hook_id = create_resp.json()["id"]

    resp = await client.delete(f"/hook/{hook_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_delete_request(client: AsyncClient) -> None:
    """Deleting a specific request removes it."""
    create_resp = await client.post("/hook")
    hook_id = create_resp.json()["id"]

    await client.post(f"/hook/{hook_id}", json={"to_delete": True})

    list_resp = await client.get(f"/hook/{hook_id}")
    request_id = list_resp.json()["requests"][0]["id"]

    resp = await client.delete(f"/hook/{hook_id}/{request_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Verify request is actually gone
    list_resp2 = await client.get(f"/hook/{hook_id}")
    assert list_resp2.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_nonexistent_request(client: AsyncClient) -> None:
    """Deleting a non-existent request returns 404."""
    create_resp = await client.post("/hook")
    hook_id = create_resp.json()["id"]

    resp = await client.delete(f"/hook/{hook_id}/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_request_invalid_hook(client: AsyncClient) -> None:
    """Deleting a request from a non-existent hook returns 404."""
    resp = await client.delete("/hook/nonexistent123/1")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_nonexistent_hook(client: AsyncClient) -> None:
    """Requesting a non-existent hook returns 404."""
    resp = await client.get("/hook/nonexistent123")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_webhook_captures_method(client: AsyncClient) -> None:
    """Various HTTP methods are captured correctly via catch-all."""
    create_resp = await client.post("/hook")
    hook_id = create_resp.json()["id"]

    await client.post(f"/hook/{hook_id}", json={"post": True})
    await client.put(f"/hook/{hook_id}", json={"put": True})
    await client.patch(f"/hook/{hook_id}", json={"patch": True})

    list_resp = await client.get(f"/hook/{hook_id}")
    methods = [r["method"] for r in list_resp.json()["requests"]]
    assert "POST" in methods
    assert "PUT" in methods
    assert "PATCH" in methods


@pytest.mark.asyncio
async def test_export_hook(client: AsyncClient) -> None:
    """Export returns hook metadata and all requests."""
    create_resp = await client.post("/hook")
    hook_id = create_resp.json()["id"]

    await client.post(f"/hook/{hook_id}", json={"test": 1})
    await client.post(f"/hook/{hook_id}", json={"test": 2})

    resp = await client.get(f"/hook/{hook_id}/export")
    assert resp.status_code == 200
    data = resp.json()
    assert "hook" in data
    assert "requests" in data
    assert data["hook"]["id"] == hook_id
    assert len(data["requests"]) == 2
    assert resp.headers.get("content-disposition", "").startswith("attachment")


@pytest.mark.asyncio
async def test_export_nonexistent_hook(client: AsyncClient) -> None:
    """Exporting a non-existent hook returns 404."""
    resp = await client.get("/hook/nonexistent123/export")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_replay_request(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replaying a request forwards it to a target URL."""
    from unittest.mock import AsyncMock

    create_resp = await client.post("/hook")
    hook_id = create_resp.json()["id"]

    await client.post(f"/hook/{hook_id}", json={"event": "test"})
    list_resp = await client.get(f"/hook/{hook_id}")
    request_id = list_resp.json()["requests"][0]["id"]

    mock_response = AsyncMock()
    mock_response.status_code = 201
    mock_response.headers = {"X-Replayed": "true"}
    mock_response.text = '{"ok": true}'

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.request = AsyncMock(return_value=mock_response)

    monkeypatch.setattr("hookbox.services.hook_service.httpx.AsyncClient", lambda **kwargs: mock_client)

    resp = await client.post(
        f"/hook/{hook_id}/{request_id}/replay",
        json={"target_url": "http://localhost:3000/webhook"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status_code"] == 201
    assert data["body"] == '{"ok": true}'
    mock_client.request.assert_awaited_once()


@pytest.mark.asyncio
async def test_replay_nonexistent_request(client: AsyncClient) -> None:
    """Replaying a non-existent request returns 404."""
    create_resp = await client.post("/hook")
    hook_id = create_resp.json()["id"]

    resp = await client.post(
        f"/hook/{hook_id}/99999/replay",
        json={"target_url": "http://localhost:3000/webhook"},
    )
    assert resp.status_code == 404
