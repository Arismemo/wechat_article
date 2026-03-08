import os
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.db.redis_client import get_redis_client
from app.db.session import get_engine, get_session_factory
from app.models.content_brief import ContentBrief
from app.models.generation import Generation
from app.models.system_setting import SystemSetting
from app.models.task import Task
from app.models.wechat_draft import WechatDraft
from app.services.feedback_queue_service import FeedbackSyncEnqueueResult
from app.services.feedback_sync_service import FeedbackSyncService
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class DummyQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[int], str]] = []

    def enqueue(self, task_id: str, *, day_offsets: list[int], operator: str) -> FeedbackSyncEnqueueResult:
        self.calls.append((task_id, day_offsets, operator))
        return FeedbackSyncEnqueueResult(
            task_id=task_id,
            enqueued=True,
            queue_depth=len(self.calls),
            day_offsets=day_offsets,
        )


class FeedbackSyncServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "feedback-sync.db")
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
                "LLM_MODEL_REVIEW": "glm-5",
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
        session = self.Session()

        primary_task = Task(
            task_code="tsk_feedback_sync",
            source_url="https://mp.weixin.qq.com/s/feedback-sync",
            normalized_url="https://mp.weixin.qq.com/s/feedback-sync",
            source_type="wechat",
            status="draft_saved",
        )
        session.add(primary_task)
        session.flush()
        brief = ContentBrief(task_id=primary_task.id, brief_version=1, positioning="工程师科普稿")
        session.add(brief)
        session.flush()
        generation = Generation(
            task_id=primary_task.id,
            brief_id=brief.id,
            version_no=4,
            prompt_type="phase4_write",
            prompt_version="phase4-v2",
            model_name="glm-5",
            title="终版",
            markdown_content="# 终版",
            status="accepted",
        )
        session.add(generation)
        session.flush()
        session.add(
            WechatDraft(
                task_id=primary_task.id,
                generation_id=generation.id,
                media_id="media-sync-1",
                push_status="success",
            )
        )

        secondary_task = Task(
            task_code="tsk_feedback_sync_2",
            source_url="https://mp.weixin.qq.com/s/feedback-sync-2",
            normalized_url="https://mp.weixin.qq.com/s/feedback-sync-2",
            source_type="wechat",
            status="draft_saved",
        )
        session.add(secondary_task)
        session.flush()
        secondary_brief = ContentBrief(task_id=secondary_task.id, brief_version=1, positioning="工程师科普稿")
        session.add(secondary_brief)
        session.flush()
        secondary_generation = Generation(
            task_id=secondary_task.id,
            brief_id=secondary_brief.id,
            version_no=2,
            prompt_type="phase4_write",
            prompt_version="phase4-v1",
            model_name="glm-5",
            title="次终版",
            markdown_content="# 次终版",
            status="accepted",
        )
        session.add(secondary_generation)
        session.flush()
        session.add(
            WechatDraft(
                task_id=secondary_task.id,
                generation_id=secondary_generation.id,
                media_id="media-sync-2",
                push_status="success",
            )
        )
        session.commit()
        self.task_id = primary_task.id
        self.generation_id = generation.id
        self.secondary_task_id = secondary_task.id
        session.close()

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        self.temp_dir.cleanup()

    def test_run_imports_snapshots_from_http_provider(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FEEDBACK_SYNC_PROVIDER": "http",
                "FEEDBACK_SYNC_HTTP_URL": "https://feedback.example.test/sync",
            },
            clear=False,
        ):
            get_settings.cache_clear()
            session = self.Session()
            service = FeedbackSyncService(session)
            with patch(
                "app.services.feedback_sync_service.httpx.post",
                return_value=DummyResponse(
                    {
                        "provider": "http-metrics",
                        "snapshots": [
                            {
                                "day_offset": 1,
                                "snapshot_at": "2026-03-08T09:30:00+08:00",
                                "read_count": 1666,
                                "like_count": 101,
                                "share_count": 18,
                                "comment_count": 6,
                                "click_rate": 0.2031,
                            },
                            {
                                "day_offset": 3,
                                "snapshot_at": "2026-03-10T09:30:00+08:00",
                                "read_count": 2333,
                                "like_count": 140,
                                "share_count": 28,
                                "comment_count": 9,
                                "click_rate": 0.2542,
                            },
                        ],
                    }
                ),
            ) as mocked_post:
                result = service.run(self.task_id, day_offsets=[1, 3], operator="sync-bot")

            self.assertEqual(result.provider, "http")
            self.assertEqual(result.imported_count, 2)
            self.assertEqual(result.imported_day_offsets, [1, 3])
            self.assertEqual(result.skipped_day_offsets, [])
            self.assertEqual(mocked_post.call_count, 1)

            metrics = service.feedback.list_task_metrics(self.task_id)
            self.assertEqual(len(metrics), 2)
            self.assertEqual({item.day_offset for item in metrics}, {1, 3})
            self.assertEqual({item.source_type for item in metrics}, {"auto:http-metrics"})
            self.assertEqual(metrics[0].imported_by, "feedback-sync")
            session.close()

    def test_enqueue_recent_scans_successful_drafts(self) -> None:
        with patch.dict(os.environ, {"FEEDBACK_SYNC_PROVIDER": "mock"}, clear=False):
            get_settings.cache_clear()
            session = self.Session()
            service = FeedbackSyncService(session)
            queue = DummyQueue()
            service.queue = queue

            result = service.enqueue_recent(limit=2, day_offsets=[1, 7], operator="ops-auto")

            self.assertEqual(result.requested_count, 2)
            self.assertEqual(result.enqueued_count, 2)
            self.assertEqual(result.day_offsets, [1, 7])
            self.assertEqual(len(queue.calls), 2)
            self.assertEqual(queue.calls[0][1], [1, 7])
            self.assertEqual(queue.calls[0][2], "ops-auto")
            self.assertIn(self.task_id, result.task_ids)
            self.assertIn(self.secondary_task_id, result.task_ids)
            session.close()

    def test_run_uses_database_backed_provider_and_day_offsets(self) -> None:
        session = self.Session()
        session.add(SystemSetting(key="feedback.sync_provider", value="mock"))
        session.add(SystemSetting(key="feedback.sync_day_offsets", value=[2, 5]))
        session.commit()

        service = FeedbackSyncService(session)
        result = service.run(self.task_id, operator="sync-bot")

        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.requested_day_offsets, [2, 5])
        self.assertEqual(result.imported_day_offsets, [2, 5])
        metrics = service.feedback.list_task_metrics(self.task_id)
        self.assertEqual({item.day_offset for item in metrics}, {2, 5})
        session.close()


if __name__ == "__main__":
    unittest.main()
