import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.enums import TopicFetchRunStatus, TopicSourceType
from app.db.base import Base
from app.db.redis_client import get_redis_client
from app.db.session import get_engine, get_session_factory
from app.models.topic_candidate import TopicCandidate
from app.models.topic_plan import TopicPlan
from app.repositories.topic_source_repository import TopicSourceRepository
from app.services.search_service import SearchResult
from app.services.topic_intelligence_service import TopicIntelligenceService
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class TopicIntelligenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "topic-intelligence-service.db")
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

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        self.temp_dir.cleanup()

    def test_list_sources_persists_registry_entries_for_followup_sessions(self) -> None:
        session = self.Session()
        sources = TopicIntelligenceService(session).list_sources()
        self.assertEqual(len(sources), 3)
        source_id = next(item.id for item in sources if item.source_key == "wechat_ecosystem_watchlist")
        session.close()

        verification = self.Session()
        source = TopicSourceRepository(verification).get_by_id(source_id)
        self.assertIsNotNone(source)
        self.assertEqual(source.source_type, TopicSourceType.SEARCH_WATCHLIST.value)
        verification.close()

    def test_run_source_rolls_back_partial_state_when_refresh_candidates_fails(self) -> None:
        session = self.Session()
        service = TopicIntelligenceService(session)
        source_id = next(item.id for item in service.list_sources() if item.source_key == "wechat_ecosystem_watchlist")
        published_at = datetime.now(timezone.utc)

        with patch(
            "app.services.search_service.SearchService.search_many",
            return_value=[
                SearchResult(
                    query_text="微信搜一搜 内容 机会",
                    title="微信搜一搜窗口期",
                    url="https://example.com/rollback",
                    summary="验证失败回滚。",
                    source_site="Example",
                    published_at=published_at,
                )
            ],
        ), patch(
            "app.services.topic_intelligence_service.TopicIntelligenceService.refresh_candidates",
            side_effect=RuntimeError("refresh failed"),
        ):
            with self.assertRaises(RuntimeError):
                service.run_source(source_id, trigger_type="manual-run")

        session.close()

        verification = self.Session()
        runs = verification.execute(select(app.models.TopicFetchRun)).scalars().all()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].status, TopicFetchRunStatus.FAILED.value)
        self.assertEqual(len(verification.execute(select(app.models.TopicSignal)).scalars().all()), 0)
        self.assertEqual(len(verification.execute(select(app.models.TopicCandidate)).scalars().all()), 0)
        self.assertEqual(len(verification.execute(select(app.models.TopicPlan)).scalars().all()), 0)
        verification.close()

    def test_promote_plan_rejects_invalid_seed_url(self) -> None:
        session = self.Session()
        service = TopicIntelligenceService(session)
        service.list_sources()

        candidate = TopicCandidate(
            cluster_key="url:invalid-seed",
            topic_title="非法 URL 选题",
            canonical_seed_url="not-a-valid-url",
            status="planned",
            signal_count=0,
        )
        session.add(candidate)
        session.flush()
        plan = TopicPlan(candidate_id=candidate.id, plan_version=1, angle="校验非法 seed URL")
        session.add(plan)
        session.commit()

        with self.assertRaisesRegex(ValueError, "invalid canonical seed URL"):
            service.promote_plan(plan.id, enqueue_phase3=False)

        session.close()


if __name__ == "__main__":
    unittest.main()
