"""FastAPI application and route definitions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request, Response, WebSocket  # noqa: TC002
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from hookbox.adapters.database import Database, RequestData
from hookbox.api.websocket import manager as ws_manager, websocket_endpoint
from hookbox.config import Settings
from hookbox.exceptions import HookboxError, NotFoundError
from hookbox.logging import get_logger, setup_logging
from hookbox.services.cleanup import cleanup_task
from hookbox.services.hook_service import HookService

settings = Settings()
setup_logging("DEBUG" if settings.debug else "INFO")
logger = get_logger(__name__)

db = Database(settings)
hook_service = HookService(db, base_url=f"http://localhost:{settings.port}")

STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Manage application startup and shutdown lifecycle."""
    await db.connect()
    cleanup = asyncio.create_task(cleanup_task(db, settings.cleanup_interval_seconds))
    logger.info("Hookbox started on %s:%d", settings.host, settings.port)
    yield
    cleanup.cancel()
    await db.close()
    logger.info("Hookbox shut down")


app = FastAPI(
    title="Hookbox",
    description="Self-hosted webhook inspector",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(HookboxError)
async def hookbox_error_handler(_request: Request, exc: HookboxError) -> JSONResponse:
    """Handle application-specific errors."""
    status = 404 if isinstance(exc, NotFoundError) else 400
    return JSONResponse(status_code=status, content={"error": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation errors."""
    return JSONResponse(
        status_code=422, content={"error": "Validation failed", "details": str(exc)}
    )


# ── Health ────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    """Service health check endpoint."""
    return {"status": "healthy"}


# ── Hook Management ──────────────────────────────────────────────────


@app.post("/hook")
async def create_hook(name: str | None = Query(default=None)) -> dict[str, Any]:
    """Create a new webhook endpoint and return its ID and URL."""
    result = await hook_service.create_hook(name)
    return result.model_dump()


# ── WebSocket (must be registered before catch-all) ──────────────────


@app.websocket("/hook/{hook_id}/ws")
async def ws_hook(websocket: WebSocket, hook_id: str) -> None:
    """WebSocket endpoint for real-time webhook inspection."""
    await websocket_endpoint(websocket, hook_id)


# ── Hook-specific operations (before catch-all) ──────────────────────


@app.get("/hook/{hook_id}")
async def get_requests(
    hook_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """List stored webhook requests for a hook (paginated)."""
    requests, total = await hook_service.get_requests(hook_id, offset, limit)
    return {"requests": requests, "total": total, "offset": offset, "limit": limit}


@app.delete("/hook/{hook_id}")
async def delete_hook(hook_id: str) -> dict[str, str]:
    """Delete a hook and all its stored requests."""
    await hook_service.delete_hook(hook_id)
    await ws_manager.broadcast(
        hook_id, {"type": "hook_deleted", "data": {"hook_id": hook_id}}
    )
    return {"status": "deleted"}


# ── Webhook Catch-All ────────────────────────────────────────────────

CATCH_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


@app.api_route("/hook/{hook_id}/{path:path}", methods=CATCH_METHODS)
async def catch_webhook_with_path(
    request: Request, hook_id: str, path: str
) -> Response:
    """Catch any HTTP request with a sub-path to a hook endpoint."""
    return await _capture_and_broadcast(request, hook_id, f"/{path}")


@app.api_route("/hook/{hook_id}", methods=CATCH_METHODS)
async def catch_webhook(request: Request, hook_id: str) -> Response:
    """Catch any HTTP request to a hook endpoint, store it, and broadcast via WebSocket."""
    return await _capture_and_broadcast(request, hook_id, request.url.path)


async def _capture_and_broadcast(request: Request, hook_id: str, path: str) -> Response:
    """Capture request details, store, and broadcast to WebSocket clients."""
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8", errors="replace")

    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host",)}

    request_data = RequestData(
        hook_id=hook_id,
        method=request.method,
        path=path,
        query_string=str(request.query_params),
        headers=headers,
        body=body_str,
        content_type=request.headers.get("content-type", ""),
        source_ip=request.client.host if request.client else "",
    )

    stored = await hook_service.capture_request(request_data)

    event = {"type": "new_request", "data": stored}
    await ws_manager.broadcast(hook_id, event)

    return Response(status_code=200, content="ok")


# ── Static Frontend (must be last mount) ─────────────────────────────

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
