from __future__ import annotations

from typing import Optional

from app.core.review_metadata import extract_review_metadata
from app.models.review_report import ReviewReport
from app.schemas.tasks import ReviewReportResponse, ReviewRewriteTargetResponse


def build_review_report_response(review: Optional[ReviewReport]) -> Optional[ReviewReportResponse]:
    if review is None:
        return None

    metadata = extract_review_metadata(review.issues, review.suggestions)
    return ReviewReportResponse(
        review_report_id=review.id,
        similarity_score=float(review.similarity_score) if review.similarity_score is not None else None,
        factual_risk_score=float(review.factual_risk_score) if review.factual_risk_score is not None else None,
        policy_risk_score=float(review.policy_risk_score) if review.policy_risk_score is not None else None,
        readability_score=float(review.readability_score) if review.readability_score is not None else None,
        title_score=float(review.title_score) if review.title_score is not None else None,
        novelty_score=float(review.novelty_score) if review.novelty_score is not None else None,
        issues=review.issues,
        suggestions=review.suggestions,
        final_decision=review.final_decision,
        ai_trace_score=metadata.ai_trace_score,
        ai_trace_patterns=metadata.ai_trace_patterns,
        rewrite_targets=[
            ReviewRewriteTargetResponse(
                block_id=item.block_id,
                reason=item.reason,
                instruction=item.instruction,
            )
            for item in metadata.rewrite_targets
        ],
        voice_summary=metadata.voice_summary,
        humanize_applied=metadata.humanize_applied,
        humanize_block_ids=metadata.humanize_block_ids,
    )
