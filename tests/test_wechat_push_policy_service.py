import os
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.db.redis_client import get_redis_client
from app.models.task import Task
from app.services.wechat_push_policy_service import WechatPushPolicyService
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


class WechatPushPolicyServiceTests(unittest.TestCase):
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

    def test_default_policy_allows_push(self) -> None:
        session = self.Session()
        task = self._seed_task(session)

        policy = WechatPushPolicyService(session).get_policy(task.id)

        self.assertEqual(policy.mode, "default")
        self.assertTrue(policy.can_push)
        self.assertIsNone(policy.note)
        session.close()

    def test_allow_push_records_manual_policy(self) -> None:
        session = self.Session()
        task = self._seed_task(session)

        result = WechatPushPolicyService(session).allow_push(task.id, operator="ops", note="已人工放行")
        policy = WechatPushPolicyService(session).get_policy(task.id)

        self.assertEqual(result.mode, "allowed")
        self.assertTrue(result.can_push)
        self.assertEqual(policy.mode, "allowed")
        self.assertTrue(policy.can_push)
        self.assertEqual(policy.note, "已人工放行")
        self.assertEqual(policy.operator, "ops")
        session.close()

    def test_block_push_records_manual_policy(self) -> None:
        session = self.Session()
        task = self._seed_task(session)

        result = WechatPushPolicyService(session).block_push(task.id, operator="ops", note="先不要进草稿箱")
        policy = WechatPushPolicyService(session).get_policy(task.id)

        self.assertEqual(result.mode, "blocked")
        self.assertFalse(result.can_push)
        self.assertEqual(policy.mode, "blocked")
        self.assertFalse(policy.can_push)
        self.assertEqual(policy.note, "先不要进草稿箱")
        self.assertEqual(policy.operator, "ops")
        session.close()

    def _seed_task(self, session) -> Task:
        task = Task(
            task_code="tsk_push_policy",
            source_url="https://mp.weixin.qq.com/s/push-policy",
            normalized_url="https://mp.weixin.qq.com/s/push-policy",
            source_type="wechat",
            status="review_passed",
        )
        session.add(task)
        session.commit()
        return task


if __name__ == "__main__":
    unittest.main()
