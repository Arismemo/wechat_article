import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
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
from app.models.task import Task
from app.models.wechat_draft import WechatDraft
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class FeedbackApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "feedback.db")
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

        from app.main import create_app

        self.client = TestClient(create_app())
        session = self.Session()
        task = Task(
            task_code="tsk_feedback",
            source_url="https://mp.weixin.qq.com/s/feedback",
            normalized_url="https://mp.weixin.qq.com/s/feedback",
            source_type="wechat",
            status="review_passed",
        )
        session.add(task)
        session.flush()
        brief = ContentBrief(
            task_id=task.id,
            brief_version=1,
            positioning="工程师科普稿",
        )
        session.add(brief)
        session.flush()
        generation = Generation(
            task_id=task.id,
            brief_id=brief.id,
            version_no=3,
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
                task_id=task.id,
                generation_id=generation.id,
                media_id="media-test-1",
                push_status="success",
            )
        )
        session.commit()
        self.task_id = task.id
        self.generation_id = generation.id
        session.close()

    def tearDown(self) -> None:
        self.client.close()
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        self.temp_dir.cleanup()

    def test_import_feedback_updates_task_feedback_and_prompt_experiments(self) -> None:
        first = self.client.post(
            f"/internal/v1/tasks/{self.task_id}/import-feedback",
            headers={"Authorization": "Bearer test-token"},
            json={
                "day_offset": 1,
                "read_count": 1200,
                "like_count": 88,
                "share_count": 11,
                "comment_count": 3,
                "click_rate": 0.1825,
                "operator": "editor-a",
                "notes": "T+1 手工回填",
            },
        )

        self.assertEqual(first.status_code, 200)
        first_body = first.json()
        self.assertEqual(first_body["generation_id"], self.generation_id)
        self.assertEqual(first_body["prompt_type"], "phase4_write")
        self.assertEqual(first_body["prompt_version"], "phase4-v2")
        self.assertEqual(first_body["sample_count"], 1)

        second = self.client.post(
            f"/internal/v1/tasks/{self.task_id}/import-feedback",
            headers={"Authorization": "Bearer test-token"},
            json={
                "generation_id": self.generation_id,
                "day_offset": 1,
                "read_count": 1600,
                "like_count": 96,
                "share_count": 14,
                "comment_count": 4,
                "click_rate": 0.205,
                "operator": "editor-b",
            },
        )

        self.assertEqual(second.status_code, 200)
        second_body = second.json()
        self.assertEqual(second_body["metric_id"], first_body["metric_id"])
        self.assertEqual(second_body["sample_count"], 1)

        feedback = self.client.get(
            f"/api/v1/tasks/{self.task_id}/feedback",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(feedback.status_code, 200)
        feedback_body = feedback.json()
        self.assertEqual(feedback_body["task_id"], self.task_id)
        self.assertEqual(len(feedback_body["metrics"]), 1)
        self.assertEqual(feedback_body["metrics"][0]["read_count"], 1600)
        self.assertEqual(feedback_body["metrics"][0]["wechat_media_id"], "media-test-1")

        experiments = self.client.get(
            "/api/v1/feedback/experiments?limit=5",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(experiments.status_code, 200)
        experiments_body = experiments.json()
        self.assertEqual(len(experiments_body), 1)
        self.assertEqual(experiments_body[0]["sample_count"], 1)
        self.assertEqual(experiments_body[0]["avg_read_count"], 1600.0)
        self.assertEqual(experiments_body[0]["best_read_count"], 1600)
        self.assertEqual(experiments_body[0]["last_task_id"], self.task_id)

    def test_create_and_list_style_assets(self) -> None:
        create_response = self.client.post(
            "/internal/v1/style-assets",
            headers={"Authorization": "Bearer test-token"},
            json={
                "asset_type": "opening_hook",
                "title": "反直觉开头",
                "content": "先抛错结论，再层层拆解。",
                "tags": ["技术科普", "误区纠偏"],
                "weight": 1.5,
                "source_task_id": self.task_id,
                "source_generation_id": self.generation_id,
                "operator": "editor-a",
            },
        )

        self.assertEqual(create_response.status_code, 200)
        create_body = create_response.json()
        self.assertEqual(create_body["asset_type"], "opening_hook")
        self.assertEqual(create_body["status"], "active")

        list_response = self.client.get(
            "/api/v1/feedback/style-assets?limit=5",
            headers={"Authorization": "Bearer test-token"},
        )

        self.assertEqual(list_response.status_code, 200)
        list_body = list_response.json()
        self.assertEqual(len(list_body), 1)
        self.assertEqual(list_body[0]["title"], "反直觉开头")
        self.assertEqual(list_body[0]["weight"], 1.5)
        self.assertEqual(list_body[0]["tags"], ["技术科普", "误区纠偏"])

    def test_import_feedback_csv_uses_default_task_id_and_rolls_up_results(self) -> None:
        response = self.client.post(
            "/internal/v1/feedback/import-csv",
            headers={"Authorization": "Bearer test-token"},
            json={
                "default_task_id": self.task_id,
                "imported_by": "ops-batch",
                "operator": "ops-batch",
                "csv_text": (
                    "generation_id,day_offset,read_count,like_count,share_count,comment_count,click_rate,notes\n"
                    f"{self.generation_id},1,1800,120,21,8,0.221,第一批回填\n"
                    f"{self.generation_id},3,2400,165,33,13,0.265,T+3 回填\n"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["imported_count"], 2)
        self.assertEqual(body["results"][0]["row_no"], 2)
        self.assertEqual(body["results"][0]["prompt_version"], "phase4-v2")
        self.assertEqual(body["results"][1]["day_offset"], 3)

        feedback = self.client.get(
            f"/api/v1/tasks/{self.task_id}/feedback",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(feedback.status_code, 200)
        metrics = feedback.json()["metrics"]
        self.assertEqual(len(metrics), 2)
        self.assertEqual({item["day_offset"] for item in metrics}, {1, 3})

        experiments = self.client.get(
            "/api/v1/feedback/experiments?limit=5",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(experiments.status_code, 200)
        experiment_rows = experiments.json()
        self.assertEqual(len(experiment_rows), 2)
        self.assertEqual({item["day_offset"] for item in experiment_rows}, {1, 3})

    def test_import_feedback_csv_returns_400_for_invalid_row(self) -> None:
        response = self.client.post(
            "/internal/v1/feedback/import-csv",
            headers={"Authorization": "Bearer test-token"},
            json={
                "default_task_id": self.task_id,
                "csv_text": (
                    "generation_id,day_offset,read_count\n"
                    f"{self.generation_id},oops,1800\n"
                ),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Row 2", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
