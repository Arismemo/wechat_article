from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from redis import Redis


@dataclass(frozen=True)
class QueueRuntimeSnapshot:
    name: str
    label: str
    queue_depth: int
    processing_depth: int
    pending_count: int
    last_seen_at: Optional[datetime]
    current_task_id: Optional[str]
    healthy: bool
    status: str
    stale_after_seconds: int


def mark_worker_heartbeat(
    redis_client: Redis,
    *,
    heartbeat_key: str,
    stale_after_seconds: int,
    current_task_id: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    redis_client.hset(
        heartbeat_key,
        mapping={
            "last_seen_at": now,
            "current_task_id": current_task_id or "",
        },
    )
    redis_client.expire(heartbeat_key, max(stale_after_seconds * 3, 30))


def read_queue_runtime(
    redis_client: Redis,
    *,
    name: str,
    label: str,
    queue_key: str,
    processing_key: str,
    pending_key: str,
    heartbeat_key: str,
    stale_after_seconds: int,
) -> QueueRuntimeSnapshot:
    queue_depth = int(redis_client.llen(queue_key))
    processing_depth = int(redis_client.llen(processing_key))
    pending_count = int(redis_client.scard(pending_key))
    raw_heartbeat = redis_client.hgetall(heartbeat_key) or {}

    last_seen_at = _parse_datetime(raw_heartbeat.get("last_seen_at"))
    current_task_id = (raw_heartbeat.get("current_task_id") or "").strip() or None
    healthy = bool(last_seen_at and (datetime.now(timezone.utc) - last_seen_at) <= timedelta(seconds=stale_after_seconds))

    if healthy and processing_depth > 0:
        status = "busy"
    elif healthy:
        status = "idle"
    elif queue_depth > 0 or processing_depth > 0:
        status = "stale"
    elif last_seen_at is None:
        status = "unknown"
    else:
        status = "offline"

    return QueueRuntimeSnapshot(
        name=name,
        label=label,
        queue_depth=queue_depth,
        processing_depth=processing_depth,
        pending_count=pending_count,
        last_seen_at=last_seen_at,
        current_task_id=current_task_id,
        healthy=healthy,
        status=status,
        stale_after_seconds=stale_after_seconds,
    )


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
