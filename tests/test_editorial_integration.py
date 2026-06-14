"""Task 11: End-to-end integration test — editorial board chain (all LLM mocked).

Chain under test:
  seed(task + generation + brief + source)
  → EditorialBoardService.review(task_id)          [FakeClient, no real GLM]
  → EditorialReview row persisted                  [status/rounds/decision/transcript]
  → ReviewReport row persisted                     [final_decision, risk scores 0-1 scale]
  → extract_review_metadata(report.issues, report.suggestions)
                                                   [rewrite_targets non-empty for 'revise']

Scope (T11):
  - Single end-to-end happy-path (decision='revise', early converge, similarity 0.20 on 0-1).
  - Does NOT duplicate T6 (test_editorial_board_service.py) fine-grained unit assertions:
      max_rounds, score arithmetic per column, chief_directives mapping detail, etc.
  - Phase4 hook path (EDITORIAL_ENABLED enqueue) is covered by T9
    (test_phase4_editorial_integration.py); not repeated here.
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
from app.core.review_metadata import extract_review_metadata
from app.db.base import Base
from app.models.content_brief import ContentBrief
from app.models.generation import Generation
from app.models.source_article import SourceArticle
from app.models.task import Task
from app.repositories.editorial_review_repository import EditorialReviewRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.services.editorial_board_service import EditorialBoardService


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


# ── env patch ────────────────────────────────────────────────────────────────
_ENV = {
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
    # T11-specific: editorial enabled, early convergence after 1 round
    "EDITORIAL_ENABLED": "true",
    "EDITORIAL_MAX_DEBATE_ROUNDS": "2",
    "EDITORIAL_LLM_MAX_CONCURRENCY": "3",
}


# ── FakeClient ───────────────────────────────────────────────────────────────
class _FakeClient:
    """Routes complete_json by detecting intent in the prompt content.

    - convergence prompt (contains 'new_substantive_objection') → converge immediately
    - chief verdict prompt (contains 'final_scores' and 'decision') → 'revise' verdict
    - reviewer prompts (everything else) → mixed stances (pass / revise / reject)
    """

    _STANCES = ["revise", "pass", "revise", "reject", "revise", "pass"]

    def __init__(self) -> None:
        self._call_count = 0

    def complete_json(self, *, system_prompt: str, user_prompt: str, **_kwargs) -> dict:
        haystack = f"{system_prompt}\n{user_prompt}"

        # Convergence judgement (managing_editor step)
        if "new_substantive_objection" in haystack:
            return {
                "new_substantive_objection": False,  # converge after round 1
                "summary": "no new substantive objection",
            }

        # Chief verdict (chief_editor step)
        if "final_scores" in haystack and "decision" in haystack:
            return {
                "decision": "revise",
                "final_scores": {
                    # similarity on 0-100 scale (chief uses 0-100);
                    # _persist_review_report will convert to 0-1 (÷100).
                    "similarity": 20,
                    "factual_risk": 10,
                    "policy_risk": 5,
                    "readability": 75,
                    "title": 72,
                    "novelty": 68,
                    "ai_trace": 60,
                    "overall": 70,
                },
                "rationale": "标题缺数字，论证不足",
                "revision_directives": [
                    {
                        "location": "标题",
                        "problem": "无具体数字",
                        "fix": "加具体数字到标题",
                    },
                    {
                        "location": "段落b2",
                        "problem": "论证不足",
                        "fix": "补充数据支撑",
                    },
                ],
                "dissent_summary": "法务保留异议",
            }

        # Reviewer role opinion (mix of stances for realism)
        stance = self._STANCES[self._call_count % len(self._STANCES)]
        self._call_count += 1
        return {
            "scores": {"overall": 70},
            "issues": ["机械腔过重"],
            "stance": stance,
            "key_argument": "表达机械，缺少人味",
        }


# ── Test ──────────────────────────────────────────────────────────────────────
class EditorialIntegrationTest(unittest.TestCase):
    """Single end-to-end chain: board.review() → EditorialReview → ReviewReport → metadata."""

    def setUp(self) -> None:
        self._env_patch = patch.dict(os.environ, _ENV, clear=False)
        self._env_patch.start()
        from app.settings import get_settings
        get_settings.cache_clear()

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False
        )

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self._env_patch.stop()
        from app.settings import get_settings
        get_settings.cache_clear()

    # ── seed helpers ─────────────────────────────────────────────────────────

    def _seed(self, session) -> tuple[Task, Generation]:
        task = Task(
            task_code="tsk_e2e_integration",
            source_url="https://mp.weixin.qq.com/s/e2e",
            normalized_url="https://mp.weixin.qq.com/s/e2e",
            source_type="wechat",
            status=TaskStatus.PENDING_EDITORIAL.value,
        )
        session.add(task)
        session.flush()

        generation = Generation(
            task_id=task.id,
            model_name="glm-4",
            title="AI 创业者必读：3 个反直觉结论",
            subtitle="副标题",
            digest="摘要内容",
            markdown_content=(
                "# AI 创业者必读：3 个反直觉结论\n\n"
                "## 第一节\n第一节正文内容，数据支撑。\n\n"
                "## 第二节\n第二节正文内容，论证不足。\n\n"
                "## 结语\n总结。\n"
            ),
            status="generated",
        )
        session.add(generation)
        session.flush()

        # ContentBrief — read by _safe_brief_summary
        session.add(
            ContentBrief(
                task_id=task.id,
                brief_version=1,
                positioning="AI+产业",
                new_angle="反直觉结论",
                target_reader="单人运营者",
            )
        )

        # SourceArticle — read by _safe_source_summary
        session.add(
            SourceArticle(
                task_id=task.id,
                url=task.source_url,
                title="原文标题",
                summary="原文摘要，供相似度判断使用。",
                cleaned_text="原文正文内容。",
                fetch_status="success",
                word_count=600,
            )
        )
        session.flush()
        return task, generation

    # ── single chain test ────────────────────────────────────────────────────

    def test_end_to_end_chain(self) -> None:
        """Full chain: board.review() → EditorialReview → ReviewReport → extract_review_metadata."""
        session = self.Session()
        task, generation = self._seed(session)
        session.commit()

        fake_client = _FakeClient()
        service = EditorialBoardService(session, fake_client)
        review = service.review(task.id)
        session.commit()

        # ── 1. EditorialReview row persisted ─────────────────────────────────
        # Status: converged (FakeClient always returns new_substantive_objection=False)
        self.assertEqual(review.status, "converged", "EditorialReview.status must be 'converged'")

        # Early convergence: rounds_used < EDITORIAL_MAX_DEBATE_ROUNDS (2)
        self.assertLess(
            review.rounds_used,
            2,
            f"Expected early convergence (rounds_used < 2), got {review.rounds_used}",
        )

        # Decision from chief verdict
        self.assertEqual(review.decision, "revise", "EditorialReview.decision must be 'revise'")

        # Transcript structure: round 0 (independent) + at least round 1 (debate)
        self.assertIsNotNone(review.transcript, "transcript must not be None")
        round_nos = [r["round_no"] for r in review.transcript["rounds"]]
        self.assertIn(0, round_nos, "transcript must contain round 0 (independent review)")
        self.assertIn(1, round_nos, "transcript must contain round 1 (debate round)")

        # Revision directives populated for 'revise' decision
        self.assertTrue(
            review.revision_directives,
            "revision_directives must be non-empty when decision='revise'",
        )

        # Fetchable via repository
        fetched_review = EditorialReviewRepository(session).get_latest_by_task_id(task.id)
        self.assertIsNotNone(fetched_review)
        self.assertEqual(fetched_review.id, review.id)

        # ── 2. ReviewReport row persisted ────────────────────────────────────
        report = ReviewReportRepository(session).get_latest_by_generation_id(generation.id)
        self.assertIsNotNone(report, "ReviewReport row must be created by the board service")

        # final_decision matches chief verdict
        self.assertEqual(report.final_decision, "revise", "report.final_decision must be 'revise'")

        # review_report_id cross-linked
        self.assertEqual(review.review_report_id, report.id)

        # Risk scores converted from 0-100 (chief) → 0-1 scale (ReviewReport)
        similarity = float(report.similarity_score or 0)
        self.assertAlmostEqual(
            similarity,
            0.20,
            places=6,
            msg=f"similarity_score must be 0.20 (not 20 — should be on 0-1 scale), got {similarity}",
        )
        self.assertLessEqual(
            similarity,
            1.0,
            msg="similarity_score > 1.0 — still on 0-100 scale!",
        )

        factual_risk = float(report.factual_risk_score or 0)
        self.assertAlmostEqual(factual_risk, 0.10, places=6)
        self.assertLessEqual(factual_risk, 1.0, msg="factual_risk_score > 1.0")

        policy_risk = float(report.policy_risk_score or 0)
        self.assertAlmostEqual(policy_risk, 0.05, places=6)
        self.assertLessEqual(policy_risk, 1.0, msg="policy_risk_score > 1.0")

        # ── 3. extract_review_metadata yields non-empty rewrite_targets ───────
        # This is the humanize/auto-revise contract: the board's revision_directives
        # must flow through ReviewReport.suggestions into extract_review_metadata.
        metadata = extract_review_metadata(report.issues, report.suggestions)
        self.assertTrue(
            metadata.rewrite_targets,
            "extract_review_metadata must yield non-empty rewrite_targets "
            "(board→ReviewReport→metadata chain is broken)",
        )
        self.assertEqual(
            len(metadata.rewrite_targets),
            2,
            "Expected 2 rewrite_targets (one per revision_directive)",
        )

        # Each target has required fields
        for target in metadata.rewrite_targets:
            self.assertTrue(target.block_id, "rewrite_target missing block_id")
            self.assertTrue(target.reason, "rewrite_target missing reason")
            self.assertTrue(target.instruction, "rewrite_target missing instruction")

        # Field mapping: location→block_id, problem→reason, fix→instruction
        block_ids = {t.block_id for t in metadata.rewrite_targets}
        self.assertIn("标题", block_ids, "location '标题' must map to block_id")
        self.assertIn("段落b2", block_ids, "location '段落b2' must map to block_id")

        reasons = {t.reason for t in metadata.rewrite_targets}
        self.assertIn("无具体数字", reasons, "problem must map to reason")

        instructions = {t.instruction for t in metadata.rewrite_targets}
        self.assertIn("加具体数字到标题", instructions, "fix must map to instruction")

        session.close()


if __name__ == "__main__":
    unittest.main()
