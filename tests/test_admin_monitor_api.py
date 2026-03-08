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
from app.models.content_brief import ContentBrief
from app.models.generation import Generation
from app.models.task import Task
from app.models.wechat_draft import WechatDraft
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class AdminMonitorApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "admin-monitor.db")
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

        running_task = Task(
            task_code="tsk_monitor_running",
            source_url="https://mp.weixin.qq.com/s/running",
            normalized_url="https://mp.weixin.qq.com/s/running",
            source_type="wechat",
            status="generating",
        )
        session.add(running_task)
        session.flush()
        running_task.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.add(ContentBrief(task_id=running_task.id, brief_version=1, positioning="监控测试"))
        session.flush()
        session.add(
            Generation(
                task_id=running_task.id,
                brief_id=session.query(ContentBrief).filter(ContentBrief.task_id == running_task.id).one().id,
                version_no=1,
                prompt_type="phase4_write",
                prompt_version="phase4-v2",
                model_name="glm-5",
                title="运行中任务",
                markdown_content="# 运行中任务",
                status="generated",
            )
        )

        draft_task = Task(
            task_code="tsk_monitor_draft",
            source_url="https://mp.weixin.qq.com/s/draft",
            normalized_url="https://mp.weixin.qq.com/s/draft",
            source_type="wechat",
            status="draft_saved",
        )
        session.add(draft_task)
        session.flush()
        draft_brief = ContentBrief(task_id=draft_task.id, brief_version=1, positioning="监控测试")
        session.add(draft_brief)
        session.flush()
        draft_generation = Generation(
            task_id=draft_task.id,
            brief_id=draft_brief.id,
            version_no=2,
            prompt_type="phase4_write",
            prompt_version="phase4-v2",
            model_name="glm-5",
            title="草稿完成任务",
            markdown_content="# 草稿完成任务",
            status="accepted",
        )
        session.add(draft_generation)
        session.flush()
        session.add(
            WechatDraft(
                task_id=draft_task.id,
                generation_id=draft_generation.id,
                media_id="media-monitor-1",
                push_status="success",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
        self.running_task_id = running_task.id
        self.draft_task_id = draft_task.id
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

    def test_admin_monitor_snapshot_returns_summary_tasks_and_workspace(self) -> None:
        running_task_id = self.running_task_id
        draft_task_id = self.draft_task_id

        class FakeRedis:
            def llen(self, key):
                return {"phase2:queue": 1, "phase2:processing": 0, "phase3:queue": 0, "phase3:processing": 1}.get(key, 0)

            def scard(self, key):
                return {"phase2:pending": 1, "phase3:pending": 1}.get(key, 0)

            def hgetall(self, key):
                if key == "phase2:worker:heartbeat":
                    return {
                        "last_seen_at": datetime.now(timezone.utc).isoformat(),
                        "current_task_id": running_task_id,
                    }
                if key == "phase3:worker:heartbeat":
                    return {
                        "last_seen_at": datetime.now(timezone.utc).isoformat(),
                        "current_task_id": draft_task_id,
                    }
                return {}

        with patch("app.services.admin_monitor_service.get_redis_client", return_value=FakeRedis()):
            response = self.client.get(
                f"/api/v1/admin/monitor/snapshot?limit=20&selected_task_id={self.draft_task_id}",
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["filtered_total"], 2)
        self.assertEqual(body["summary"]["filtered_active"], 1)
        self.assertEqual(body["summary"]["filtered_draft_saved"], 1)
        self.assertEqual(body["summary"]["filtered_stuck"], 1)
        self.assertEqual(body["summary"]["today_submitted"], 2)
        self.assertEqual(body["summary"]["today_review_success_rate"], 100.0)
        self.assertEqual(len(body["tasks"]), 2)
        self.assertTrue(body["operations"]["available"])
        self.assertEqual(len(body["operations"]["workers"]), 4)
        self.assertEqual(body["operations"]["workers"][0]["name"], "phase2")
        self.assertEqual(body["workspace"]["task_id"], self.draft_task_id)
        self.assertEqual(body["workspace"]["wechat_media_id"], "media-monitor-1")

    def test_admin_console_stream_once_returns_snapshot_event(self) -> None:
        response = self.client.get("/admin/console/stream?once=true&limit=20")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))
        self.assertIn("event: snapshot", response.text)
        self.assertIn('"filtered_total": 2', response.text)


if __name__ == "__main__":
    unittest.main()
