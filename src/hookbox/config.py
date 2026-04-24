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
    cors_origins: str = Field(
        default="",
        description="Comma-separated allowed CORS origins (e.g. https://example.com,http://localhost:3000)",
    )

    @property
    def db_path(self) -> Path:
        """Extract filesystem path from database_url."""
        raw = self.database_url
        if raw.startswith("sqlite+aiosqlite://"):
            raw = raw[len("sqlite+aiosqlite://") :]
        # After the scheme, sqlite URLs have:
        #   /path      → relative path (strip leading /)
        #   //path     → absolute path (strip one /)
        #   /:memory:  → in-memory DB (strip leading /)
        if raw.startswith("//"):
            raw = raw[1:]  # keep one slash for absolute path
        elif raw.startswith("/"):
            raw = raw[1:]  # relative path or :memory:
        return Path(raw)

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
