import os
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.enums import TaskStatus
from app.db.base import Base
from app.db.redis_client import get_redis_client
from app.models.audit_log import AuditLog
from app.models.generation import Generation
from app.models.task import Task
from app.models.wechat_draft import WechatDraft
from app.services.manual_review_service import ManualReviewConflictError, ManualReviewService
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
}


class ManualReviewServiceTests(unittest.TestCase):
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

    def test_approve_latest_generation_marks_task_review_passed_and_logs(self) -> None:
        session = self.Session()
        task, generation = self._seed_task_with_generation(session, task_status="needs_manual_review", generation_status="needs_manual_review")

        result = ManualReviewService(session).approve_latest_generation(
            task.id,
            operator="phase5-console",
            note="人工确认结构可用",
        )

        self.assertEqual(result.status, TaskStatus.REVIEW_PASSED.value)
        refreshed_task = session.get(Task, task.id)
        refreshed_generation = session.get(Generation, generation.id)
        self.assertEqual(refreshed_task.status, TaskStatus.REVIEW_PASSED.value)
        self.assertEqual(refreshed_generation.status, "accepted")

        logs = session.scalars(select(AuditLog).where(AuditLog.task_id == task.id)).all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].action, "phase5.manual_review.approved")
        self.assertEqual(logs[0].operator, "phase5-console")
        self.assertEqual(logs[0].payload["note"], "人工确认结构可用")
        session.close()

    def test_approve_latest_generation_keeps_draft_saved_when_wechat_draft_exists(self) -> None:
        session = self.Session()
        task, generation = self._seed_task_with_generation(session, task_status="review_passed", generation_status="accepted")
        session.add(
            WechatDraft(
                task_id=task.id,
                generation_id=generation.id,
                media_id="draft-1",
                push_status="success",
                push_response={"media_id": "draft-1"},
            )
        )
        session.commit()

        result = ManualReviewService(session).approve_latest_generation(task.id, operator="reviewer")

        self.assertEqual(result.status, TaskStatus.DRAFT_SAVED.value)
        refreshed_task = session.get(Task, task.id)
        self.assertEqual(refreshed_task.status, TaskStatus.DRAFT_SAVED.value)
        session.close()

    def test_reject_latest_generation_marks_task_needs_regenerate_and_logs(self) -> None:
        session = self.Session()
        task, generation = self._seed_task_with_generation(session, task_status="needs_manual_review", generation_status="needs_manual_review")

        result = ManualReviewService(session).reject_latest_generation(
            task.id,
            operator="phase5-console",
            note="论证顺序仍然重复原文",
        )

        self.assertEqual(result.status, TaskStatus.NEEDS_REGENERATE.value)
        refreshed_task = session.get(Task, task.id)
        refreshed_generation = session.get(Generation, generation.id)
        self.assertEqual(refreshed_task.status, TaskStatus.NEEDS_REGENERATE.value)
        self.assertEqual(refreshed_generation.status, "rejected")

        logs = session.scalars(select(AuditLog).where(AuditLog.task_id == task.id)).all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].action, "phase5.manual_review.rejected")
        self.assertEqual(logs[0].payload["note"], "论证顺序仍然重复原文")
        session.close()

    def test_reject_latest_generation_raises_conflict_after_wechat_push(self) -> None:
        session = self.Session()
        task, generation = self._seed_task_with_generation(session, task_status="draft_saved", generation_status="accepted")
        session.add(
            WechatDraft(
                task_id=task.id,
                generation_id=generation.id,
                media_id="draft-1",
                push_status="success",
                push_response={"media_id": "draft-1"},
            )
        )
        session.commit()

        with self.assertRaises(ManualReviewConflictError):
            ManualReviewService(session).reject_latest_generation(task.id, operator="reviewer")

        refreshed_task = session.get(Task, task.id)
        refreshed_generation = session.get(Generation, generation.id)
        self.assertEqual(refreshed_task.status, TaskStatus.DRAFT_SAVED.value)
        self.assertEqual(refreshed_generation.status, "accepted")
        session.close()

    def test_select_generation_marks_history_version_as_current_and_logs(self) -> None:
        session = self.Session()
        task = Task(
            task_code="tsk_manual_review_select",
            source_url="https://mp.weixin.qq.com/s/manual-review-select",
            normalized_url="https://mp.weixin.qq.com/s/manual-review-select",
            source_type="wechat",
            status=TaskStatus.NEEDS_MANUAL_REVIEW.value,
        )
        session.add(task)
        session.flush()
        selected_generation = Generation(
            task_id=task.id,
            version_no=1,
            model_name="glm-5",
            title="历史通过稿",
            digest="历史摘要",
            markdown_content="# 历史通过稿",
            html_content="<h1>历史通过稿</h1>",
            status="accepted",
        )
        latest_generation = Generation(
            task_id=task.id,
            version_no=2,
            model_name="glm-5",
            title="最新待审稿",
            digest="最新摘要",
            markdown_content="# 最新待审稿",
            html_content="<h1>最新待审稿</h1>",
            status="needs_manual_review",
        )
        session.add_all([selected_generation, latest_generation])
        session.commit()

        result = ManualReviewService(session).select_generation(
            task.id,
            generation_id=selected_generation.id,
            operator="phase5-console",
            note="保留历史稳定版本",
        )

        self.assertEqual(result.status, TaskStatus.REVIEW_PASSED.value)
        refreshed_task = session.get(Task, task.id)
        self.assertEqual(refreshed_task.status, TaskStatus.REVIEW_PASSED.value)
        self.assertEqual(session.get(Generation, selected_generation.id).status, "accepted")
        self.assertEqual(session.get(Generation, latest_generation.id).status, "needs_manual_review")

        logs = session.scalars(select(AuditLog).where(AuditLog.task_id == task.id)).all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].action, "phase5.manual_review.selected_generation")
        self.assertEqual(logs[0].operator, "phase5-console")
        self.assertEqual(logs[0].payload["generation_id"], selected_generation.id)
        self.assertEqual(logs[0].payload["selected_version_no"], 1)
        self.assertEqual(logs[0].payload["note"], "保留历史稳定版本")
        session.close()

    def test_select_generation_raises_conflict_when_other_version_has_saved_draft(self) -> None:
        session = self.Session()
        task = Task(
            task_code="tsk_manual_review_select_conflict",
            source_url="https://mp.weixin.qq.com/s/manual-review-select-conflict",
            normalized_url="https://mp.weixin.qq.com/s/manual-review-select-conflict",
            source_type="wechat",
            status=TaskStatus.DRAFT_SAVED.value,
        )
        session.add(task)
        session.flush()
        selected_generation = Generation(
            task_id=task.id,
            version_no=1,
            model_name="glm-5",
            title="历史通过稿",
            digest="历史摘要",
            markdown_content="# 历史通过稿",
            html_content="<h1>历史通过稿</h1>",
            status="accepted",
        )
        draft_generation = Generation(
            task_id=task.id,
            version_no=2,
            model_name="glm-5",
            title="当前草稿稿件",
            digest="当前摘要",
            markdown_content="# 当前草稿稿件",
            html_content="<h1>当前草稿稿件</h1>",
            status="accepted",
        )
        session.add_all([selected_generation, draft_generation])
        session.flush()
        session.add(
            WechatDraft(
                task_id=task.id,
                generation_id=draft_generation.id,
                media_id="draft-locked",
                push_status="success",
                push_response={"media_id": "draft-locked"},
            )
        )
        session.commit()

        with self.assertRaises(ManualReviewConflictError):
            ManualReviewService(session).select_generation(
                task.id,
                generation_id=selected_generation.id,
                operator="phase5-console",
            )

        refreshed_task = session.get(Task, task.id)
        self.assertEqual(refreshed_task.status, TaskStatus.DRAFT_SAVED.value)
        self.assertEqual(
            session.scalars(select(AuditLog).where(AuditLog.task_id == task.id)).all(),
            [],
        )
        session.close()

    def test_select_generation_marks_target_accepted_and_logs_selection(self) -> None:
        session = self.Session()
        task, latest_generation = self._seed_task_with_generation(
            session,
            task_status="needs_manual_review",
            generation_status="needs_manual_review",
        )
        historical_generation = Generation(
            task_id=task.id,
            version_no=0,
            model_name="glm-5",
            title="历史稿",
            digest="历史稿摘要",
            markdown_content="# 历史稿\n\n正文",
            html_content="<h1>历史稿</h1><p>正文</p>",
            status="accepted",
        )
        session.add(historical_generation)
        session.commit()

        result = ManualReviewService(session).select_generation(
            task.id,
            generation_id=historical_generation.id,
            operator="phase5-console",
            note="保留历史稿做当前版本",
        )

        self.assertEqual(result.status, TaskStatus.REVIEW_PASSED.value)
        refreshed_task = session.get(Task, task.id)
        refreshed_historical = session.get(Generation, historical_generation.id)
        refreshed_latest = session.get(Generation, latest_generation.id)
        self.assertEqual(refreshed_task.status, TaskStatus.REVIEW_PASSED.value)
        self.assertEqual(refreshed_historical.status, "accepted")
        self.assertEqual(refreshed_latest.status, "needs_manual_review")

        logs = session.scalars(
            select(AuditLog).where(AuditLog.task_id == task.id, AuditLog.action == "phase5.manual_review.selected_generation")
        ).all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].operator, "phase5-console")
        self.assertEqual(logs[0].payload["generation_id"], historical_generation.id)
        self.assertEqual(logs[0].payload["selected_version_no"], 0)
        self.assertEqual(logs[0].payload["note"], "保留历史稿做当前版本")
        session.close()

    def test_select_generation_raises_conflict_when_other_generation_has_saved_draft(self) -> None:
        session = self.Session()
        task, latest_generation = self._seed_task_with_generation(
            session,
            task_status="draft_saved",
            generation_status="accepted",
        )
        historical_generation = Generation(
            task_id=task.id,
            version_no=0,
            model_name="glm-5",
            title="历史稿",
            digest="历史稿摘要",
            markdown_content="# 历史稿\n\n正文",
            html_content="<h1>历史稿</h1><p>正文</p>",
            status="accepted",
        )
        session.add(historical_generation)
        session.flush()
        session.add(
            WechatDraft(
                task_id=task.id,
                generation_id=latest_generation.id,
                media_id="draft-latest",
                push_status="success",
                push_response={"media_id": "draft-latest"},
            )
        )
        session.commit()

        with self.assertRaises(ManualReviewConflictError):
            ManualReviewService(session).select_generation(
                task.id,
                generation_id=historical_generation.id,
                operator="reviewer",
            )

        refreshed_task = session.get(Task, task.id)
        refreshed_historical = session.get(Generation, historical_generation.id)
        self.assertEqual(refreshed_task.status, TaskStatus.DRAFT_SAVED.value)
        self.assertEqual(refreshed_historical.status, "accepted")
        session.close()

    def _seed_task_with_generation(
        self,
        session,
        *,
        task_status: str,
        generation_status: str,
    ) -> tuple[Task, Generation]:
        task = Task(
            task_code="tsk_manual_review",
            source_url="https://mp.weixin.qq.com/s/manual-review",
            normalized_url="https://mp.weixin.qq.com/s/manual-review",
            source_type="wechat",
            status=task_status,
        )
        session.add(task)
        session.flush()
        generation = Generation(
            task_id=task.id,
            version_no=1,
            model_name="glm-5",
            title="稿件标题",
            digest="稿件摘要",
            markdown_content="# 稿件标题\n\n正文",
            html_content="<h1>稿件标题</h1><p>正文</p>",
            status=generation_status,
        )
        session.add(generation)
        session.commit()
        return task, generation


if __name__ == "__main__":
    unittest.main()
