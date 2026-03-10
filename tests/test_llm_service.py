import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import httpx

from app.services.llm_service import LLMProviderHTTPError, LLMService
from app.settings import get_settings


class LLMServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(
            os.environ,
            {
                "APP_BASE_URL": "https://example.com",
                "API_BEARER_TOKEN": "test-token",
                "DATABASE_URL": "sqlite+pysqlite:///:memory:",
                "REDIS_URL": "redis://localhost:6379/0",
                "LLM_PROVIDER": "ZHIPU",
                "LLM_API_BASE": "https://open.bigmodel.cn/api/coding/paas/v4",
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

    def tearDown(self) -> None:
        self.env_patch.stop()
        get_settings.cache_clear()
        self.temp_dir.cleanup()

    def test_complete_json_raises_http_error_with_response_excerpt(self) -> None:
        request = httpx.Request("POST", "https://example.test/v1/chat/completions")
        response = httpx.Response(
            400,
            request=request,
            text='{"error":{"message":"model not found","type":"invalid_request_error"}}',
        )
        mocked = Mock()
        mocked.raise_for_status.side_effect = httpx.HTTPStatusError("bad request", request=request, response=response)
        mocked.text = response.text

        with patch("app.services.llm_service.httpx.post", return_value=mocked):
            service = LLMService(api_base="https://example.test/v1", api_key="sk-test", default_model="model-a")
            with self.assertRaises(LLMProviderHTTPError) as exc:
                service.complete_json(system_prompt="sys", user_prompt="usr", json_mode=True)

        self.assertEqual(exc.exception.status_code, 400)
        self.assertIn("model not found", str(exc.exception))

    def test_complete_json_supports_responses_endpoint(self) -> None:
        request = httpx.Request("POST", "https://example.test/v1/responses")
        body = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"ok": true, "message": "pong"}',
                        }
                    ],
                }
            ]
        }
        mocked = Mock()
        mocked.raise_for_status.return_value = None
        mocked.json.return_value = body

        with patch("app.services.llm_service.httpx.post", return_value=mocked) as mocked_post:
            service = LLMService(api_base="https://example.test/v1/responses", api_key="sk-test", default_model="model-a")
            payload = service.complete_json(system_prompt="sys", user_prompt="usr", json_mode=True)

        self.assertEqual(payload, {"ok": True, "message": "pong"})
        call = mocked_post.call_args.kwargs["json"]
        self.assertEqual(call["model"], "model-a")
        self.assertEqual(call["text"], {"format": {"type": "json_object"}})
        self.assertEqual(call["input"][0]["role"], "system")
        self.assertEqual(call["input"][1]["role"], "user")


if __name__ == "__main__":
    unittest.main()
