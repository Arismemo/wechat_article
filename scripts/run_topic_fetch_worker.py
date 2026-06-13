from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import get_session_factory
from app.services.topic_fetch_queue_service import TopicFetchQueueService
from app.services.topic_intelligence_service import TopicIntelligenceService
from app.services.worker_failure import handle_worker_failure
from app.services.worker_heartbeat import heartbeat_refresh_interval, keep_worker_heartbeat


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("topic-fetch-worker")


def main() -> None:
    queue = TopicFetchQueueService()
    heartbeat_interval = heartbeat_refresh_interval(queue.settings.worker_heartbeat_stale_seconds)
    recovered = queue.requeue_processing_jobs()
    if recovered:
        logger.info("recovered %s in-flight topic fetch job(s) back to the queue", recovered)
    queue.mark_worker_heartbeat()

    session_factory = get_session_factory()
    while True:
        queue.mark_worker_heartbeat()
        source_id = queue.pop_next()
        if not source_id:
            queue.mark_worker_heartbeat()
            queue.idle_sleep()
            continue

        logger.info("running topic source %s", source_id)
        session = session_factory()
        outcome = "ok"
        try:
            with keep_worker_heartbeat(
                queue.mark_worker_heartbeat,
                current_task_id=source_id,
                interval_seconds=heartbeat_interval,
                logger=logger,
            ):
                TopicIntelligenceService(session).run_source(source_id, trigger_type="queue-worker")
            logger.info("topic source %s completed", source_id)
        except Exception as exc:  # noqa: BLE001
            # Topic fetch keys on a TopicSource id, not a Task row, so there is no
            # per-job retry counter. Apply queue-level DLQ only (max_retries=0)
            # so a persistently-failing source can't loop forever in the queue.
            outcome = handle_worker_failure(
                queue,
                session,
                None,
                exc,
                failed_status="failed",
                max_retries=0,
                backoff_seconds=queue.settings.worker_retry_backoff_seconds,
                queue_ref=source_id,
            )
            logger.exception("topic source %s failed (outcome=%s)", source_id, outcome)
        finally:
            session.close()
            if outcome != "retried":
                queue.acknowledge(source_id)
            queue.mark_worker_heartbeat()


if __name__ == "__main__":
    main()
