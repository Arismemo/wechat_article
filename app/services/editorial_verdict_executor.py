"""EditorialVerdictExecutor — act on the editorial board's verdict.

EditorialBoardService.review() produces an EditorialReview (+ an authoritative
ReviewReport) but does NOTHING with the verdict. This executor closes that loop:
on a clean pushable pass it pushes the WeChat draft; otherwise it reports
"needs_revision" so the worker's bounded revise loop (OPT-2) can feed the board's
directives back to the writer and re-submit an improved draft.

execute(review) → outcome:
  pass + thresholds pass → push draft:
       success                  → DRAFT_SAVED (set by push svc)   ("pushed")
       WechatPushBlockedError   → NEEDS_MANUAL_REVIEW             ("push_blocked")
       other push error         → PUSH_FAILED + re-raise (T3a retries)
  everything else (reject / revise / pass-but-thresholds-fail)
                              → log editorial.verdict.needs_revision,
                                leave status as-is                 ("needs_revision")

The executor NO LONGER terminally rejects/manual-reviews non-pass verdicts: the
worker loop owns iteration. When iterations are exhausted the worker calls
finalize_manual(review, reason=...) for the single terminal NEEDS_MANUAL_REVIEW
write.

This service owns its commits (mirrors WechatDraftPublishService) so status
writes are durable even when the caller's try/except converts a push failure
into a retry.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.models.audit_log import AuditLog
from app.models.editorial_review import EditorialReview
from app.models.generation import Generation
from app.models.review_report import ReviewReport
from app.models.task import Task
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.repositories.task_repository import TaskRepository
from app.services.phase4_pipeline_service import passes_review_thresholds
from app.services.system_setting_service import SystemSettingService
from app.services.wechat_draft_publish_service import WechatDraftPublishService
from app.services.wechat_push_policy_service import WechatPushBlockedError


class EditorialVerdictExecutor:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.generations = GenerationRepository(session)
        self.reviews = ReviewReportRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.system_settings = SystemSettingService(session)

    def execute(self, editorial_review: EditorialReview) -> str:
        task = self.tasks.get_by_id(editorial_review.task_id)
        if task is None:
            raise ValueError("editorial verdict: task not found")
        generation = self.generations.get_latest_by_task_id(editorial_review.task_id)
        if generation is None:
            raise ValueError("editorial verdict: generation not found")
        report = self._load_report(editorial_review, generation)

        decision = (editorial_review.decision or "").strip().lower()

        if decision == "pass":
            return self._pass(task, generation, editorial_review, report)
        # reject / revise / anything unexpected → NOT a clean push. Report
        # "needs_revision" WITHOUT a terminal status write so the worker's bounded
        # revise loop (OPT-2) can feed the board's directives (persisted on the
        # EditorialReview + ReviewReport.rewrite_targets) back to the writer and
        # re-submit. The worker calls finalize_manual() when iterations run out.
        return self._needs_revision(task, generation, editorial_review, reason=decision or "unknown")

    def finalize_manual(self, editorial_review: EditorialReview, *, reason: str) -> str:
        """Terminal NEEDS_MANUAL_REVIEW write — called by the worker when the
        bounded revise loop is exhausted. Mirrors the old non-pass terminal path,
        but now happens exactly once, after all revise iterations are spent."""
        task = self.tasks.get_by_id(editorial_review.task_id)
        if task is None:
            raise ValueError("editorial verdict: task not found")
        generation = self.generations.get_latest_by_task_id(editorial_review.task_id)
        if generation is None:
            raise ValueError("editorial verdict: generation not found")
        return self._manual_review(task, generation, editorial_review, reason=reason)

    # ── decision branches ────────────────────────────────────────────────────
    def _needs_revision(
        self, task: Task, generation: Generation, review: EditorialReview, *, reason: str
    ) -> str:
        # NO terminal status write — the task stays as-is (PENDING_EDITORIAL)
        # while the worker loop feeds the board's directives back to the writer
        # and re-submits. Just log the audit event so the loop is observable.
        self._log(
            task.id,
            "editorial.verdict.needs_revision",
            {
                "generation_id": generation.id,
                "editorial_review_id": review.id,
                "review_report_id": review.review_report_id,
                "decision": review.decision,
                "reason": reason,
            },
        )
        self.session.commit()
        return "needs_revision"

    def _pass(
        self,
        task: Task,
        generation: Generation,
        review: EditorialReview,
        report: Optional[ReviewReport],
    ) -> str:
        if report is None or not passes_review_thresholds(report, self.system_settings):
            # A "pass" verdict whose scores still miss a phase4 threshold is not
            # pushable → treat as needs_revision (no terminal write) so the loop
            # can try to improve the draft.
            return self._needs_revision(task, generation, review, reason="thresholds_failed")

        # Thresholds clear → attempt the authoritative push. The publish service
        # internally honours WECHAT_ENABLE_DRAFT_PUSH + the per-task push policy
        # and, on success, transitions the task to DRAFT_SAVED itself.
        try:
            WechatDraftPublishService(self.session).push_latest_accepted_generation(task.id)
        except WechatPushBlockedError:
            # Push policy (e.g. manual-only) blocks auto-push → hand to a human.
            return self._manual_review(
                task, generation, review, reason="push_blocked", outcome="push_blocked"
            )
        except Exception:
            # Transient/other push failure → mark PUSH_FAILED and let the worker
            # retry/DLQ layer (T3a) decide. The publish service may already have
            # set PUSH_FAILED; we re-assert it so the status is durable here.
            self._set_task_status(task, TaskStatus.PUSH_FAILED)
            self._log(
                task.id,
                "editorial.verdict.push_failed",
                {"generation_id": generation.id, "editorial_review_id": review.id},
            )
            self.session.commit()
            raise

        self._log(
            task.id,
            "editorial.verdict.pushed",
            {
                "generation_id": generation.id,
                "editorial_review_id": review.id,
                "review_report_id": review.review_report_id,
            },
        )
        self.session.commit()
        return "pushed"

    def _manual_review(
        self,
        task: Task,
        generation: Generation,
        review: EditorialReview,
        *,
        reason: str,
        outcome: str = "manual_review",
    ) -> str:
        # Mirror phase4._mark_needs_manual_review's status write. ``outcome``
        # lets the push-blocked path report "push_blocked" while still routing
        # the task to NEEDS_MANUAL_REVIEW.
        self._set_task_status(task, TaskStatus.NEEDS_MANUAL_REVIEW)
        self._log(
            task.id,
            "editorial.verdict.manual_required",
            {
                "generation_id": generation.id,
                "editorial_review_id": review.id,
                "review_report_id": review.review_report_id,
                "decision": review.decision,
                "reason": reason,
            },
        )
        self.session.commit()
        return outcome

    # ── helpers ──────────────────────────────────────────────────────────────
    def _load_report(
        self, review: EditorialReview, generation: Generation
    ) -> Optional[ReviewReport]:
        if review.review_report_id:
            report = self.session.get(ReviewReport, review.review_report_id)
            if report is not None:
                return report
        # Fall back to the latest report on this generation (the board persists
        # exactly one authoritative report per verdict).
        return self.reviews.get_latest_by_generation_id(generation.id)

    def _set_task_status(self, task: Task, status: TaskStatus) -> None:
        self.tasks.update_runtime_state(
            task,
            status=status.value,
            error_code=None,
            error_message=None,
        )

    def _log(self, task_id: str, action: str, payload: Optional[dict]) -> None:
        self.audit_logs.create(AuditLog(task_id=task_id, action=action, operator="system", payload=payload))
