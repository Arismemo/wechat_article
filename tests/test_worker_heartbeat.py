from __future__ import annotations

import time
import unittest
from typing import Optional

from app.services.worker_heartbeat import heartbeat_refresh_interval, keep_worker_heartbeat


class WorkerHeartbeatTests(unittest.TestCase):
    def test_heartbeat_refresh_interval_is_bounded(self) -> None:
        self.assertEqual(heartbeat_refresh_interval(0), 10.0)
        self.assertEqual(heartbeat_refresh_interval(9), 5.0)
        self.assertEqual(heartbeat_refresh_interval(60), 20.0)
        self.assertEqual(heartbeat_refresh_interval(300), 20.0)

    def test_keep_worker_heartbeat_refreshes_until_context_exit(self) -> None:
        calls: list[tuple[Optional[str], float]] = []

        def heartbeat(task_id: Optional[str]) -> None:
            calls.append((task_id, time.monotonic()))

        with keep_worker_heartbeat(heartbeat, current_task_id="task-1", interval_seconds=0.02):
            time.sleep(0.08)

        call_count_after_exit = len(calls)
        time.sleep(0.05)

        self.assertGreaterEqual(call_count_after_exit, 3)
        self.assertTrue(all(task_id == "task-1" for task_id, _ in calls))
        self.assertEqual(len(calls), call_count_after_exit)


if __name__ == "__main__":
    unittest.main()
