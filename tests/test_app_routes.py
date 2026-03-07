import os
import tempfile
import unittest
from importlib import import_module, reload
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db.redis_client import get_redis_client
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


class AppRouteTests(unittest.TestCase):
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

    def test_internal_phase2_route_is_registered(self) -> None:
        app_module = reload(import_module("app.main"))
        create_app = app_module.create_app
        app = create_app()
        routes = {route.path for route in app.routes}
        self.assertIn("/api/v1/tasks", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/run-phase2", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/enqueue-phase2", routes)
        self.assertIn("/internal/v1/phase2/ingest-and-run", routes)
        self.assertIn("/internal/v1/phase2/ingest-and-enqueue", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/run-phase3", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/enqueue-phase3", routes)
        self.assertIn("/internal/v1/phase3/ingest-and-run", routes)
        self.assertIn("/internal/v1/phase3/ingest-and-enqueue", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/run-phase4", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/enqueue-phase4", routes)
        self.assertIn("/internal/v1/phase4/ingest-and-run", routes)
        self.assertIn("/internal/v1/phase4/ingest-and-enqueue", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/push-wechat-draft", routes)
        self.assertIn("/api/v1/ingest/link", routes)
        self.assertIn("/api/v1/tasks/{task_id}", routes)
        self.assertIn("/api/v1/tasks/{task_id}/brief", routes)
        self.assertIn("/api/v1/tasks/{task_id}/draft", routes)
        self.assertIn("/api/v1/tasks/{task_id}/workspace", routes)
        self.assertIn("/admin/phase2", routes)
        self.assertIn("/admin/phase5", routes)

    def test_admin_phase2_page_renders(self) -> None:
        app_module = reload(import_module("app.main"))
        client = TestClient(app_module.create_app())

        response = client.get("/admin/phase2")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Phase 2 手动触发台", response.text)
        self.assertIn("提交链接并入队", response.text)
        self.assertIn("提交链接并执行阶段2", response.text)
        self.assertIn("刷新最近任务", response.text)

    def test_admin_phase5_page_renders(self) -> None:
        app_module = reload(import_module("app.main"))
        client = TestClient(app_module.create_app())

        response = client.get("/admin/phase5")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Phase 5 工作台", response.text)
        self.assertIn("任务看板、人工审核与手动干预", response.text)
        self.assertIn("推送微信草稿", response.text)


if __name__ == "__main__":
    unittest.main()
