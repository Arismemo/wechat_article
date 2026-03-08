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


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("feedback-worker")


def main() -> None:
    queue = FeedbackQueueService()
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

        queue.mark_worker_heartbeat(job.task_id)
        logger.info("syncing feedback for task %s day_offsets=%s", job.task_id, job.day_offsets)
        session = session_factory()
        try:
            FeedbackSyncService(session).run(
                job.task_id,
                day_offsets=job.day_offsets,
                operator=job.operator,
            )
            logger.info("feedback sync completed for task %s", job.task_id)
        except Exception:  # noqa: BLE001
            logger.exception("feedback sync failed for task %s", job.task_id)
        finally:
            session.close()
            queue.acknowledge(job)
            queue.mark_worker_heartbeat()


if __name__ == "__main__":
    main()
