"""WebSocket handler for real-time webhook inspection."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket  # noqa: TC002
from starlette.websockets import WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections grouped by hook ID."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    def connect(self, hook_id: str, websocket: WebSocket) -> None:
        """Register a WebSocket connection for a hook.

        Args:
            hook_id: Hook identifier to subscribe to.
            websocket: The WebSocket connection.
        """
        if hook_id not in self._connections:
            self._connections[hook_id] = []
        self._connections[hook_id].append(websocket)
        logger.info("WebSocket connected for hook %s", hook_id)

    def disconnect(self, hook_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection.

        Args:
            hook_id: Hook identifier.
            websocket: The WebSocket connection to remove.
        """
        if hook_id in self._connections:
            self._connections[hook_id] = [
                ws for ws in self._connections[hook_id] if ws is not websocket
            ]
            if not self._connections[hook_id]:
                del self._connections[hook_id]
        logger.info("WebSocket disconnected for hook %s", hook_id)

    async def broadcast(self, hook_id: str, event: dict[str, Any]) -> None:
        """Send an event to all WebSocket clients subscribed to a hook.

        Args:
            hook_id: Hook identifier.
            event: Event payload to broadcast.
        """
        connections = self._connections.get(hook_id, [])
        stale: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(event)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(hook_id, ws)

    @property
    def active_hooks(self) -> list[str]:
        """Return list of hook IDs with active connections."""
        return list(self._connections.keys())


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, hook_id: str) -> None:
    """Handle a WebSocket connection for real-time webhook inspection.

    Args:
        websocket: The incoming WebSocket connection.
        hook_id: Hook identifier to subscribe to.
    """
    await websocket.accept()
    manager.connect(hook_id, websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(hook_id, websocket)
    except Exception:
        manager.disconnect(hook_id, websocket)
