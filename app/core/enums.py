from enum import Enum


class TaskStatus(str, Enum):
    QUEUED = "queued"
    DEDUPING = "deduping"
    FETCHING_SOURCE = "fetching_source"
    SOURCE_READY = "source_ready"
    ANALYZING_SOURCE = "analyzing_source"
    SEARCHING_RELATED = "searching_related"
    FETCHING_RELATED = "fetching_related"
    BUILDING_BRIEF = "building_brief"
    BRIEF_READY = "brief_ready"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    REVIEW_PASSED = "review_passed"
    PUSHING_WECHAT_DRAFT = "pushing_wechat_draft"
    DRAFT_SAVED = "draft_saved"
    FETCH_FAILED = "fetch_failed"
    ANALYZE_FAILED = "analyze_failed"
    SEARCH_FAILED = "search_failed"
    BRIEF_FAILED = "brief_failed"
    GENERATE_FAILED = "generate_failed"
    REVIEW_FAILED = "review_failed"
    PUSH_FAILED = "push_failed"
    NEEDS_MANUAL_SOURCE = "needs_manual_source"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
    NEEDS_REGENERATE = "needs_regenerate"


class TopicSourceType(str, Enum):
    SEARCH_WATCHLIST = "search_watchlist"
    PAGE_MONITOR = "page_monitor"
    MANUAL_SEED = "manual_seed"


class TopicSignalType(str, Enum):
    SEARCH_RESULT = "search_result"
    REPORT_UPDATE = "report_update"
    OFFICIAL_NEWS = "official_news"
    MANUAL_SEED = "manual_seed"


class TopicFetchRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TopicCandidateStatus(str, Enum):
    NEW = "new"
    WATCHING = "watching"
    PLANNED = "planned"
    PROMOTED = "promoted"
    IGNORED = "ignored"


FINAL_FAILURE_STATUSES = {
    TaskStatus.FETCH_FAILED,
    TaskStatus.ANALYZE_FAILED,
    TaskStatus.SEARCH_FAILED,
    TaskStatus.BRIEF_FAILED,
    TaskStatus.GENERATE_FAILED,
    TaskStatus.REVIEW_FAILED,
    TaskStatus.PUSH_FAILED,
}

ACTIVE_TASK_STATUSES = {
    TaskStatus.QUEUED,
    TaskStatus.DEDUPING,
    TaskStatus.FETCHING_SOURCE,
    TaskStatus.SOURCE_READY,
    TaskStatus.ANALYZING_SOURCE,
    TaskStatus.SEARCHING_RELATED,
    TaskStatus.FETCHING_RELATED,
    TaskStatus.BUILDING_BRIEF,
    TaskStatus.BRIEF_READY,
    TaskStatus.GENERATING,
    TaskStatus.REVIEWING,
    TaskStatus.REVIEW_PASSED,
    TaskStatus.PUSHING_WECHAT_DRAFT,
    TaskStatus.NEEDS_MANUAL_SOURCE,
    TaskStatus.NEEDS_MANUAL_REVIEW,
    TaskStatus.NEEDS_REGENERATE,
}
