import base64
import os
import tempfile
import unittest
from types import SimpleNamespace
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
from app.repositories.topic_source_repository import TopicSourceRepository
from app.services.topic_fetch_queue_service import TopicFetchEnqueueResult
from app.services.topic_source_registry_service import TopicSourceRegistryService
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class AdminTopicsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "admin-topics.db")
        self.env_patch = patch.dict(
            os.environ,
            {
                "APP_BASE_URL": "https://example.com",
                "API_BEARER_TOKEN": "test-token",
                "ADMIN_USERNAME": "admin",
                "ADMIN_PASSWORD": "secret-pass",
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
        self.auth_headers = {
            "Authorization": f"Basic {base64.b64encode(b'admin:secret-pass').decode('ascii')}",
        }

    def tearDown(self) -> None:
        self.client.close()
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        self.temp_dir.cleanup()

    def test_admin_run_topic_source_returns_payload(self) -> None:
        with patch(
            "app.api.admin_topics.TopicIntelligenceService.run_source",
            return_value=SimpleNamespace(
                source_id="source-1",
                source_key="wechat_ecosystem_watchlist",
                run_id="run-1",
                status="succeeded",
                fetched_count=5,
                new_signal_count=3,
                candidate_count=2,
                latest_plan_ids=["plan-1", "plan-2"],
            ),
        ):
            response = self.client.post("/admin/api/topics/sources/source-1/run", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source_id"], "source-1")
        self.assertEqual(body["new_signal_count"], 3)
        self.assertEqual(body["latest_plan_ids"], ["plan-1", "plan-2"])

    def test_admin_enqueue_topic_source_returns_queue_depth(self) -> None:
        with self.Session() as session:
            TopicSourceRegistryService(session).sync_sources()
            session.commit()
            source = TopicSourceRepository(session).get_by_source_key("wechat_ecosystem_watchlist")
            self.assertIsNotNone(source)
            source_id = source.id

        with patch(
            "app.api.admin_topics.TopicFetchQueueService.enqueue",
            return_value=TopicFetchEnqueueResult(source_id=source_id, enqueued=True, queue_depth=4),
        ):
            response = self.client.post(f"/admin/api/topics/sources/{source_id}/enqueue", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "source_id": source_id,
                "enqueued": True,
                "queue_depth": 4,
            },
        )

    def test_admin_refresh_candidates_and_promote_routes_return_payloads(self) -> None:
        with patch(
            "app.api.admin_topics.TopicIntelligenceService.refresh_candidates",
            return_value=["plan-1", "plan-2"],
        ):
            refresh_response = self.client.post("/admin/api/topics/refresh-candidates", headers=self.auth_headers)

        with patch(
            "app.api.admin_topics.TopicIntelligenceService.promote_plan",
            return_value=SimpleNamespace(
                plan_id="plan-1",
                candidate_id="candidate-1",
                task_id="task-1",
                task_code="tsk_topic_1",
                deduped=False,
                status="queued",
                enqueued=True,
                queue_depth=2,
            ),
        ):
            promote_response = self.client.post(
                "/admin/api/topics/plans/plan-1/promote",
                headers=self.auth_headers,
                json={"operator": "admin-topics", "note": "推进到主链路", "enqueue_phase3": True},
            )

        self.assertEqual(refresh_response.status_code, 200)
        self.assertEqual(refresh_response.json(), ["plan-1", "plan-2"])
        self.assertEqual(promote_response.status_code, 200)
        self.assertEqual(promote_response.json()["task_code"], "tsk_topic_1")
        self.assertTrue(promote_response.json()["enqueued"])

    def test_admin_candidate_status_routes_return_payloads(self) -> None:
        with patch(
            "app.api.admin_topics.TopicIntelligenceService.update_candidate_status",
            return_value=SimpleNamespace(
                candidate_id="candidate-1",
                previous_status="planned",
                status="watching",
                changed=True,
            ),
        ):
            watch_response = self.client.post(
                "/admin/api/topics/candidates/candidate-1/watch",
                headers=self.auth_headers,
                json={"operator": "admin-topics", "note": "继续观察"},
            )

        with patch(
            "app.api.admin_topics.TopicIntelligenceService.update_candidate_status",
            return_value=SimpleNamespace(
                candidate_id="candidate-1",
                previous_status="watching",
                status="ignored",
                changed=True,
            ),
        ):
            ignore_response = self.client.post(
                "/admin/api/topics/candidates/candidate-1/ignore",
                headers=self.auth_headers,
                json={"operator": "admin-topics", "note": "先忽略"},
            )

        with patch(
            "app.api.admin_topics.TopicIntelligenceService.update_candidate_status",
            return_value=SimpleNamespace(
                candidate_id="candidate-1",
                previous_status="ignored",
                status="planned",
                changed=True,
            ),
        ):
            plan_response = self.client.post(
                "/admin/api/topics/candidates/candidate-1/plan",
                headers=self.auth_headers,
                json={"operator": "admin-topics", "note": "恢复计划"},
            )

        self.assertEqual(watch_response.status_code, 200)
        self.assertEqual(watch_response.json()["status"], "watching")
        self.assertEqual(ignore_response.status_code, 200)
        self.assertEqual(ignore_response.json()["status"], "ignored")
        self.assertEqual(plan_response.status_code, 200)
        self.assertEqual(plan_response.json()["status"], "planned")

    def test_admin_candidate_status_route_maps_not_found_to_404(self) -> None:
        with patch(
            "app.api.admin_topics.TopicIntelligenceService.update_candidate_status",
            side_effect=ValueError("Topic candidate not found."),
        ):
            response = self.client.post(
                "/admin/api/topics/candidates/missing/watch",
                headers=self.auth_headers,
                json={"operator": "admin-topics"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Topic candidate not found.")


if __name__ == "__main__":
    unittest.main()
