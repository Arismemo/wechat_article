import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app.services.editorial_llm_client import EditorialLLMClient


class EditorialLLMClientTests(unittest.TestCase):
    def test_concurrency_never_exceeds_cap(self) -> None:
        client = EditorialLLMClient(api_base="http://x", api_key="k", model="glm-5.2", max_concurrency=3)
        active = {"n": 0, "max": 0}
        lock = threading.Lock()

        def fake_call(_payload, _timeout):
            with lock:
                active["n"] += 1
                active["max"] = max(active["max"], active["n"])
            time.sleep(0.02)
            with lock:
                active["n"] -= 1
            return {"ok": True}

        with patch.object(client, "_raw_completion", side_effect=fake_call):
            with ThreadPoolExecutor(max_workers=10) as ex:
                list(ex.map(lambda _: client.complete_json(system_prompt="s", user_prompt="u"), range(10)))
        self.assertLessEqual(active["max"], 3)
        self.assertGreaterEqual(active["max"], 1)

    def test_returns_parsed_json(self) -> None:
        client = EditorialLLMClient(api_base="http://x", api_key="k", model="glm-5.2", max_concurrency=3)
        with patch.object(client, "_raw_completion", return_value={"choices": [{"message": {"content": '{"stance":"pass"}'}}]}):
            out = client.complete_json(system_prompt="s", user_prompt="u")
        self.assertEqual(out["stance"], "pass")
