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
from app.models.content_brief import ContentBrief
from app.models.generation import Generation
from app.models.task import Task
from app.repositories.editorial_review_repository import EditorialReviewRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.services.editorial_board_service import EditorialBoardService


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
    "EDITORIAL_MAX_DEBATE_ROUNDS": "2",
    "EDITORIAL_LLM_MAX_CONCURRENCY": "3",
}


class FakeClient:
    """Routes complete_json by detecting role intent in the prompts.

    - managing/convergence prompt -> {"new_substantive_objection": ...}
    - chief verdict prompt -> EditorialVerdict-shaped dict
    - everything else (reviewers) -> RoleOpinion-shaped dict
    """

    def __init__(
        self,
        *,
        new_substantive_objection: bool = False,
        chief_decision: str = "pass",
        chief_directives: list[dict] | None = None,
    ) -> None:
        self.new_substantive_objection = new_substantive_objection
        self.chief_decision = chief_decision
        self.chief_directives = chief_directives or []
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, *, system_prompt: str, user_prompt: str, **_kwargs) -> dict:
        self.calls.append((system_prompt, user_prompt))
        haystack = f"{system_prompt}\n{user_prompt}"
        if "new_substantive_objection" in haystack:
            return {
                "new_substantive_objection": self.new_substantive_objection,
                "summary": "managing summary",
            }
        if "final_scores" in haystack and "decision" in haystack:
            return {
                "decision": self.chief_decision,
                "final_scores": {
                    "similarity": 12,
                    "factual_risk": 8,
                    "policy_risk": 5,
                    "readability": 82,
                    "title": 77,
                    "novelty": 70,
                    "ai_trace": 65,
                    "overall": 74,
                },
                "rationale": "chief rationale",
                "revision_directives": self.chief_directives,
                "dissent_summary": "legal holds reservation",
            }
        return {
            "scores": {"overall": 70},
            "issues": ["some issue"],
            "stance": "revise",
            "key_argument": "mechanical tone",
        }


class EditorialBoardServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        from app.settings import get_settings

        get_settings.cache_clear()

    def _seed(self, session) -> tuple[Task, Generation]:
        task = Task(
            task_code="tsk_board",
            source_url="https://mp.weixin.qq.com/s/board",
            normalized_url="https://mp.weixin.qq.com/s/board",
            source_type="wechat",
            status=TaskStatus.PENDING_EDITORIAL.value,
        )
        session.add(task)
        session.flush()

        generation = Generation(
            task_id=task.id,
            model_name="glm-4",
            title="一篇关于 AI 的稿件",
            subtitle="副标题",
            digest="摘要内容",
            markdown_content="# 标题\n\n正文第一段。\n\n正文第二段。",
            status="generated",
        )
        session.add(generation)
        session.flush()

        brief = ContentBrief(
            task_id=task.id,
            brief_version=1,
            positioning="AI+产业",
            new_angle="反直觉结论",
            target_reader="单人运营者",
        )
        session.add(brief)
        session.flush()
        return task, generation

    def _run(self, client: FakeClient):
        with patch.dict(os.environ, BASE_ENV, clear=False):
            from app.settings import get_settings

            get_settings.cache_clear()
            session = self.Session()
            task, generation = self._seed(session)
            session.commit()
            service = EditorialBoardService(session, client)
            review = service.review(task.id)
            session.commit()
            return session, task, generation, review

    def test_convergence_stops_early(self) -> None:
        client = FakeClient(new_substantive_objection=False)
        session, task, generation, review = self._run(client)

        self.assertEqual(review.status, "converged")
        # MAX=2, converges at round 1 -> rounds_used == 1 < MAX.
        self.assertLess(review.rounds_used, 2)
        self.assertEqual(review.rounds_used, 1)
        session.close()

    def test_max_rounds_when_always_objecting(self) -> None:
        client = FakeClient(new_substantive_objection=True)
        session, task, generation, review = self._run(client)

        self.assertEqual(review.status, "max_rounds")
        self.assertEqual(review.rounds_used, 2)
        session.close()

    def test_terminal_persists_editorial_review_and_report(self) -> None:
        client = FakeClient(new_substantive_objection=False, chief_decision="pass")
        session, task, generation, review = self._run(client)

        # EditorialReview row persisted with decision + transcript.
        self.assertEqual(review.decision, "pass")
        self.assertIsNotNone(review.transcript)
        round_nos = [r["round_no"] for r in review.transcript["rounds"]]
        self.assertIn(0, round_nos)  # independent review round
        self.assertIn(1, round_nos)  # at least one debate round
        # round 0 opinions exist and exclude chief/managing.
        round0 = next(r for r in review.transcript["rounds"] if r["round_no"] == 0)
        role_keys = {o["role_key"] for o in round0["opinions"]}
        self.assertNotIn("chief_editor", role_keys)
        self.assertNotIn("managing_editor", role_keys)
        self.assertGreater(len(round0["opinions"]), 0)

        # A new ReviewReport row created with final_decision == verdict.decision.
        report = ReviewReportRepository(session).get_latest_by_generation_id(generation.id)
        self.assertIsNotNone(report)
        self.assertEqual(report.final_decision, "pass")
        self.assertEqual(review.review_report_id, report.id)
        # score columns mapped from final_scores.
        self.assertAlmostEqual(float(report.readability_score), 82.0)
        self.assertAlmostEqual(float(report.factual_risk_score), 8.0)

        # editorial review fetchable via repository.
        fetched = EditorialReviewRepository(session).get_latest_by_task_id(task.id)
        self.assertEqual(fetched.id, review.id)
        session.close()

    def test_revise_decision_populates_directives(self) -> None:
        client = FakeClient(
            new_substantive_objection=False,
            chief_decision="revise",
            chief_directives=[{"location": "标题", "problem": "无数字", "fix": "加具体数字"}],
        )
        session, task, generation, review = self._run(client)

        self.assertEqual(review.decision, "revise")
        self.assertTrue(review.revision_directives)
        self.assertEqual(review.revision_directives[0]["location"], "标题")

        report = ReviewReportRepository(session).get_latest_by_generation_id(generation.id)
        self.assertEqual(report.final_decision, "revise")
        session.close()


if __name__ == "__main__":
    unittest.main()
