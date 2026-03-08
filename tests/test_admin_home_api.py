import base64
import os
import tempfile
import unittest
from datetime import datetime, timezone
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
from app.models.task import Task
from app.settings import get_settings
from app.services.phase4_queue_service import Phase4EnqueueResult


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class AdminHomeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "admin-home.db")
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

    def test_admin_home_snapshot_returns_payload(self) -> None:
        payload = {
            "summary": {
                "filtered_total": 1,
                "filtered_active": 1,
                "filtered_manual": 0,
                "filtered_review_passed": 0,
                "filtered_draft_saved": 0,
                "filtered_failed": 0,
                "filtered_stuck": 0,
                "today_submitted": 1,
                "today_draft_saved": 0,
                "today_failed": 0,
                "today_review_success_rate": None,
                "today_auto_push_success_rate": None,
                "stuck_threshold_minutes": 30,
                "status_counts": {"queued": 1},
                "selected_task_id": None,
                "generated_at": datetime.now(timezone.utc),
            },
            "tasks": [],
            "operations": {
                "available": True,
                "workers": [],
                "note": None,
            },
            "workspace": None,
        }
        with patch("app.api.admin_console.AdminMonitorService.build_snapshot", return_value=payload):
            response = self.client.get("/admin/api/home-snapshot", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["filtered_total"], 1)
        self.assertTrue(body["operations"]["available"])

    def test_admin_ingest_enqueues_phase4(self) -> None:
        with patch(
            "app.api.admin_console.Phase4QueueService.enqueue",
            return_value=Phase4EnqueueResult(task_id="unused", enqueued=True, queue_depth=2),
        ):
            response = self.client.post(
                "/admin/api/ingest",
                headers=self.auth_headers,
                json={"url": "https://mp.weixin.qq.com/s/admin-home-ingest"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["dispatch_mode"], "phase4_enqueue")
        self.assertTrue(body["enqueued"])
        self.assertEqual(body["queue_depth"], 2)

        with self.Session() as session:
            tasks = session.query(Task).all()
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].source_url, "https://mp.weixin.qq.com/s/admin-home-ingest")
            self.assertEqual(tasks[0].status, "queued")

    def test_admin_retry_phase4_requeues_task(self) -> None:
        with self.Session() as session:
            task = Task(
                task_code="tsk_retry_home",
                source_url="https://mp.weixin.qq.com/s/retry-home",
                normalized_url="https://mp.weixin.qq.com/s/retry-home",
                source_type="wechat",
                status="needs_regenerate",
            )
            session.add(task)
            session.commit()
            task_id = task.id

        with patch(
            "app.api.admin_console.Phase4QueueService.enqueue",
            return_value=Phase4EnqueueResult(task_id=task_id, enqueued=True, queue_depth=4),
        ):
            response = self.client.post(f"/admin/api/tasks/{task_id}/retry", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "queued")
        self.assertTrue(response.json()["enqueued"])

    def test_admin_action_routes_return_service_payloads(self) -> None:
        with patch(
            "app.api.admin_console.ManualReviewService.approve_latest_generation",
            return_value=SimpleNamespace(
                task_id="task-approve",
                status="review_passed",
                generation_id="gen-approve",
                decision="approved",
            ),
        ):
            approve_response = self.client.post("/admin/api/tasks/task-approve/approve", headers=self.auth_headers)

        with patch(
            "app.api.admin_console.ManualReviewService.reject_latest_generation",
            return_value=SimpleNamespace(
                task_id="task-reject",
                status="needs_regenerate",
                generation_id="gen-reject",
                decision="rejected",
            ),
        ):
            reject_response = self.client.post("/admin/api/tasks/task-reject/reject", headers=self.auth_headers)

        with patch(
            "app.api.admin_console.WechatDraftPublishService.push_latest_accepted_generation",
            return_value=SimpleNamespace(
                task_id="task-push",
                status="draft_saved",
                generation_id="gen-push",
                wechat_media_id="media-1",
                reused_existing=False,
            ),
        ):
            push_response = self.client.post("/admin/api/tasks/task-push/push-draft", headers=self.auth_headers)

        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.json()["decision"], "approved")
        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(reject_response.json()["decision"], "rejected")
        self.assertEqual(push_response.status_code, 200)
        self.assertEqual(push_response.json()["wechat_media_id"], "media-1")


if __name__ == "__main__":
    unittest.main()
