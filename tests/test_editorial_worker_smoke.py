"""Smoke test for run_editorial_worker — verifies the module imports cleanly
and exposes a callable `main` without executing the infinite loop."""
from __future__ import annotations

import importlib
import unittest


class EditorialWorkerSmokeTests(unittest.TestCase):
    def test_module_imports(self) -> None:
        mod = importlib.import_module("scripts.run_editorial_worker")
        self.assertIsNotNone(mod)

    def test_main_is_callable(self) -> None:
        mod = importlib.import_module("scripts.run_editorial_worker")
        self.assertTrue(callable(getattr(mod, "main", None)))
