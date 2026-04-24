"""Hook service — business logic for hook and request operations."""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING, Any

import aiosqlite
import httpx

from hookbox.adapters.database import RequestData  # noqa: TC001
from hookbox.domain.models import HookCreateResponse

if TYPE_CHECKING:
    from hookbox.adapters.database import Database

logger = logging.getLogger(__name__)


def generate_hook_id() -> str:
    """Generate a short, URL-safe hook identifier.

    Returns:
        12-character hex string suitable for use in URLs.
    """
    return secrets.token_hex(6)


class HookService:
    """Business logic for hook and webhook request operations."""

    def __init__(self, db: Database, base_url: str = "http://localhost:8080") -> None:
        self._db = db
        self._base_url = base_url.rstrip("/")

    async def create_hook(self, name: str | None = None) -> HookCreateResponse:
        """Create a new webhook endpoint.

        Args:
            name: Optional human-readable name for the hook.

        Returns:
            HookCreateResponse with the generated ID and full URL.
        """
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            hook_id = generate_hook_id()
            try:
                await self._db.create_hook(hook_id, name)
                break
            except aiosqlite.IntegrityError:
                if attempt == max_attempts:
                    raise
                logger.warning("Hook ID collision, retrying (%d/%d)", attempt, max_attempts)
        url = f"{self._base_url}/hook/{hook_id}"
        logger.info("Created hook %s at %s", hook_id, url)
        return HookCreateResponse(id=hook_id, url=url)

    async def get_hook(self, hook_id: str) -> dict[str, Any]:
        """Retrieve hook metadata.

        Args:
            hook_id: Hook identifier.

        Returns:
            Hook data dictionary.

        Raises:
            NotFoundError: If hook does not exist.
        """
        return await self._db.get_hook(hook_id)

    async def update_hook(self, hook_id: str, **kwargs: Any) -> dict[str, Any]:
        """Update hook metadata and response configuration.

        Args:
            hook_id: Hook identifier.
            **kwargs: Fields to update.

        Returns:
            Updated hook data dictionary.

        Raises:
            NotFoundError: If hook does not exist.
        """
        return await self._db.update_hook(hook_id, **kwargs)

    async def delete_hook(self, hook_id: str) -> None:
        """Delete a hook and all its requests.

        Args:
            hook_id: Hook identifier.

        Raises:
            NotFoundError: If hook does not exist.
        """
        await self._db.delete_hook(hook_id)
        logger.info("Deleted hook %s", hook_id)

    async def capture_request(
        self, request_data: RequestData
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Capture and store an incoming webhook request.

        Args:
            request_data: Structured request capture data.

        Returns:
            Tuple of (stored request data, hook config dictionary).

        Raises:
            NotFoundError: If hook does not exist.
        """
        hook = await self._db.get_hook(request_data.hook_id)
        stored = await self._db.store_request(request_data)
        return stored, hook

    async def get_requests(
        self,
        hook_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated requests for a hook.

        Args:
            hook_id: Hook identifier.
            offset: Pagination offset.
            limit: Page size.

        Returns:
            Tuple of (request list, total count).

        Raises:
            NotFoundError: If hook does not exist.
        """
        await self._db.get_hook(hook_id)
        return await self._db.get_requests(hook_id, offset, limit)

    async def get_request(self, hook_id: str, request_id: int) -> dict[str, Any]:
        """Get a single request by ID.

        Args:
            hook_id: Hook identifier.
            request_id: Request ID.

        Returns:
            Request data dictionary.

        Raises:
            NotFoundError: If hook or request does not exist.
        """
        return await self._db.get_request(hook_id, request_id)

    async def delete_request(self, hook_id: str, request_id: int) -> None:
        """Delete a single request.

        Args:
            hook_id: Hook identifier.
            request_id: Request ID.

        Raises:
            NotFoundError: If request does not exist.
        """
        await self._db.delete_request(hook_id, request_id)

    async def replay_request(
        self, hook_id: str, request_id: int, target_url: str
    ) -> dict[str, Any]:
        """Replay a captured request to a target URL.

        Args:
            hook_id: Hook identifier.
            request_id: Request ID to replay.
            target_url: URL to send the replayed request to.

        Returns:
            Dictionary with status_code, headers, and body from target.

        Raises:
            NotFoundError: If hook or request does not exist.
        """
        req = await self._db.get_request(hook_id, request_id)
        headers = {k: v for k, v in req["headers"].items() if k.lower() not in ("host", "content-length")}
        body_bytes = req["body"].encode("utf-8") if req["body"] else None

        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.request(
                req["method"],
                target_url,
                headers=headers,
                content=body_bytes,
            )

        logger.info(
            "Replayed request %d from hook %s to %s -> %d",
            request_id,
            hook_id,
            target_url,
            response.status_code,
        )
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.text,
        }

    async def export_requests(
        self, hook_id: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Export all data for a hook.

        Args:
            hook_id: Hook identifier.

        Returns:
            Tuple of (hook metadata, all requests).

        Raises:
            NotFoundError: If hook does not exist.
        """
        hook = await self._db.get_hook(hook_id)
        requests = await self._db.get_all_requests(hook_id)
        return hook, requests
