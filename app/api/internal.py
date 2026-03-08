from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import verify_bearer_token
from app.db.session import get_db_session
from app.services.feedback_service import FeedbackService
from app.services.feedback_sync_service import FeedbackSyncProviderError, FeedbackSyncService
from app.services.manual_review_service import ManualReviewConflictError, ManualReviewService
from app.services.phase2_pipeline_service import Phase2PipelineService
from app.services.phase2_queue_service import Phase2QueueService
from app.services.phase3_pipeline_service import Phase3PipelineService
from app.services.phase3_queue_service import Phase3QueueService
from app.services.phase4_pipeline_service import Phase4PipelineService
from app.services.phase4_queue_service import Phase4QueueService
from app.services.task_service import TaskService
from app.services.wechat_push_policy_service import WechatPushBlockedError, WechatPushPolicyService
from app.services.wechat_draft_publish_service import WechatDraftPublishService
from app.schemas.ingest import IngestLinkRequest
from app.schemas.internal import (
    FeedbackCsvImportRequest,
    FeedbackCsvImportResponse,
    FeedbackCsvImportRowResponse,
    FeedbackImportRequest,
    FeedbackImportResponse,
    FeedbackSyncEnqueueResponse,
    FeedbackSyncRecentEnqueueRequest,
    FeedbackSyncRecentEnqueueResponse,
    FeedbackSyncRequest,
    FeedbackSyncResponse,
    ManualReviewActionRequest,
    ManualReviewActionResponse,
    Phase2EnqueueResponse,
    Phase2RunResponse,
    Phase3EnqueueResponse,
    Phase3RunResponse,
    Phase4EnqueueResponse,
    Phase4RunResponse,
    StyleAssetCreateRequest,
    StyleAssetCreateResponse,
    WechatPushPolicyActionRequest,
    WechatPushPolicyActionResponse,
    WechatPushResponse,
)

router = APIRouter()


def _raise_value_error_for_internal(exc: ValueError) -> None:
    detail = str(exc)
    status_code = status.HTTP_404_NOT_FOUND if detail == "Task not found." else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("/tasks/{task_id}/run-phase2", response_model=Phase2RunResponse, dependencies=[Depends(verify_bearer_token)])
def run_phase2(task_id: str, session: Session = Depends(get_db_session)) -> Phase2RunResponse:
    try:
        result = Phase2PipelineService(session).run(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Phase2RunResponse(
        task_id=result.task_id,
        status=result.status,
        source_title=result.source_title,
        generation_id=result.generation_id,
        wechat_media_id=result.wechat_media_id,
        snapshot_path=result.snapshot_path,
    )


@router.post("/tasks/{task_id}/enqueue-phase2", response_model=Phase2EnqueueResponse, dependencies=[Depends(verify_bearer_token)])
def enqueue_phase2(task_id: str, session: Session = Depends(get_db_session)) -> Phase2EnqueueResponse:
    task_service = TaskService(session)
    try:
        task = task_service.require_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    task = task_service.mark_queued_for_phase2(task, reason="manual-enqueue")
    result = Phase2QueueService().enqueue(task.id)
    return Phase2EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post("/phase2/ingest-and-run", response_model=Phase2RunResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_and_run_phase2(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> Phase2RunResponse:
    task, _ = TaskService(session).ingest_link(payload)
    try:
        result = Phase2PipelineService(session).run(task.id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Phase2RunResponse(
        task_id=result.task_id,
        status=result.status,
        source_title=result.source_title,
        generation_id=result.generation_id,
        wechat_media_id=result.wechat_media_id,
        snapshot_path=result.snapshot_path,
    )


@router.post("/phase2/ingest-and-enqueue", response_model=Phase2EnqueueResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_and_enqueue_phase2(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> Phase2EnqueueResponse:
    task_service = TaskService(session)
    task, _ = task_service.ingest_link(payload)
    task = task_service.mark_queued_for_phase2(task, reason="ingest-and-enqueue")
    result = Phase2QueueService().enqueue(task.id)
    return Phase2EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post("/tasks/{task_id}/run-phase3", response_model=Phase3RunResponse, dependencies=[Depends(verify_bearer_token)])
def run_phase3(task_id: str, session: Session = Depends(get_db_session)) -> Phase3RunResponse:
    try:
        result = Phase3PipelineService(session).run(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Phase3RunResponse(
        task_id=result.task_id,
        status=result.status,
        analysis_id=result.analysis_id,
        brief_id=result.brief_id,
        related_count=result.related_count,
    )


@router.post("/tasks/{task_id}/enqueue-phase3", response_model=Phase3EnqueueResponse, dependencies=[Depends(verify_bearer_token)])
def enqueue_phase3(task_id: str, session: Session = Depends(get_db_session)) -> Phase3EnqueueResponse:
    task_service = TaskService(session)
    try:
        task = task_service.require_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    task = task_service.mark_queued_for_phase3(task, reason="manual-enqueue")
    result = Phase3QueueService().enqueue(task.id)
    return Phase3EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post("/phase3/ingest-and-run", response_model=Phase3RunResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_and_run_phase3(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> Phase3RunResponse:
    task, _ = TaskService(session).ingest_link(payload)
    try:
        result = Phase3PipelineService(session).run(task.id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Phase3RunResponse(
        task_id=result.task_id,
        status=result.status,
        analysis_id=result.analysis_id,
        brief_id=result.brief_id,
        related_count=result.related_count,
    )


@router.post("/phase3/ingest-and-enqueue", response_model=Phase3EnqueueResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_and_enqueue_phase3(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> Phase3EnqueueResponse:
    task_service = TaskService(session)
    task, _ = task_service.ingest_link(payload)
    task = task_service.mark_queued_for_phase3(task, reason="ingest-and-enqueue")
    result = Phase3QueueService().enqueue(task.id)
    return Phase3EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post("/tasks/{task_id}/run-phase4", response_model=Phase4RunResponse, dependencies=[Depends(verify_bearer_token)])
def run_phase4(task_id: str, session: Session = Depends(get_db_session)) -> Phase4RunResponse:
    try:
        result = Phase4PipelineService(session).run(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Phase4RunResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        review_report_id=result.review_report_id,
        decision=result.decision,
        auto_revised=result.auto_revised,
    )


@router.post("/tasks/{task_id}/enqueue-phase4", response_model=Phase4EnqueueResponse, dependencies=[Depends(verify_bearer_token)])
def enqueue_phase4(task_id: str, session: Session = Depends(get_db_session)) -> Phase4EnqueueResponse:
    task_service = TaskService(session)
    try:
        task = task_service.require_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    task = task_service.mark_queued_for_phase4(task, reason="manual-enqueue")
    result = Phase4QueueService().enqueue(task.id)
    return Phase4EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post("/phase4/ingest-and-run", response_model=Phase4RunResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_and_run_phase4(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> Phase4RunResponse:
    task, _ = TaskService(session).ingest_link(payload)
    try:
        result = Phase4PipelineService(session).run(task.id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Phase4RunResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        review_report_id=result.review_report_id,
        decision=result.decision,
        auto_revised=result.auto_revised,
    )


@router.post("/phase4/ingest-and-enqueue", response_model=Phase4EnqueueResponse, dependencies=[Depends(verify_bearer_token)])
def ingest_and_enqueue_phase4(payload: IngestLinkRequest, session: Session = Depends(get_db_session)) -> Phase4EnqueueResponse:
    task_service = TaskService(session)
    task, _ = task_service.ingest_link(payload)
    task = task_service.mark_queued_for_phase4(task, reason="ingest-and-enqueue")
    result = Phase4QueueService().enqueue(task.id)
    return Phase4EnqueueResponse(
        task_id=task.id,
        status=task.status,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
    )


@router.post(
    "/tasks/{task_id}/import-feedback",
    response_model=FeedbackImportResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def import_feedback(
    task_id: str,
    payload: FeedbackImportRequest,
    session: Session = Depends(get_db_session),
) -> FeedbackImportResponse:
    try:
        result = FeedbackService(session).import_publication_metric(
            task_id,
            generation_id=payload.generation_id,
            day_offset=payload.day_offset,
            snapshot_at=payload.snapshot_at,
            prompt_type=payload.prompt_type,
            prompt_version=payload.prompt_version,
            wechat_media_id=payload.wechat_media_id,
            read_count=payload.read_count,
            like_count=payload.like_count,
            share_count=payload.share_count,
            comment_count=payload.comment_count,
            click_rate=payload.click_rate,
            source_type=payload.source_type,
            imported_by=payload.imported_by,
            notes=payload.notes,
            raw_payload=payload.raw_payload,
            operator=payload.operator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return FeedbackImportResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        metric_id=result.metric_id,
        prompt_type=result.prompt_type,
        prompt_version=result.prompt_version,
        day_offset=result.day_offset,
        sample_count=result.sample_count,
    )


@router.post(
    "/feedback/import-csv",
    response_model=FeedbackCsvImportResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def import_feedback_csv(
    payload: FeedbackCsvImportRequest,
    session: Session = Depends(get_db_session),
) -> FeedbackCsvImportResponse:
    try:
        result = FeedbackService(session).import_publication_metrics_csv(
            payload.csv_text,
            default_task_id=payload.default_task_id,
            source_type=payload.source_type,
            imported_by=payload.imported_by,
            operator=payload.operator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return FeedbackCsvImportResponse(
        imported_count=result.imported_count,
        results=[
            FeedbackCsvImportRowResponse(
                row_no=item.row_no,
                task_id=item.task_id,
                status=item.status,
                generation_id=item.generation_id,
                metric_id=item.metric_id,
                prompt_type=item.prompt_type,
                prompt_version=item.prompt_version,
                day_offset=item.day_offset,
                sample_count=item.sample_count,
            )
            for item in result.results
        ],
    )


@router.post(
    "/tasks/{task_id}/run-feedback-sync",
    response_model=FeedbackSyncResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def run_feedback_sync(
    task_id: str,
    payload: FeedbackSyncRequest,
    session: Session = Depends(get_db_session),
) -> FeedbackSyncResponse:
    try:
        result = FeedbackSyncService(session).run(
            task_id,
            day_offsets=payload.day_offsets,
            operator=payload.operator,
        )
    except ValueError as exc:
        _raise_value_error_for_internal(exc)
    except FeedbackSyncProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return FeedbackSyncResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        wechat_media_id=result.wechat_media_id,
        provider=result.provider,
        requested_day_offsets=result.requested_day_offsets,
        imported_count=result.imported_count,
        imported_day_offsets=result.imported_day_offsets,
        skipped_day_offsets=result.skipped_day_offsets,
        metric_ids=[item.metric_id for item in result.results],
    )


@router.post(
    "/tasks/{task_id}/enqueue-feedback-sync",
    response_model=FeedbackSyncEnqueueResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def enqueue_feedback_sync(
    task_id: str,
    payload: FeedbackSyncRequest,
    session: Session = Depends(get_db_session),
) -> FeedbackSyncEnqueueResponse:
    try:
        result = FeedbackSyncService(session).enqueue(
            task_id,
            day_offsets=payload.day_offsets,
            operator=payload.operator,
        )
    except ValueError as exc:
        _raise_value_error_for_internal(exc)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return FeedbackSyncEnqueueResponse(
        task_id=result.task_id,
        enqueued=result.enqueued,
        queue_depth=result.queue_depth,
        day_offsets=result.day_offsets,
    )


@router.post(
    "/feedback/enqueue-recent-sync",
    response_model=FeedbackSyncRecentEnqueueResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def enqueue_recent_feedback_sync(
    payload: FeedbackSyncRecentEnqueueRequest,
    session: Session = Depends(get_db_session),
) -> FeedbackSyncRecentEnqueueResponse:
    try:
        result = FeedbackSyncService(session).enqueue_recent(
            limit=payload.limit,
            day_offsets=payload.day_offsets,
            operator=payload.operator,
        )
    except ValueError as exc:
        _raise_value_error_for_internal(exc)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return FeedbackSyncRecentEnqueueResponse(
        requested_count=result.requested_count,
        enqueued_count=result.enqueued_count,
        queue_depth=result.queue_depth,
        task_ids=result.task_ids,
        day_offsets=result.day_offsets,
    )


@router.post("/style-assets", response_model=StyleAssetCreateResponse, dependencies=[Depends(verify_bearer_token)])
def create_style_asset(
    payload: StyleAssetCreateRequest,
    session: Session = Depends(get_db_session),
) -> StyleAssetCreateResponse:
    try:
        result = FeedbackService(session).create_style_asset(
            asset_type=payload.asset_type,
            title=payload.title,
            content=payload.content,
            tags=payload.tags,
            status=payload.status,
            weight=payload.weight,
            source_task_id=payload.source_task_id,
            source_generation_id=payload.source_generation_id,
            notes=payload.notes,
            operator=payload.operator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return StyleAssetCreateResponse(
        style_asset_id=result.style_asset_id,
        asset_type=result.asset_type,
        title=result.title,
        status=result.status,
    )


@router.post(
    "/tasks/{task_id}/approve-latest-generation",
    response_model=ManualReviewActionResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def approve_latest_generation(
    task_id: str,
    payload: Optional[ManualReviewActionRequest] = None,
    session: Session = Depends(get_db_session),
) -> ManualReviewActionResponse:
    try:
        result = ManualReviewService(session).approve_latest_generation(
            task_id,
            operator=payload.operator if payload else None,
            note=payload.note if payload else None,
        )
    except ManualReviewConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return ManualReviewActionResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        decision=result.decision,
    )


@router.post(
    "/tasks/{task_id}/reject-latest-generation",
    response_model=ManualReviewActionResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def reject_latest_generation(
    task_id: str,
    payload: Optional[ManualReviewActionRequest] = None,
    session: Session = Depends(get_db_session),
) -> ManualReviewActionResponse:
    try:
        result = ManualReviewService(session).reject_latest_generation(
            task_id,
            operator=payload.operator if payload else None,
            note=payload.note if payload else None,
        )
    except ManualReviewConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return ManualReviewActionResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        decision=result.decision,
    )


@router.post(
    "/tasks/{task_id}/allow-wechat-draft-push",
    response_model=WechatPushPolicyActionResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def allow_wechat_draft_push(
    task_id: str,
    payload: Optional[WechatPushPolicyActionRequest] = None,
    session: Session = Depends(get_db_session),
) -> WechatPushPolicyActionResponse:
    try:
        result = WechatPushPolicyService(session).allow_push(
            task_id,
            operator=payload.operator if payload else None,
            note=payload.note if payload else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return WechatPushPolicyActionResponse(
        task_id=result.task_id,
        mode=result.mode,
        can_push=result.can_push,
        note=result.note,
        operator=result.operator,
    )


@router.post(
    "/tasks/{task_id}/block-wechat-draft-push",
    response_model=WechatPushPolicyActionResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def block_wechat_draft_push(
    task_id: str,
    payload: Optional[WechatPushPolicyActionRequest] = None,
    session: Session = Depends(get_db_session),
) -> WechatPushPolicyActionResponse:
    try:
        result = WechatPushPolicyService(session).block_push(
            task_id,
            operator=payload.operator if payload else None,
            note=payload.note if payload else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return WechatPushPolicyActionResponse(
        task_id=result.task_id,
        mode=result.mode,
        can_push=result.can_push,
        note=result.note,
        operator=result.operator,
    )


@router.post("/tasks/{task_id}/push-wechat-draft", response_model=WechatPushResponse, dependencies=[Depends(verify_bearer_token)])
def push_wechat_draft(task_id: str, session: Session = Depends(get_db_session)) -> WechatPushResponse:
    try:
        result = WechatDraftPublishService(session).push_latest_accepted_generation(task_id)
    except WechatPushBlockedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return WechatPushResponse(
        task_id=result.task_id,
        status=result.status,
        generation_id=result.generation_id,
        wechat_media_id=result.wechat_media_id,
        reused_existing=result.reused_existing,
    )
