from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Optional

from redis import Redis

from app.db.redis_client import get_redis_client
from app.services.queue_observability_service import QueueRuntimeSnapshot, mark_worker_heartbeat, read_queue_runtime
from app.settings import get_settings


@dataclass
class TopicFetchEnqueueResult:
    source_id: str
    enqueued: bool
    queue_depth: int


class TopicFetchQueueService:
    def __init__(self, redis_client: Optional[Redis] = None) -> None:
        self.settings = get_settings()
        self.redis = redis_client or get_redis_client()

    def enqueue(self, source_id: str) -> TopicFetchEnqueueResult:
        enqueued = bool(self.redis.sadd(self.settings.topic_fetch_pending_set_key, source_id))
        if enqueued:
            self.redis.lpush(self.settings.topic_fetch_queue_key, source_id)
        queue_depth = int(self.redis.llen(self.settings.topic_fetch_queue_key))
        return TopicFetchEnqueueResult(source_id=source_id, enqueued=enqueued, queue_depth=queue_depth)

    def pop_next(self) -> Optional[str]:
        source_id = self.redis.brpoplpush(
            self.settings.topic_fetch_queue_key,
            self.settings.topic_fetch_processing_key,
            timeout=self.settings.topic_fetch_worker_poll_timeout_seconds,
        )
        return source_id if isinstance(source_id, str) and source_id else None

    def acknowledge(self, source_id: str) -> None:
        self.redis.lrem(self.settings.topic_fetch_processing_key, 0, source_id)
        self.redis.srem(self.settings.topic_fetch_pending_set_key, source_id)

    def requeue_processing_jobs(self) -> int:
        recovered = 0
        while True:
            source_id = self.redis.rpoplpush(self.settings.topic_fetch_processing_key, self.settings.topic_fetch_queue_key)
            if source_id is None:
                break
            recovered += 1
        return recovered

    def idle_sleep(self) -> None:
        sleep(self.settings.topic_fetch_worker_idle_sleep_seconds)

    def mark_worker_heartbeat(self, current_source_id: Optional[str] = None) -> None:
        mark_worker_heartbeat(
            self.redis,
            heartbeat_key=self.settings.topic_fetch_worker_heartbeat_key,
            stale_after_seconds=self.settings.worker_heartbeat_stale_seconds,
            current_task_id=current_source_id,
        )

    def runtime_snapshot(self) -> QueueRuntimeSnapshot:
        return read_queue_runtime(
            self.redis,
            name="topic_fetch",
            label="Topic Intelligence 抓取",
            queue_key=self.settings.topic_fetch_queue_key,
            processing_key=self.settings.topic_fetch_processing_key,
            pending_key=self.settings.topic_fetch_pending_set_key,
            heartbeat_key=self.settings.topic_fetch_worker_heartbeat_key,
            stale_after_seconds=self.settings.worker_heartbeat_stale_seconds,
        )
