from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import get_session_factory
from app.services.phase4_pipeline_service import Phase4PipelineService
from app.services.phase4_queue_service import Phase4QueueService
from app.services.worker_heartbeat import heartbeat_refresh_interval, keep_worker_heartbeat


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("phase4-worker")


def main() -> None:
    queue = Phase4QueueService()
    heartbeat_interval = heartbeat_refresh_interval(queue.settings.worker_heartbeat_stale_seconds)
    recovered = queue.requeue_processing_jobs()
    if recovered:
        logger.info("recovered %s in-flight phase4 job(s) back to the queue", recovered)
    queue.mark_worker_heartbeat()

    session_factory = get_session_factory()
    while True:
        queue.mark_worker_heartbeat()
        task_id = queue.pop_next()
        if not task_id:
            queue.mark_worker_heartbeat()
            queue.idle_sleep()
            continue

        logger.info("processing task %s", task_id)
        session = session_factory()
        try:
            with keep_worker_heartbeat(
                queue.mark_worker_heartbeat,
                current_task_id=task_id,
                interval_seconds=heartbeat_interval,
                logger=logger,
            ):
                Phase4PipelineService(session).run(task_id)
            logger.info("task %s completed", task_id)
        except Exception:  # noqa: BLE001
            logger.exception("task %s failed", task_id)
        finally:
            session.close()
            queue.acknowledge(task_id)
            queue.mark_worker_heartbeat()


if __name__ == "__main__":
    main()
