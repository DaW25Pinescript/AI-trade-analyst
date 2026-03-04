"""
Per-run async progress queue registry.

Analyst nodes push ProgressEvent dicts to a registered queue as they complete.
Consumers (SSE endpoint, CLI --live) read from the queue to display live progress.

Usage — producer (analyst_nodes.py):
    from ..core.progress_store import push_event
    await push_event(run_id, {"type": "analyst_done", "stage": "phase1", ...})

Usage — consumer (SSE endpoint):
    queue = progress_store.register(run_id)
    event = await queue.get()
    progress_store.unregister(run_id)

Thread-safety: asyncio.Queue is not thread-safe, but this module is only used
within a single asyncio event loop per process, which is sufficient.
"""
import asyncio
from typing import Optional

# Registry: run_id → asyncio.Queue of event dicts
_queues: dict[str, asyncio.Queue] = {}


def register(run_id: str) -> asyncio.Queue:
    """Create and register an asyncio.Queue for the given run_id. Returns the queue."""
    q: asyncio.Queue = asyncio.Queue()
    _queues[run_id] = q
    return q


def get(run_id: str) -> Optional[asyncio.Queue]:
    """Return the registered queue for run_id, or None if not registered."""
    return _queues.get(run_id)


def unregister(run_id: str) -> None:
    """Remove the queue for run_id (called after consumer finishes reading)."""
    _queues.pop(run_id, None)


async def push_event(run_id: str, event: dict) -> None:
    """Push an event dict to the run's queue if one is registered. No-op otherwise."""
    q = _queues.get(run_id)
    if q is not None:
        await q.put(event)
