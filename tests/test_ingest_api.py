import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles

import app.models  # noqa: F401
from app.db.base import Base
from app.db.redis_client import get_redis_client
from app.db.session import get_engine, get_session_factory
from app.settings import get_settings
from app.services.phase4_queue_service import Phase4EnqueueResult


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class IngestApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "ingest.db")
        self.env_patch = patch.dict(
            os.environ,
            {
                "APP_BASE_URL": "https://example.com",
                "API_BEARER_TOKEN": "test-token",
                "DATABASE_URL": f"sqlite+pysqlite:///{self.db_path}",
                "REDIS_URL": "redis://localhost:6379/0",
                "LLM_PROVIDER": "ZHIPU",
                "LLM_API_KEY": "test-key",
                "LLM_MODEL_ANALYZE": "glm-5",
                "LLM_MODEL_WRITE": "glm-5",
                "LLM_MODEL_REVIEW": "glm-5",
                "SEARCH_PROVIDER": "ZHIPU_MCP",
                "WECHAT_APP_ID": "wx-test",
                "WECHAT_APP_SECRET": "secret-test",
                "LOCAL_STORAGE_ROOT": self.temp_dir.name,
            },
            clear=False,
        )
        self.env_patch.start()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()

        self.engine = create_engine(f"sqlite+pysqlite:///{self.db_path}", future=True)
        Base.metadata.create_all(self.engine)

        from app.main import create_app

        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        self.temp_dir.cleanup()

    def test_ingest_link_auto_enqueues_phase4_for_ios_shortcuts(self) -> None:
        with patch(
            "app.api.ingest.Phase4QueueService.enqueue",
            return_value=Phase4EnqueueResult(task_id="unused", enqueued=True, queue_depth=1),
        ) as enqueue:
            response = self.client.post(
                "/api/v1/ingest/link",
                headers={"Authorization": "Bearer test-token"},
                json={"url": "https://mp.weixin.qq.com/s/phase4-auto"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["deduped"])
        self.assertEqual(body["dispatch_mode"], "phase4_enqueue")
        self.assertTrue(body["enqueued"])
        self.assertEqual(body["queue_depth"], 1)
        enqueue.assert_called_once()

    def test_ingest_link_keeps_admin_console_in_ingest_only_mode(self) -> None:
        with patch("app.api.ingest.Phase4QueueService.enqueue") as enqueue:
            response = self.client.post(
                "/api/v1/ingest/link",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "url": "https://mp.weixin.qq.com/s/admin-only",
                    "source": "admin-console",
                    "dispatch_mode": "auto",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["dispatch_mode"], "ingest_only")
        self.assertFalse(body["enqueued"])
        self.assertIsNone(body["queue_depth"])
        enqueue.assert_not_called()

    def test_ingest_link_deduped_shortcut_request_does_not_reenqueue(self) -> None:
        with patch(
            "app.api.ingest.Phase4QueueService.enqueue",
            return_value=Phase4EnqueueResult(task_id="unused", enqueued=True, queue_depth=1),
        ) as enqueue:
            first = self.client.post(
                "/api/v1/ingest/link",
                headers={"Authorization": "Bearer test-token"},
                json={"url": "https://mp.weixin.qq.com/s/deduped"},
            )
            second = self.client.post(
                "/api/v1/ingest/link",
                headers={"Authorization": "Bearer test-token"},
                json={"url": "https://mp.weixin.qq.com/s/deduped"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(first.json()["deduped"])
        self.assertTrue(first.json()["enqueued"])
        self.assertTrue(second.json()["deduped"])
        self.assertEqual(second.json()["dispatch_mode"], "phase4_enqueue")
        self.assertFalse(second.json()["enqueued"])
        self.assertIsNone(second.json()["queue_depth"])
        enqueue.assert_called_once()

    def test_ingest_shortcut_get_endpoint_accepts_query_key(self) -> None:
        with patch(
            "app.api.ingest.Phase4QueueService.enqueue",
            return_value=Phase4EnqueueResult(task_id="unused", enqueued=True, queue_depth=1),
        ) as enqueue:
            response = self.client.get(
                "/api/v1/ingest/shortcut",
                params={
                    "url": "https://mp.weixin.qq.com/s/shortcut-trigger",
                    "key": "test-token",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["dispatch_mode"], "phase4_enqueue")
        self.assertTrue(body["enqueued"])
        enqueue.assert_called_once()

    def test_ingest_shortcut_get_endpoint_rejects_invalid_key(self) -> None:
        response = self.client.get(
            "/api/v1/ingest/shortcut",
            params={
                "url": "https://mp.weixin.qq.com/s/shortcut-trigger",
                "key": "wrong-token",
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid shortcut key.")

    def test_ingest_shortcut_get_endpoint_rejects_invalid_url_value(self) -> None:
        response = self.client.get(
            "/api/v1/ingest/shortcut",
            params={
                "url": "文章链接",
                "key": "test-token",
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
