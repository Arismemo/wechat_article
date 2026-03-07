import os
import tempfile
import unittest
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
from app.models.generation import Generation
from app.models.related_article import RelatedArticle
from app.models.review_report import ReviewReport
from app.models.source_article import SourceArticle
from app.models.task import Task
from app.services.phase4_pipeline_service import Phase4PipelineService
from app.services.wechat_draft_publish_service import WechatDraftPublishResult
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


class Phase4PipelineServiceTests(unittest.TestCase):
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

    def test_phase4_pipeline_generates_and_reviews_passed_draft(self) -> None:
        session = self.Session()
        task = self._seed_phase4_ready_task(session, "tsk_phase4_pass")

        service = Phase4PipelineService(session)
        service.llm = MagicMock()
        service.llm.complete_json.side_effect = [
            {
                "title": "虚拟内存不是 swap：真正该理解的是内存抽象",
                "subtitle": "给开发者的一次基础概念重构",
                "digest": "从概念、性能和误区三个维度，重新理解虚拟内存。",
                "markdown_content": (
                    "# 虚拟内存不是 swap：真正该理解的是内存抽象\n\n"
                    "> 给开发者的一次基础概念重构\n\n"
                    "## 先把最容易混淆的问题拆开\n"
                    "虚拟内存不是单一机制，而是一整套抽象。\n\n"
                    "## 为什么性能讨论不能跳过缺页异常\n"
                    "如果只讲概念，不讲代价，读者就无法形成判断。\n\n"
                    "## 最后给一个更稳的理解框架\n"
                    "- 先区分地址空间与物理内存\n"
                    "- 再理解分页与缺页异常\n"
                ),
            },
            {
                "final_decision": "pass",
                "similarity_score": 0.22,
                "factual_risk_score": 0.18,
                "policy_risk_score": 0.08,
                "readability_score": 86,
                "title_score": 84,
                "novelty_score": 82,
                "issues": ["结构完整，论证顺序有重构。"],
                "suggestions": ["可以进入下一阶段。"],
            },
        ]

        result = service.run(task.id)

        self.assertEqual(result.status, TaskStatus.REVIEW_PASSED.value)
        self.assertFalse(result.auto_revised)
        refreshed_task = session.get(Task, task.id)
        self.assertEqual(refreshed_task.status, TaskStatus.REVIEW_PASSED.value)

        generation_rows = list(session.scalars(select(Generation).where(Generation.task_id == task.id)))
        review_rows = list(
            session.scalars(
                select(ReviewReport)
                .join(Generation, ReviewReport.generation_id == Generation.id)
                .where(Generation.task_id == task.id)
            )
        )
        self.assertEqual(len(generation_rows), 1)
        self.assertEqual(len(review_rows), 1)
        self.assertEqual(generation_rows[0].status, "accepted")
        self.assertGreater(float(generation_rows[0].score_overall or 0), 75)
        self.assertEqual(review_rows[0].final_decision, "pass")
        self.assertEqual(service.llm.complete_json.call_args_list[0].kwargs["timeout_seconds"], 180)
        self.assertEqual(service.llm.complete_json.call_args_list[1].kwargs["timeout_seconds"], 90)
        session.close()

    def test_phase4_pipeline_auto_revises_once_after_revise_decision(self) -> None:
        session = self.Session()
        task = self._seed_phase4_ready_task(session, "tsk_phase4_revise")

        service = Phase4PipelineService(session)
        service.llm = MagicMock()
        service.llm.complete_json.side_effect = [
            {
                "title": "虚拟内存的基础知识",
                "subtitle": "第一版",
                "digest": "第一版摘要",
                "markdown_content": (
                    "# 虚拟内存的基础知识\n\n"
                    "## 概念\n"
                    "第一版结构偏平。\n\n"
                    "## 误区\n"
                    "第一版还不够有增量。\n"
                ),
            },
            {
                "final_decision": "revise",
                "similarity_score": 0.53,
                "factual_risk_score": 0.24,
                "policy_risk_score": 0.10,
                "readability_score": 70,
                "title_score": 68,
                "novelty_score": 64,
                "issues": ["与原文距离不够。"],
                "suggestions": ["重排结构并补入性能判断框架。"],
            },
            {
                "title": "虚拟内存最该重学的，不是定义而是判断框架",
                "subtitle": "修订版",
                "digest": "修订版摘要",
                "markdown_content": (
                    "# 虚拟内存最该重学的，不是定义而是判断框架\n\n"
                    "> 修订版\n\n"
                    "## 先纠偏\n"
                    "把地址空间、分页和 swap 拆开。\n\n"
                    "## 再讲性能代价\n"
                    "缺页异常为什么会改变系统表现。\n\n"
                    "## 最后给出判断框架\n"
                    "- 先看抽象层\n"
                    "- 再看成本\n"
                    "- 再看常见误解\n"
                ),
            },
            {
                "final_decision": "pass",
                "similarity_score": 0.21,
                "factual_risk_score": 0.18,
                "policy_risk_score": 0.06,
                "readability_score": 88,
                "title_score": 86,
                "novelty_score": 87,
                "issues": ["修订后结构更清晰。"],
                "suggestions": ["可以进入下一阶段。"],
            },
        ]

        result = service.run(task.id)

        self.assertEqual(result.status, TaskStatus.REVIEW_PASSED.value)
        self.assertTrue(result.auto_revised)
        generations = list(
            session.scalars(select(Generation).where(Generation.task_id == task.id).order_by(Generation.version_no.asc()))
        )
        review_rows = list(
            session.scalars(
                select(ReviewReport)
                .join(Generation, ReviewReport.generation_id == Generation.id)
                .where(Generation.task_id == task.id)
                .order_by(Generation.version_no.asc())
            )
        )
        self.assertEqual(len(generations), 2)
        self.assertEqual(len(review_rows), 2)
        self.assertEqual(generations[-1].version_no, 2)
        self.assertEqual(generations[-1].status, "accepted")
        self.assertEqual(review_rows[0].final_decision, "revise")
        self.assertEqual(review_rows[-1].final_decision, "pass")
        session.close()

    def test_phase4_pipeline_auto_pushes_wechat_draft_when_enabled(self) -> None:
        session = self.Session()
        task = self._seed_phase4_ready_task(session, "tsk_phase4_autopush")

        with patch.dict(
            os.environ,
            {"PHASE4_AUTO_PUSH_WECHAT_DRAFT": "true", "WECHAT_ENABLE_DRAFT_PUSH": "true"},
            clear=False,
        ):
            get_settings.cache_clear()
            service = Phase4PipelineService(session)
            service.llm = MagicMock()
            service.llm.complete_json.side_effect = [
                {
                    "title": "虚拟内存真正的价值，是抽象带来的秩序",
                    "subtitle": "自动推送测试",
                    "digest": "自动推送测试摘要",
                    "markdown_content": (
                        "# 虚拟内存真正的价值，是抽象带来的秩序\n\n"
                        "## 先纠偏\n"
                        "虚拟内存不是 swap。\n\n"
                        "## 再讲代价\n"
                        "缺页异常会带来成本。\n\n"
                        "## 最后给框架\n"
                        "- 地址空间\n"
                        "- 分页\n"
                        "- 缺页异常\n"
                    ),
                },
                {
                    "final_decision": "pass",
                    "similarity_score": 0.18,
                    "factual_risk_score": 0.10,
                    "policy_risk_score": 0.05,
                    "readability_score": 87,
                    "title_score": 85,
                    "novelty_score": 84,
                    "issues": ["通过。"],
                    "suggestions": ["可以推草稿箱。"],
                },
            ]
            service.wechat_publisher = MagicMock()

            def push_generation_side_effect(passed_task, generation):
                passed_task.status = TaskStatus.DRAFT_SAVED.value
                return WechatDraftPublishResult(
                    task_id=passed_task.id,
                    status=TaskStatus.DRAFT_SAVED.value,
                    generation_id=generation.id,
                    wechat_media_id="draft-auto-1",
                    reused_existing=False,
                )

            service.wechat_publisher.push_generation.side_effect = push_generation_side_effect

            result = service.run(task.id)

        self.assertEqual(result.status, TaskStatus.DRAFT_SAVED.value)
        refreshed_task = session.get(Task, task.id)
        self.assertEqual(refreshed_task.status, TaskStatus.DRAFT_SAVED.value)
        service.wechat_publisher.push_generation.assert_called_once()
        session.close()
        get_settings.cache_clear()

    def _seed_phase4_ready_task(self, session, task_code: str) -> Task:
        task = Task(
            task_code=task_code,
            source_url="https://mp.weixin.qq.com/s/example",
            normalized_url="https://mp.weixin.qq.com/s/example",
            source_type="wechat",
            status=TaskStatus.BRIEF_READY.value,
        )
        session.add(task)
        session.flush()
        session.add(
            SourceArticle(
                task_id=task.id,
                url=task.source_url,
                title="虚拟内存的基础知识",
                author="专注Linux",
                summary="解释虚拟内存概念、分页和常见误区。",
                cleaned_text="虚拟内存的关键在于地址空间抽象、分页和缺页异常。",
                fetch_status="success",
                word_count=1500,
            )
        )
        session.add(
            ArticleAnalysis(
                task_id=task.id,
                theme="虚拟内存",
                audience="技术读者",
                angle="从误区和性能切入",
                tone="理性拆解",
                key_points={"items": ["概念", "分页", "缺页异常"]},
                facts={"items": ["缺页异常会带来额外开销"]},
                hooks={"items": ["很多人把虚拟内存等同于 swap"]},
                risks={"items": ["不要做绝对化判断"]},
                gaps={"items": ["原文没有把性能代价讲透"]},
                structure={"items": [{"section": "定义", "purpose": "讲清概念"}]},
            )
        )
        brief = ContentBrief(
            task_id=task.id,
            brief_version=1,
            positioning="给工程师看的概念重构稿",
            new_angle="从性能损耗和误解切入，而不是重复概念定义",
            target_reader="需要理解操作系统基础的开发者",
            must_cover={"items": ["地址空间", "分页", "缺页异常"]},
            must_avoid={"items": ["照搬原文顺序", "绝对化判断"]},
            difference_matrix={"items": [{"topic": "性能", "opportunity": "补足代价判断"}]},
            outline={"items": ["先纠偏", "再讲性能", "最后给框架"]},
            title_directions={"items": ["虚拟内存最该重学的，不是定义而是判断框架"]},
        )
        session.add(brief)
        session.add(
            RelatedArticle(
                task_id=task.id,
                query_text="虚拟内存 分析",
                rank_no=1,
                url="https://example.com/related-1",
                title="虚拟内存为什么重要",
                source_site="Example",
                summary="从性能和抽象两个角度解释虚拟内存。",
                cleaned_text="相关正文一",
                fetch_status="success",
                selected=True,
            )
        )
        session.add(
            RelatedArticle(
                task_id=task.id,
                query_text="虚拟内存 误区",
                rank_no=2,
                url="https://example.com/related-2",
                title="虚拟内存的几个误区",
                source_site="Example",
                summary="围绕 swap、分页和性能误区展开。",
                cleaned_text="相关正文二",
                fetch_status="success",
                selected=True,
            )
        )
        session.commit()
        return task
