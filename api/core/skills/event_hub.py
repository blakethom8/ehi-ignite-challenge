"""Per-run event hub — Layer-1 connection primitive.

See `docs/architecture/skill-runtime/STREAMING-AND-GATEWAY.md` for design + rationale.

One `EventHub` per active run. The runner publishes to the hub via
non-blocking `publish_nowait`; SSE endpoints subscribe and yield events
to connected browsers. Disk artifacts (transcript.jsonl) remain the
durable source of truth — the hub is the live fast path.

The hub lifecycle is owned by the worker pool: created when a run is
submitted, closed when the run terminates. After close, late
subscribers receive only the historical replay (which the SSE endpoint
reads from disk separately) and an immediate `stream_closed` sentinel.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator


# Reasonable upper bound for a single subscriber's queue. Chosen so a
# slow client can buffer ~30s of events at the deterministic-loop's
# current cadence without blocking publish — but small enough that a
# truly stuck client doesn't grow memory unbounded.
_DEFAULT_QUEUE_SIZE = 256


class EventHub:
    """Multi-subscriber, non-blocking pub/sub for one run.

    Publishers call `publish_nowait`. Subscribers call `subscribe` and
    iterate the resulting async generator. Subscribers that fall behind
    drop events at their own queue's tail; the runner keeps moving.

    Properties:
    - **Non-blocking publish.** Safe to call from sync code paths inside
      the runner. A slow subscriber never blocks the runner.
    - **Per-subscriber isolation.** One slow subscriber doesn't slow
      other subscribers.
    - **Idempotent close.** `close()` can be called multiple times;
      subscribers wake exactly once and the iterator completes.
    - **No replay.** Late subscribers do not receive past events from
      the hub. The SSE endpoint replays from `transcript.jsonl` before
      subscribing — that's the correct division of responsibility:
      hub for live, disk for durability.
    """

    def __init__(self, queue_size: int = _DEFAULT_QUEUE_SIZE) -> None:
        self._queue_size = queue_size
        self._subscribers: list[asyncio.Queue[dict[str, Any] | None]] = []
        self._closed = False
        self._lock = asyncio.Lock()

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish_nowait(self, event: dict[str, Any]) -> None:
        """Publish an event to every current subscriber.

        Synchronous and non-blocking. Drops the event for any subscriber
        whose queue is full; publishers do not block on slow consumers.
        Safe to call after `close()` — silently dropped.
        """
        if self._closed:
            return
        # Snapshot to avoid mutation during iteration; subscribe/unsubscribe
        # may race from other tasks.
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Slow subscriber — drop this event for them. Disk replay
                # covers correctness; this just degrades their live view.
                continue

    async def subscribe(
        self, *, maxsize: int | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield events published from this point forward.

        `maxsize` overrides the hub's default per-subscriber queue size —
        useful when one subscriber is known to be slow (e.g., a test
        validating drop-on-full behavior) and shouldn't consume more
        memory than necessary.

        On hub close (or if the hub was already closed), the iterator
        terminates cleanly.
        """
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(
            maxsize=maxsize if maxsize is not None else self._queue_size
        )
        async with self._lock:
            if self._closed:
                # Already closed — yield nothing, terminate.
                return
            self._subscribers.append(queue)

        try:
            while True:
                event = await queue.get()
                if event is None:  # close sentinel
                    return
                yield event
        finally:
            async with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

    async def close(self) -> None:
        """End-of-stream signal. All current subscribers complete."""
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            for queue in self._subscribers:
                # put_nowait(None) — the close sentinel. If a queue is
                # full of dropped events, force-clear one slot first; the
                # sentinel must be delivered.
                try:
                    queue.put_nowait(None)
                except asyncio.QueueFull:
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        queue.put_nowait(None)
                    except asyncio.QueueFull:
                        # Truly stuck; the subscriber's iterator will
                        # eventually time out on the next read.
                        pass
