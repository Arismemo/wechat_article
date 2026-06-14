from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app.db.redis_client import get_redis_client
from app.services.editorial_queue_service import EditorialEnqueueResult, EditorialQueueService
from app.settings import get_settings


TEST_ENV = {
    "APP_BASE_URL": "https://example.com",
    "API_BEARER_TOKEN": "test-token",
    "DATABASE_URL": "postgresql+psycopg://postgres:postgres@localhost:5432/wechat_artical",
    "REDIS_URL": "redis://localhost:6379/0",
    "LLM_PROVIDER": "ZHIPU",
    "LLM_API_KEY": "test-key",
    "LLM_MODEL_ANALYZE": "glm-5",
    "LLM_MODEL_WRITE": "glm-5",
    "LLM_MODEL_REVIEW": "glm-5",
    "SEARCH_PROVIDER": "ZHIPU_MCP",
    "WECHAT_APP_ID": "wx-test",
    "WECHAT_APP_SECRET": "secret-test",
}


class FakeRedis:
    def __init__(self) -> None:
        self.pending: set[str] = set()
        self.queue: list[str] = []
        self.processing: list[str] = []

    def sadd(self, key: str, value: str) -> int:
        del key
        if value in self.pending:
            return 0
        self.pending.add(value)
        return 1

    def lpush(self, key: str, value: str) -> None:
        del key
        self.queue.insert(0, value)

    def llen(self, key: str) -> int:
        del key
        return len(self.queue)

    def brpoplpush(self, source: str, destination: str, timeout: int):
        del source, destination, timeout
        if not self.queue:
            return None
        value = self.queue.pop()
        self.processing.insert(0, value)
        return value

    def lrem(self, key: str, count: int, value: str) -> None:
        del key, count
        self.processing = [item for item in self.processing if item != value]

    def srem(self, key: str, value: str) -> None:
        del key
        self.pending.discard(value)

    def rpoplpush(self, source: str, destination: str):
        del source, destination
        if not self.processing:
            return None
        value = self.processing.pop()
        self.queue.insert(0, value)
        return value


class KeyAwareFakeRedis:
    """Fake redis that tracks separate lists/sets per key name.

    Needed to assert the dead-letter list is a SEPARATE structure from the
    main queue, which the key-agnostic FakeRedis above cannot model.
    """

    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}
        self.sets: dict[str, set[str]] = {}

    def sadd(self, key: str, value: str) -> int:
        bucket = self.sets.setdefault(key, set())
        if value in bucket:
            return 0
        bucket.add(value)
        return 1

    def srem(self, key: str, value: str) -> None:
        self.sets.setdefault(key, set()).discard(value)

    def lpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).insert(0, value)

    def llen(self, key: str) -> int:
        return len(self.lists.get(key, []))

    def lrem(self, key: str, count: int, value: str) -> None:
        del count
        self.lists[key] = [item for item in self.lists.get(key, []) if item != value]

    def brpoplpush(self, source: str, destination: str, timeout: int):
        del timeout
        src = self.lists.get(source, [])
        if not src:
            return None
        value = src.pop()
        self.lists.setdefault(destination, []).insert(0, value)
        return value

    def rpoplpush(self, source: str, destination: str):
        src = self.lists.get(source, [])
        if not src:
            return None
        value = src.pop()
        self.lists.setdefault(destination, []).insert(0, value)
        return value


class EditorialQueueRetryDeadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {**TEST_ENV, "LOCAL_STORAGE_ROOT": self.temp_dir.name}, clear=False)
        self.env_patch.start()
        get_settings.cache_clear()
        get_redis_client.cache_clear()

    def tearDown(self) -> None:
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        self.temp_dir.cleanup()

    def test_requeue_for_retry_returns_job_to_queue_keeping_pending(self) -> None:
        redis = KeyAwareFakeRedis()
        service = EditorialQueueService(redis_client=redis)
        s = service.settings

        service.enqueue("task-1")
        service.pop_next()  # moves task-1 into processing

        self.assertEqual(redis.lists.get(s.editorial_processing_key), ["task-1"])

        service.requeue_for_retry("task-1")

        self.assertEqual(redis.lists.get(s.editorial_processing_key), [])
        self.assertEqual(redis.lists.get(s.editorial_queue_key), ["task-1"])
        # pending membership preserved so a concurrent enqueue stays deduplicated
        self.assertIn("task-1", redis.sets.get(s.editorial_pending_set_key, set()))
        # dead list untouched
        self.assertEqual(redis.lists.get(s.editorial_dead_key, []), [])

    def test_move_to_dead_uses_separate_dead_list(self) -> None:
        redis = KeyAwareFakeRedis()
        service = EditorialQueueService(redis_client=redis)
        s = service.settings

        service.enqueue("task-1")
        service.pop_next()

        service.move_to_dead("task-1", reason="llm_http_503")

        self.assertEqual(redis.lists.get(s.editorial_processing_key), [])
        self.assertEqual(redis.lists.get(s.editorial_queue_key, []), [])
        self.assertNotIn("task-1", redis.sets.get(s.editorial_pending_set_key, set()))
        # dead list is a separate structure holding the id
        self.assertEqual(redis.lists.get(s.editorial_dead_key), ["task-1"])
        self.assertNotEqual(s.editorial_dead_key, s.editorial_queue_key)


class EditorialQueueServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {**TEST_ENV, "LOCAL_STORAGE_ROOT": self.temp_dir.name}, clear=False)
        self.env_patch.start()
        get_settings.cache_clear()
        get_redis_client.cache_clear()

    def tearDown(self) -> None:
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        self.temp_dir.cleanup()

    def test_enqueue_is_deduplicated_and_acknowledged(self) -> None:
        redis = FakeRedis()
        service = EditorialQueueService(redis_client=redis)

        first = service.enqueue("task-1")
        second = service.enqueue("task-1")
        popped = service.pop_next()
        service.acknowledge("task-1")

        self.assertTrue(first.enqueued)
        self.assertFalse(second.enqueued)
        self.assertEqual(first.queue_depth, 1)
        self.assertEqual(popped, "task-1")
        self.assertEqual(redis.processing, [])
        self.assertEqual(redis.pending, set())

    def test_enqueue_result_is_editorial_enqueue_result(self) -> None:
        redis = FakeRedis()
        service = EditorialQueueService(redis_client=redis)
        result = service.enqueue("task-99")
        self.assertIsInstance(result, EditorialEnqueueResult)
        self.assertEqual(result.task_id, "task-99")
        self.assertTrue(result.enqueued)
        self.assertEqual(result.queue_depth, 1)

    def test_pop_next_returns_none_when_empty(self) -> None:
        redis = FakeRedis()
        service = EditorialQueueService(redis_client=redis)
        result = service.pop_next()
        self.assertIsNone(result)

    def test_requeue_processing_jobs_recovers_stuck_items(self) -> None:
        redis = KeyAwareFakeRedis()
        service = EditorialQueueService(redis_client=redis)
        s = service.settings

        service.enqueue("task-A")
        service.enqueue("task-B")
        service.pop_next()
        service.pop_next()

        # Both tasks are now in processing
        self.assertEqual(len(redis.lists.get(s.editorial_processing_key, [])), 2)
        self.assertEqual(len(redis.lists.get(s.editorial_queue_key, [])), 0)

        recovered = service.requeue_processing_jobs()

        self.assertEqual(recovered, 2)
        self.assertEqual(len(redis.lists.get(s.editorial_processing_key, [])), 0)
        self.assertEqual(len(redis.lists.get(s.editorial_queue_key, [])), 2)
