"""通用 Pipeline Runner — 顺序执行步骤列表。

Runner 是无状态的通用执行器，遍历 Step 列表，依次调用 run()，
自动管理 task 状态、audit 日志和错误处理。

当前阶段（第二步）：Runner 和 Step 类独立存在，
Phase2/3/4 PipelineService.run() 保持不变，
未来第三步改为 Worker 直接调用 Runner。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.core.pipeline import PipelineStep, StepContext, StepResult
from app.models.audit_log import AuditLog
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.task_repository import TaskRepository

logger = logging.getLogger(__name__)


class PipelineRunner:
    """通用 pipeline 执行器。"""

    def __init__(self, steps: list[PipelineStep], session: Session) -> None:
        self.steps = steps
        self.session = session
        self.tasks = TaskRepository(session)
        self.audit_logs = AuditLogRepository(session)

    def execute(self, task_id: str) -> StepContext:
        """顺序执行所有 step，返回最终 context。"""
        ctx = StepContext(task_id=task_id, session=self.session)

        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        for step in self.steps:
            logger.info("pipeline.step.started step=%s task=%s", step.id, task_id)
            self._log(task_id, f"{step.id}.started", {"step_label": step.label})

            try:
                result = step.run(ctx)
            except Exception as exc:
                logger.exception("pipeline.step.failed step=%s task=%s", step.id, task_id)
                self._log(task_id, f"{step.id}.failed", {"error": str(exc)})
                self.session.commit()
                raise

            ctx.artifacts.update(result.artifacts)

            if not result.success:
                logger.warning("pipeline.step.rejected step=%s task=%s", step.id, task_id)
                self._log(task_id, f"{step.id}.rejected", {"error": result.error or "unknown"})
                self.session.commit()
                break

            self._log(task_id, f"{step.id}.completed", {})
            self.session.commit()

            if result.skip_remaining:
                logger.info("pipeline.step.skip_remaining step=%s task=%s", step.id, task_id)
                break

        return ctx

    def _log(self, task_id: str, action: str, details: dict[str, Any]) -> None:
        self.audit_logs.create(
            AuditLog(
                task_id=task_id,
                action=action,
                details=details,
            )
        )
