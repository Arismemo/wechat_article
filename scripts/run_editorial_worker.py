"""Editorial board worker — MUST run as a SINGLE instance.

The GLM concurrency cap (≤3 simultaneous calls) is enforced by
EditorialLLMClient's BoundedSemaphore, which is a per-process in-memory
lock.  Running multiple instances of this worker defeats that cap and will
overwhelm the GLM-5.2 dedicated channel.  Use a process supervisor (e.g.
systemd, supervisor) configured to allow exactly ONE replica at a time.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.enums import TaskStatus
from app.db.session import get_session_factory
from app.services.editorial_board_service import EditorialBoardService
from app.services.editorial_llm_client import EditorialLLMClient
from app.services.editorial_queue_service import EditorialQueueService
from app.services.editorial_verdict_executor import EditorialVerdictExecutor
from app.services.worker_failure import handle_worker_failure
from app.services.worker_heartbeat import heartbeat_refresh_interval, keep_worker_heartbeat
from app.settings import get_settings


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("editorial-worker")


def main() -> None:
    settings = get_settings()

    # Fail fast on misconfiguration (editorial is opt-in, so the api_key stays
    # Optional in Settings; we validate it here only when the worker is actually
    # meant to run — avoids forcing the key on every deployment / test).
    if not settings.editorial_enabled:
        logger.warning("EDITORIAL_ENABLED is false; editorial worker has nothing to do, exiting.")
        return
    if not settings.editorial_llm_api_key:
        raise SystemExit("EDITORIAL_LLM_API_KEY is required when EDITORIAL_ENABLED=true.")

    # Build the LLM client ONCE before the loop — the BoundedSemaphore lives
    # in this object for the lifetime of the process.
    client = EditorialLLMClient(
        api_base=settings.editorial_llm_api_base,
        api_key=settings.editorial_llm_api_key,
        model=settings.editorial_llm_model,
        max_concurrency=settings.editorial_llm_max_concurrency,
        timeout_seconds=settings.editorial_llm_timeout_seconds,
    )

    queue = EditorialQueueService()
    heartbeat_interval = heartbeat_refresh_interval(queue.settings.worker_heartbeat_stale_seconds)
    recovered = queue.requeue_processing_jobs()
    if recovered:
        logger.info("recovered %s in-flight editorial job(s) back to the queue", recovered)
    queue.mark_worker_heartbeat()

    session_factory = get_session_factory()
    while True:
        queue.mark_worker_heartbeat()
        task_id = queue.pop_next()
        if not task_id:
            queue.mark_worker_heartbeat()
            queue.idle_sleep()
            continue

        logger.info("processing editorial task %s", task_id)
        session = session_factory()
        outcome = "ok"
        try:
            with keep_worker_heartbeat(
                queue.mark_worker_heartbeat,
                current_task_id=task_id,
                interval_seconds=heartbeat_interval,
                logger=logger,
            ):
                review = EditorialBoardService(session, client).review(task_id)
                # Act on the verdict: transition the task and, on a clean pass,
                # push the WeChat draft. Kept inside the same try/except so a
                # push/transition failure flows through handle_worker_failure
                # (retry / DLQ) just like a debate failure.
                verdict_outcome = EditorialVerdictExecutor(session).execute(review)
            logger.info("editorial task %s completed (verdict=%s)", task_id, verdict_outcome)
        except Exception as exc:  # noqa: BLE001
            outcome = handle_worker_failure(
                queue,
                session,
                task_id,
                exc,
                failed_status=TaskStatus.NEEDS_MANUAL_REVIEW.value,
                max_retries=queue.settings.worker_max_retries,
                backoff_seconds=queue.settings.worker_retry_backoff_seconds,
                queue_ref=task_id,
            )
            logger.exception("editorial task %s failed (outcome=%s)", task_id, outcome)
        finally:
            session.close()
            if outcome != "retried":
                queue.acknowledge(task_id)
            queue.mark_worker_heartbeat()


if __name__ == "__main__":
    main()
