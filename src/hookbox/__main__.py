"""Application entry point."""

from __future__ import annotations

import uvicorn

from hookbox.config import Settings


def main() -> None:
    """Run the Hookbox webhook inspector server."""
    settings = Settings()
    uvicorn.run(
        "hookbox.api.routes:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_config=None,
    )


if __name__ == "__main__":
    main()
