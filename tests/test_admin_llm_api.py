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


class AdminLLMApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "admin-llm.db")
        self.env_patch = patch.dict(
            os.environ,
            {
                "APP_BASE_URL": "https://example.com",
                "API_BEARER_TOKEN": "test-token",
                "DATABASE_URL": f"sqlite+pysqlite:///{self.db_path}",
                "REDIS_URL": "redis://localhost:6379/0",
                "LLM_PROVIDER": "ZHIPU",
                "LLM_API_BASE": "https://open.bigmodel.cn/api/coding/paas/v4",
                "LLM_API_KEY": "test-key-env",
                "LLM_MODEL_ANALYZE": "glm-5",
                "LLM_MODEL_WRITE": "glm-5",
                "LLM_MODEL_REVIEW": "glm-5-air",
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

    def test_get_llm_config_returns_env_default_provider(self) -> None:
        response = self.client.get("/api/v1/admin/llm-config", headers={"Authorization": "Bearer test-token"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["selection"]["active_provider_id"], "env-default")
        self.assertEqual(body["selection"]["analyze_model"], "glm-5")
        self.assertEqual(body["selection"]["write_model"], "glm-5")
        self.assertEqual(body["selection"]["review_model"], "glm-5-air")
        self.assertEqual(len(body["providers"]), 1)
        self.assertEqual(body["providers"][0]["provider_id"], "env-default")
        self.assertTrue(body["providers"][0]["has_api_key"])
        self.assertEqual(body["providers"][0]["models"], ["glm-5", "glm-5-air"])

    def test_put_llm_config_persists_provider_and_selection(self) -> None:
        response = self.client.put(
            "/api/v1/admin/llm-config",
            headers={"Authorization": "Bearer test-token"},
            json={
                "providers": [
                    {
                        "provider_id": "openrouter-main",
                        "vendor": "OPENROUTER",
                        "label": "OpenRouter 主线路",
                        "api_base": "https://openrouter.ai/api/v1",
                        "api_key": "sk-or-test",
                        "models": ["openai/gpt-4.1-mini", "openai/gpt-4.1"],
                    }
                ],
                "active_provider_id": "openrouter-main",
                "analyze_model": "openai/gpt-4.1-mini",
                "write_model": "openai/gpt-4.1",
                "review_model": "openai/gpt-4.1-mini",
                "operator": "tester",
                "note": "切到 openrouter",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["selection"]["active_provider_id"], "openrouter-main")
        self.assertEqual(body["selection"]["write_model"], "openai/gpt-4.1")
        self.assertEqual(body["providers"][0]["provider_id"], "openrouter-main")
        self.assertTrue(body["providers"][0]["has_api_key"])

        with self.Session() as session:
            rows = {item.key: item.value for item in session.query(SystemSetting).all()}
        self.assertEqual(rows["llm.active_provider"], "openrouter-main")
        self.assertEqual(rows["llm.analyze_model"], "openai/gpt-4.1-mini")
        self.assertEqual(rows["phase4.write_model"], "openai/gpt-4.1")
        self.assertEqual(rows["phase4.review_model"], "openai/gpt-4.1-mini")
        self.assertEqual(rows["llm.providers"][0]["provider_id"], "openrouter-main")
        self.assertEqual(rows["llm.providers"][0]["api_key"], "sk-or-test")

    def test_post_llm_test_uses_selected_provider(self) -> None:
        with self.Session() as session:
            session.add(SystemSetting(key="llm.providers", value=[{
                "provider_id": "custom-1",
                "vendor": "CUSTOM",
                "label": "自定义",
                "api_base": "https://example.test/v1",
                "api_key": "sk-custom",
                "models": ["model-a", "model-b"],
            }]))
            session.add(SystemSetting(key="llm.active_provider", value="custom-1"))
            session.add(SystemSetting(key="llm.analyze_model", value="model-a"))
            session.add(SystemSetting(key="phase4.write_model", value="model-b"))
            session.add(SystemSetting(key="phase4.review_model", value="model-a"))
            session.commit()

        with patch("app.services.llm_runtime_service.LLMService.complete_json", return_value={"ok": True, "message": "pong"}) as mocked_complete:
            response = self.client.post(
                "/api/v1/admin/llm-test",
                headers={"Authorization": "Bearer test-token"},
                json={"provider_id": "custom-1", "model": "model-b", "operator": "tester"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["provider_id"], "custom-1")
        self.assertEqual(body["model"], "model-b")
        self.assertEqual(body["response_payload"], {"ok": True, "message": "pong"})
        mocked_complete.assert_called_once()
        self.assertEqual(mocked_complete.call_args.kwargs["model"], "model-b")


if __name__ == "__main__":
    unittest.main()
