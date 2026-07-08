import asyncio
import logging
import sys

from app.config import settings
from app.db import get_conn
from app.services.compression import compress_stale_memories
from app.services.scoring import recompute_all_decay_scores

logger = logging.getLogger("palimpsest.scheduler")
logger.setLevel(logging.INFO)
if not logger.handlers:
    # Explicit handler: Python's logging module does nothing by default, and
    # Uvicorn only configures its own "uvicorn.*" loggers, not arbitrary ones —
    # without this, these log lines would silently never print anywhere.
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.propagate = False


def _run_maintenance_pass():
    """Runs synchronously — called via asyncio.to_thread so it doesn't block the event loop."""
    with get_conn() as conn:
        updated = recompute_all_decay_scores(conn)
        compressed = compress_stale_memories(conn)
    logger.info(
        "maintenance pass complete: rescored %d memories, created %d compressed group(s)",
        updated, len(compressed),
    )


async def maintenance_loop():
    """
    Runs decay rescoring and stale-memory compression on a fixed interval for the
    lifetime of the app, so 'forgetting' actually happens continuously in the
    background rather than only when someone manually clicks a dashboard button.
    The manual /memories/rescore and /memories/compress endpoints still exist too —
    useful for demos where you want to trigger it on-camera rather than wait.
    """
    while True:
        try:
            await asyncio.to_thread(_run_maintenance_pass)
        except Exception:
            # A failed maintenance pass should never crash the whole app — log and
            # retry on the next interval.
            logger.exception("maintenance pass failed")
        await asyncio.sleep(settings.maintenance_interval_seconds)
