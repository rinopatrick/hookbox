"""Domain models for Hookbox."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Hook(BaseModel):
    """A webhook endpoint that captures incoming HTTP requests.

    Attributes:
        id: Unique hook identifier (short random string).
        created_at: Timestamp when the hook was created.
        name: Optional human-readable name for the hook.
    """

    id: str = Field(description="Unique hook identifier")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    name: str | None = Field(default=None, description="Optional human-readable name")


class WebhookRequest(BaseModel):
    """A captured incoming HTTP request to a hook.

    Attributes:
        id: Unique request identifier (auto-increment from DB).
        hook_id: The hook that received this request.
        method: HTTP method (GET, POST, etc.).
        path: Request path.
        query_string: Raw query string.
        headers: Request headers as key-value pairs.
        body: Request body as string (truncated if too large).
        content_type: Value of the Content-Type header.
        source_ip: Client IP address.
        received_at: Timestamp when the request was captured.
    """

    id: int = Field(description="Auto-increment request ID")
    hook_id: str = Field(description="Hook identifier that received this request")
    method: str = Field(description="HTTP method")
    path: str = Field(default="/", description="Request path")
    query_string: str = Field(default="", description="Raw query string")
    headers: dict[str, str] = Field(default_factory=dict, description="Request headers")
    body: str = Field(default="", description="Request body")
    content_type: str = Field(default="", description="Content-Type header value")
    source_ip: str = Field(default="", description="Client IP address")
    received_at: datetime = Field(
        default_factory=datetime.now, description="Capture timestamp"
    )


class HookCreateResponse(BaseModel):
    """Response returned when a new hook is created.

    Attributes:
        id: The generated hook ID.
        url: The full URL where webhooks should be sent.
    """

    id: str = Field(description="Generated hook ID")
    url: str = Field(description="Full webhook URL")


class HookUpdateRequest(BaseModel):
    """Payload for updating hook metadata and response configuration.

    Attributes:
        name: Optional human-readable name.
        response_status: HTTP status code to return for this hook.
        response_body: Body content to return.
        response_content_type: Content-Type of the response.
        response_headers: Custom response headers as key-value pairs.
    """

    name: str | None = Field(default=None, description="Human-readable name")
    response_status: int = Field(default=200, ge=100, le=599, description="HTTP status code")
    response_body: str = Field(default="", description="Response body content")
    response_content_type: str = Field(default="text/plain", description="Response Content-Type")
    response_headers: dict[str, str] = Field(
        default_factory=dict, description="Custom response headers"
    )


class ReplayRequest(BaseModel):
    """Payload for replaying a captured request to a target URL.

    Attributes:
        target_url: The URL to replay the captured request to.
    """

    target_url: str = Field(description="Target URL to replay the request to")


class ReplayResponse(BaseModel):
    """Response from replaying a captured request.

    Attributes:
        status_code: HTTP status code from the target.
        headers: Response headers from the target.
        body: Response body from the target.
    """

    status_code: int = Field(description="HTTP status from target")
    headers: dict[str, str] = Field(default_factory=dict, description="Response headers")
    body: str = Field(default="", description="Response body")


class ExportResponse(BaseModel):
    """Full export of a hook and all its captured requests.

    Attributes:
        hook: Hook metadata.
        requests: List of all captured requests.
    """

    hook: dict[str, Any] = Field(description="Hook metadata")
    requests: list[dict[str, Any]] = Field(default_factory=list, description="All requests")


class RequestListResponse(BaseModel):
    """Paginated list of webhook requests for a hook.

    Attributes:
        requests: List of captured webhook requests.
        total: Total number of requests for this hook.
        offset: Pagination offset.
        limit: Pagination limit.
    """

    requests: list[WebhookRequest] = Field(default_factory=list)
    total: int = Field(default=0)
    offset: int = Field(default=0)
    limit: int = Field(default=50)


class WSEvent(BaseModel):
    """Event broadcast to WebSocket clients.

    Attributes:
        type: Event type (new_request, hook_deleted, etc.).
        data: Event payload.
    """

    type: str = Field(description="Event type")
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload")
