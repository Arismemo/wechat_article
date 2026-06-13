"""Tests for T5: per-article publication metrics surfaced in admin snapshot.

Covers:
- task WITH metrics → latest_metrics populated with correct read/like/share/day_offset
- task WITHOUT metrics → latest_metrics is None
- only ONE batch metrics query is issued per snapshot call (no N+1)
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

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
from app.models.publication_metric import PublicationMetric
from app.models.task import Task
from app.models.wechat_draft import WechatDraft
from app.repositories.publication_metric_repository import PublicationMetricRepository
from app.services.admin_monitor_service import AdminMonitorFilters, AdminMonitorService
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class SnapshotLatestMetricsTests(unittest.TestCase):
    """Integration-style tests against an in-memory SQLite DB."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "snapshot-metrics.db")
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
        self.Session = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False
        )

        session = self.Session()

        # Task WITH metrics
        task_with = Task(
            task_code="tsk_metrics_yes",
            source_url="https://mp.weixin.qq.com/s/metrics-yes",
            normalized_url="https://mp.weixin.qq.com/s/metrics-yes",
            source_type="wechat",
            status="draft_saved",
        )
        session.add(task_with)
        session.flush()
        brief_with = ContentBrief(task_id=task_with.id, brief_version=1, positioning="测试")
        session.add(brief_with)
        session.flush()
        gen_with = Generation(
            task_id=task_with.id,
            brief_id=brief_with.id,
            version_no=1,
            prompt_type="phase4_write",
            prompt_version="phase4-v1",
            model_name="glm-5",
            title="有指标任务",
            markdown_content="# 有指标",
            status="accepted",
        )
        session.add(gen_with)
        session.flush()
        session.add(
            WechatDraft(
                task_id=task_with.id,
                generation_id=gen_with.id,
                media_id="media-metrics-1",
                push_status="success",
            )
        )
        # Two metric rows — day_offset=7 should win (highest)
        snapshot_ts = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        session.add(
            PublicationMetric(
                task_id=task_with.id,
                generation_id=gen_with.id,
                prompt_type="phase4_write",
                prompt_version="phase4-v1",
                day_offset=1,
                snapshot_at=snapshot_ts,
                read_count=500,
                like_count=20,
                share_count=5,
                source_type="auto:mock",
                imported_by="test",
            )
        )
        session.add(
            PublicationMetric(
                task_id=task_with.id,
                generation_id=gen_with.id,
                prompt_type="phase4_write",
                prompt_version="phase4-v1",
                day_offset=7,
                snapshot_at=snapshot_ts,
                read_count=1500,
                like_count=80,
                share_count=30,
                source_type="auto:mock",
                imported_by="test",
            )
        )

        # Task WITHOUT metrics
        task_without = Task(
            task_code="tsk_metrics_no",
            source_url="https://mp.weixin.qq.com/s/metrics-no",
            normalized_url="https://mp.weixin.qq.com/s/metrics-no",
            source_type="wechat",
            status="generating",
        )
        session.add(task_without)
        session.flush()

        session.commit()
        self.task_with_id = task_with.id
        self.task_without_id = task_without.id
        session.close()

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        self.temp_dir.cleanup()

    def _make_service(self, session):
        return AdminMonitorService(session)

    def _fake_redis(self):
        class FakeRedis:
            def llen(self, _key):
                return 0

            def scard(self, _key):
                return 0

            def hgetall(self, _key):
                return {}

        return FakeRedis()

    def test_task_with_metrics_returns_latest_metrics_highest_day_offset(self) -> None:
        session = self.Session()
        try:
            with patch("app.services.admin_monitor_service.get_redis_client", return_value=self._fake_redis()):
                service = self._make_service(session)
                snapshot = service.build_snapshot(AdminMonitorFilters(limit=50))
        finally:
            session.close()

        task_summary = next(t for t in snapshot.tasks if t.task_id == self.task_with_id)
        self.assertIsNotNone(task_summary.latest_metrics)
        m = task_summary.latest_metrics
        # day_offset=7 row should win (highest day_offset)
        self.assertEqual(m.day_offset, 7)
        self.assertEqual(m.read_count, 1500)
        self.assertEqual(m.like_count, 80)
        self.assertEqual(m.share_count, 30)

    def test_task_without_metrics_returns_latest_metrics_none(self) -> None:
        session = self.Session()
        try:
            with patch("app.services.admin_monitor_service.get_redis_client", return_value=self._fake_redis()):
                service = self._make_service(session)
                snapshot = service.build_snapshot(AdminMonitorFilters(limit=50))
        finally:
            session.close()

        task_summary = next(t for t in snapshot.tasks if t.task_id == self.task_without_id)
        self.assertIsNone(task_summary.latest_metrics)

    def test_only_one_batch_metrics_query_per_snapshot(self) -> None:
        """list_latest_by_task_ids must be called exactly once per build_snapshot call."""
        session = self.Session()
        call_count = 0
        original_method = PublicationMetricRepository.list_latest_by_task_ids

        def counting_list_latest(self_repo, task_ids):
            nonlocal call_count
            call_count += 1
            return original_method(self_repo, task_ids)

        try:
            with (
                patch("app.services.admin_monitor_service.get_redis_client", return_value=self._fake_redis()),
                patch.object(PublicationMetricRepository, "list_latest_by_task_ids", counting_list_latest),
            ):
                service = self._make_service(session)
                service.build_snapshot(AdminMonitorFilters(limit=50))
        finally:
            session.close()

        self.assertEqual(call_count, 1, "Expected exactly 1 call to list_latest_by_task_ids (no N+1).")


class EnqueueRecentFeedbackDryRunTests(unittest.TestCase):
    """Tests for the enqueue_recent_feedback CLI script, dry-run branch."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "enqueue-feedback.db")
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
                # Provider disabled — dry-run must still work
                "FEEDBACK_SYNC_PROVIDER": "disabled",
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
        self.Session = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False
        )

        session = self.Session()
        task = Task(
            task_code="tsk_enqueue_dry",
            source_url="https://mp.weixin.qq.com/s/enqueue-dry",
            normalized_url="https://mp.weixin.qq.com/s/enqueue-dry",
            source_type="wechat",
            status="draft_saved",
        )
        session.add(task)
        session.flush()
        gen = Generation(
            task_id=task.id,
            version_no=1,
            prompt_type="phase4_write",
            prompt_version="phase4-v1",
            model_name="glm-5",
            title="测试",
            markdown_content="# 测试",
            status="accepted",
        )
        session.add(gen)
        session.flush()
        session.add(
            WechatDraft(
                task_id=task.id,
                generation_id=gen.id,
                media_id="media-dry-1",
                push_status="success",
            )
        )
        session.commit()
        self.task_id = task.id
        session.close()

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        self.temp_dir.cleanup()

    def test_dry_run_lists_candidates_without_enqueuing(self) -> None:
        """--dry-run must print candidates and exit 0 even when provider is disabled."""
        import sys
        from io import StringIO

        # We need to import the script module directly and call main() with mocked args.
        # Use sys.argv patching and capture stdout.
        import importlib.util
        from pathlib import Path

        script_path = Path(__file__).resolve().parents[1] / "scripts" / "enqueue_recent_feedback.py"
        spec = importlib.util.spec_from_file_location("enqueue_recent_feedback", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        captured_output = StringIO()
        with (
            patch.object(sys, "argv", ["enqueue_recent_feedback.py", "--dry-run", "--limit", "5"]),
            patch("sys.stdout", captured_output),
        ):
            with self.assertRaises(SystemExit) as ctx:
                module.main()

        self.assertEqual(ctx.exception.code, 0)
        output = captured_output.getvalue()
        self.assertIn("[dry-run]", output)
        self.assertIn(self.task_id, output)

    def test_disabled_provider_real_run_exits_nonzero(self) -> None:
        """Real run with FEEDBACK_SYNC_PROVIDER=disabled must exit non-zero."""
        import sys
        import importlib.util
        from pathlib import Path

        script_path = Path(__file__).resolve().parents[1] / "scripts" / "enqueue_recent_feedback.py"
        spec = importlib.util.spec_from_file_location("enqueue_recent_feedback_real", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with patch.object(sys, "argv", ["enqueue_recent_feedback.py", "--limit", "5"]):
            with self.assertRaises(SystemExit) as ctx:
                module.main()

        self.assertNotEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
