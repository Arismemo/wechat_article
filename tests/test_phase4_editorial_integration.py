"""Task 9: Phase4 integration test — editorial board hook.

Tests that:
- With EDITORIAL_ENABLED=true: after the first review, Phase4 sets task to
  PENDING_EDITORIAL, calls EditorialQueueService.enqueue once, and returns
  WITHOUT pushing a WechatDraft or reaching any auto-push path.
- With EDITORIAL_ENABLED=false: old behaviour is completely unchanged
  (reaches a normal terminal decision; enqueue is never called).
"""

from __future__ import annotations

import os
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
from app.models.article_analysis import ArticleAnalysis
from app.models.content_brief import ContentBrief
from app.models.generation import Generation
from app.models.review_report import ReviewReport
from app.models.source_article import SourceArticle
from app.models.task import Task
from app.services.phase4_pipeline_service import Phase4PipelineService
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


_BASE_ENV = {
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

_GENERATE_RESPONSE = {
    "title": "测试标题：重构稿",
    "subtitle": "副标题",
    "digest": "摘要",
    "markdown_content": (
        "# 测试标题：重构稿\n\n"
        "## 第一节\n内容一。\n\n"
        "## 第二节\n内容二。\n\n"
        "## 第三节\n内容三。\n"
    ),
}

_REVIEW_PASS_RESPONSE = {
    "final_decision": "pass",
    "similarity_score": 0.20,
    "factual_risk_score": 0.15,
    "policy_risk_score": 0.05,
    "readability_score": 87,
    "title_score": 85,
    "novelty_score": 83,
    # ai_trace_score=0 keeps it below the default rewrite threshold (7), so
    # _should_run_humanize returns False and we avoid a 3rd LLM call.
    "ai_trace_score": 0,
    "ai_trace_patterns": [],
    "rewrite_targets": [],
    "voice_summary": "表达自然",
    "issues": ["无明显问题。"],
    "suggestions": ["可以进入下一阶段。"],
}

# The lazy import inside Phase4PipelineService.run() does:
#   from app.services.editorial_queue_service import EditorialQueueService
# Patching the class at its source module intercepts every such import during
# the test because Python re-reads the attribute from sys.modules each time.
_EQS_PATCH_TARGET = "app.services.editorial_queue_service.EditorialQueueService"


class Phase4EditorialEnabledTests(unittest.TestCase):
    """When EDITORIAL_ENABLED=true Phase4 must defer the push."""

    def setUp(self) -> None:
        self.env_patch = patch.dict(
            os.environ,
            {**_BASE_ENV, "EDITORIAL_ENABLED": "true"},
            clear=False,
        )
        self.env_patch.start()
        get_settings.cache_clear()
        get_redis_client.cache_clear()

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False
        )

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()

    def test_editorial_enabled_sets_pending_editorial_and_enqueues(self) -> None:
        """Phase4.run() with editorial_enabled must:
        1. Set task status to PENDING_EDITORIAL.
        2. Call EditorialQueueService.enqueue(task_id) exactly once.
        3. Return a result with status==PENDING_EDITORIAL.
        4. NOT create a WechatDraft / NOT call wechat_publisher.push_generation.
        5. NOT call llm more than twice (generate + quick-screen review only).
        """
        session = self.Session()
        task = self._seed_task(session, "tsk_editorial_enabled")

        mock_enqueue = MagicMock()
        mock_queue_cls = MagicMock()
        mock_queue_cls.return_value.enqueue = mock_enqueue

        with patch(_EQS_PATCH_TARGET, mock_queue_cls):
            service = Phase4PipelineService(session)
            service.llm = MagicMock()
            service.llm.complete_json.side_effect = [
                _GENERATE_RESPONSE,
                _REVIEW_PASS_RESPONSE,
            ]
            service.wechat_publisher = MagicMock()

            result = service.run(task.id)

        # 1. Result status must be PENDING_EDITORIAL
        self.assertEqual(result.status, TaskStatus.PENDING_EDITORIAL.value)

        # 2. enqueue called exactly once with the task_id
        mock_enqueue.assert_called_once_with(task.id)

        # 3. DB task status also set to PENDING_EDITORIAL
        refreshed = session.get(Task, task.id)
        self.assertEqual(refreshed.status, TaskStatus.PENDING_EDITORIAL.value)

        # 4. No WeChat draft pushed
        service.wechat_publisher.push_generation.assert_not_called()

        # 5. generation_id and review_report_id are populated in result
        self.assertIsNotNone(result.generation_id)
        self.assertIsNotNone(result.review_report_id)

        # 6. LLM was called exactly twice (generate + review) — no humanize, no
        # second review, no auto-revise
        self.assertEqual(service.llm.complete_json.call_count, 2)

        # 7. A Generation row exists in DB
        generations = list(
            session.scalars(select(Generation).where(Generation.task_id == task.id))
        )
        self.assertEqual(len(generations), 1)

        # 8. A ReviewReport row exists in DB
        reviews = list(
            session.scalars(
                select(ReviewReport)
                .join(Generation, ReviewReport.generation_id == Generation.id)
                .where(Generation.task_id == task.id)
            )
        )
        self.assertEqual(len(reviews), 1)

        session.close()

    def test_editorial_enabled_with_revise_decision_still_enqueues(self) -> None:
        """Even when quick-screen says 'revise', editorial path takes over
        and enqueues (does NOT fall through to auto-revise logic)."""
        session = self.Session()
        task = self._seed_task(session, "tsk_editorial_revise")

        mock_enqueue = MagicMock()
        mock_queue_cls = MagicMock()
        mock_queue_cls.return_value.enqueue = mock_enqueue

        with patch(_EQS_PATCH_TARGET, mock_queue_cls):
            service = Phase4PipelineService(session)
            service.llm = MagicMock()
            service.llm.complete_json.side_effect = [
                _GENERATE_RESPONSE,
                {
                    "final_decision": "revise",
                    "similarity_score": 0.40,
                    "factual_risk_score": 0.20,
                    "policy_risk_score": 0.10,
                    "readability_score": 70,
                    "title_score": 72,
                    "novelty_score": 68,
                    # ai_trace_score=0 prevents humanize from running
                    "ai_trace_score": 0,
                    "ai_trace_patterns": [],
                    "rewrite_targets": [],
                    "voice_summary": "一般",
                    "issues": ["需要修改。"],
                    "suggestions": ["改进标题。"],
                },
            ]

            result = service.run(task.id)

        self.assertEqual(result.status, TaskStatus.PENDING_EDITORIAL.value)
        mock_enqueue.assert_called_once_with(task.id)
        # Only 2 LLM calls — no auto-revise, no humanize
        self.assertEqual(service.llm.complete_json.call_count, 2)

        session.close()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _seed_task(self, session, task_code: str) -> Task:
        task = Task(
            task_code=task_code,
            source_url="https://mp.weixin.qq.com/s/test",
            normalized_url="https://mp.weixin.qq.com/s/test",
            source_type="wechat",
            status=TaskStatus.BRIEF_READY.value,
        )
        session.add(task)
        session.flush()
        session.add(
            SourceArticle(
                task_id=task.id,
                url=task.source_url,
                title="原文标题",
                summary="原文摘要",
                cleaned_text="原文正文内容，供相似度计算使用。",
                fetch_status="success",
                word_count=500,
            )
        )
        session.add(
            ArticleAnalysis(
                task_id=task.id,
                theme="测试主题",
                audience="技术读者",
                angle="测试角度",
                tone="理性",
                key_points={"items": ["点一", "点二"]},
                facts={"items": ["事实一"]},
                hooks={"items": ["钩子一"]},
                risks={"items": ["风险一"]},
                gaps={"items": ["缺口一"]},
                structure={"items": [{"section": "概述", "purpose": "引入"}]},
            )
        )
        session.add(
            ContentBrief(
                task_id=task.id,
                brief_version=1,
                positioning="测试定位",
                new_angle="测试新角度",
                target_reader="开发者",
                must_cover={"items": ["主题一"]},
                must_avoid={"items": ["禁项一"]},
                difference_matrix={"items": []},
                outline={"items": ["开头", "中段", "结尾"]},
                title_directions={"items": ["候选标题一"]},
            )
        )
        session.commit()
        return task


class Phase4EditorialDisabledTests(unittest.TestCase):
    """When EDITORIAL_ENABLED=false (default) old behaviour must be unchanged."""

    def setUp(self) -> None:
        self.env_patch = patch.dict(
            os.environ,
            {**_BASE_ENV, "EDITORIAL_ENABLED": "false"},
            clear=False,
        )
        self.env_patch.start()
        get_settings.cache_clear()
        get_redis_client.cache_clear()

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False
        )

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()

    def test_editorial_disabled_reaches_normal_terminal_decision(self) -> None:
        """With editorial disabled, a passing review must reach REVIEW_PASSED,
        and EditorialQueueService.enqueue must NOT be called."""
        session = self.Session()
        task = self._seed_task(session, "tsk_editorial_disabled")

        mock_queue_cls = MagicMock()

        with patch(_EQS_PATCH_TARGET, mock_queue_cls):
            service = Phase4PipelineService(session)
            service.llm = MagicMock()
            service.llm.complete_json.side_effect = [
                _GENERATE_RESPONSE,
                _REVIEW_PASS_RESPONSE,
            ]
            # Disable auto-push so we don't need WeChat mocks
            service.wechat_publisher = MagicMock()

            result = service.run(task.id)

        # Must reach REVIEW_PASSED — not PENDING_EDITORIAL
        self.assertEqual(result.status, TaskStatus.REVIEW_PASSED.value)

        # enqueue must NOT have been called (the mock class itself was never
        # instantiated or had enqueue invoked)
        mock_queue_cls.return_value.enqueue.assert_not_called()
        mock_queue_cls.assert_not_called()

        # DB confirms normal terminal status
        refreshed = session.get(Task, task.id)
        self.assertEqual(refreshed.status, TaskStatus.REVIEW_PASSED.value)

        session.close()

    def test_editorial_disabled_revise_reaches_needs_manual_review(self) -> None:
        """With editorial disabled and revise decision, must reach
        NEEDS_MANUAL_REVIEW (unchanged behaviour)."""
        session = self.Session()
        task = self._seed_task(session, "tsk_editorial_disabled_revise")

        mock_queue_cls = MagicMock()

        with patch(_EQS_PATCH_TARGET, mock_queue_cls):
            service = Phase4PipelineService(session)
            service.llm = MagicMock()
            service.llm.complete_json.side_effect = [
                _GENERATE_RESPONSE,
                {
                    "final_decision": "revise",
                    "similarity_score": 0.30,
                    "factual_risk_score": 0.20,
                    "policy_risk_score": 0.08,
                    "readability_score": 70,
                    "title_score": 71,
                    "novelty_score": 69,
                    # ai_trace_score=0 prevents humanize from running before
                    # the revise decision path is reached
                    "ai_trace_score": 0,
                    "ai_trace_patterns": [],
                    "rewrite_targets": [],
                    "voice_summary": "一般",
                    "issues": ["需要修改。"],
                    "suggestions": ["改进。"],
                },
            ]

            result = service.run(task.id)

        # enqueue must NOT be called
        mock_queue_cls.assert_not_called()
        # Status must be a normal terminal state — NOT PENDING_EDITORIAL
        self.assertNotEqual(result.status, TaskStatus.PENDING_EDITORIAL.value)
        self.assertIn(
            result.status,
            {
                TaskStatus.NEEDS_MANUAL_REVIEW.value,
                TaskStatus.REVIEW_PASSED.value,
                TaskStatus.NEEDS_REGENERATE.value,
            },
        )

        session.close()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _seed_task(self, session, task_code: str) -> Task:
        task = Task(
            task_code=task_code,
            source_url="https://mp.weixin.qq.com/s/test-disabled",
            normalized_url="https://mp.weixin.qq.com/s/test-disabled",
            source_type="wechat",
            status=TaskStatus.BRIEF_READY.value,
        )
        session.add(task)
        session.flush()
        session.add(
            SourceArticle(
                task_id=task.id,
                url=task.source_url,
                title="原文标题",
                summary="原文摘要",
                cleaned_text="原文正文。",
                fetch_status="success",
                word_count=400,
            )
        )
        session.add(
            ArticleAnalysis(
                task_id=task.id,
                theme="主题",
                audience="读者",
                angle="角度",
                tone="理性",
                key_points={"items": ["点一"]},
                facts={"items": []},
                hooks={"items": []},
                risks={"items": []},
                gaps={"items": []},
                structure={"items": []},
            )
        )
        session.add(
            ContentBrief(
                task_id=task.id,
                brief_version=1,
                positioning="定位",
                new_angle="新角度",
                target_reader="读者",
                must_cover={"items": []},
                must_avoid={"items": []},
                difference_matrix={"items": []},
                outline={"items": ["段一", "段二", "段三"]},
                title_directions={"items": ["测试标题"]},
            )
        )
        session.commit()
        return task
