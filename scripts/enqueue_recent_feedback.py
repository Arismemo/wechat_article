from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import get_session_factory
from app.repositories.wechat_draft_repository import WechatDraftRepository
from app.services.feedback_sync_service import FeedbackSyncService
from app.settings import get_settings


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("enqueue-recent-feedback")


def _parse_day_offsets(value: str) -> list[int]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    result: list[int] = []
    for part in parts:
        try:
            parsed = int(part)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid day offset {part!r}: must be an integer.") from exc
        if parsed < 0:
            raise argparse.ArgumentTypeError(f"Invalid day offset {parsed}: must be >= 0.")
        result.append(parsed)
    if not result:
        raise argparse.ArgumentTypeError("day-offsets must contain at least one value.")
    return result


def main() -> None:
    settings = get_settings()

    default_day_offsets_raw = settings.feedback_sync_day_offsets
    default_day_offsets = [
        int(part.strip())
        for part in default_day_offsets_raw.split(",")
        if part.strip() and int(part.strip()) >= 0
    ]

    parser = argparse.ArgumentParser(
        description="Enqueue feedback-sync jobs for recently-published tasks.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=settings.feedback_sync_recent_limit,
        help=f"Max number of tasks to enqueue (default: {settings.feedback_sync_recent_limit}).",
    )
    parser.add_argument(
        "--day-offsets",
        type=_parse_day_offsets,
        default=default_day_offsets,
        metavar="1,3,7",
        help=f"Comma-separated T+n day offsets to sync (default: {default_day_offsets_raw}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Resolve and print candidate tasks WITHOUT enqueuing anything. "
            "No Redis writes, no side effects. Exit 0."
        ),
    )
    args = parser.parse_args()

    limit: int = max(args.limit, 1)
    day_offsets: list[int] = sorted(set(args.day_offsets))
    dry_run: bool = args.dry_run

    if dry_run:
        session_factory = get_session_factory()
        session = session_factory()
        try:
            drafts = WechatDraftRepository(session).list_recent_successful(limit=max(limit * 5, limit))
            seen: set[str] = set()
            candidates: list[str] = []
            for draft in drafts:
                if draft.task_id in seen:
                    continue
                seen.add(draft.task_id)
                candidates.append(draft.task_id)
                if len(candidates) >= limit:
                    break
            print(f"[dry-run] Would enqueue {len(candidates)} task(s) with day_offsets={day_offsets}:")
            for task_id in candidates:
                print(f"  {task_id}")
        finally:
            session.close()
        sys.exit(0)

    session_factory = get_session_factory()
    session = session_factory()
    try:
        result = FeedbackSyncService(session).enqueue_recent(
            limit=limit,
            day_offsets=day_offsets,
            operator="cron:enqueue-recent-feedback",
        )
        logger.info(
            "enqueue_recent completed: requested=%s enqueued=%s queue_depth=%s day_offsets=%s",
            result.requested_count,
            result.enqueued_count,
            result.queue_depth,
            result.day_offsets,
        )
    except ValueError as exc:
        logger.error("enqueue_recent failed: %s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
