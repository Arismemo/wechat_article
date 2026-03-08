import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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
from app.models.task import Task
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class TaskListApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "task-list.db")
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

    def tearDown(self) -> None:
        self.client.close()
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        self.temp_dir.cleanup()

    def test_list_tasks_supports_active_only_status_source_query_and_date_filter(self) -> None:
        session = self.Session()
        older = datetime.now(timezone.utc) - timedelta(days=2)
        recent = datetime.now(timezone.utc) - timedelta(hours=2)
        pending = Task(
            task_code="tsk_pending",
            source_url="https://example.com/pending",
            normalized_url="https://example.com/pending",
            source_type="wechat",
            status="needs_manual_review",
        )
        pending.created_at = recent
        pending.updated_at = recent
        done = Task(
            task_code="tsk_done",
            source_url="https://example.com/done",
            normalized_url="https://example.com/done",
            source_type="wechat",
            status="draft_saved",
        )
        done.created_at = older
        done.updated_at = older
        failed = Task(
            task_code="tsk_failed",
            source_url="https://other.example.com/failed",
            normalized_url="https://other.example.com/failed",
            source_type="http",
            status="review_failed",
        )
        failed.created_at = recent
        failed.updated_at = recent
        session.add_all([pending, done, failed])
        session.commit()
        session.close()

        response = self.client.get("/api/v1/tasks?limit=10&active_only=true", headers={"Authorization": "Bearer test-token"})
        self.assertEqual(response.status_code, 200)
        active_ids = {item["task_code"] for item in response.json()}
        self.assertIn("tsk_pending", active_ids)
        self.assertNotIn("tsk_done", active_ids)
        self.assertNotIn("tsk_failed", active_ids)

        response = self.client.get(
            "/api/v1/tasks?limit=10&status=draft_saved",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["task_code"], "tsk_done")

        response = self.client.get(
            "/api/v1/tasks?limit=10&source_type=http",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["task_code"], "tsk_failed")

        response = self.client.get(
            "/api/v1/tasks?limit=10&query=other.example.com",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["task_code"], "tsk_failed")

        response = self.client.get(
            "/api/v1/tasks",
            params={"limit": 10, "created_after": recent.isoformat()},
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(response.status_code, 200)
        task_codes = {item["task_code"] for item in response.json()}
        self.assertIn("tsk_pending", task_codes)
        self.assertIn("tsk_failed", task_codes)
        self.assertNotIn("tsk_done", task_codes)

        response = self.client.get(
            "/api/v1/tasks?limit=10&status=not_a_status",
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
