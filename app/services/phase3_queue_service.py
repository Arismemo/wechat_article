from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Optional

from redis import Redis

from app.db.redis_client import get_redis_client
from app.services.queue_observability_service import QueueRuntimeSnapshot, mark_worker_heartbeat, read_queue_runtime
from app.settings import get_settings


@dataclass
class Phase3EnqueueResult:
    task_id: str
    enqueued: bool
    queue_depth: int


class Phase3QueueService:
    def __init__(self, redis_client: Optional[Redis] = None) -> None:
        self.settings = get_settings()
        self.redis = redis_client or get_redis_client()

    def enqueue(self, task_id: str) -> Phase3EnqueueResult:
        enqueued = bool(self.redis.sadd(self.settings.phase3_pending_set_key, task_id))
        if enqueued:
            self.redis.lpush(self.settings.phase3_queue_key, task_id)
        queue_depth = int(self.redis.llen(self.settings.phase3_queue_key))
        return Phase3EnqueueResult(task_id=task_id, enqueued=enqueued, queue_depth=queue_depth)

    def pop_next(self) -> Optional[str]:
        task_id = self.redis.brpoplpush(
            self.settings.phase3_queue_key,
            self.settings.phase3_processing_key,
            timeout=self.settings.phase3_worker_poll_timeout_seconds,
        )
        return task_id if isinstance(task_id, str) and task_id else None

    def acknowledge(self, task_id: str) -> None:
        self.redis.lrem(self.settings.phase3_processing_key, 0, task_id)
        self.redis.srem(self.settings.phase3_pending_set_key, task_id)

    def requeue_processing_jobs(self) -> int:
        recovered = 0
        while True:
            task_id = self.redis.rpoplpush(self.settings.phase3_processing_key, self.settings.phase3_queue_key)
            if task_id is None:
                break
            recovered += 1
        return recovered

    def idle_sleep(self) -> None:
        sleep(self.settings.phase3_worker_idle_sleep_seconds)

    def mark_worker_heartbeat(self, current_task_id: Optional[str] = None) -> None:
        mark_worker_heartbeat(
            self.redis,
            heartbeat_key=self.settings.phase3_worker_heartbeat_key,
            stale_after_seconds=self.settings.worker_heartbeat_stale_seconds,
            current_task_id=current_task_id,
        )

    def runtime_snapshot(self) -> QueueRuntimeSnapshot:
        return read_queue_runtime(
            self.redis,
            name="phase3",
            label="Phase 3 研究与 Brief",
            queue_key=self.settings.phase3_queue_key,
            processing_key=self.settings.phase3_processing_key,
            pending_key=self.settings.phase3_pending_set_key,
            heartbeat_key=self.settings.phase3_worker_heartbeat_key,
            stale_after_seconds=self.settings.worker_heartbeat_stale_seconds,
        )
