import unittest

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.enums import TopicCandidateStatus, TopicSourceType
from app.db.base import Base
from app.models.system_setting import SystemSetting
from app.models.topic_plan import TopicPlan
from app.repositories.topic_candidate_repository import TopicCandidateRepository
from app.repositories.topic_plan_repository import TopicPlanRepository
from app.repositories.topic_source_repository import TopicSourceRepository
from app.services.topic_source_registry_service import TopicSourceRegistryService


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class TopicIntelligenceFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)

    def test_sync_sources_creates_default_watchlists(self) -> None:
        session = self.Session()

        registry = TopicSourceRegistryService(session)
        rows = registry.sync_sources()

        self.assertEqual(len(rows), 3)

        repo = TopicSourceRepository(session)
        all_sources = repo.list_all()
        self.assertEqual([item.source_key for item in all_sources], [
            "ai_industry_watchlist",
            "solopreneur_methods_watchlist",
            "wechat_ecosystem_watchlist",
        ])
        self.assertTrue(all(item.source_type == TopicSourceType.SEARCH_WATCHLIST.value for item in all_sources))
        self.assertTrue(all(item.enabled for item in all_sources))
        self.assertEqual(
            all_sources[0].config["queries"],
            [
                "人工智能 制造业 最新 进展",
                "智能体 产业 应用",
                "AI 政策 产业 数字化",
            ],
        )
        session.close()

    def test_registry_override_merges_defaults_and_adds_custom_source(self) -> None:
        session = self.Session()
        session.add(
            SystemSetting(
                key=TopicSourceRegistryService.SETTINGS_KEY,
                value=[
                    {
                        "source_key": "wechat_ecosystem_watchlist",
                        "enabled": False,
                        "fetch_interval_minutes": 60,
                        "config": {
                            "queries": ["公众号 生态 机会"],
                        },
                    },
                    {
                        "source_key": "policy_briefing_watchlist",
                        "name": "政策解读监控",
                        "source_type": TopicSourceType.SEARCH_WATCHLIST.value,
                        "content_pillar": "ai_industry",
                        "config": {
                            "queries": ["人工智能 政策 解读"],
                            "recommended_business_goal": "build_trust",
                        },
                    },
                ],
            )
        )
        session.commit()

        registry = TopicSourceRegistryService(session)
        registry.sync_sources()

        repo = TopicSourceRepository(session)
        wechat = repo.get_by_source_key("wechat_ecosystem_watchlist")
        self.assertIsNotNone(wechat)
        self.assertFalse(wechat.enabled)
        self.assertEqual(wechat.fetch_interval_minutes, 60)
        self.assertEqual(wechat.config["queries"], ["公众号 生态 机会"])
        self.assertEqual(wechat.config["recommended_business_goal"], "build_trust")

        custom = repo.get_by_source_key("policy_briefing_watchlist")
        self.assertIsNotNone(custom)
        self.assertEqual(custom.name, "政策解读监控")
        self.assertEqual(custom.content_pillar, "ai_industry")

        enabled_keys = [item.source_key for item in registry.list_enabled_sources()]
        self.assertEqual(
            enabled_keys,
            [
                "ai_industry_watchlist",
                "policy_briefing_watchlist",
                "solopreneur_methods_watchlist",
            ],
        )
        session.close()

    def test_candidate_upsert_and_plan_versioning(self) -> None:
        session = self.Session()

        candidates = TopicCandidateRepository(session)
        candidate = candidates.upsert(
            cluster_key="wechat-search-opportunity",
            topic_title="微信搜一搜带来的内容机会",
            topic_summary="从平台能力变化看内容入口重估。",
            content_pillar="wechat_ecosystem",
            hotness_score=78.0,
            commercial_fit_score=88.0,
            evidence_score=80.0,
            novelty_score=72.0,
            wechat_fit_score=91.0,
            risk_score=12.0,
            total_score=82.4,
            recommended_business_goal="build_trust",
            recommended_article_type="industry_analysis",
            canonical_seed_url="https://example.com/wechat-search",
            status=TopicCandidateStatus.NEW.value,
            signal_count=3,
            latest_signal_at=None,
        )
        session.commit()

        updated = candidates.upsert(
            cluster_key="wechat-search-opportunity",
            topic_title="微信搜一搜带来的新内容机会",
            topic_summary="从搜一搜和内容分发看公众号新入口。",
            content_pillar="wechat_ecosystem",
            hotness_score=80.0,
            commercial_fit_score=89.0,
            evidence_score=82.0,
            novelty_score=75.0,
            wechat_fit_score=93.0,
            risk_score=10.0,
            total_score=84.2,
            recommended_business_goal="build_trust",
            recommended_article_type="decision_guide",
            canonical_seed_url="https://example.com/wechat-search-v2",
            status=TopicCandidateStatus.PLANNED.value,
            signal_count=4,
            latest_signal_at=None,
        )
        session.commit()

        self.assertEqual(candidate.id, updated.id)
        self.assertEqual(updated.topic_title, "微信搜一搜带来的新内容机会")
        self.assertEqual(updated.status, TopicCandidateStatus.PLANNED.value)
        self.assertEqual(len(candidates.list_recent()), 1)

        plans = TopicPlanRepository(session)
        first_version = plans.get_next_plan_version(updated.id)
        self.assertEqual(first_version, 1)
        plans.create(
            TopicPlan(
                candidate_id=updated.id,
                plan_version=first_version,
                business_goal="build_trust",
                article_type="industry_analysis",
                angle="不是讲功能，而是讲分发格局变化。",
            )
        )
        second_version = plans.get_next_plan_version(updated.id)
        self.assertEqual(second_version, 2)
        plans.create(
            TopicPlan(
                candidate_id=updated.id,
                plan_version=second_version,
                business_goal="generate_leads",
                article_type="decision_guide",
                angle="从运营动作设计看可执行机会。",
            )
        )
        session.commit()

        latest = plans.get_latest_by_candidate_id(updated.id)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.plan_version, 2)
        self.assertEqual(latest.article_type, "decision_guide")
        session.close()


if __name__ == "__main__":
    unittest.main()
