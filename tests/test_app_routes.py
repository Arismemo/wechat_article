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
        self.assertIn("/admin/api/home-snapshot", routes)
        self.assertIn("/admin/api/ingest", routes)
        self.assertIn("/admin/api/tasks/{task_id}/retry", routes)
        self.assertIn("/admin/api/tasks/{task_id}/approve", routes)
        self.assertIn("/admin/api/tasks/{task_id}/reject", routes)
        self.assertIn("/admin/api/tasks/{task_id}/push-draft", routes)
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
        self.assertIn("审核台", response.text)
        self.assertIn("怎么用", response.text)
        self.assertIn("推送草稿", response.text)
        self.assertIn("版本差异视图", response.text)
        self.assertIn("人工通过", response.text)
        self.assertIn("人工驳回重写", response.text)
        self.assertIn("允许推稿", response.text)
        self.assertIn("禁止推稿", response.text)
        self.assertIn('aria-label="后台分区"', response.text)
        self.assertIn("const apiUrl = (path) => new URL(path, window.location.origin).toString();", response.text)
        self.assertIn("const scrollWorkspaceIntoView = () => {", response.text)

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
        self.assertIn("这里只改少量运行开关，不碰密钥和基础设施。", response.text)
        self.assertIn('aria-label="后台分区"', response.text)
        self.assertIn(">设置<", response.text)
        self.assertIn(">审核<", response.text)
        self.assertIn("辅助工具", response.text)
        self.assertIn("测试告警", response.text)
        self.assertIn("环境状态", response.text)
        self.assertIn("const apiUrl = (path) => new URL(path, window.location.origin).toString();", response.text)

    def test_admin_portal_page_renders(self) -> None:
        app_module = reload(import_module("app.main"))
        client = TestClient(app_module.create_app())

        response = client.get("/admin")

        self.assertEqual(response.status_code, 200)
        self.assertIn("微信文章工厂", response.text)
        self.assertIn("贴链接，任务会自己往下走。", response.text)
        self.assertIn("开始一个任务", response.text)
        self.assertIn("最近任务", response.text)
        self.assertIn("任务详情", response.text)
        self.assertIn("开始处理", response.text)
        self.assertIn("跳到任务主区", response.text)
        self.assertIn("微信公众号文章链接", response.text)
        self.assertIn("任务概览", response.text)
        self.assertIn("今天提交", response.text)
        self.assertIn("先贴链接。需要人工判断时，再点下面这排。", response.text)
        self.assertIn('aria-label="后台分区"', response.text)
        self.assertIn('role="status"', response.text)
        self.assertIn(">反馈<", response.text)
        self.assertIn("更多信息", response.text)
        self.assertIn("清空", response.text)
        self.assertIn("这里只收微信公众号文章链接。", response.text)
        self.assertIn("composer-actions", response.text)
        self.assertIn("alignSelectedTaskToVisibleTasks", response.text)
        self.assertIn("scrollTaskDetailIntoView", response.text)
        self.assertIn("当前筛选下没有任务。换个筛选看看。", response.text)

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
        self.assertIn("哪套 prompt 更稳。", response.text)
        self.assertIn("哪些写法值得留下来复用。", response.text)
        self.assertIn("立即同步", response.text)
        self.assertIn("导入 CSV", response.text)
        self.assertIn("新建资产", response.text)
        self.assertIn(">总览<", response.text)
        self.assertIn("const apiUrl = (path) => new URL(path, window.location.origin).toString();", response.text)

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
            self.assertIn("微信文章工厂", portal_authorized.text)

            admin_api_unauthorized = client.get("/admin/api/home-snapshot")
            self.assertEqual(admin_api_unauthorized.status_code, 401)

            phase6_unauthorized = client.get("/admin/phase6")
            self.assertEqual(phase6_unauthorized.status_code, 401)

            phase6_authorized = client.get("/admin/phase6", headers={"Authorization": f"Basic {encoded}"})
            self.assertEqual(phase6_authorized.status_code, 200)
            self.assertIn("Phase 6 反馈台", phase6_authorized.text)

            client.close()
            get_settings.cache_clear()


if __name__ == "__main__":
    unittest.main()
