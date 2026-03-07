from app.core.enums import TaskStatus


TASK_PROGRESS_MAP: dict[TaskStatus, int] = {
    TaskStatus.QUEUED: 5,
    TaskStatus.DEDUPING: 10,
    TaskStatus.FETCHING_SOURCE: 20,
    TaskStatus.SOURCE_READY: 30,
    TaskStatus.ANALYZING_SOURCE: 40,
    TaskStatus.SEARCHING_RELATED: 50,
    TaskStatus.FETCHING_RELATED: 60,
    TaskStatus.BUILDING_BRIEF: 70,
    TaskStatus.BRIEF_READY: 75,
    TaskStatus.GENERATING: 80,
    TaskStatus.REVIEWING: 90,
    TaskStatus.REVIEW_PASSED: 95,
    TaskStatus.PUSHING_WECHAT_DRAFT: 97,
    TaskStatus.DRAFT_SAVED: 100,
    TaskStatus.FETCH_FAILED: 100,
    TaskStatus.ANALYZE_FAILED: 100,
    TaskStatus.SEARCH_FAILED: 100,
    TaskStatus.BRIEF_FAILED: 100,
    TaskStatus.GENERATE_FAILED: 100,
    TaskStatus.REVIEW_FAILED: 100,
    TaskStatus.PUSH_FAILED: 100,
    TaskStatus.NEEDS_MANUAL_SOURCE: 100,
    TaskStatus.NEEDS_MANUAL_REVIEW: 100,
    TaskStatus.NEEDS_REGENERATE: 100,
}


def get_progress(status: TaskStatus) -> int:
    return TASK_PROGRESS_MAP.get(status, 0)
