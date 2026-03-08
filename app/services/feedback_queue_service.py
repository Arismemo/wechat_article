from __future__ import annotations

import json
from dataclasses import dataclass
from time import sleep
from typing import Optional

from redis import Redis

from app.db.redis_client import get_redis_client
from app.services.queue_observability_service import QueueRuntimeSnapshot, mark_worker_heartbeat, read_queue_runtime
from app.settings import get_settings


@dataclass
class FeedbackSyncQueueJob:
    task_id: str
    day_offsets: list[int]
    operator: str
    raw_payload: str


@dataclass
class FeedbackSyncEnqueueResult:
    task_id: str
    enqueued: bool
    queue_depth: int
    day_offsets: list[int]


class FeedbackQueueService:
    def __init__(self, redis_client: Optional[Redis] = None) -> None:
        self.settings = get_settings()
        self.redis = redis_client or get_redis_client()

    def enqueue(
        self,
        task_id: str,
        *,
        day_offsets: Optional[list[int]] = None,
        operator: Optional[str] = None,
    ) -> FeedbackSyncEnqueueResult:
        normalized_day_offsets = self._normalize_day_offsets(day_offsets)
        payload = json.dumps(
            {
                "task_id": task_id,
                "day_offsets": normalized_day_offsets,
                "operator": (operator or "").strip() or "feedback-sync",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        enqueued = bool(self.redis.sadd(self.settings.feedback_sync_pending_set_key, task_id))
        if enqueued:
            self.redis.lpush(self.settings.feedback_sync_queue_key, payload)
        queue_depth = int(self.redis.llen(self.settings.feedback_sync_queue_key))
        return FeedbackSyncEnqueueResult(
            task_id=task_id,
            enqueued=enqueued,
            queue_depth=queue_depth,
            day_offsets=normalized_day_offsets,
        )

    def pop_next(self) -> Optional[FeedbackSyncQueueJob]:
        payload = self.redis.brpoplpush(
            self.settings.feedback_sync_queue_key,
            self.settings.feedback_sync_processing_key,
            timeout=self.settings.feedback_sync_worker_poll_timeout_seconds,
        )
        if not isinstance(payload, str) or not payload:
            return None
        parsed = json.loads(payload)
        return FeedbackSyncQueueJob(
            task_id=str(parsed["task_id"]),
            day_offsets=self._normalize_day_offsets(parsed.get("day_offsets")),
            operator=(str(parsed.get("operator") or "").strip() or "feedback-sync"),
            raw_payload=payload,
        )

    def acknowledge(self, job: FeedbackSyncQueueJob) -> None:
        self.redis.lrem(self.settings.feedback_sync_processing_key, 0, job.raw_payload)
        self.redis.srem(self.settings.feedback_sync_pending_set_key, job.task_id)

    def requeue_processing_jobs(self) -> int:
        recovered = 0
        while True:
            payload = self.redis.rpoplpush(
                self.settings.feedback_sync_processing_key,
                self.settings.feedback_sync_queue_key,
            )
            if payload is None:
                break
            recovered += 1
        return recovered

    def idle_sleep(self) -> None:
        sleep(self.settings.feedback_sync_worker_idle_sleep_seconds)

    def mark_worker_heartbeat(self, current_task_id: Optional[str] = None) -> None:
        mark_worker_heartbeat(
            self.redis,
            heartbeat_key=self.settings.feedback_sync_worker_heartbeat_key,
            stale_after_seconds=self.settings.worker_heartbeat_stale_seconds,
            current_task_id=current_task_id,
        )

    def runtime_snapshot(self) -> QueueRuntimeSnapshot:
        return read_queue_runtime(
            self.redis,
            name="feedback",
            label="Phase 6 自动反馈",
            queue_key=self.settings.feedback_sync_queue_key,
            processing_key=self.settings.feedback_sync_processing_key,
            pending_key=self.settings.feedback_sync_pending_set_key,
            heartbeat_key=self.settings.feedback_sync_worker_heartbeat_key,
            stale_after_seconds=self.settings.worker_heartbeat_stale_seconds,
        )

    def _normalize_day_offsets(self, day_offsets: Optional[list[int]]) -> list[int]:
        items = day_offsets or self._default_day_offsets()
        normalized = sorted({int(value) for value in items if int(value) >= 0})
        return normalized or self._default_day_offsets()

    def _default_day_offsets(self) -> list[int]:
        values: list[int] = []
        for item in (self.settings.feedback_sync_day_offsets or "").split(","):
            normalized = item.strip()
            if not normalized:
                continue
            values.append(int(normalized))
        return values or [1, 3, 7]
