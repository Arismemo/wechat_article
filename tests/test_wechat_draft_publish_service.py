import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.enums import TaskStatus
from app.db.base import Base
from app.db.redis_client import get_redis_client
from app.models.generation import Generation
from app.models.source_article import SourceArticle
from app.models.task import Task
from app.models.wechat_draft import WechatDraft
from app.services.wechat_draft_publish_service import WechatDraftPublishService
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


TEST_ENV = {
    "APP_BASE_URL": "https://example.com",
    "API_BEARER_TOKEN": "test-token",
    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "REDIS_URL": "redis://localhost:6379/0",
    "LLM_PROVIDER": "ZHIPU",
    "LLM_API_KEY": "test-key",
    "LLM_MODEL_ANALYZE": "glm-5",
    "LLM_MODEL_WRITE": "glm-5",
    "LLM_MODEL_REVIEW": "glm-5",
    "SEARCH_PROVIDER": "ZHIPU_MCP",
    "WECHAT_APP_ID": "wx-test",
    "WECHAT_APP_SECRET": "secret-test",
    "WECHAT_ENABLE_DRAFT_PUSH": "true",
}


class WechatDraftPublishServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {**TEST_ENV, "LOCAL_STORAGE_ROOT": self.temp_dir.name}, clear=False)
        self.env_patch.start()
        get_settings.cache_clear()
        get_redis_client.cache_clear()

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        self.temp_dir.cleanup()

    def test_push_latest_accepted_generation_saves_wechat_draft(self) -> None:
        session = self.Session()
        task = Task(
            task_code="tsk_push",
            source_url="https://mp.weixin.qq.com/s/example",
            normalized_url="https://mp.weixin.qq.com/s/example",
            source_type="wechat",
            status=TaskStatus.REVIEW_PASSED.value,
        )
        session.add(task)
        session.flush()
        session.add(
            SourceArticle(
                task_id=task.id,
                url=task.source_url,
                title="源标题",
                author="作者",
                summary="摘要",
                cleaned_text="正文",
                fetch_status="success",
            )
        )
        generation = Generation(
            task_id=task.id,
            version_no=1,
            model_name="glm-5",
            title="重构稿标题",
            digest="重构稿摘要",
            html_content="<section><h1>重构稿标题</h1><p>正文</p></section>",
            markdown_content="# 重构稿标题\n\n正文",
            status="accepted",
        )
        session.add(generation)
        session.commit()

        service = WechatDraftPublishService(session)
        service.wechat = MagicMock()
        service.wechat.build_fallback_thumb.return_value = (b"png", "thumb.png", "image/png")
        service.wechat.upload_image_material.return_value = {"media_id": "thumb-1"}
        service.wechat.add_draft.return_value = {"media_id": "draft-1"}

        result = service.push_latest_accepted_generation(task.id)

        self.assertEqual(result.status, TaskStatus.DRAFT_SAVED.value)
        self.assertEqual(result.wechat_media_id, "draft-1")
        self.assertFalse(result.reused_existing)

        refreshed_task = session.get(Task, task.id)
        self.assertEqual(refreshed_task.status, TaskStatus.DRAFT_SAVED.value)
        draft = session.scalar(select(WechatDraft).where(WechatDraft.task_id == task.id))
        self.assertIsNotNone(draft)
        self.assertEqual(draft.media_id, "draft-1")
        self.assertEqual(draft.generation_id, generation.id)
        session.close()
