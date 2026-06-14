"""T7 前端去字符串化第一刀：/admin/settings 迁移到 Jinja2 模板。

这些测试钉住"模板渲染结果与旧字符串实现等价"的不变量，并验证 vendored 静态资产
（htmx）可经 /static 挂载提供。
"""

import os
import unittest
from importlib import import_module, reload
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.admin_console import settings_console
from app.api.admin_ui import (
    admin_shared_script_helpers,
    admin_shared_styles,
    render_admin_page,
)
from app.settings import get_settings
from app.templating import render_template


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

# 迁移前的设置页里出现的关键元素 id（数据由 JSON API 客户端渲染，这些是静态壳锚点）。
EXPECTED_IDS = (
    'id="flash-msg"',
    'id="btn-refresh"',
    'id="btn-save"',
    'id="llm-card"',
    'id="settings-card"',
    'id="env-card"',
)


class SettingsTemplateTests(unittest.TestCase):
    def test_template_renders_shared_blobs_and_anchors(self) -> None:
        rendered = render_template(
            "admin/settings.html",
            shared_styles=admin_shared_styles(),
            shared_script_helpers=admin_shared_script_helpers(),
        )

        # 注入点确实被替换（不再残留占位符）。
        self.assertNotIn("__ADMIN_SHARED_STYLES__", rendered)
        self.assertNotIn("__ADMIN_SHARED_SCRIPT_HELPERS__", rendered)
        # 共享 CSS / JS blob 已注入。
        self.assertIn("--sidebar-w", rendered)  # admin_shared_styles 标志
        self.assertIn("AdminUiShared", rendered)  # admin_shared_script_helpers 标志
        # 页面文案与锚点。
        self.assertIn("运行设置", rendered)
        self.assertIn("LLM 配置", rendered)
        self.assertIn("环境状态", rendered)
        for anchor in EXPECTED_IDS:
            self.assertIn(anchor, rendered)

    def test_settings_console_output_equals_template_through_frame(self) -> None:
        """settings_console() == render_admin_page(template_render(...))。

        钉住模板渲染 + admin 框体包裹后的输出，与路由实际返回逐字节一致。
        """
        expected = render_admin_page(
            render_template(
                "admin/settings.html",
                shared_styles=admin_shared_styles(),
                shared_script_helpers=admin_shared_script_helpers(),
            ),
            "settings",
        )
        self.assertEqual(settings_console(), expected)

    def test_settings_console_contains_key_text_and_ids(self) -> None:
        out = settings_console()
        self.assertIn("运行设置", out)
        self.assertIn("--sidebar-w", out)  # 共享样式
        self.assertIn("AdminUiShared", out)  # 共享脚本助手
        for anchor in EXPECTED_IDS:
            self.assertIn(anchor, out)
        # 框体锚点（render_admin_page 包裹后应存在）。
        self.assertIn('class="admin-app"', out)
        self.assertIn("admin-sidebar", out)


class StaticMountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, TEST_ENV, clear=False)
        self.env_patch.start()
        get_settings.cache_clear()

    def tearDown(self) -> None:
        self.env_patch.stop()
        get_settings.cache_clear()

    def test_vendored_htmx_served_from_static_mount(self) -> None:
        app_module = reload(import_module("app.main"))
        client = TestClient(app_module.create_app())

        response = client.get("/static/htmx.min.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("htmx", response.text[:200])


if __name__ == "__main__":
    unittest.main()
