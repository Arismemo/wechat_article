from __future__ import annotations

from time import sleep
from typing import Any, Optional

import httpx

from app.core.enums import FINAL_FAILURE_STATUSES
from app.models.task import Task

_RETRIABLE_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}
_TERMINAL_FAILURE_VALUES = {status.value for status in FINAL_FAILURE_STATUSES}
_MAX_ERROR_MESSAGE_CHARS = 1000
_UNSET = object()

# Fix 3: import Redis exceptions defensively so a missing redis package does not
# crash the module (e.g. in unit-test environments that mock it out).
try:
    from redis.exceptions import ConnectionError as _RedisConnectionError
    from redis.exceptions import TimeoutError as _RedisTimeoutError

    _REDIS_RETRIABLE: tuple[type, ...] = (_RedisConnectionError, _RedisTimeoutError)
except ImportError:  # pragma: no cover
    _REDIS_RETRIABLE = ()


class RetryableError(Exception):
    """Marker exception pipeline code can raise to force a worker retry."""


def is_retriable(exc: BaseException) -> bool:
    """Classify whether a worker failure is worth retrying.

    Retriable: explicit RetryableError markers, httpx timeouts/transport errors
    (covers ConnectError/ReadError/etc.), provider HTTP errors whose status code
    is transient, and transient Redis connection/timeout errors.  Everything
    else (parse/validation/programming errors) is non-retriable and goes
    straight to the dead-letter queue.
    """
    if isinstance(exc, RetryableError):
        return True
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if _REDIS_RETRIABLE and isinstance(exc, _REDIS_RETRIABLE):
        return True

    # Duck-typed HTTP-status check: if the exception carries an integer
    # status_code attribute, classify by that code regardless of whether the
    # typed import succeeded.  This must run BEFORE the generic LLMServiceError
    # branch because LLMProviderHTTPError is a subclass of LLMServiceError —
    # falling through to that branch would wrongly mark a 400 as retriable.
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code in _RETRIABLE_HTTP_STATUS

    # A bare LLMServiceError that is NOT an HTTP error means the LLM returned a
    # malformed / unparseable / schema-invalid response (covers LLMSchemaError,
    # which subclasses LLMServiceError). Re-sampling can fix it, so it's retriable.
    service_error = _llm_service_error_type()
    if service_error is not None and isinstance(exc, service_error):
        return True
    return False


def handle_worker_failure(
    queue: Any,
    session: Any,
    task_id: Optional[str],
    exc: BaseException,
    *,
    failed_status: str,
    max_retries: int,
    backoff_seconds: float,
    queue_ref: Any = _UNSET,
    update_status: bool = True,
) -> str:
    """Apply retry / dead-letter policy for a failed worker job.

    Returns one of "retried" or "dead". When a DB ``Task`` row backs the job we
    update retry bookkeeping and error fields; for queues without a Task row
    (``task_id is None``) we apply queue-level retry/DLQ only.

    ``queue_ref`` is the identifier the queue's ``requeue_for_retry`` /
    ``move_to_dead`` methods expect. It defaults to ``task_id`` (phase2/3/4 and
    topic_fetch pass the bare id), but feedback passes its ``FeedbackSyncQueueJob``
    because that queue stores a JSON payload rather than the bare id.

    ``update_status=False`` suppresses all writes to ``task.status``,
    ``task.error_code``, and ``task.error_message``.  Feedback uses this
    because its job is a post-publish side task — clobbering the article's
    terminal status or surfacing a misleading error would be wrong — while
    still getting a *bounded* retry via the Task's retry_count.
    """
    # Fix 2: discard any uncommitted dirty objects left by the failed pipeline
    # before we load the Task so we get a clean view and commit only our
    # bookkeeping writes.
    session.rollback()

    if queue_ref is _UNSET:
        queue_ref = task_id

    error_code = _error_code(exc)
    error_message = _truncate(str(exc))

    task = session.get(Task, task_id) if task_id is not None else None
    if task_id is not None and task is None:
        queue.move_to_dead(queue_ref, "task-not-found")
        return "dead"

    retriable = is_retriable(exc)
    retry_count = task.retry_count if task is not None else 0

    if retriable and retry_count < max_retries:
        if task is not None:
            task.retry_count += 1
            if update_status:
                task.error_code = error_code
                task.error_message = error_message
            # NOTE: status is intentionally NOT reset here; the pipeline
            # re-enters from any status on the requeued run.
            session.commit()
        if backoff_seconds > 0:
            sleep(backoff_seconds)
        queue.requeue_for_retry(queue_ref)
        return "retried"

    if task is not None:
        # Fix 1: only stamp error fields (and status) when update_status=True.
        # With update_status=False (feedback worker) the Task is the published
        # article's record — writing error fields would surface a misleading
        # "error" in the admin UI against a successfully-published article.
        if update_status:
            task.error_code = error_code
            task.error_message = error_message
            if task.status not in _TERMINAL_FAILURE_VALUES:
                task.status = failed_status
        session.commit()
    queue.move_to_dead(queue_ref, reason=error_code)
    return "dead"


def _truncate(message: str) -> str:
    if len(message) <= _MAX_ERROR_MESSAGE_CHARS:
        return message
    return message[:_MAX_ERROR_MESSAGE_CHARS]


def _error_code(exc: BaseException) -> str:
    provider_http_error = _llm_provider_http_error_type()
    if provider_http_error is not None and isinstance(exc, provider_http_error):
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            return f"llm_http_{status_code}"
    return type(exc).__name__


def _llm_provider_http_error_type() -> Optional[type]:
    # Imported defensively so relocating LLMProviderHTTPError does not crash the
    # classifier — non-import failures simply fall back to "not a provider error".
    try:
        from app.services.llm_service import LLMProviderHTTPError
    except Exception:  # noqa: BLE001
        return None
    return LLMProviderHTTPError


def _llm_service_error_type() -> Optional[type]:
    # Imported defensively (mirrors _llm_provider_http_error_type) to avoid import
    # cycles and to stay robust if the exception class is relocated.
    try:
        from app.services.llm_service import LLMServiceError
    except Exception:  # noqa: BLE001
        return None
    return LLMServiceError
