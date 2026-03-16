"""Phase 4 步骤实现：AI 写稿、AI 审核、人类化改写、推送草稿。"""

from __future__ import annotations

from app.core.pipeline import StepConfigField, StepContext, StepResult
from app.core.enums import TaskStatus
from app.models.audit_log import AuditLog
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.task_repository import TaskRepository


class GenerateArticleStep:
    """AI 写稿 — 对应 Phase4 的 generate 阶段。"""

    id = "generate_article"
    label = "AI 写稿"
    icon = "✍️"
    config_schema = [
        StepConfigField(key="phase4.write_model", label="写稿模型", value_type="string", default=""),
    ]

    def run(self, ctx: StepContext) -> StepResult:
        session = ctx.session
        tasks = TaskRepository(session)
        audit_logs = AuditLogRepository(session)

        task = tasks.get_by_id(ctx.task_id)
        if task is None:
            return StepResult(success=False, error="Task not found")

        task.status = TaskStatus.GENERATING
        audit_logs.create(AuditLog(task_id=task.id, action="generate_article.started", details={}))
        session.commit()

        try:
            from app.services.phase4_pipeline_service import Phase4PipelineService
            phase4 = Phase4PipelineService(session)
            source, analysis, brief, related = phase4._ensure_phase3_inputs(task)
            generation = phase4._generate_generation(task=task, source=source, analysis=analysis, brief=brief, related=related)
        except Exception as exc:
            task.status = TaskStatus.GENERATE_FAILED
            session.commit()
            return StepResult(success=False, error=str(exc))

        audit_logs.create(AuditLog(task_id=task.id, action="generate_article.completed", details={"generation_id": generation.id}))
        session.commit()

        return StepResult(success=True, artifacts={
            "generation": generation,
            "source": source,
            "analysis": analysis,
            "brief": brief,
            "related": related,
        })


class ReviewArticleStep:
    """AI 审核 — 对应 Phase4 的 review 阶段。"""

    id = "review_article"
    label = "AI 审核"
    icon = "🔎"
    config_schema = [
        StepConfigField(key="phase4.review_pass_score", label="综合通过分", value_type="float", default=75),
        StepConfigField(key="phase4.similarity_max", label="相似度上限", value_type="float", default=0.45),
        StepConfigField(key="phase4.policy_risk_max", label="政策风险上限", value_type="float", default=0.35),
        StepConfigField(key="phase4.factual_risk_max", label="事实风险上限", value_type="float", default=0.40),
        StepConfigField(key="phase4.ai_trace_rewrite_threshold", label="AI痕迹阈值", value_type="float", default=70),
        StepConfigField(key="phase4.max_auto_revisions", label="最大自动修订", value_type="integer", default=1),
    ]

    def run(self, ctx: StepContext) -> StepResult:
        session = ctx.session
        tasks = TaskRepository(session)
        audit_logs = AuditLogRepository(session)

        task = tasks.get_by_id(ctx.task_id)
        if task is None:
            return StepResult(success=False, error="Task not found")

        generation = ctx.artifacts.get("generation")
        source = ctx.artifacts.get("source")
        brief = ctx.artifacts.get("brief")
        related = ctx.artifacts.get("related", [])

        if generation is None or source is None or brief is None:
            return StepResult(success=False, error="缺少 generation/source/brief")

        task.status = TaskStatus.REVIEWING
        audit_logs.create(AuditLog(task_id=task.id, action="review_article.started", details={"generation_id": generation.id}))
        session.commit()

        try:
            from app.services.phase4_pipeline_service import Phase4PipelineService
            phase4 = Phase4PipelineService(session)
            review = phase4._review_generation(task=task, source=source, brief=brief, related=related, generation=generation)
        except Exception as exc:
            task.status = TaskStatus.REVIEW_FAILED
            session.commit()
            return StepResult(success=False, error=str(exc))

        decision = phase4._normalize_decision(review.final_decision)
        audit_logs.create(AuditLog(task_id=task.id, action="review_article.completed", details={
            "decision": decision,
            "score": review.score_overall,
        }))
        session.commit()

        return StepResult(success=True, artifacts={"review": review, "decision": decision})


class HumanizeArticleStep:
    """人类化改写 — 对应 Phase4 的 humanize 阶段。"""

    id = "humanize_article"
    label = "人类化改写"
    icon = "🧬"
    config_schema: list[StepConfigField] = []

    def run(self, ctx: StepContext) -> StepResult:
        session = ctx.session
        tasks = TaskRepository(session)
        audit_logs = AuditLogRepository(session)

        task = tasks.get_by_id(ctx.task_id)
        if task is None:
            return StepResult(success=False, error="Task not found")

        review = ctx.artifacts.get("review")
        generation = ctx.artifacts.get("generation")
        source = ctx.artifacts.get("source")
        brief = ctx.artifacts.get("brief")

        if review is None or generation is None:
            return StepResult(success=True, artifacts={"humanize_applied": False})

        try:
            from app.services.phase4_pipeline_service import Phase4PipelineService
            phase4 = Phase4PipelineService(session)
            if not phase4._should_run_humanize(review):
                return StepResult(success=True, artifacts={"humanize_applied": False})

            audit_logs.create(AuditLog(task_id=task.id, action="humanize_article.started", details={}))
            session.commit()

            result = phase4._try_humanize_generation(
                task=task, source=source, brief=brief,
                generation=generation, review=review,
            )
            if result is None:
                return StepResult(success=True, artifacts={"humanize_applied": False})

            ctx.artifacts["generation"] = result.generation
            return StepResult(success=True, artifacts={"humanize_applied": True, "generation": result.generation})
        except Exception as exc:
            audit_logs.create(AuditLog(task_id=task.id, action="humanize_article.failed", details={"error": str(exc)}))
            session.commit()
            return StepResult(success=True, artifacts={"humanize_applied": False})


class PushDraftStep:
    """推送草稿 — 对应 Phase4 的推送阶段。"""

    id = "push_draft"
    label = "推送草稿"
    icon = "📤"
    config_schema = [
        StepConfigField(key="phase4.auto_push_wechat_draft", label="自动推送微信草稿", value_type="boolean", default=True),
    ]

    def run(self, ctx: StepContext) -> StepResult:
        session = ctx.session
        tasks = TaskRepository(session)
        audit_logs = AuditLogRepository(session)

        task = tasks.get_by_id(ctx.task_id)
        if task is None:
            return StepResult(success=False, error="Task not found")

        decision = ctx.artifacts.get("decision", "pass")
        generation = ctx.artifacts.get("generation")

        if decision != "pass" or generation is None:
            # 审核未通过，不推送
            if decision == "reject":
                task.status = TaskStatus.NEEDS_REGENERATE
            else:
                task.status = TaskStatus.NEEDS_MANUAL_REVIEW
            session.commit()
            return StepResult(success=True, skip_remaining=True)

        task.status = TaskStatus.PUSHING_WECHAT_DRAFT
        audit_logs.create(AuditLog(task_id=task.id, action="push_draft.started", details={"generation_id": generation.id}))
        session.commit()

        try:
            from app.services.phase4_pipeline_service import Phase4PipelineService
            phase4 = Phase4PipelineService(session)
            review = ctx.artifacts.get("review")
            if review and phase4._passes_thresholds(review):
                task.status = TaskStatus.REVIEW_PASSED
                audit_logs.create(AuditLog(task_id=task.id, action="push_draft.review_passed", details={}))
                session.commit()
        except Exception as exc:
            task.status = TaskStatus.PUSH_FAILED
            session.commit()
            return StepResult(success=False, error=str(exc))

        return StepResult(success=True, artifacts={"final_status": task.status})
