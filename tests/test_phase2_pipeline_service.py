import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.db.redis_client import get_redis_client
from app.models.source_article import SourceArticle
from app.services.phase2_pipeline_service import Phase2PipelineService
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


class Phase2PipelineServiceTests(unittest.TestCase):
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

    def test_collect_source_images_deduplicates_and_limits(self) -> None:
        service = Phase2PipelineService(MagicMock())
        article = SourceArticle(
            task_id="task-1",
            url="https://mp.weixin.qq.com/s/example",
            cover_image_url="https://cdn.example.com/cover.png",
            raw_html="""
            <div id="js_content">
              <p>正文</p>
              <img src="https://cdn.example.com/cover.png" />
              <img data-src="https://cdn.example.com/body-1.png" />
              <img src="https://cdn.example.com/body-2.png" />
              <img src="https://cdn.example.com/body-3.png" />
            </div>
            """,
        )

        image_urls = service._collect_source_image_urls(article)

        self.assertEqual(
            image_urls,
            [
                "https://cdn.example.com/cover.png",
                "https://cdn.example.com/body-1.png",
                "https://cdn.example.com/body-2.png",
            ],
        )

    def test_rewrite_html_images_uploads_non_wechat_images(self) -> None:
        service = Phase2PipelineService(MagicMock())
        service.fetcher = MagicMock()
        service.wechat = MagicMock()
        service.fetcher.download_binary.return_value = (b"image-bytes", "image/png")
        service.wechat.upload_draft_image.return_value = {"url": "https://mmbiz.qpic.cn/rewritten.png"}

        html, logs = service._rewrite_html_images_for_wechat(
            '<section><img src="https://cdn.example.com/body.png" alt="test" /></section>'
        )

        self.assertIn("https://mmbiz.qpic.cn/rewritten.png", html)
        self.assertEqual(logs[0]["status"], "uploaded")
        service.wechat.upload_draft_image.assert_called_once()
