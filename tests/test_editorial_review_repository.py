import unittest

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.enums import TaskStatus
from app.db.base import Base
from app.models.editorial_review import EditorialReview
from app.models.generation import Generation
from app.models.task import Task
from app.repositories.editorial_review_repository import EditorialReviewRepository
from app.schemas.editorial import EditorialVerdict, RevisionDirective


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class EditorialReviewRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)

    def _make_task_and_generation(self, session):
        task = Task(
            task_code="tsk_editorial_test",
            source_url="https://mp.weixin.qq.com/s/editorial_test",
            normalized_url="https://mp.weixin.qq.com/s/editorial_test",
            source_type="wechat",
            status=TaskStatus.REVIEWING.value,
        )
        session.add(task)
        session.flush()

        generation = Generation(
            task_id=task.id,
            model_name="glm-4",
            status="generated",
        )
        session.add(generation)
        session.flush()

        return task, generation

    def test_create_and_get_latest_by_task_id(self) -> None:
        session = self.Session()
        task, generation = self._make_task_and_generation(session)

        repo = EditorialReviewRepository(session)
        review = EditorialReview(
            task_id=task.id,
            generation_id=generation.id,
            status="running",
        )
        created = repo.create(review)
        session.commit()

        self.assertIsNotNone(created.id)
        self.assertEqual(created.task_id, task.id)
        self.assertEqual(created.generation_id, generation.id)
        self.assertEqual(created.status, "running")

        fetched = repo.get_latest_by_task_id(task.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, created.id)

        session.close()

    def test_get_by_generation_id(self) -> None:
        session = self.Session()
        task, generation = self._make_task_and_generation(session)

        repo = EditorialReviewRepository(session)
        review = EditorialReview(
            task_id=task.id,
            generation_id=generation.id,
            status="running",
        )
        created = repo.create(review)
        session.commit()

        fetched = repo.get_by_generation_id(generation.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, created.id)

        session.close()

    def test_get_latest_by_task_id_returns_none_when_absent(self) -> None:
        session = self.Session()
        repo = EditorialReviewRepository(session)
        result = repo.get_latest_by_task_id("non-existent-id")
        self.assertIsNone(result)
        session.close()

    def test_get_by_generation_id_returns_none_when_absent(self) -> None:
        session = self.Session()
        repo = EditorialReviewRepository(session)
        result = repo.get_by_generation_id("non-existent-id")
        self.assertIsNone(result)
        session.close()

    def test_transcript_json_roundtrip(self) -> None:
        session = self.Session()
        task, generation = self._make_task_and_generation(session)

        repo = EditorialReviewRepository(session)
        transcript = {
            "rounds": [
                {
                    "round_no": 0,
                    "opinions": [
                        {"role_key": "copy_editor", "scores": {"ai_trace": 70}, "issues": ["机械腔"], "stance": "revise", "key_argument": "排序词过多"},
                        {"role_key": "chief_editor", "scores": {"overall": 80}, "issues": [], "stance": "pass", "key_argument": "整体尚可"},
                    ],
                }
            ]
        }
        review = EditorialReview(
            task_id=task.id,
            generation_id=generation.id,
            status="converged",
            transcript=transcript,
        )
        repo.create(review)
        session.commit()

        fetched = repo.get_latest_by_task_id(task.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.transcript["rounds"][0]["round_no"], 0)
        self.assertEqual(len(fetched.transcript["rounds"][0]["opinions"]), 2)
        self.assertEqual(fetched.transcript["rounds"][0]["opinions"][0]["role_key"], "copy_editor")

        session.close()

    def test_update_result(self) -> None:
        session = self.Session()
        task, generation = self._make_task_and_generation(session)

        repo = EditorialReviewRepository(session)
        review = EditorialReview(
            task_id=task.id,
            generation_id=generation.id,
            status="running",
        )
        created = repo.create(review)
        session.commit()

        verdict = EditorialVerdict(
            decision="revise",
            final_scores={"overall": 72.5, "title": 65.0},
            rationale="标题偏弱,主体内容尚可",
            revision_directives=[
                RevisionDirective(location="标题", problem="缺少具体数字", fix="加入具体数字钩子"),
            ],
            dissent_summary="法务委员保留意见",
        )
        transcript = {"rounds": [{"round_no": 0, "opinions": []}]}

        updated = repo.update_result(
            created,
            status="converged",
            rounds_used=2,
            verdict=verdict,
            transcript=transcript,
            review_report_id="rpt_abc123",
        )
        session.commit()

        self.assertEqual(updated.status, "converged")
        self.assertEqual(updated.rounds_used, 2)
        self.assertEqual(updated.decision, "revise")
        self.assertAlmostEqual(updated.final_scores["overall"], 72.5)
        self.assertEqual(updated.rationale, "标题偏弱,主体内容尚可")
        self.assertIsInstance(updated.revision_directives, list)
        self.assertEqual(len(updated.revision_directives), 1)
        self.assertEqual(updated.revision_directives[0]["location"], "标题")
        self.assertEqual(updated.dissent_summary, "法务委员保留意见")
        self.assertEqual(updated.transcript["rounds"][0]["round_no"], 0)
        self.assertEqual(updated.review_report_id, "rpt_abc123")

        # Verify persisted via fresh fetch
        fetched = repo.get_latest_by_task_id(task.id)
        self.assertEqual(fetched.decision, "revise")
        self.assertEqual(fetched.review_report_id, "rpt_abc123")

        session.close()

    def test_update(self) -> None:
        session = self.Session()
        task, generation = self._make_task_and_generation(session)

        repo = EditorialReviewRepository(session)
        review = EditorialReview(
            task_id=task.id,
            generation_id=generation.id,
            status="running",
        )
        created = repo.create(review)
        session.commit()

        created.status = "failed"
        repo.update(created)
        session.commit()

        fetched = repo.get_latest_by_task_id(task.id)
        self.assertEqual(fetched.status, "failed")

        session.close()


if __name__ == "__main__":
    unittest.main()
