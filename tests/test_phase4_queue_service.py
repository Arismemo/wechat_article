import os
import tempfile
import unittest
from unittest.mock import patch

from app.db.redis_client import get_redis_client
from app.services.phase4_queue_service import Phase4QueueService
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
        self.pending = set()
        self.queue = []
        self.processing = []

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


class Phase4QueueServiceTests(unittest.TestCase):
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
        service = Phase4QueueService(redis_client=redis)

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
