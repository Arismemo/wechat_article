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
        try:
            with keep_worker_heartbeat(
                queue.mark_worker_heartbeat,
                current_task_id=source_id,
                interval_seconds=heartbeat_interval,
                logger=logger,
            ):
                TopicIntelligenceService(session).run_source(source_id, trigger_type="queue-worker")
            logger.info("topic source %s completed", source_id)
        except Exception:  # noqa: BLE001
            logger.exception("topic source %s failed", source_id)
        finally:
            session.close()
            queue.acknowledge(source_id)
            queue.mark_worker_heartbeat()


if __name__ == "__main__":
    main()
