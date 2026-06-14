"""Tests for the editorial bounded revise loop (OPT-2).

run_editorial_revise_loop drives: review → act; if not a clean pushable pass,
regenerate an improved draft from the board's directives and re-submit — until
pass+thresholds (push) or max iterations (then NEEDS_MANUAL_REVIEW).

We exercise the REAL loop function with the REAL EditorialVerdictExecutor against
an in-memory DB, mocking only the two heavy collaborators the loop has no business
running for real:
  * the editorial board (a FakeBoard returning a scripted decision per turn), and
  * Phase4PipelineService.regenerate_from_editorial (so no LLM / no real rewrite).
The WeChat push is mocked too (pushed path).

Covered:
  1. Convergence: revise → (regenerate) → pass+thresholds → "pushed".
  2. Exhaustion: always revise → after max_iter, finalize_manual → NEEDS_MANUAL_REVIEW.
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
from app.models.audit_log import AuditLog
from app.models.editorial_review import EditorialReview
from app.models.generation import Generation
from app.models.review_report import ReviewReport
from app.models.task import Task
from scripts.run_editorial_worker import run_editorial_revise_loop


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

_PASSING_SCORES = {
    "similarity_score": 0.15,
    "factual_risk_score": 0.10,
    "policy_risk_score": 0.05,
    "readability_score": 88.0,
    "title_score": 85.0,
    "novelty_score": 84.0,
}
# similarity 0.95 misses the phase4 similarity threshold even with decision=pass.
_FAILING_SCORES = dict(_PASSING_SCORES, similarity_score=0.95)


class FakeBoard:
    """Stands in for EditorialBoardService. Each .review() call persists a fresh
    EditorialReview + ReviewReport scripted by the next (decision, scores) pair,
    so the REAL executor sees an authoritative report exactly as in production."""

    def __init__(self, session, *, script):
        self._session = session
        self._script = list(script)
        self._i = 0
        self.review_calls = 0

    def __call__(self, session, client):  # EditorialBoardService(session, client)
        return self

    def review(self, task_id: str) -> EditorialReview:
        self.review_calls += 1
        decision, scores = self._script[min(self._i, len(self._script) - 1)]
        self._i += 1
        generation = (
            self._session.scalars(
                select(Generation).where(Generation.task_id == task_id)
            )
            .all()[-1]
        )
        report = ReviewReport(
            generation_id=generation.id,
            final_decision=decision,
            issues={"source": "editorial_board", "ai_trace_score": 5.0},
            suggestions={"rewrite_targets": []},
            **scores,
        )
        self._session.add(report)
        self._session.flush()
        review = EditorialReview(
            task_id=task_id,
            generation_id=generation.id,
            status="converged",
            rounds_used=1,
            decision=decision,
            review_report_id=report.id,
        )
        self._session.add(review)
        self._session.flush()
        self._session.commit()
        return review


class EditorialReviseLoopTests(unittest.TestCase):
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

    def _seed(self, session) -> Task:
        task = Task(
            task_code="tsk_revise_loop",
            source_url="https://mp.weixin.qq.com/s/loop",
            normalized_url="https://mp.weixin.qq.com/s/loop",
            source_type="wechat",
            status=TaskStatus.PENDING_EDITORIAL.value,
        )
        session.add(task)
        session.flush()
        session.add(
            Generation(
                task_id=task.id,
                model_name="glm-5.2",
                title="一篇稿件",
                digest="摘要",
                markdown_content="# 标题\n\n正文。",
                status="accepted",
            )
        )
        session.flush()
        session.commit()
        return task

    def _status(self, session, task_id: str) -> str:
        session.expire_all()
        return session.get(Task, task_id).status

    # ── 1. convergence: revise then pass -> pushed ───────────────────────────
    def test_loop_converges_revise_then_pass_pushes(self) -> None:
        session = self.Session()
        task = self._seed(session)
        fake_board = FakeBoard(
            session,
            script=[("revise", _PASSING_SCORES), ("pass", _PASSING_SCORES)],
        )

        with patch(
            "scripts.run_editorial_worker.EditorialBoardService", fake_board
        ), patch(
            "scripts.run_editorial_worker.Phase4PipelineService"
        ) as mock_phase4_cls, patch(
            "app.services.editorial_verdict_executor.WechatDraftPublishService"
        ) as mock_publish_cls:
            mock_publish_cls.return_value.push_latest_accepted_generation.return_value = object()
            outcome = run_editorial_revise_loop(
                session, client=MagicMock(), max_iter=2, task_id=task.id
            )

        self.assertEqual(outcome, "pushed")
        # First verdict was revise -> one regenerate fed the directives back.
        mock_phase4_cls.return_value.regenerate_from_editorial.assert_called_once_with(
            task.id
        )
        # Board reviewed twice (initial + after-revise), push attempted once.
        self.assertEqual(fake_board.review_calls, 2)
        mock_publish_cls.return_value.push_latest_accepted_generation.assert_called_once_with(
            task.id
        )
        session.close()

    # ── 2. exhaustion: always revise -> finalize_manual ──────────────────────
    def test_loop_exhausts_to_manual_review(self) -> None:
        session = self.Session()
        task = self._seed(session)
        fake_board = FakeBoard(session, script=[("revise", _PASSING_SCORES)])

        with patch(
            "scripts.run_editorial_worker.EditorialBoardService", fake_board
        ), patch(
            "scripts.run_editorial_worker.Phase4PipelineService"
        ) as mock_phase4_cls, patch(
            "app.services.editorial_verdict_executor.WechatDraftPublishService"
        ) as mock_publish_cls:
            outcome = run_editorial_revise_loop(
                session, client=MagicMock(), max_iter=2, task_id=task.id
            )

        self.assertEqual(outcome, "manual_exhausted")
        # max_iter=2 -> 3 review turns; regenerate runs on turns 0 and 1 (not the
        # last, which finalizes), push never attempted.
        self.assertEqual(fake_board.review_calls, 3)
        self.assertEqual(
            mock_phase4_cls.return_value.regenerate_from_editorial.call_count, 2
        )
        mock_publish_cls.assert_not_called()
        self.assertEqual(
            self._status(session, task.id), TaskStatus.NEEDS_MANUAL_REVIEW.value
        )
        manual_logs = list(
            session.scalars(
                select(AuditLog).where(
                    AuditLog.task_id == task.id,
                    AuditLog.action == "editorial.verdict.manual_required",
                )
            )
        )
        self.assertEqual(len(manual_logs), 1)
        self.assertEqual(manual_logs[0].payload["reason"], "revise_exhausted")
        session.close()

    # ── 3. pass-but-thresholds-fail also drives a revise turn ────────────────
    def test_pass_thresholds_fail_then_clean_pass_pushes(self) -> None:
        session = self.Session()
        task = self._seed(session)
        fake_board = FakeBoard(
            session,
            # decision=pass but failing scores -> needs_revision -> then clean pass.
            script=[("pass", _FAILING_SCORES), ("pass", _PASSING_SCORES)],
        )

        with patch(
            "scripts.run_editorial_worker.EditorialBoardService", fake_board
        ), patch(
            "scripts.run_editorial_worker.Phase4PipelineService"
        ) as mock_phase4_cls, patch(
            "app.services.editorial_verdict_executor.WechatDraftPublishService"
        ) as mock_publish_cls:
            mock_publish_cls.return_value.push_latest_accepted_generation.return_value = object()
            outcome = run_editorial_revise_loop(
                session, client=MagicMock(), max_iter=2, task_id=task.id
            )

        self.assertEqual(outcome, "pushed")
        mock_phase4_cls.return_value.regenerate_from_editorial.assert_called_once_with(
            task.id
        )
        session.close()


if __name__ == "__main__":
    unittest.main()
