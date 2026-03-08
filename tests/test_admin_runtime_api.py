import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.db.redis_client import get_redis_client
from app.db.session import get_engine, get_session_factory
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class AdminRuntimeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "admin-runtime.db")
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
                "LLM_MODEL_REVIEW": "glm-5-air",
                "SEARCH_PROVIDER": "ZHIPU_MCP",
                "WECHAT_APP_ID": "wx-test",
                "WECHAT_APP_SECRET": "secret-test",
                "ADMIN_USERNAME": "admin",
                "ADMIN_PASSWORD": "secret-pass",
                "FEEDBACK_SYNC_PROVIDER": "http",
                "FEEDBACK_SYNC_HTTP_URL": "https://feedback.example.test/sync",
                "ALERT_WEBHOOK_URL": "https://hooks.example.test/notify",
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
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

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

    def test_runtime_status_returns_environment_and_alerts(self) -> None:
        response = self.client.get("/api/v1/admin/runtime-status", headers={"Authorization": "Bearer test-token"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        env_items = {item["key"]: item for item in body["environment"]}
        self.assertTrue(env_items["API_BEARER_TOKEN"]["configured"])
        self.assertTrue(env_items["API_BEARER_TOKEN"]["secret"])
        self.assertIsNone(env_items["API_BEARER_TOKEN"]["preview"])
        self.assertEqual(env_items["FEEDBACK_SYNC_HTTP_URL"]["preview"], "https://feedback.example.test")
        self.assertTrue(body["alerts"]["enabled"])
        self.assertEqual(body["alerts"]["destination_preview"], "https://hooks.example.test")

    def test_send_test_alert_calls_webhook(self) -> None:
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.raise_for_status.return_value = None

        with patch("app.services.alert_service.httpx.post", return_value=mock_response) as mocked_post:
            response = self.client.post(
                "/api/v1/admin/alerts/test",
                headers={"Authorization": "Bearer test-token"},
                json={"operator": "tester", "note": "phase7d smoke"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["sent"])
        self.assertEqual(body["destination_preview"], "https://hooks.example.test")
        mocked_post.assert_called_once()
        args, kwargs = mocked_post.call_args
        self.assertEqual(args[0], "https://hooks.example.test/notify")
        self.assertEqual(kwargs["json"]["event"], "phase7.test_alert")
        self.assertEqual(kwargs["json"]["operator"], "tester")


if __name__ == "__main__":
    unittest.main()
