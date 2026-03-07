import os
import tempfile
import unittest
from typing import Optional
from unittest.mock import patch

from app.db.redis_client import get_redis_client
from app.services.wechat_exporter_service import WechatArticleExporterError, WechatArticleExporterService
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
    "WECHAT_EXPORTER_BASE_URL": "https://exporter.example.com",
}


class FakeResponse:
    def __init__(self, text: str, payload: Optional[dict] = None, content_type: str = "application/json") -> None:
        self.text = text
        self._payload = payload or {}
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class WechatExporterServiceTests(unittest.TestCase):
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

    def test_download_html_returns_html_body(self) -> None:
        service = WechatArticleExporterService()
        with patch.object(service, "_request", return_value=FakeResponse("<html>ok</html>", content_type="text/html")):
            html = service.download_html("https://mp.weixin.qq.com/s/example")

        self.assertEqual(html, "<html>ok</html>")

    def test_resolve_account_by_url_raises_for_exporter_error(self) -> None:
        service = WechatArticleExporterService()
        with patch.object(
            service,
            "_request",
            return_value=FakeResponse(
                text='{"base_resp":{"ret":-1,"err_msg":"bad"}}',
                payload={"base_resp": {"ret": -1, "err_msg": "bad"}},
            ),
        ):
            with self.assertRaises(WechatArticleExporterError):
                service.resolve_account_by_url("https://mp.weixin.qq.com/s/example")
