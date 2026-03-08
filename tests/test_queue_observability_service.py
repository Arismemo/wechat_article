from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import TestCase

from app.services.queue_observability_service import mark_worker_heartbeat, read_queue_runtime


class FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.lists: dict[str, list[str]] = {}
        self.sets: dict[str, set[str]] = {}
        self.expire_calls: list[tuple[str, int]] = []

    def hset(self, key: str, mapping: dict[str, str]) -> None:
        self.hashes[key] = dict(mapping)

    def expire(self, key: str, seconds: int) -> None:
        self.expire_calls.append((key, seconds))

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def llen(self, key: str) -> int:
        return len(self.lists.get(key, []))

    def scard(self, key: str) -> int:
        return len(self.sets.get(key, set()))


class QueueObservabilityServiceTests(TestCase):
    def test_mark_worker_heartbeat_sets_fields_and_expiry(self) -> None:
        redis_client = FakeRedis()

        mark_worker_heartbeat(
            redis_client,
            heartbeat_key="phase4:worker:heartbeat",
            stale_after_seconds=60,
            current_task_id="task-123",
        )

        heartbeat = redis_client.hgetall("phase4:worker:heartbeat")
        self.assertIn("last_seen_at", heartbeat)
        self.assertEqual(heartbeat["current_task_id"], "task-123")
        self.assertEqual(redis_client.expire_calls, [("phase4:worker:heartbeat", 180)])

    def test_read_queue_runtime_reports_busy_and_stale(self) -> None:
        redis_client = FakeRedis()
        redis_client.lists["phase4:queue"] = ["a", "b"]
        redis_client.lists["phase4:processing"] = ["task-1"]
        redis_client.sets["phase4:pending"] = {"a", "b", "task-1"}
        redis_client.hashes["phase4:worker:heartbeat"] = {
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
            "current_task_id": "task-1",
        }

        busy = read_queue_runtime(
            redis_client,
            name="phase4",
            label="Phase 4",
            queue_key="phase4:queue",
            processing_key="phase4:processing",
            pending_key="phase4:pending",
            heartbeat_key="phase4:worker:heartbeat",
            stale_after_seconds=60,
        )

        self.assertEqual(busy.status, "busy")
        self.assertTrue(busy.healthy)
        self.assertEqual(busy.queue_depth, 2)
        self.assertEqual(busy.processing_depth, 1)
        self.assertEqual(busy.pending_count, 3)

        redis_client.hashes["phase4:worker:heartbeat"]["last_seen_at"] = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).isoformat()
        stale = read_queue_runtime(
            redis_client,
            name="phase4",
            label="Phase 4",
            queue_key="phase4:queue",
            processing_key="phase4:processing",
            pending_key="phase4:pending",
            heartbeat_key="phase4:worker:heartbeat",
            stale_after_seconds=60,
        )

        self.assertEqual(stale.status, "stale")
        self.assertFalse(stale.healthy)

