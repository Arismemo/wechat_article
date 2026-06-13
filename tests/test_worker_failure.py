import os
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch

import httpx
import redis.exceptions
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.enums import TaskStatus
from app.db.base import Base
from app.models.task import Task
from app.services.llm_service import LLMProviderHTTPError, LLMServiceError
from app.services.worker_failure import (
    RetryableError,
    handle_worker_failure,
    is_retriable,
)


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


def _http_error(status_code: int) -> LLMProviderHTTPError:
    return LLMProviderHTTPError(
        url="https://llm.example/chat/completions",
        status_code=status_code,
        response_text="boom",
    )


class FakeQueue:
    """Key-agnostic stub modelling queue / processing / dead lists."""

    def __init__(self, processing_id: str) -> None:
        self.queue: list[str] = []
        self.processing: list[str] = [processing_id]
        self.pending = {processing_id}
        self.dead: list[str] = []
        self.requeue_calls: list[str] = []
        self.dead_calls: list[tuple] = []

    def requeue_for_retry(self, task_id: str) -> None:
        self.requeue_calls.append(task_id)
        if task_id in self.processing:
            self.processing.remove(task_id)
        self.queue.insert(0, task_id)

    def move_to_dead(self, task_id: str, reason=None) -> None:
        self.dead_calls.append((task_id, reason))
        if task_id in self.processing:
            self.processing.remove(task_id)
        self.pending.discard(task_id)
        self.dead.insert(0, task_id)


class IsRetriableTests(unittest.TestCase):
    def test_retriable_cases(self) -> None:
        self.assertTrue(is_retriable(RetryableError("force")))
        self.assertTrue(is_retriable(httpx.TimeoutException("slow")))
        self.assertTrue(is_retriable(httpx.ConnectError("down")))  # TransportError subclass
        self.assertTrue(is_retriable(_http_error(503)))
        self.assertTrue(is_retriable(_http_error(429)))

    def test_non_retriable_cases(self) -> None:
        self.assertFalse(is_retriable(ValueError("bad value")))
        self.assertFalse(is_retriable(LLMServiceError("parse failed")))
        self.assertFalse(is_retriable(_http_error(400)))
        self.assertFalse(is_retriable(_http_error(404)))

    # Fix 3: transient Redis errors must be retriable
    def test_redis_connection_error_is_retriable(self) -> None:
        self.assertTrue(is_retriable(redis.exceptions.ConnectionError("lost")))

    def test_redis_timeout_error_is_retriable(self) -> None:
        self.assertTrue(is_retriable(redis.exceptions.TimeoutError("timed out")))


class HandleWorkerFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "worker-failure.db")
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

        self.task_id = str(uuid4())
        self.engine = create_engine(f"sqlite+pysqlite:///{self.db_path}", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def _make_task(self, session, *, retry_count: int = 0, status: str = TaskStatus.GENERATING.value) -> Task:
        task = Task(
            id=self.task_id,
            task_code="T-1",
            source_url="https://src.example/a",
            normalized_url="https://src.example/a",
            status=status,
            retry_count=retry_count,
        )
        session.add(task)
        session.commit()
        return task

    def test_retry_branch_increments_and_requeues(self) -> None:
        session = self.Session()
        queue = FakeQueue(self.task_id)
        self._make_task(session, retry_count=0)

        outcome = handle_worker_failure(
            queue,
            session,
            self.task_id,
            httpx.TimeoutException("slow"),
            failed_status=TaskStatus.GENERATE_FAILED.value,
            max_retries=3,
            backoff_seconds=0,
        )

        self.assertEqual(outcome, "retried")
        self.assertEqual(queue.requeue_calls, [self.task_id])
        self.assertEqual(queue.queue, [self.task_id])
        self.assertEqual(queue.dead, [])
        refreshed = session.get(Task, self.task_id)
        self.assertEqual(refreshed.retry_count, 1)
        # status stays re-runnable on a retry
        self.assertEqual(refreshed.status, TaskStatus.GENERATING.value)
        session.close()

    def test_exhausted_retries_moves_to_dead(self) -> None:
        session = self.Session()
        queue = FakeQueue(self.task_id)
        self._make_task(session, retry_count=3)

        outcome = handle_worker_failure(
            queue,
            session,
            self.task_id,
            _http_error(503),
            failed_status=TaskStatus.GENERATE_FAILED.value,
            max_retries=3,
            backoff_seconds=0,
        )

        self.assertEqual(outcome, "dead")
        self.assertEqual(queue.requeue_calls, [])
        self.assertEqual(queue.dead, [self.task_id])
        refreshed = session.get(Task, self.task_id)
        self.assertEqual(refreshed.status, TaskStatus.GENERATE_FAILED.value)
        self.assertEqual(refreshed.error_code, "llm_http_503")
        session.close()

    def test_non_retriable_moves_to_dead_immediately(self) -> None:
        session = self.Session()
        queue = FakeQueue(self.task_id)
        self._make_task(session, retry_count=0)

        outcome = handle_worker_failure(
            queue,
            session,
            self.task_id,
            ValueError("bad value"),
            failed_status=TaskStatus.GENERATE_FAILED.value,
            max_retries=3,
            backoff_seconds=0,
        )

        self.assertEqual(outcome, "dead")
        self.assertEqual(queue.requeue_calls, [])
        self.assertEqual(queue.dead, [self.task_id])
        refreshed = session.get(Task, self.task_id)
        self.assertEqual(refreshed.status, TaskStatus.GENERATE_FAILED.value)
        self.assertEqual(refreshed.retry_count, 0)
        session.close()

    def test_missing_task_moves_to_dead(self) -> None:
        session = self.Session()
        queue = FakeQueue(self.task_id)
        # no task inserted

        outcome = handle_worker_failure(
            queue,
            session,
            self.task_id,
            httpx.TimeoutException("slow"),
            failed_status=TaskStatus.GENERATE_FAILED.value,
            max_retries=3,
            backoff_seconds=0,
        )

        self.assertEqual(outcome, "dead")
        self.assertEqual(queue.dead_calls, [(self.task_id, "task-not-found")])
        session.close()

    def test_terminal_status_not_overwritten(self) -> None:
        session = self.Session()
        queue = FakeQueue(self.task_id)
        self._make_task(session, retry_count=0, status=TaskStatus.PUSH_FAILED.value)

        outcome = handle_worker_failure(
            queue,
            session,
            self.task_id,
            ValueError("bad value"),
            failed_status=TaskStatus.GENERATE_FAILED.value,
            max_retries=3,
            backoff_seconds=0,
        )

        self.assertEqual(outcome, "dead")
        refreshed = session.get(Task, self.task_id)
        # already a terminal *_FAILED status, must be preserved
        self.assertEqual(refreshed.status, TaskStatus.PUSH_FAILED.value)
        session.close()

    def test_update_status_false_keeps_status_but_dead_letters(self) -> None:
        session = self.Session()
        queue = FakeQueue(self.task_id)
        self._make_task(session, retry_count=3, status=TaskStatus.DRAFT_SAVED.value)

        outcome = handle_worker_failure(
            queue,
            session,
            self.task_id,
            ValueError("bad value"),
            failed_status="failed",
            max_retries=3,
            backoff_seconds=0,
            update_status=False,
        )

        self.assertEqual(outcome, "dead")
        refreshed = session.get(Task, self.task_id)
        # post-publish side job must not clobber the article's terminal status
        self.assertEqual(refreshed.status, TaskStatus.DRAFT_SAVED.value)
        # Fix 1: error fields must NOT be written when update_status=False
        self.assertIsNone(refreshed.error_code)
        self.assertIsNone(refreshed.error_message)
        # job must still reach the dead-letter list for observability
        self.assertEqual(outcome, "dead")
        self.assertEqual(queue.dead, [self.task_id])
        session.close()

    # Fix 1: explicit test — non-retriable failure with update_status=False
    def test_update_status_false_does_not_write_error_fields(self) -> None:
        """Feedback failures must not stamp error_code/error_message on the Task."""
        session = self.Session()
        queue = FakeQueue(self.task_id)
        self._make_task(session, retry_count=0, status=TaskStatus.DRAFT_SAVED.value)

        outcome = handle_worker_failure(
            queue,
            session,
            self.task_id,
            ValueError("feedback broke"),
            failed_status="feedback_failed",
            max_retries=0,
            backoff_seconds=0,
            update_status=False,
        )

        self.assertEqual(outcome, "dead")
        refreshed = session.get(Task, self.task_id)
        self.assertIsNone(refreshed.error_code)
        self.assertIsNone(refreshed.error_message)
        self.assertEqual(refreshed.status, TaskStatus.DRAFT_SAVED.value)
        self.assertEqual(queue.dead, [self.task_id])
        session.close()

    # Fix 2: dirty uncommitted objects from the pipeline must be discarded
    def test_rollback_discards_dirty_pipeline_state(self) -> None:
        """Uncommitted changes on the session before handle_worker_failure must not persist."""
        session = self.Session()
        queue = FakeQueue(self.task_id)
        task = self._make_task(session, retry_count=0, status=TaskStatus.GENERATING.value)

        # Simulate a dirty write left by the failed pipeline (not committed)
        task.source_url = "https://dirty.example/should-not-persist"
        # Do NOT call session.commit() — this is the partial pipeline state

        handle_worker_failure(
            queue,
            session,
            self.task_id,
            ValueError("pipeline crashed"),
            failed_status=TaskStatus.GENERATE_FAILED.value,
            max_retries=0,
            backoff_seconds=0,
        )

        # The dirty source_url change must have been rolled back
        refreshed = session.get(Task, self.task_id)
        self.assertEqual(refreshed.source_url, "https://src.example/a")
        session.close()


if __name__ == "__main__":
    unittest.main()
