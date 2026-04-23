"""Background task for cleaning up expired webhook requests."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hookbox.adapters.database import Database

logger = logging.getLogger(__name__)


async def cleanup_task(db: Database, interval_seconds: int) -> None:
    """Periodically delete expired webhook requests.

    Args:
        db: Database adapter instance.
        interval_seconds: Seconds between cleanup runs.
    """
    logger.info("Starting cleanup task (interval=%ds)", interval_seconds)
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            deleted = await db.cleanup_expired()
            if deleted > 0:
                logger.info("Cleanup: removed %d expired requests", deleted)
        except asyncio.CancelledError:
            logger.info("Cleanup task cancelled")
            break
        except Exception:
            logger.exception("Cleanup task error")
            await asyncio.sleep(60)
