import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.enums import TopicCandidateStatus, TopicFetchRunStatus
from app.db.base import Base
from app.db.redis_client import get_redis_client
from app.db.session import get_engine, get_session_factory
from app.models.audit_log import AuditLog
from app.models.task import Task
from app.models.topic_candidate import TopicCandidate
from app.models.topic_candidate_signal import TopicCandidateSignal
from app.models.topic_plan import TopicPlan
from app.models.topic_plan_task_link import TopicPlanTaskLink
from app.models.topic_signal import TopicSignal
from app.repositories.topic_source_repository import TopicSourceRepository
from app.services.search_service import SearchResult
from app.services.topic_fetch_queue_service import TopicFetchEnqueueResult
from app.services.topic_source_registry_service import TopicSourceRegistryService
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class TopicIntelligenceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "topic-intelligence.db")
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
        self._seed_topic_workspace()

    def tearDown(self) -> None:
        self.client.close()
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        self.temp_dir.cleanup()

    def _seed_topic_workspace(self) -> None:
        session = self.Session()
        registry = TopicSourceRegistryService(session)
        registry.sync_sources()
        session.flush()
        published_at = datetime.now(timezone.utc)

        source = TopicSourceRepository(session).get_by_source_key("wechat_ecosystem_watchlist")
        assert source is not None

        signal = TopicSignal(
            source_id=source.id,
            signal_type="search_result",
            title="微信搜一搜正在重估公众号分发",
            url="https://example.com/wechat-search",
            normalized_url="https://example.com/wechat-search",
            summary="平台入口变化带来了新的内容分发窗口。",
            source_site="Example",
            source_tier="A",
            published_at=published_at,
            fetch_status="discovered",
        )
        session.add(signal)
        session.flush()

        candidate = TopicCandidate(
            cluster_key="url:https://example.com/wechat-search",
            topic_title="微信搜一搜带来的新分发机会",
            topic_summary="从平台入口变化看内容供给和分发格局的再平衡。",
            content_pillar="wechat_ecosystem",
            hotness_score=91,
            commercial_fit_score=86,
            evidence_score=84,
            novelty_score=82,
            wechat_fit_score=93,
            risk_score=15,
            total_score=87.2,
            recommended_business_goal="build_trust",
            recommended_article_type="industry_analysis",
            canonical_seed_url="https://example.com/wechat-search",
            status=TopicCandidateStatus.PLANNED.value,
            signal_count=1,
            latest_signal_at=published_at,
        )
        session.add(candidate)
        session.flush()

        session.add(TopicCandidateSignal(candidate_id=candidate.id, signal_id=signal.id, rank_no=1))
        plan = TopicPlan(
            candidate_id=candidate.id,
            plan_version=1,
            business_goal="build_trust",
            article_type="industry_analysis",
            angle="不是复述功能，而是解释入口变化背后的分发逻辑。",
            why_now="平台入口和创作者策略都在同步调整。",
            target_reader="公众号内容操盘者",
            must_cover={"points": ["入口变化", "分发逻辑", "操盘建议"]},
            must_avoid={"points": ["空泛趋势判断"]},
            keywords={"primary": ["微信搜一搜", "公众号分发"]},
            search_friendly_title="微信搜一搜变化下，公众号内容分发机会怎么判断",
            distribution_friendly_title="别只盯涨粉，微信搜一搜正在改写公众号分发逻辑",
            summary="围绕微信入口变化，输出可执行的内容策略判断。",
            cta_mode="consult",
            source_grade="A",
            recommended_queries={"queries": ["微信搜一搜 公众号 分发"]},
            seed_source_pack={"urls": ["https://example.com/wechat-search"]},
        )
        session.add(plan)
        session.commit()

        self.source_id = source.id
        self.candidate_id = candidate.id
        self.plan_id = plan.id
        session.close()

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer test-token"}

    def test_list_topic_sources_returns_signal_counts(self) -> None:
        response = self.client.get("/api/v1/admin/topics/sources", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 3)
        source = next(item for item in body if item["source_id"] == self.source_id)
        self.assertEqual(source["source_key"], "wechat_ecosystem_watchlist")
        self.assertEqual(source["signal_count"], 1)
        self.assertEqual(source["config"]["recommended_business_goal"], "build_trust")
        self.assertNotIn("_signal_count", source["config"])

    def test_topic_snapshot_returns_summary_candidates_and_workspace(self) -> None:
        response = self.client.get(
            f"/api/v1/admin/topics/snapshot?limit=10&status=planned&selected_plan_id={self.plan_id}",
            headers=self._auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["source_total"], 3)
        self.assertEqual(body["summary"]["source_enabled"], 3)
        self.assertEqual(body["summary"]["planned_total"], 1)
        self.assertEqual(body["summary"]["candidate_total"], 1)
        self.assertEqual(body["summary"]["new_signal_24h"], 1)
        self.assertEqual(len(body["sources"]), 3)
        self.assertEqual(len(body["candidates"]), 1)
        self.assertEqual(body["workspace"]["candidate"]["candidate_id"], self.candidate_id)
        self.assertEqual(body["workspace"]["plan"]["plan_id"], self.plan_id)
        self.assertEqual(len(body["workspace"]["signals"]), 1)
        self.assertEqual(body["workspace"]["signals"][0]["title"], "微信搜一搜正在重估公众号分发")
        self.assertEqual(body["workspace"]["task_links"], [])

    def test_run_topic_source_creates_run_signal_candidate_and_plan(self) -> None:
        published_at = datetime.now(timezone.utc)
        mock_results = [
            SearchResult(
                query_text="微信搜一搜 内容 机会",
                title="微信搜一搜入口调整，内容供给迎来窗口期",
                url="https://example.com/topic-run",
                summary="内容入口和分发逻辑正在同步变化。",
                source_site="Example",
                published_at=published_at,
            )
        ]

        with patch("app.services.search_service.SearchService.search_many", return_value=mock_results):
            response = self.client.post(
                f"/internal/v1/topic-sources/{self.source_id}/run",
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source_id"], self.source_id)
        self.assertEqual(body["status"], TopicFetchRunStatus.SUCCEEDED.value)
        self.assertEqual(body["fetched_count"], 1)
        self.assertEqual(body["new_signal_count"], 1)
        self.assertEqual(body["candidate_count"], 2)
        self.assertEqual(len(body["latest_plan_ids"]), 2)

        session = self.Session()
        runs = session.execute(select(app.models.TopicFetchRun)).scalars().all()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].status, TopicFetchRunStatus.SUCCEEDED.value)
        signals = session.execute(select(app.models.TopicSignal)).scalars().all()
        self.assertEqual(len(signals), 2)
        self.assertEqual(len(session.execute(select(app.models.TopicCandidate)).scalars().all()), 2)
        self.assertEqual(len(session.execute(select(app.models.TopicPlan)).scalars().all()), 3)
        audit_logs = session.execute(select(AuditLog).where(AuditLog.action == "topics.source.run.completed")).scalars().all()
        self.assertEqual(len(audit_logs), 1)
        session.close()

    def test_enqueue_topic_source_returns_queue_depth(self) -> None:
        enqueue_result = TopicFetchEnqueueResult(source_id=self.source_id, enqueued=True, queue_depth=3)
        with patch("app.api.topic_internal.TopicFetchQueueService.enqueue", return_value=enqueue_result):
            response = self.client.post(
                f"/internal/v1/topic-sources/{self.source_id}/enqueue",
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["enqueued"])
        self.assertEqual(body["queue_depth"], 3)
        self.assertEqual(body["source_id"], self.source_id)

    def test_refresh_topic_candidates_returns_latest_plan_ids(self) -> None:
        session = self.Session()
        source = session.get(app.models.TopicSource, self.source_id)
        assert source is not None
        signal = TopicSignal(
            source_id=source.id,
            signal_type="search_result",
            title="公众号作者开始重做搜一搜选题",
            url="https://example.com/topic-refresh",
            normalized_url="https://example.com/topic-refresh",
            summary="更多公开讨论开始聚焦内容分发和搜索入口。",
            source_site="Example",
            source_tier="A",
            published_at=datetime(2026, 3, 17, tzinfo=timezone.utc),
            fetch_status="discovered",
        )
        session.add(signal)
        session.commit()
        session.close()

        response = self.client.post("/internal/v1/topics/refresh-candidates", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(len(body), 1)

    def test_promote_topic_plan_creates_task_and_plan_link(self) -> None:
        response = self.client.post(
            f"/api/v1/admin/topics/plans/{self.plan_id}/promote",
            headers=self._auth_headers(),
            json={"operator": "reviewer", "note": "纳入选题池", "enqueue_phase3": False},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["plan_id"], self.plan_id)
        self.assertEqual(body["candidate_id"], self.candidate_id)
        self.assertFalse(body["deduped"])
        self.assertFalse(body["enqueued"])
        self.assertIsNone(body["queue_depth"])
        self.assertEqual(body["status"], "queued")
        self.assertTrue(body["task_code"].startswith("tsk_"))

        session = self.Session()
        tasks = session.execute(select(Task)).scalars().all()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].source_url, "https://example.com/wechat-search")
        plan_links = session.execute(select(TopicPlanTaskLink)).scalars().all()
        self.assertEqual(len(plan_links), 1)
        self.assertEqual(plan_links[0].plan_id, self.plan_id)
        self.assertEqual(plan_links[0].operator, "reviewer")
        self.assertEqual(plan_links[0].note, "纳入选题池")
        candidate = session.get(TopicCandidate, self.candidate_id)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.status, TopicCandidateStatus.PROMOTED.value)
        audit_logs = session.execute(select(AuditLog).where(AuditLog.action == "topics.plan.promoted")).scalars().all()
        self.assertEqual(len(audit_logs), 1)
        self.assertEqual(audit_logs[0].payload["plan_id"], self.plan_id)
        session.close()

    def test_promote_topic_plan_rejects_invalid_seed_url_with_400(self) -> None:
        session = self.Session()
        invalid_candidate = TopicCandidate(
            cluster_key="url:invalid-seed",
            topic_title="非法 URL 选题",
            topic_summary="用于验证 promote 时的 URL 校验。",
            content_pillar="wechat_ecosystem",
            canonical_seed_url="not-a-valid-url",
            status=TopicCandidateStatus.PLANNED.value,
            signal_count=0,
        )
        session.add(invalid_candidate)
        session.flush()
        invalid_plan = TopicPlan(candidate_id=invalid_candidate.id, plan_version=1, angle="校验非法 seed URL")
        session.add(invalid_plan)
        session.commit()
        invalid_plan_id = invalid_plan.id
        session.close()

        response = self.client.post(
            f"/api/v1/admin/topics/plans/{invalid_plan_id}/promote",
            headers=self._auth_headers(),
            json={"operator": "reviewer", "enqueue_phase3": False},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Topic plan has invalid canonical seed URL.")


if __name__ == "__main__":
    unittest.main()
