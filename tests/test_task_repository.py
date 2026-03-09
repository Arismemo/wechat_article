import unittest

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.enums import TaskStatus
from app.db.base import Base
from app.models.task import Task
from app.repositories.task_repository import TaskRepository


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(_type, _compiler, **_kwargs) -> str:
    return "CHAR(36)"


class TaskRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)

    def test_update_runtime_state_clears_stale_error_from_concurrent_session(self) -> None:
        writer_session = self.Session()
        task = Task(
            task_code="tsk_concurrent_error",
            source_url="https://mp.weixin.qq.com/s/example",
            normalized_url="https://mp.weixin.qq.com/s/example",
            source_type="wechat",
            status=TaskStatus.QUEUED.value,
        )
        writer_session.add(task)
        writer_session.commit()

        stale_session = self.Session()
        concurrent_session = self.Session()

        stale_task = stale_session.get(Task, task.id)
        self.assertIsNotNone(stale_task)
        self.assertIsNone(stale_task.error_message)

        concurrent_task = concurrent_session.get(Task, task.id)
        concurrent_task.status = TaskStatus.SEARCH_FAILED.value
        concurrent_task.error_code = "phase3_search_failed"
        concurrent_task.error_message = "No related search results were found."
        concurrent_session.commit()

        repo = TaskRepository(stale_session)
        repo.update_runtime_state(
            stale_task,
            status=TaskStatus.NEEDS_REGENERATE.value,
            error_code=None,
            error_message=None,
        )
        stale_session.commit()

        verification_session = self.Session()
        refreshed = verification_session.get(Task, task.id)
        self.assertEqual(refreshed.status, TaskStatus.NEEDS_REGENERATE.value)
        self.assertIsNone(refreshed.error_code)
        self.assertIsNone(refreshed.error_message)

        verification_session.close()
        concurrent_session.close()
        stale_session.close()
        writer_session.close()


if __name__ == "__main__":
    unittest.main()
