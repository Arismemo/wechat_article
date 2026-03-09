from __future__ import annotations

import logging
from contextlib import contextmanager
from threading import Event, Thread
from typing import Callable, Iterator, Optional


HeartbeatFn = Callable[[Optional[str]], None]
_LOGGER = logging.getLogger("worker-heartbeat")


def heartbeat_refresh_interval(stale_after_seconds: int) -> float:
    if stale_after_seconds <= 0:
        return 10.0
    return max(5.0, min(20.0, stale_after_seconds / 3))


@contextmanager
def keep_worker_heartbeat(
    heartbeat: HeartbeatFn,
    *,
    current_task_id: Optional[str],
    interval_seconds: float,
    logger: Optional[logging.Logger] = None,
) -> Iterator[None]:
    stop_event = Event()
    log = logger or _LOGGER

    def refresh() -> None:
        try:
            heartbeat(current_task_id)
        except Exception:  # noqa: BLE001
            log.exception("worker heartbeat refresh failed for task %s", current_task_id or "unknown")

    def loop() -> None:
        while not stop_event.wait(interval_seconds):
            refresh()

    refresh()
    thread = Thread(target=loop, name="worker-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=max(interval_seconds, 0.1) + 0.5)
