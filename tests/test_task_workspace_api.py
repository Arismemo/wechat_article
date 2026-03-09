import os
import tempfile
import unittest
from datetime import datetime, timezone
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
from app.models.article_analysis import ArticleAnalysis
from app.models.audit_log import AuditLog
from app.models.content_brief import ContentBrief
from app.models.generation import Generation
from app.models.review_report import ReviewReport
from app.models.source_article import SourceArticle
from app.models.task import Task
from app.models.wechat_draft import WechatDraft
from app.settings import get_settings


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class TaskWorkspaceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "workspace.db")
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

    def test_task_workspace_returns_source_brief_generations_and_audits(self) -> None:
        session = self.Session()
        task = Task(
            task_code="tsk_workspace",
            source_url="https://mp.weixin.qq.com/s/workspace",
            normalized_url="https://mp.weixin.qq.com/s/workspace",
            source_type="wechat",
            status="review_passed",
        )
        session.add(task)
        session.flush()
        session.add(
            SourceArticle(
                task_id=task.id,
                url=task.source_url,
                title="源文标题",
                author="原作者",
                published_at=datetime(2026, 3, 7, tzinfo=timezone.utc),
                summary="源文摘要",
                cleaned_text="源文正文" * 30,
                fetch_status="success",
                word_count=1200,
            )
        )
        session.add(
            ArticleAnalysis(
                task_id=task.id,
                theme="虚拟内存",
                audience="开发者",
                angle="误区纠偏",
                tone="理性",
                key_points={"items": ["分页", "缺页异常"]},
            )
        )
        brief = ContentBrief(
            task_id=task.id,
            brief_version=1,
            positioning="工程师科普稿",
            new_angle="从判断框架切入",
            target_reader="后端开发者",
            must_cover={"items": ["地址空间", "分页"]},
        )
        session.add(brief)
        session.flush()
        generation_v1 = Generation(
            task_id=task.id,
            brief_id=brief.id,
            version_no=1,
            model_name="phase4-fallback-template",
            title="第一版",
            digest="第一版摘要",
            markdown_content="# 第一版",
            status="rejected",
        )
        generation_v2 = Generation(
            task_id=task.id,
            brief_id=brief.id,
            version_no=2,
            model_name="glm-5",
            title="第二版",
            digest="第二版摘要",
            markdown_content="# 第二版",
            score_overall=88,
            status="accepted",
        )
        session.add(generation_v1)
        session.add(generation_v2)
        session.flush()
        session.add(
            ReviewReport(
                generation_id=generation_v1.id,
                similarity_score=0.55,
                factual_risk_score=0.20,
                policy_risk_score=0.05,
                readability_score=66,
                title_score=60,
                novelty_score=62,
                issues={"items": ["太像原文"]},
                suggestions={"items": ["重写结构"]},
                final_decision="reject",
            )
        )
        session.add(
            ReviewReport(
                generation_id=generation_v2.id,
                similarity_score=0.18,
                factual_risk_score=0.06,
                policy_risk_score=0.01,
                readability_score=90,
                title_score=86,
                novelty_score=84,
                issues={
                    "items": ["通过"],
                    "ai_trace_score": 28,
                    "ai_trace_patterns": ["表达自然，基本无模板味"],
                    "voice_summary": "整体像编辑写的讲解稿，节奏自然。",
                },
                suggestions={
                    "items": ["可推稿"],
                    "rewrite_targets": [
                        {
                            "block_id": "b3",
                            "reason": "如需进一步润色，可以补一点细节。",
                            "instruction": "把判断写得更有场景感。",
                        }
                    ],
                    "humanize": {"applied": True, "block_ids": ["b3"]},
                },
                final_decision="pass",
            )
        )
        session.add(
            WechatDraft(
                task_id=task.id,
                generation_id=generation_v2.id,
                media_id="mid-1",
                push_status="success",
                push_response={"draft": {"media_id": "mid-1"}},
            )
        )
        session.add(AuditLog(task_id=task.id, action="phase4.review.passed", operator="system", payload={"version": 2}))
        session.add(AuditLog(task_id=task.id, action="wechat.push.completed", operator="system", payload={"media_id": "mid-1"}))
        session.add(
            AuditLog(
                task_id=task.id,
                action="phase5.wechat_push.blocked",
                operator="editor",
                payload={"note": "先别推草稿"},
            )
        )
        session.commit()
        session.close()

        response = self.client.get(
            f"/api/v1/tasks/{task.id}/workspace",
            headers={"Authorization": "Bearer test-token"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["task_id"], task.id)
        self.assertEqual(body["status"], "review_passed")
        self.assertEqual(body["source_article"]["title"], "源文标题")
        self.assertEqual(body["brief"]["new_angle"], "从判断框架切入")
        self.assertEqual(len(body["generations"]), 2)
        self.assertEqual(body["generations"][0]["version_no"], 2)
        self.assertEqual(body["generations"][0]["prompt_version"], "phase4-v1")
        self.assertEqual(body["generations"][0]["review"]["final_decision"], "pass")
        self.assertEqual(body["generations"][0]["review"]["ai_trace_score"], 28.0)
        self.assertEqual(body["generations"][0]["review"]["rewrite_targets"][0]["block_id"], "b3")
        self.assertTrue(body["generations"][0]["review"]["humanize_applied"])
        self.assertEqual(body["generations"][0]["review"]["humanize_block_ids"], ["b3"])
        self.assertEqual(body["wechat_media_id"], "mid-1")
        self.assertEqual(body["wechat_draft_url"], "https://mp.weixin.qq.com/")
        self.assertFalse(body["wechat_draft_url_direct"])
        self.assertIn("media_id", body["wechat_draft_url_hint"])
        self.assertEqual(body["wechat_push_policy"]["mode"], "blocked")
        self.assertFalse(body["wechat_push_policy"]["can_push"])
        self.assertEqual(body["wechat_push_policy"]["note"], "先别推草稿")
        self.assertEqual(body["wechat_push_policy"]["operator"], "editor")
        self.assertEqual(len(body["audits"]), 3)
        self.assertEqual(
            {item["action"] for item in body["audits"]},
            {"phase4.review.passed", "wechat.push.completed", "phase5.wechat_push.blocked"},
        )


if __name__ == "__main__":
    unittest.main()
