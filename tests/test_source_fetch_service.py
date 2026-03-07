import os
import tempfile
import unittest
from unittest.mock import patch

import httpx

from app.db.redis_client import get_redis_client
from app.services.source_fetch_service import SourceFetchService, SourceFetchError
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


class SourceFetchServiceTests(unittest.TestCase):
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

    def test_parse_wechat_article_extracts_core_fields(self) -> None:
        html = """
        <html>
          <head>
            <meta property="og:title" content="测试文章标题" />
            <meta property="og:image" content="https://cdn.example.com/cover.jpg" />
          </head>
          <body>
            <div id="js_name">奇点作者</div>
            <div id="js_content">
              <p>第一段内容。</p>
              <p>第二段内容。</p>
              <blockquote>第三段观点。</blockquote>
            </div>
            <script>var publish_time = "1700000000";</script>
          </body>
        </html>
        """
        service = SourceFetchService()

        article = service._parse_wechat_article(httpx.URL("https://mp.weixin.qq.com/s?__biz=abc"), html)

        self.assertEqual(article.title, "测试文章标题")
        self.assertEqual(article.author, "奇点作者")
        self.assertEqual(article.cover_image_url, "https://cdn.example.com/cover.jpg")
        self.assertIn("第一段内容。", article.cleaned_text)
        self.assertIn("第三段观点。", article.cleaned_text)
        self.assertTrue(article.summary.startswith("第一段内容。 第二段内容。"))
        self.assertIsNotNone(article.published_at)

    def test_fetch_falls_back_to_playwright_when_http_fails(self) -> None:
        html = """
        <html>
          <head><meta property="og:title" content="浏览器兜底标题" /></head>
          <body>
            <div id="js_name">浏览器作者</div>
            <div id="js_content"><p>兜底正文第一段。</p><p>兜底正文第二段。</p></div>
          </body>
        </html>
        """
        service = SourceFetchService()

        with patch.object(service, "_fetch_via_http", side_effect=SourceFetchError("http failed")):
            with patch.object(
                service,
                "_fetch_via_playwright",
                return_value=("https://mp.weixin.qq.com/s?__biz=fallback", html),
            ):
                fetched = service.fetch("task-fallback", "https://mp.weixin.qq.com/s?__biz=fallback", "wechat")

        self.assertEqual(fetched.fetch_method, "playwright")
        self.assertEqual(fetched.title, "浏览器兜底标题")
        self.assertIn("兜底正文第一段。", fetched.cleaned_text)
        self.assertTrue(os.path.exists(fetched.snapshot_path))

    def test_fetch_tries_exporter_before_playwright_when_configured(self) -> None:
        html = """
        <html>
          <head><meta property="og:title" content="Exporter 标题" /></head>
          <body>
            <div id="js_name">Exporter 作者</div>
            <div id="js_content"><p>Exporter 正文第一段。</p></div>
          </body>
        </html>
        """
        with patch.dict(os.environ, {"WECHAT_EXPORTER_BASE_URL": "https://exporter.example.com"}, clear=False):
            get_settings.cache_clear()
            service = SourceFetchService()

        with patch.object(service, "_fetch_via_http", side_effect=SourceFetchError("http failed")):
            with patch.object(service.wechat_exporter, "download_html", return_value=html) as exporter_mock:
                with patch.object(service, "_fetch_via_playwright", side_effect=AssertionError("playwright should not run")):
                    fetched = service.fetch("task-exporter", "https://mp.weixin.qq.com/s?__biz=exporter", "wechat")

        self.assertEqual(fetched.fetch_method, "wechat_exporter")
        self.assertEqual(fetched.title, "Exporter 标题")
        exporter_mock.assert_called_once()

    def test_playwright_channels_are_parsed(self) -> None:
        with patch.dict(os.environ, {"PLAYWRIGHT_BROWSER_CHANNELS": "chromium, chrome ,"}, clear=False):
            get_settings.cache_clear()
            service = SourceFetchService()

        self.assertEqual(service._playwright_channels(), ["chromium", "chrome"])


if __name__ == "__main__":
    unittest.main()
