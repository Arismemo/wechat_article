from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.task import Task
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.task_repository import TaskRepository


ALLOW_ACTION = "phase5.wechat_push.allowed"
BLOCK_ACTION = "phase5.wechat_push.blocked"
POLICY_ACTIONS = [ALLOW_ACTION, BLOCK_ACTION]


@dataclass
class WechatPushPolicyState:
    task_id: str
    mode: str
    can_push: bool
    note: Optional[str]
    operator: Optional[str]
    updated_at: Optional[datetime]
    source_action: Optional[str]


@dataclass
class WechatPushPolicyActionResult:
    task_id: str
    mode: str
    can_push: bool
    note: Optional[str]
    operator: str


class WechatPushBlockedError(ValueError):
    pass


class WechatPushPolicyService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.audit_logs = AuditLogRepository(session)

    def get_policy(self, task_id: str) -> WechatPushPolicyState:
        log = self.audit_logs.get_latest_by_task_id_and_actions(task_id, POLICY_ACTIONS)
        if log is None:
            return WechatPushPolicyState(
                task_id=task_id,
                mode="default",
                can_push=True,
                note=None,
                operator=None,
                updated_at=None,
                source_action=None,
            )
        return self._state_from_log(task_id, log)

    def allow_push(
        self,
        task_id: str,
        *,
        operator: Optional[str] = None,
        note: Optional[str] = None,
    ) -> WechatPushPolicyActionResult:
        task = self._require_task(task_id)
        normalized_operator = self._normalize_operator(operator)
        normalized_note = self._normalize_note(note)
        self.audit_logs.create(
            AuditLog(
                task_id=task.id,
                action=ALLOW_ACTION,
                operator=normalized_operator,
                payload={"note": normalized_note},
            )
        )
        self.session.commit()
        return WechatPushPolicyActionResult(
            task_id=task.id,
            mode="allowed",
            can_push=True,
            note=normalized_note,
            operator=normalized_operator,
        )

    def block_push(
        self,
        task_id: str,
        *,
        operator: Optional[str] = None,
        note: Optional[str] = None,
    ) -> WechatPushPolicyActionResult:
        task = self._require_task(task_id)
        normalized_operator = self._normalize_operator(operator)
        normalized_note = self._normalize_note(note)
        self.audit_logs.create(
            AuditLog(
                task_id=task.id,
                action=BLOCK_ACTION,
                operator=normalized_operator,
                payload={"note": normalized_note},
            )
        )
        self.session.commit()
        return WechatPushPolicyActionResult(
            task_id=task.id,
            mode="blocked",
            can_push=False,
            note=normalized_note,
            operator=normalized_operator,
        )

    def ensure_push_allowed(self, task_id: str) -> WechatPushPolicyState:
        policy = self.get_policy(task_id)
        if not policy.can_push:
            raise WechatPushBlockedError("Wechat draft push is blocked by manual policy.")
        return policy

    def _require_task(self, task_id: str) -> Task:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")
        return task

    def _state_from_log(self, task_id: str, log: AuditLog) -> WechatPushPolicyState:
        return WechatPushPolicyState(
            task_id=task_id,
            mode="allowed" if log.action == ALLOW_ACTION else "blocked",
            can_push=log.action != BLOCK_ACTION,
            note=self._extract_note(log),
            operator=log.operator,
            updated_at=log.created_at,
            source_action=log.action,
        )

    def _extract_note(self, log: AuditLog) -> Optional[str]:
        payload = log.payload or {}
        note = str(payload.get("note") or "").strip()
        return note or None

    def _normalize_operator(self, operator: Optional[str]) -> str:
        return (operator or "").strip() or "manual"

    def _normalize_note(self, note: Optional[str]) -> Optional[str]:
        normalized = (note or "").strip()
        return normalized or None
