from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.core.progress import get_progress
from app.core.prompt_versions import resolve_generation_prompt_metadata
from app.core.review_metadata import extract_review_metadata
from app.models.audit_log import AuditLog
from app.models.generation import Generation
from app.models.review_report import ReviewReport
from app.models.task import Task
from app.repositories.article_analysis_repository import ArticleAnalysisRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.content_brief_repository import ContentBriefRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.related_article_repository import RelatedArticleRepository
from app.repositories.review_report_repository import ReviewReportRepository
from app.repositories.source_article_repository import SourceArticleRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.wechat_draft_repository import WechatDraftRepository
from app.schemas.tasks import (
    ArticleAnalysisResponse,
    AuditLogResponse,
    ContentBriefResponse,
    GenerationAiTraceDiagnosisResponse,
    GenerationWorkspaceResponse,
    RelatedArticleResponse,
    SourceArticleDetailResponse,
    TaskTimelineEventResponse,
    TaskWorkspaceResponse,
    WechatPushPolicyResponse,
)
from app.services.phase4_pipeline_service import Phase4PipelineService
from app.services.review_report_response_service import build_review_report_response
from app.services.system_setting_service import SystemSettingService
from app.services.task_generation_selection_service import TaskGenerationSelectionService
from app.services.wechat_draft_metadata_service import build_wechat_draft_metadata
from app.services.wechat_push_policy_service import WechatPushPolicyService
from app.settings import get_settings


class TaskWorkspaceQueryService:

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.system_settings = SystemSettingService(session)
        self.tasks = TaskRepository(session)
        self.source_articles = SourceArticleRepository(session)
        self.analyses = ArticleAnalysisRepository(session)
        self.briefs = ContentBriefRepository(session)
        self.generations = GenerationRepository(session)
        self.reviews = ReviewReportRepository(session)
        self.related_articles = RelatedArticleRepository(session)
        self.wechat_drafts = WechatDraftRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.wechat_push_policy = WechatPushPolicyService(session)
        self.selection = TaskGenerationSelectionService(session)

    def build_workspace(self, task_id: str) -> TaskWorkspaceResponse:
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError("Task not found.")

        source_article = self.source_articles.get_latest_by_task_id(task_id)
        analysis = self.analyses.get_latest_by_task_id(task_id)
        brief = self.briefs.get_latest_by_task_id(task_id)
        generations = self.generations.list_by_task_id(task_id, limit=8)
        audits = self.audit_logs.list_by_task_id(task_id, limit=25)
        related_articles = self.related_articles.list_selected_by_task_id(task_id)
        related_count = len(related_articles)
        push_policy = self.wechat_push_policy.get_policy(task_id)
        error = task.error_message or task.error_code
        task_status = TaskStatus(task.status)
        selected_generation = self.selection.build_response(task_id)
        wechat_draft = self._resolve_workspace_draft(
            task_id,
            generation_id=selected_generation.generation_id if selected_generation is not None else None,
        )
        draft_metadata = build_wechat_draft_metadata(wechat_draft)

        generation_rows: list[GenerationWorkspaceResponse] = []
        for generation in generations:
            review = self.reviews.get_latest_by_generation_id(generation.id)
            generation_prompt_type, generation_prompt_version = resolve_generation_prompt_metadata(
                generation.model_name,
                stored_prompt_type=generation.prompt_type,
                stored_prompt_version=generation.prompt_version,
            )
            generation_draft = self.wechat_drafts.get_latest_by_generation_id(generation.id)
            has_saved_draft = self._is_successful_draft(generation_draft)
            generation_rows.append(
                GenerationWorkspaceResponse(
                    generation_id=generation.id,
                    version_no=generation.version_no,
                    prompt_type=generation_prompt_type,
                    prompt_version=generation_prompt_version,
                    model_name=generation.model_name,
                    title=generation.title,
                    subtitle=generation.subtitle,
                    digest=generation.digest,
                    markdown_content=generation.markdown_content,
                    html_content=generation.html_content,
                    score_overall=float(generation.score_overall) if generation.score_overall is not None else None,
                    score_title=float(generation.score_title) if generation.score_title is not None else None,
                    score_readability=float(generation.score_readability) if generation.score_readability is not None else None,
                    score_novelty=float(generation.score_novelty) if generation.score_novelty is not None else None,
                    score_risk=float(generation.score_risk) if generation.score_risk is not None else None,
                    status=generation.status,
                    created_at=generation.created_at,
                    review=build_review_report_response(review),
                    ai_trace_diagnosis=self._build_ai_trace_diagnosis(generation, review, audits),
                    is_selected=selected_generation is not None and selected_generation.generation_id == generation.id,
                    draft_saved=has_saved_draft,
                    wechat_media_id=(generation_draft.media_id if has_saved_draft and generation_draft is not None else None),
                )
            )

        return TaskWorkspaceResponse(
            task_id=task.id,
            task_code=task.task_code,
            source_url=task.source_url,
            source_type=task.source_type,
            status=task.status,
            progress=get_progress(task_status),
            title=source_article.title if source_article else None,
            wechat_media_id=draft_metadata.media_id,
            wechat_draft_url=draft_metadata.draft_url,
            wechat_draft_url_direct=draft_metadata.draft_url_direct,
            wechat_draft_url_hint=draft_metadata.draft_url_hint,
            brief_id=brief.id if brief else None,
            generation_id=generations[0].id if generations else None,
            related_article_count=related_count,
            error=error,
            created_at=task.created_at,
            updated_at=task.updated_at,
            wechat_push_policy=WechatPushPolicyResponse(
                mode=push_policy.mode,
                can_push=push_policy.can_push,
                note=push_policy.note,
                operator=push_policy.operator,
                source_action=push_policy.source_action,
                updated_at=push_policy.updated_at,
            ),
            source_article=(
                SourceArticleDetailResponse(
                    source_article_id=source_article.id,
                    url=source_article.url,
                    title=source_article.title,
                    author=source_article.author,
                    published_at=source_article.published_at,
                    cover_image_url=source_article.cover_image_url,
                    summary=source_article.summary,
                    cleaned_text_excerpt=(source_article.cleaned_text or "")[:3000] or None,
                    snapshot_path=source_article.snapshot_path,
                    fetch_status=source_article.fetch_status,
                    word_count=source_article.word_count,
                    created_at=source_article.created_at,
                )
                if source_article
                else None
            ),
            analysis=(
                ArticleAnalysisResponse(
                    analysis_id=analysis.id,
                    theme=analysis.theme,
                    audience=analysis.audience,
                    angle=analysis.angle,
                    tone=analysis.tone,
                    key_points=analysis.key_points,
                    facts=analysis.facts,
                    hooks=analysis.hooks,
                    risks=analysis.risks,
                    gaps=analysis.gaps,
                    structure=analysis.structure,
                )
                if analysis
                else None
            ),
            brief=(
                ContentBriefResponse(
                    brief_id=brief.id,
                    brief_version=brief.brief_version,
                    positioning=brief.positioning,
                    new_angle=brief.new_angle,
                    target_reader=brief.target_reader,
                    must_cover=brief.must_cover,
                    must_avoid=brief.must_avoid,
                    difference_matrix=brief.difference_matrix,
                    outline=brief.outline,
                    title_directions=brief.title_directions,
                )
                if brief
                else None
            ),
            related_articles=[
                RelatedArticleResponse(
                    article_id=item.id,
                    query_text=item.query_text,
                    rank_no=item.rank_no,
                    url=item.url,
                    title=item.title,
                    source_site=item.source_site,
                    summary=item.summary,
                    published_at=item.published_at,
                    popularity_score=float(item.popularity_score) if item.popularity_score is not None else None,
                    relevance_score=float(item.relevance_score) if item.relevance_score is not None else None,
                    diversity_score=float(item.diversity_score) if item.diversity_score is not None else None,
                    factual_density_score=float(item.factual_density_score) if item.factual_density_score is not None else None,
                    snapshot_path=item.snapshot_path,
                    fetch_status=item.fetch_status,
                    selected=item.selected,
                )
                for item in related_articles
            ],
            selected_generation=selected_generation,
            generations=generation_rows,
            timeline=self._build_timeline(task, audits),
            audits=[
                AuditLogResponse(
                    audit_log_id=log.id,
                    action=log.action,
                    operator=log.operator,
                    payload=log.payload,
                    created_at=log.created_at,
                )
                for log in audits
            ],
        )

    def _build_ai_trace_diagnosis(
        self,
        generation: Generation,
        review: Optional[ReviewReport],
        audits: list[AuditLog],
    ) -> Optional[GenerationAiTraceDiagnosisResponse]:
        if review is None:
            return None

        metadata = extract_review_metadata(review.issues, review.suggestions)
        target_block_ids = [item.block_id for item in metadata.rewrite_targets]
        matching_events = [
            audit
            for audit in audits
            if audit.action.startswith("phase4.humanize.")
            and self._audit_matches_generation(audit, generation.id)
        ]
        latest_event = max(matching_events, key=lambda item: item.created_at, default=None)
        reason_codes: list[str] = []
        reasons: list[str] = []
        state = "not_triggered"
        triggered = False
        applied = metadata.humanize_applied
        rewritten_block_ids = list(metadata.humanize_block_ids)

        if metadata.humanize_applied:
            state = "completed"
            triggered = True
            reason_codes.append("humanize_applied")
            reasons.append("已执行 AI 去痕，并对指定段落完成定点润色。")
        elif latest_event is not None:
            triggered = True
            event_payload = latest_event.payload if isinstance(latest_event.payload, dict) else {}
            event_reason = str(event_payload.get("reason") or "").strip()
            if latest_event.action.endswith(".started"):
                state = "running"
                reason_codes.append("humanize_running")
                reasons.append("AI 去痕已启动，正在等待后续结果。")
            elif latest_event.action.endswith(".skipped"):
                state = "skipped"
                reason_codes.append(event_reason or "humanize_skipped")
                reasons.append(self._humanize_skip_reason_label(event_reason))
            elif latest_event.action.endswith(".failed"):
                state = "failed"
                reason_codes.append("humanize_failed")
                reasons.append("AI 去痕执行失败，请查看流水线时间线中的失败原因。")
            elif latest_event.action.endswith(".completed"):
                state = "completed"
                reason_codes.append("humanize_completed")
                reasons.append("AI 去痕已执行完成。")
                rewritten_block_ids = self._coerce_string_list(event_payload.get("rewritten_block_ids"))
        else:
            if metadata.ai_trace_score is None:
                reason_codes.append("missing_ai_trace_score")
                reasons.append("当前审稿结果没有提供 AI 痕迹分数。")
            elif metadata.ai_trace_score < self.system_settings.phase4_ai_trace_rewrite_threshold():
                reason_codes.append("ai_trace_below_threshold")
                threshold = int(self.system_settings.phase4_ai_trace_rewrite_threshold())
                reasons.append(f"AI 痕迹分数未达到 {threshold} 分触发阈值。")
            if not target_block_ids:
                reason_codes.append("no_rewrite_targets")
                reasons.append("审稿结果没有给出去痕需要改写的具体段落。")
            if float(review.policy_risk_score or 0) > self.system_settings.phase4_policy_risk_max():
                reason_codes.append("policy_risk_too_high")
                reasons.append("策略命中风险过高，本轮不允许自动去痕。")
            if float(review.factual_risk_score or 0) > self.system_settings.phase4_factual_risk_max():
                reason_codes.append("factual_risk_too_high")
                reasons.append("事实风险过高，本轮不允许自动去痕。")

        return GenerationAiTraceDiagnosisResponse(
            state=state,
            triggered=triggered,
            applied=applied,
            threshold_score=self.system_settings.phase4_ai_trace_rewrite_threshold(),
            ai_trace_score=metadata.ai_trace_score,
            rewrite_target_count=len(target_block_ids),
            rewrite_target_block_ids=target_block_ids,
            policy_risk_score=float(review.policy_risk_score) if review.policy_risk_score is not None else None,
            policy_risk_max=float(self.system_settings.phase4_policy_risk_max()),
            factual_risk_score=float(review.factual_risk_score) if review.factual_risk_score is not None else None,
            factual_risk_max=float(self.system_settings.phase4_factual_risk_max()),
            reason_codes=reason_codes,
            reasons=reasons,
            last_event_action=latest_event.action if latest_event is not None else None,
            last_event_at=latest_event.created_at if latest_event is not None else None,
            rewritten_block_ids=rewritten_block_ids,
        )

    def _build_timeline(self, task: Task, audits: list[AuditLog]) -> list[TaskTimelineEventResponse]:
        events = [
            TaskTimelineEventResponse(
                action="task.created",
                stage="task",
                status="completed",
                title="任务创建",
                summary=f"已接收链接并创建任务：{task.source_url}",
                created_at=task.created_at,
                payload={"task_id": task.id, "source_url": task.source_url},
            )
        ]
        ordered_audits = sorted(audits, key=lambda item: item.created_at)
        for audit in ordered_audits:
            payload = audit.payload if isinstance(audit.payload, dict) else {}
            events.append(
                TaskTimelineEventResponse(
                    action=audit.action,
                    stage=self._timeline_stage(audit.action),
                    status=self._timeline_status(audit.action),
                    title=self._timeline_title(audit.action),
                    summary=self._timeline_summary(audit.action, payload),
                    created_at=audit.created_at,
                    generation_id=self._extract_generation_id(payload),
                    review_report_id=self._extract_review_report_id(payload),
                    payload=audit.payload,
                )
            )
        return events

    def _timeline_stage(self, action: str) -> str:
        if action.startswith("phase4.generation") or action.startswith("phase4.revision"):
            return "generation"
        if action.startswith("phase4.review"):
            return "review"
        if action.startswith("phase4.humanize"):
            return "humanize"
        if action.startswith("phase5.manual_review"):
            return "manual_review"
        if action.startswith("wechat.push") or action.startswith("phase5.wechat_push"):
            return "wechat"
        return "system"

    def _timeline_status(self, action: str) -> str:
        if action.endswith(".started"):
            return "started"
        if action.endswith(".completed") or action.endswith(".passed") or action.endswith(".approved"):
            return "completed"
        if action.endswith(".selected_generation"):
            return "selected"
        if action.endswith(".skipped"):
            return "skipped"
        if action.endswith(".failed") or action.endswith(".rejected"):
            return "failed"
        if action.endswith(".manual_required"):
            return "manual"
        if action.endswith(".reused_existing"):
            return "reused"
        if action.endswith(".blocked") or action.endswith(".blocked_attempt"):
            return "blocked"
        return "info"

    def _timeline_title(self, action: str) -> str:
        titles = {
            "phase4.generation.started": "开始写稿",
            "phase4.generation.completed": "写稿完成",
            "phase4.review.started": "开始审稿",
            "phase4.review.completed": "审稿完成",
            "phase4.review.passed": "审稿通过",
            "phase4.review.rejected": "审稿驳回",
            "phase4.review.manual_required": "转人工审核",
            "phase4.revision.started": "开始自动修订",
            "phase4.humanize.started": "开始 AI 去痕",
            "phase4.humanize.completed": "AI 去痕完成",
            "phase4.humanize.skipped": "AI 去痕跳过",
            "phase4.humanize.failed": "AI 去痕失败",
            "wechat.push.started": "开始推送微信草稿",
            "wechat.push.completed": "微信草稿推送完成",
            "wechat.push.reused_existing": "复用已有微信草稿",
            "wechat.push.failed": "微信草稿推送失败",
            "phase5.manual_review.approved": "人工通过当前版本",
            "phase5.manual_review.rejected": "人工驳回当前版本",
            "phase5.manual_review.selected_generation": "人工采用指定历史版本",
        }
        return titles.get(action, action)

    def _timeline_summary(self, action: str, payload: dict) -> str:
        generation_id = self._extract_generation_id(payload)
        review_report_id = self._extract_review_report_id(payload)
        if action == "phase4.review.completed":
            decision = str(payload.get("decision") or "unknown")
            score = payload.get("overall_score")
            return f"审稿完成，结论为 {decision}，综合分 {score if score is not None else '暂无'}。"
        if action == "phase4.humanize.skipped":
            return self._humanize_skip_reason_label(str(payload.get("reason") or "humanize_skipped"))
        if action == "phase4.humanize.completed":
            block_ids = self._coerce_string_list(payload.get("rewritten_block_ids"))
            return f"AI 去痕已完成，改写段落：{', '.join(block_ids) if block_ids else '未记录'}。"
        if action == "phase5.manual_review.selected_generation":
            version_no = payload.get("selected_version_no")
            return f"人工采用了历史版本 v{version_no if version_no is not None else '?'} 作为当前版本。"
        if action == "phase5.manual_review.approved":
            return "人工确认当前版本可继续进入推稿阶段。"
        if action == "phase5.manual_review.rejected":
            return "人工确认当前版本需要重写。"
        if action == "wechat.push.completed":
            media_id = payload.get("media_id")
            return f"已推送到微信草稿箱，media_id={media_id or '未知'}。"
        if action == "wechat.push.reused_existing":
            media_id = payload.get("media_id")
            return f"复用已有微信草稿，media_id={media_id or '未知'}。"
        if action == "phase4.review.passed":
            return "系统已判定当前版本通过审稿。"
        if action == "phase4.review.rejected":
            return "系统已判定当前版本需要重写。"
        if action == "phase4.review.manual_required":
            return "系统将当前版本转入人工审核。"
        if action == "phase4.generation.completed":
            return f"已生成新版本，generation_id={generation_id or '未知'}。"
        if action == "phase4.review.started":
            return f"开始对 generation_id={generation_id or '未知'} 进行审稿。"
        if action == "phase4.generation.started":
            return "开始根据源文、Brief 和参考素材生成新稿。"
        if action == "phase4.humanize.started":
            return f"AI 去痕已启动，review_report_id={review_report_id or '未知'}。"
        if action == "phase4.humanize.failed":
            return f"AI 去痕执行失败：{payload.get('reason') or '未知原因'}"
        if action == "phase4.revision.started":
            return "系统已进入自动修订流程。"
        if action == "wechat.push.started":
            return "开始推送当前采用版本到微信草稿箱。"
        return str(payload.get("note") or payload.get("reason") or "已记录该动作。")

    def _audit_matches_generation(self, audit: AuditLog, generation_id: str) -> bool:
        payload = audit.payload if isinstance(audit.payload, dict) else {}
        return generation_id in {
            str(payload.get("generation_id") or "").strip(),
            str(payload.get("source_generation_id") or "").strip(),
        }

    def _extract_generation_id(self, payload: dict) -> Optional[str]:
        generation_id = str(payload.get("generation_id") or "").strip()
        return generation_id or None

    def _extract_review_report_id(self, payload: dict) -> Optional[str]:
        review_report_id = str(payload.get("review_report_id") or "").strip()
        return review_report_id or None

    def _humanize_skip_reason_label(self, reason: str) -> str:
        labels = {
            "no_valid_rewrites": "AI 去痕已触发，但没有拿到有效的改写段落。",
            "markdown_unchanged": "AI 去痕已触发，但改写后正文没有产生有效变化。",
            "humanize_skipped": "AI 去痕被跳过。",
        }
        return labels.get(reason, f"AI 去痕被跳过，原因：{reason or '未知'}。")

    def _coerce_string_list(self, payload: object) -> list[str]:
        if not isinstance(payload, list):
            return []
        return [str(item).strip() for item in payload if str(item).strip()]

    def _resolve_workspace_draft(self, task_id: str, *, generation_id: Optional[str]):
        if generation_id:
            selected_draft = self.wechat_drafts.get_latest_by_generation_id(generation_id)
            if self._is_successful_draft(selected_draft):
                return selected_draft
        return self.wechat_drafts.get_latest_successful_by_task_id(task_id) or self.wechat_drafts.get_latest_by_task_id(task_id)

    def _is_successful_draft(self, draft: object) -> bool:
        return bool(getattr(draft, "push_status", None) == "success" and getattr(draft, "media_id", None))
