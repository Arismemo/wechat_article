from __future__ import annotations

import os
import tempfile
import unittest
from importlib import import_module, reload
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.models.editorial_review import EditorialReview
from app.repositories.editorial_review_repository import EditorialReviewRepository


TEST_ENV = {
    "APP_BASE_URL": "https://example.com",
    "API_BEARER_TOKEN": "test-token",
    "DATABASE_URL": "postgresql+psycopg://postgres:postgres@localhost:5432/wechat_artical",
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

# A sample EditorialReview-like object we can return from the mock.
# We use a real EditorialReview model so attribute access matches the template.


def _make_fake_review() -> EditorialReview:
    review = EditorialReview(
        task_id="task-abc-123",
        generation_id="gen-xyz-456",
        status="converged",
        rounds_used=2,
        decision="revise",
        rationale="标题缺具体数字，整体传播力不足。",
        dissent_summary="法务保留意见：合规风险尚可。",
        revision_directives=[
            {"location": "标题", "problem": "无数字", "fix": "加具体数字"}
        ],
        transcript={
            "rounds": [
                {
                    "round_no": 0,
                    "opinions": [
                        {
                            "role_key": "headline_editor",
                            "stance": "revise",
                            "key_argument": "标题无钩子",
                            "issues": ["缺少数字", "无场景标签"],
                            "scores": {"title": 60},
                        },
                        {
                            "role_key": "chief_editor",
                            "stance": "pass",
                            "key_argument": "整体质量合格",
                            "issues": [],
                            "scores": {"overall": 78},
                        },
                    ],
                },
                {
                    "round_no": 1,
                    "opinions": [
                        {
                            "role_key": "headline_editor",
                            "stance": "revise",
                            "key_argument": "标题仍需优化",
                            "issues": ["缺少数字"],
                            "scores": {"title": 62},
                        },
                    ],
                },
            ]
        },
    )
    review.id = "review-id-001"
    review.created_at = None
    return review


class AdminEditorialPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(
            os.environ,
            {**TEST_ENV, "LOCAL_STORAGE_ROOT": self.temp_dir.name},
            clear=False,
        )
        self.env_patch.start()

        from app.settings import get_settings
        from app.db.redis_client import get_redis_client

        get_settings.cache_clear()
        get_redis_client.cache_clear()

    def tearDown(self) -> None:
        self.env_patch.stop()
        from app.settings import get_settings
        from app.db.redis_client import get_redis_client

        get_settings.cache_clear()
        get_redis_client.cache_clear()
        self.temp_dir.cleanup()

    def _make_client(self):
        app_module = reload(import_module("app.main"))
        return TestClient(app_module.create_app())

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_task_with_editorial_review_returns_200_with_decision_and_role(self) -> None:
        fake_review = _make_fake_review()
        with patch.object(
            EditorialReviewRepository,
            "get_latest_by_task_id",
            return_value=fake_review,
        ):
            client = self._make_client()
            response = client.get("/admin/editorial/task-abc-123")

        self.assertEqual(response.status_code, 200)
        # Decision and Chinese label visible
        self.assertIn("revise", response.text)
        self.assertIn("修改", response.text)
        # Role content is rendered
        self.assertIn("headline_editor", response.text)
        # Rationale is visible
        self.assertIn("标题缺具体数字", response.text)
        # Dissent summary is visible
        self.assertIn("法务保留意见", response.text)
        # Admin shell is present
        self.assertIn('class="admin-app"', response.text)
        self.assertIn("admin-sidebar", response.text)
        # Task ID echoed back
        self.assertIn("task-abc-123", response.text)

    def test_task_with_no_editorial_review_returns_200_with_empty_state(self) -> None:
        with patch.object(
            EditorialReviewRepository,
            "get_latest_by_task_id",
            return_value=None,
        ):
            client = self._make_client()
            response = client.get("/admin/editorial/task-no-review")

        self.assertEqual(response.status_code, 200)
        self.assertIn("暂无编委会评审", response.text)
        # Admin shell still present
        self.assertIn('class="admin-app"', response.text)
        self.assertIn("task-no-review", response.text)

    def test_editorial_page_requires_basic_auth_when_configured(self) -> None:
        import base64

        with patch.dict(
            os.environ,
            {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "secret-pass"},
            clear=False,
        ):
            from app.settings import get_settings

            get_settings.cache_clear()
            fake_review = _make_fake_review()
            with patch.object(
                EditorialReviewRepository,
                "get_latest_by_task_id",
                return_value=fake_review,
            ):
                client = self._make_client()

                # Without credentials → 401
                unauthorized = client.get("/admin/editorial/task-abc-123")
                self.assertEqual(unauthorized.status_code, 401)
                self.assertEqual(
                    unauthorized.headers.get("www-authenticate"),
                    'Basic realm="wechat_artical-admin"',
                )

                # With correct credentials → 200 with decision content
                encoded = base64.b64encode(b"admin:secret-pass").decode("ascii")
                authorized = client.get(
                    "/admin/editorial/task-abc-123",
                    headers={"Authorization": f"Basic {encoded}"},
                )
                self.assertEqual(authorized.status_code, 200)
                self.assertIn("revise", authorized.text)

            client.close()
            get_settings.cache_clear()


if __name__ == "__main__":
    unittest.main()
