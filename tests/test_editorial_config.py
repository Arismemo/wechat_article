import os
import unittest
from unittest.mock import patch

from app.core.enums import TaskStatus, ACTIVE_TASK_STATUSES


class EditorialConfigTests(unittest.TestCase):
    def test_pending_editorial_status_exists_and_active(self) -> None:
        self.assertEqual(TaskStatus.PENDING_EDITORIAL.value, "pending_editorial")
        self.assertIn(TaskStatus.PENDING_EDITORIAL, ACTIVE_TASK_STATUSES)

    def test_editorial_settings_defaults(self) -> None:
        env = {
            "APP_BASE_URL": "https://e.com", "API_BEARER_TOKEN": "t",
            "DATABASE_URL": "sqlite+pysqlite:///:memory:", "REDIS_URL": "redis://localhost:6379/0",
            "LLM_PROVIDER": "Z", "LLM_API_KEY": "k", "LLM_MODEL_ANALYZE": "m",
            "LLM_MODEL_WRITE": "m", "LLM_MODEL_REVIEW": "m", "SEARCH_PROVIDER": "S",
            "WECHAT_APP_ID": "w", "WECHAT_APP_SECRET": "s",
        }
        with patch.dict(os.environ, env, clear=False):
            from app.settings import get_settings
            get_settings.cache_clear()
            s = get_settings()
            self.assertFalse(s.editorial_enabled)
            self.assertEqual(s.editorial_llm_model, "glm-5.2")
            self.assertEqual(s.editorial_llm_max_concurrency, 3)
            self.assertEqual(s.editorial_max_debate_rounds, 4)
            self.assertEqual(s.editorial_queue_key, "editorial:queue")
        get_settings.cache_clear()
