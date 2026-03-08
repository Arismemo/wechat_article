import base64
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
        self.assertIn("/internal/v1/tasks/{task_id}/approve-latest-generation", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/reject-latest-generation", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/allow-wechat-draft-push", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/block-wechat-draft-push", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/push-wechat-draft", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/import-feedback", routes)
        self.assertIn("/internal/v1/feedback/import-csv", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/run-feedback-sync", routes)
        self.assertIn("/internal/v1/tasks/{task_id}/enqueue-feedback-sync", routes)
        self.assertIn("/internal/v1/feedback/enqueue-recent-sync", routes)
        self.assertIn("/internal/v1/style-assets", routes)
        self.assertIn("/api/v1/ingest/link", routes)
        self.assertIn("/api/v1/ingest/shortcut", routes)
        self.assertIn("/api/v1/tasks/{task_id}", routes)
        self.assertIn("/api/v1/tasks/{task_id}/brief", routes)
        self.assertIn("/api/v1/tasks/{task_id}/draft", routes)
        self.assertIn("/api/v1/tasks/{task_id}/workspace", routes)
        self.assertIn("/api/v1/tasks/{task_id}/feedback", routes)
        self.assertIn("/api/v1/feedback/experiments", routes)
        self.assertIn("/api/v1/feedback/style-assets", routes)
        self.assertIn("/api/v1/admin/monitor/snapshot", routes)
        self.assertIn("/api/v1/admin/runtime-status", routes)
        self.assertIn("/api/v1/admin/alerts/test", routes)
        self.assertIn("/api/v1/admin/settings", routes)
        self.assertIn("/api/v1/admin/settings/{key}", routes)
        self.assertIn("/admin", routes)
        self.assertIn("/admin/phase2", routes)
        self.assertIn("/admin/console", routes)
        self.assertIn("/admin/console/stream", routes)
        self.assertIn("/admin/settings", routes)
        self.assertIn("/admin/phase5", routes)
        self.assertIn("/admin/phase6", routes)

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
        self.assertIn("版本差异视图", response.text)
        self.assertIn("人工确认通过", response.text)
        self.assertIn("人工驳回重写", response.text)
        self.assertIn("允许推草稿", response.text)
        self.assertIn("禁止推草稿", response.text)

    def test_admin_console_page_renders(self) -> None:
        app_module = reload(import_module("app.main"))
        client = TestClient(app_module.create_app())

        response = client.get("/admin/console")

        self.assertEqual(response.status_code, 200)
        self.assertIn("统一控制台", response.text)
        self.assertIn("统一任务监控首页", response.text)
        self.assertIn("自动实时更新（优先 SSE，失败时回退轮询）", response.text)
        self.assertIn("队列与 Worker 观测", response.text)
        self.assertIn("打开 Phase 5 审核台", response.text)

    def test_admin_settings_page_renders(self) -> None:
        app_module = reload(import_module("app.main"))
        client = TestClient(app_module.create_app())

        response = client.get("/admin/settings")

        self.assertEqual(response.status_code, 200)
        self.assertIn("RUNTIME SETTINGS & STATUS", response.text)
        self.assertIn("运行参数设置", response.text)
        self.assertIn("这里只允许修改可以热覆盖的运行参数", response.text)
        self.assertIn("环境状态", response.text)
        self.assertIn("告警测试", response.text)

    def test_admin_portal_page_renders(self) -> None:
        app_module = reload(import_module("app.main"))
        client = TestClient(app_module.create_app())

        response = client.get("/admin")

        self.assertEqual(response.status_code, 200)
        self.assertIn("统一后台入口", response.text)
        self.assertIn("监控首页", response.text)
        self.assertIn("审核台", response.text)
        self.assertIn("反馈台", response.text)
        self.assertIn("设置", response.text)

    def test_admin_phase6_page_renders(self) -> None:
        app_module = reload(import_module("app.main"))
        client = TestClient(app_module.create_app())

        response = client.get("/admin/phase6")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Phase 6 反馈台", response.text)
        self.assertIn("自动同步", response.text)
        self.assertIn("导入反馈", response.text)
        self.assertIn("批量导入 CSV", response.text)
        self.assertIn("Prompt 实验榜", response.text)
        self.assertIn("风格资产库", response.text)
        self.assertIn("同步当前任务", response.text)

    def test_admin_pages_require_basic_auth_when_configured(self) -> None:
        with patch.dict(os.environ, {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "secret-pass"}, clear=False):
            get_settings.cache_clear()
            app_module = reload(import_module("app.main"))
            client = TestClient(app_module.create_app())

            unauthorized = client.get("/admin/phase5")
            self.assertEqual(unauthorized.status_code, 401)
            self.assertEqual(unauthorized.headers.get("www-authenticate"), 'Basic realm="wechat_artical-admin"')

            encoded = base64.b64encode(b"admin:secret-pass").decode("ascii")
            authorized = client.get("/admin/phase5", headers={"Authorization": f"Basic {encoded}"})
            self.assertEqual(authorized.status_code, 200)
            self.assertIn("Phase 5 工作台", authorized.text)

            console_unauthorized = client.get("/admin/console")
            self.assertEqual(console_unauthorized.status_code, 401)

            console_authorized = client.get("/admin/console", headers={"Authorization": f"Basic {encoded}"})
            self.assertEqual(console_authorized.status_code, 200)
            self.assertIn("统一任务监控首页", console_authorized.text)

            settings_unauthorized = client.get("/admin/settings")
            self.assertEqual(settings_unauthorized.status_code, 401)

            settings_authorized = client.get("/admin/settings", headers={"Authorization": f"Basic {encoded}"})
            self.assertEqual(settings_authorized.status_code, 200)
            self.assertIn("运行参数设置", settings_authorized.text)

            portal_unauthorized = client.get("/admin")
            self.assertEqual(portal_unauthorized.status_code, 401)

            portal_authorized = client.get("/admin", headers={"Authorization": f"Basic {encoded}"})
            self.assertEqual(portal_authorized.status_code, 200)
            self.assertIn("统一后台入口", portal_authorized.text)

            phase6_unauthorized = client.get("/admin/phase6")
            self.assertEqual(phase6_unauthorized.status_code, 401)

            phase6_authorized = client.get("/admin/phase6", headers={"Authorization": f"Basic {encoded}"})
            self.assertEqual(phase6_authorized.status_code, 200)
            self.assertIn("Phase 6 反馈台", phase6_authorized.text)

            client.close()
            get_settings.cache_clear()


if __name__ == "__main__":
    unittest.main()
