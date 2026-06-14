from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import get_session_factory
from app.services.feedback_queue_service import FeedbackQueueService
from app.services.feedback_sync_service import FeedbackSyncService
from app.services.worker_failure import handle_worker_failure
from app.services.worker_heartbeat import heartbeat_refresh_interval, keep_worker_heartbeat


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("feedback-worker")


def main() -> None:
    queue = FeedbackQueueService()
    heartbeat_interval = heartbeat_refresh_interval(queue.settings.worker_heartbeat_stale_seconds)
    recovered = queue.requeue_processing_jobs()
    if recovered:
        logger.info("recovered %s in-flight feedback job(s) back to the queue", recovered)
    queue.mark_worker_heartbeat()

    session_factory = get_session_factory()
    while True:
        queue.mark_worker_heartbeat()
        job = queue.pop_next()
        if job is None:
            queue.mark_worker_heartbeat()
            queue.idle_sleep()
            continue

        logger.info("syncing feedback for task %s day_offsets=%s", job.task_id, job.day_offsets)
        session = session_factory()
        outcome = "ok"
        try:
            with keep_worker_heartbeat(
                queue.mark_worker_heartbeat,
                current_task_id=job.task_id,
                interval_seconds=heartbeat_interval,
                logger=logger,
            ):
                FeedbackSyncService(session).run(
                    job.task_id,
                    day_offsets=job.day_offsets,
                    operator=job.operator,
                )
            logger.info("feedback sync completed for task %s", job.task_id)
        except Exception as exc:  # noqa: BLE001
            # Feedback is a post-publish side job: use the Task for bounded retry
            # bookkeeping but never overwrite the article's terminal status.
            outcome = handle_worker_failure(
                queue,
                session,
                job.task_id,
                exc,
                # failed_status is unused because update_status=False; the
                # feedback job must not overwrite the article's terminal status.
                failed_status="failed",
                max_retries=queue.settings.worker_max_retries,
                backoff_seconds=queue.settings.worker_retry_backoff_seconds,
                queue_ref=job,
                update_status=False,
            )
            logger.exception("feedback sync failed for task %s (outcome=%s)", job.task_id, outcome)
        finally:
            session.close()
            if outcome != "retried":
                queue.acknowledge(job)
            queue.mark_worker_heartbeat()


if __name__ == "__main__":
    main()
