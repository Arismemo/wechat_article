import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.db.redis_client import get_redis_client
from app.db.session import get_engine, get_session_factory
from app.models.system_setting import SystemSetting
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class SystemSettingsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "system-settings.db")
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
                "FEEDBACK_SYNC_PROVIDER": "disabled",
                "FEEDBACK_SYNC_DAY_OFFSETS": "1,3,7",
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

    def test_list_settings_returns_env_defaults(self) -> None:
        response = self.client.get("/api/v1/admin/settings", headers={"Authorization": "Bearer test-token"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 11)
        items = {item["key"]: item for item in body}
        self.assertEqual(items["phase4.write_model"]["effective_value"], "glm-5")
        self.assertEqual(items["phase4.review_model"]["default_value"], "glm-5-air")
        self.assertEqual(items["feedback.sync_provider"]["effective_value"], "disabled")
        self.assertEqual(items["feedback.sync_day_offsets"]["effective_value"], [1, 3, 7])
        self.assertFalse(items["phase4.auto_push_wechat_draft"]["has_override"])

    def test_update_and_reset_setting(self) -> None:
        update = self.client.put(
            "/api/v1/admin/settings/phase4.write_model",
            headers={"Authorization": "Bearer test-token"},
            json={"value": "glm-5x", "operator": "editor-a", "note": "切模型"},
        )

        self.assertEqual(update.status_code, 200)
        body = update.json()
        self.assertTrue(body["has_override"])
        self.assertEqual(body["stored_value"], "glm-5x")
        self.assertEqual(body["effective_value"], "glm-5x")

        session = self.Session()
        setting = session.query(SystemSetting).filter(SystemSetting.key == "phase4.write_model").one()
        self.assertEqual(setting.value, "glm-5x")
        session.close()

        reset = self.client.put(
            "/api/v1/admin/settings/phase4.write_model",
            headers={"Authorization": "Bearer test-token"},
            json={"reset_to_default": True, "operator": "editor-a"},
        )

        self.assertEqual(reset.status_code, 200)
        reset_body = reset.json()
        self.assertFalse(reset_body["has_override"])
        self.assertIsNone(reset_body["stored_value"])
        self.assertEqual(reset_body["effective_value"], "glm-5")

    def test_update_rejects_invalid_value(self) -> None:
        response = self.client.put(
            "/api/v1/admin/settings/feedback.sync_day_offsets",
            headers={"Authorization": "Bearer test-token"},
            json={"value": "1,-3"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("non-negative integers", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
