from __future__ import annotations

import logging

from app.db.session import get_session_factory
from app.services.phase3_pipeline_service import Phase3PipelineService
from app.services.phase3_queue_service import Phase3QueueService


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("phase3-worker")


def main() -> None:
    queue = Phase3QueueService()
    recovered = queue.requeue_processing_jobs()
    if recovered:
        logger.info("recovered %s in-flight phase3 job(s) back to the queue", recovered)

    session_factory = get_session_factory()
    while True:
        task_id = queue.pop_next()
        if not task_id:
            queue.idle_sleep()
            continue

        logger.info("processing task %s", task_id)
        session = session_factory()
        try:
            Phase3PipelineService(session).run(task_id)
            logger.info("task %s completed", task_id)
        except Exception:  # noqa: BLE001
            logger.exception("task %s failed", task_id)
        finally:
            session.close()
            queue.acknowledge(task_id)


if __name__ == "__main__":
    main()
