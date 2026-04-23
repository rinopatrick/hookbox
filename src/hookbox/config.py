"""Application configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Hookbox application settings loaded from environment variables.

    Attributes:
        host: Bind address for the HTTP server.
        port: Bind port for the HTTP server.
        debug: Enable auto-reload and verbose logging.
        database_url: SQLite connection string.
        request_ttl_hours: Hours before webhook requests are auto-deleted.
        cleanup_interval_seconds: Background cleanup task interval.
        max_body_size: Maximum stored request body size in bytes.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="HOOKBOX_",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", description="Server bind address")  # noqa: S104
    port: int = Field(default=8080, description="Server bind port")
    debug: bool = Field(default=False, description="Enable debug mode with auto-reload")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./hookbox.db",
        description="SQLite database URL",
    )
    request_ttl_hours: int = Field(
        default=24,
        description="Hours before webhook requests are auto-deleted",
        ge=1,
    )
    cleanup_interval_seconds: int = Field(
        default=300,
        description="Background cleanup task interval in seconds",
        ge=60,
    )
    max_body_size: int = Field(
        default=1_048_576,
        description="Maximum stored request body size in bytes (default 1MB)",
        ge=1024,
    )

    @property
    def db_path(self) -> Path:
        """Extract filesystem path from database_url."""
        raw = self.database_url.split("///")[-1]
        return Path(raw)
