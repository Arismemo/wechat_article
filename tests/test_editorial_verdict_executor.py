"""Tests for EditorialVerdictExecutor — executing the editorial board's verdict.

The board produces an EditorialReview (+ authoritative ReviewReport) but does
NOT act on it. The executor transitions the task and pushes on pass.

Covered branches:
  1. reject                        -> NEEDS_REGENERATE, push NOT called.
  2. pass + thresholds fail        -> NEEDS_MANUAL_REVIEW, push NOT called.
  3. pass + thresholds pass + push -> "pushed" (push mocked).
  4. pass + thresholds pass + blk  -> NEEDS_MANUAL_REVIEW (WechatPushBlockedError).
  5. revise                        -> NEEDS_MANUAL_REVIEW.
Plus a shared-helper test (passes_review_thresholds parity with phase4).
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.enums import TaskStatus
from app.db.base import Base
from app.models.editorial_review import EditorialReview
from app.models.generation import Generation
from app.models.review_report import ReviewReport
from app.models.task import Task
from app.services.editorial_verdict_executor import EditorialVerdictExecutor
from app.services.wechat_push_policy_service import WechatPushBlockedError


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


BASE_ENV = {
    "APP_BASE_URL": "https://e.com",
    "API_BEARER_TOKEN": "t",
    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "REDIS_URL": "redis://localhost:6379/0",
    "LLM_PROVIDER": "Z",
    "LLM_API_KEY": "k",
    "LLM_MODEL_ANALYZE": "m",
    "LLM_MODEL_WRITE": "m",
    "LLM_MODEL_REVIEW": "m",
    "SEARCH_PROVIDER": "S",
    "WECHAT_APP_ID": "w",
    "WECHAT_APP_SECRET": "s",
}

# Scores that comfortably clear every phase4 threshold (low risk, high quality).
_PASSING_SCORES = {
    "similarity_score": 0.15,
    "factual_risk_score": 0.10,
    "policy_risk_score": 0.05,
    "readability_score": 88.0,
    "title_score": 85.0,
    "novelty_score": 84.0,
}


class EditorialVerdictExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, BASE_ENV, clear=False)
        self.env_patch.start()
        from app.settings import get_settings

        get_settings.cache_clear()

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False
        )

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        from app.settings import get_settings

        get_settings.cache_clear()

    # ── seeding ──────────────────────────────────────────────────────────────
    def _seed(
        self,
        session,
        *,
        decision: str,
        scores: dict | None = None,
    ) -> tuple[Task, Generation, EditorialReview, ReviewReport]:
        task = Task(
            task_code="tsk_verdict",
            source_url="https://mp.weixin.qq.com/s/verdict",
            normalized_url="https://mp.weixin.qq.com/s/verdict",
            source_type="wechat",
            status=TaskStatus.PENDING_EDITORIAL.value,
        )
        session.add(task)
        session.flush()

        generation = Generation(
            task_id=task.id,
            model_name="glm-5.2",
            title="一篇关于 AI 的稿件",
            subtitle="副标题",
            digest="摘要内容",
            markdown_content="# 标题\n\n正文第一段。\n\n正文第二段。",
            # The push path resolves the *accepted* generation — phase4 marks it
            # accepted at review_passed; the board hands off an already-accepted gen.
            status="accepted",
        )
        session.add(generation)
        session.flush()

        report_scores = scores if scores is not None else _PASSING_SCORES
        report = ReviewReport(
            generation_id=generation.id,
            final_decision=decision,
            # ai_trace_score 5.0 stays under the default rewrite threshold (10),
            # so a clean pass actually clears every gate.
            issues={"source": "editorial_board", "ai_trace_score": 5.0},
            suggestions={"rewrite_targets": []},
            **report_scores,
        )
        session.add(report)
        session.flush()

        review = EditorialReview(
            task_id=task.id,
            generation_id=generation.id,
            status="converged",
            rounds_used=1,
            decision=decision,
            review_report_id=report.id,
        )
        session.add(review)
        session.flush()
        session.commit()
        return task, generation, review, report

    def _refresh_status(self, session, task_id: str) -> str:
        session.expire_all()
        return session.get(Task, task_id).status

    # ── 1. reject ────────────────────────────────────────────────────────────
    def test_reject_sets_needs_regenerate(self) -> None:
        session = self.Session()
        task, _gen, review, _report = self._seed(session, decision="reject")

        with patch(
            "app.services.editorial_verdict_executor.WechatDraftPublishService"
        ) as mock_publish_cls:
            outcome = EditorialVerdictExecutor(session).execute(review)

        self.assertEqual(outcome, "reject")
        self.assertEqual(
            self._refresh_status(session, task.id), TaskStatus.NEEDS_REGENERATE.value
        )
        # No push attempted on reject.
        mock_publish_cls.assert_not_called()
        session.close()

    # ── 2. pass + thresholds fail ────────────────────────────────────────────
    def test_pass_thresholds_fail_sets_needs_manual_review_no_push(self) -> None:
        session = self.Session()
        # similarity 0.9 blows past phase4_similarity_max (default 0.45-ish) ->
        # thresholds fail even though decision is pass.
        bad_scores = dict(_PASSING_SCORES, similarity_score=0.9)
        task, _gen, review, _report = self._seed(
            session, decision="pass", scores=bad_scores
        )

        with patch(
            "app.services.editorial_verdict_executor.WechatDraftPublishService"
        ) as mock_publish_cls:
            outcome = EditorialVerdictExecutor(session).execute(review)

        self.assertEqual(outcome, "manual_review")
        self.assertEqual(
            self._refresh_status(session, task.id),
            TaskStatus.NEEDS_MANUAL_REVIEW.value,
        )
        # Thresholds failed -> push must NOT be attempted.
        mock_publish_cls.assert_not_called()
        session.close()

    # ── 3. pass + thresholds pass + push succeeds ────────────────────────────
    def test_pass_thresholds_pass_push_success_returns_pushed(self) -> None:
        session = self.Session()
        task, _gen, review, _report = self._seed(session, decision="pass")

        with patch(
            "app.services.editorial_verdict_executor.WechatDraftPublishService"
        ) as mock_publish_cls:
            instance = mock_publish_cls.return_value
            instance.push_latest_accepted_generation.return_value = object()

            outcome = EditorialVerdictExecutor(session).execute(review)

        self.assertEqual(outcome, "pushed")
        instance.push_latest_accepted_generation.assert_called_once_with(task.id)
        session.close()

    # ── 4. pass + thresholds pass + push blocked ─────────────────────────────
    def test_pass_thresholds_pass_push_blocked_sets_manual_review(self) -> None:
        session = self.Session()
        task, _gen, review, _report = self._seed(session, decision="pass")

        with patch(
            "app.services.editorial_verdict_executor.WechatDraftPublishService"
        ) as mock_publish_cls:
            instance = mock_publish_cls.return_value
            instance.push_latest_accepted_generation.side_effect = WechatPushBlockedError(
                "push policy blocks auto-push"
            )

            outcome = EditorialVerdictExecutor(session).execute(review)

        self.assertEqual(outcome, "push_blocked")
        self.assertEqual(
            self._refresh_status(session, task.id),
            TaskStatus.NEEDS_MANUAL_REVIEW.value,
        )
        session.close()

    # ── 4b. pass + thresholds pass + push errors (non-blocked) ───────────────
    def test_pass_thresholds_pass_push_error_sets_push_failed_and_reraises(self) -> None:
        session = self.Session()
        task, _gen, review, _report = self._seed(session, decision="pass")

        with patch(
            "app.services.editorial_verdict_executor.WechatDraftPublishService"
        ) as mock_publish_cls:
            instance = mock_publish_cls.return_value
            instance.push_latest_accepted_generation.side_effect = RuntimeError(
                "wechat API 500"
            )

            with self.assertRaises(RuntimeError):
                EditorialVerdictExecutor(session).execute(review)

        # Status committed as PUSH_FAILED before re-raise (T3a retry can pick up).
        self.assertEqual(
            self._refresh_status(session, task.id), TaskStatus.PUSH_FAILED.value
        )
        session.close()

    # ── 5. revise ────────────────────────────────────────────────────────────
    def test_revise_sets_needs_manual_review(self) -> None:
        session = self.Session()
        task, _gen, review, _report = self._seed(session, decision="revise")

        with patch(
            "app.services.editorial_verdict_executor.WechatDraftPublishService"
        ) as mock_publish_cls:
            outcome = EditorialVerdictExecutor(session).execute(review)

        self.assertEqual(outcome, "manual_review")
        self.assertEqual(
            self._refresh_status(session, task.id),
            TaskStatus.NEEDS_MANUAL_REVIEW.value,
        )
        mock_publish_cls.assert_not_called()
        session.close()

    # ── fallback: review_report_id missing -> latest by generation ───────────
    def test_loads_latest_report_when_review_report_id_missing(self) -> None:
        session = self.Session()
        task, _gen, review, _report = self._seed(session, decision="reject")
        # Simulate an EditorialReview that never recorded its report id.
        review.review_report_id = None
        session.flush()
        session.commit()

        with patch(
            "app.services.editorial_verdict_executor.WechatDraftPublishService"
        ):
            outcome = EditorialVerdictExecutor(session).execute(review)

        self.assertEqual(outcome, "reject")
        self.assertEqual(
            self._refresh_status(session, task.id), TaskStatus.NEEDS_REGENERATE.value
        )
        session.close()


class SharedThresholdHelperTests(unittest.TestCase):
    """passes_review_thresholds must give the same verdict phase4 relies on."""

    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, BASE_ENV, clear=False)
        self.env_patch.start()
        from app.settings import get_settings

        get_settings.cache_clear()

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False
        )

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        from app.settings import get_settings

        get_settings.cache_clear()

    def _make_report(self, session, slug: str, **scores) -> ReviewReport:
        task = Task(
            task_code=f"tsk_helper_{slug}",
            source_url=f"https://mp.weixin.qq.com/s/helper-{slug}",
            normalized_url=f"https://mp.weixin.qq.com/s/helper-{slug}",
            source_type="wechat",
            status=TaskStatus.PENDING_EDITORIAL.value,
        )
        session.add(task)
        session.flush()
        generation = Generation(
            task_id=task.id, model_name="m", markdown_content="# t\n\n正文。", status="accepted"
        )
        session.add(generation)
        session.flush()
        report = ReviewReport(
            generation_id=generation.id,
            final_decision="pass",
            issues={"ai_trace_score": 5.0},
            suggestions={},
            **scores,
        )
        session.add(report)
        session.flush()
        return report

    def test_shared_helper_matches_phase4_instance_method(self) -> None:
        from app.services.phase4_pipeline_service import (
            Phase4PipelineService,
            passes_review_thresholds,
        )
        from app.services.system_setting_service import SystemSettingService

        session = self.Session()
        passing = self._make_report(session, "pass", **_PASSING_SCORES)
        failing = self._make_report(
            session, "fail", **dict(_PASSING_SCORES, similarity_score=0.95)
        )
        session.commit()

        phase4 = Phase4PipelineService(session)
        settings_svc = SystemSettingService(session)

        # Parity: instance delegator and shared helper agree, both directions.
        self.assertTrue(passes_review_thresholds(passing, settings_svc))
        self.assertTrue(phase4._passes_thresholds(passing))
        self.assertFalse(passes_review_thresholds(failing, settings_svc))
        self.assertFalse(phase4._passes_thresholds(failing))
        session.close()


if __name__ == "__main__":
    unittest.main()
