from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import get_session_factory
from app.services.phase2_pipeline_service import Phase2PipelineService
from app.services.phase2_queue_service import Phase2QueueService


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("phase2-worker")


def main() -> None:
    queue = Phase2QueueService()
    recovered = queue.requeue_processing_jobs()
    if recovered:
        logger.info("recovered %s in-flight phase2 job(s) back to the queue", recovered)
    queue.mark_worker_heartbeat()

    session_factory = get_session_factory()
    while True:
        queue.mark_worker_heartbeat()
        task_id = queue.pop_next()
        if not task_id:
            queue.mark_worker_heartbeat()
            queue.idle_sleep()
            continue

        queue.mark_worker_heartbeat(task_id)
        logger.info("processing task %s", task_id)
        session = session_factory()
        try:
            Phase2PipelineService(session).run(task_id)
            logger.info("task %s completed", task_id)
        except Exception:  # noqa: BLE001
            logger.exception("task %s failed", task_id)
        finally:
            session.close()
            queue.acknowledge(task_id)
            queue.mark_worker_heartbeat()


if __name__ == "__main__":
    main()
