import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.enums import TaskStatus
from app.db.base import Base
from app.db.redis_client import get_redis_client
from app.models.article_analysis import ArticleAnalysis
from app.models.content_brief import ContentBrief
from app.models.related_article import RelatedArticle
from app.models.source_article import SourceArticle
from app.models.task import Task
from app.services.phase3_pipeline_service import Phase3PipelineService
from app.services.search_service import RankedSearchResult
from app.services.source_fetch_service import FetchedArticle
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


TEST_ENV = {
    "APP_BASE_URL": "https://example.com",
    "API_BEARER_TOKEN": "test-token",
    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "REDIS_URL": "redis://localhost:6379/0",
    "LLM_PROVIDER": "ZHIPU",
    "LLM_API_KEY": "test-key",
    "LLM_MODEL_ANALYZE": "glm-5",
    "LLM_MODEL_WRITE": "glm-5",
    "LLM_MODEL_REVIEW": "glm-5",
    "SEARCH_PROVIDER": "ZHIPU_MCP",
    "WECHAT_APP_ID": "wx-test",
    "WECHAT_APP_SECRET": "secret-test",
}


class Phase3PipelineServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {**TEST_ENV, "LOCAL_STORAGE_ROOT": self.temp_dir.name}, clear=False)
        self.env_patch.start()
        get_settings.cache_clear()
        get_redis_client.cache_clear()

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        get_settings.cache_clear()
        get_redis_client.cache_clear()
        self.temp_dir.cleanup()

    def test_phase3_pipeline_builds_analysis_related_articles_and_brief(self) -> None:
        session = self.Session()
        task = Task(
            task_code="tsk_phase3",
            source_url="https://mp.weixin.qq.com/s/example",
            normalized_url="https://mp.weixin.qq.com/s/example",
            source_type="wechat",
            status=TaskStatus.SOURCE_READY.value,
        )
        session.add(task)
        session.flush()
        session.add(
            SourceArticle(
                task_id=task.id,
                url=task.source_url,
                title="虚拟内存的基础知识",
                author="专注Linux",
                summary="这是一篇解释虚拟内存基本概念和常见误区的文章。",
                cleaned_text="虚拟内存的作用是提升内存管理灵活性。\n\n分页与缺页异常是理解这个主题的关键。",
                fetch_status="success",
                word_count=1280,
            )
        )
        session.commit()

        service = Phase3PipelineService(session)
        service.llm = MagicMock()
        service.search = MagicMock()
        service.fetcher = MagicMock()

        service.llm.complete_json.side_effect = [
            {
                "theme": "虚拟内存",
                "audience": "想把操作系统概念讲清楚的技术读者",
                "angle": "从性能与误区两个维度重新理解虚拟内存",
                "tone": "理性拆解",
                "key_points": ["虚拟内存是什么", "分页为什么重要"],
                "facts": ["缺页中断会带来性能代价"],
                "hooks": ["很多人把虚拟内存等同于 swap"],
                "risks": ["不要把概念写成绝对结论"],
                "gaps": ["原文没有把性能问题讲透"],
                "structure": [{"section": "定义", "purpose": "先讲清概念"}],
            },
            {
                "positioning": "面向工程师读者的虚拟内存重构稿",
                "new_angle": "从性能损耗与常见误解切入，而不是重复概念定义",
                "target_reader": "需要理解操作系统基础的开发者",
                "must_cover": ["虚拟内存的作用", "缺页异常与性能", "常见误区"],
                "must_avoid": ["照搬原文顺序", "没有证据的绝对化表述"],
                "difference_matrix": [
                    {
                        "topic": "性能影响",
                        "source_coverage": "多数文章只讲概念，不讲代价",
                        "opportunity": "补充具体性能判断方法",
                    }
                ],
                "outline": [{"heading": "先纠偏", "goal": "拆掉常见误解"}],
                "title_directions": ["虚拟内存最容易被误解的，不是 swap"],
            },
        ]
        ranked_results = [
            RankedSearchResult(
                query_text="虚拟内存 分析",
                title="虚拟内存为什么重要",
                url="https://example.com/virtual-memory-1",
                summary="从性能和系统抽象两个层面解释虚拟内存。",
                source_site="Example Tech",
                published_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                overall_score=0.91,
                relevance_score=0.9,
                diversity_score=0.9,
                factual_density_score=0.7,
            ),
            RankedSearchResult(
                query_text="虚拟内存 最新 争议 评价",
                title="虚拟内存的几个误区",
                url="https://example.org/virtual-memory-2",
                summary="重点讨论 swap、分页和性能误区。",
                source_site="Example Ops",
                published_at=datetime(2026, 2, 28, tzinfo=timezone.utc),
                overall_score=0.86,
                relevance_score=0.85,
                diversity_score=0.88,
                factual_density_score=0.72,
            ),
        ]
        service.search.search_many.return_value = []
        service.search.rank_results.return_value = ranked_results
        service.fetcher.fetch.side_effect = [
            FetchedArticle(
                url="https://example.com/virtual-memory-1",
                final_url="https://example.com/virtual-memory-1",
                fetch_method="http",
                title="虚拟内存为什么重要",
                author="甲",
                published_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                cover_image_url=None,
                raw_html="<article>one</article>",
                cleaned_text="文章一正文",
                summary="文章一摘要",
                snapshot_path="/tmp/related-1.html",
                word_count=1200,
                content_hash="hash-1",
            ),
            FetchedArticle(
                url="https://example.org/virtual-memory-2",
                final_url="https://example.org/virtual-memory-2",
                fetch_method="http",
                title="虚拟内存的几个误区",
                author="乙",
                published_at=datetime(2026, 2, 28, tzinfo=timezone.utc),
                cover_image_url=None,
                raw_html="<article>two</article>",
                cleaned_text="文章二正文",
                summary="文章二摘要",
                snapshot_path="/tmp/related-2.html",
                word_count=980,
                content_hash="hash-2",
            ),
        ]

        result = service.run(task.id)

        self.assertEqual(result.status, TaskStatus.BRIEF_READY.value)
        self.assertEqual(result.related_count, 2)
        self.assertIsNotNone(result.analysis_id)
        self.assertIsNotNone(result.brief_id)

        refreshed_task = session.get(Task, task.id)
        self.assertEqual(refreshed_task.status, TaskStatus.BRIEF_READY.value)

        analysis = session.scalar(select(ArticleAnalysis).where(ArticleAnalysis.task_id == task.id))
        brief = session.scalar(select(ContentBrief).where(ContentBrief.task_id == task.id))
        related_rows = list(session.scalars(select(RelatedArticle).where(RelatedArticle.task_id == task.id)))

        self.assertIsNotNone(analysis)
        self.assertEqual(analysis.theme, "虚拟内存")
        self.assertIsNotNone(brief)
        self.assertEqual(brief.new_angle, "从性能损耗与常见误解切入，而不是重复概念定义")
        self.assertEqual(len(related_rows), 2)
        self.assertTrue(all(item.selected for item in related_rows))
        self.assertEqual(related_rows[0].snapshot_path, "/tmp/related-1.html")

        session.close()
