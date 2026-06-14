from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.admin_ui import render_admin_page
from app.core.security import verify_admin_basic_auth
from app.db.session import get_db_session
from app.repositories.editorial_review_repository import EditorialReviewRepository
from app.templating import render_template


router = APIRouter()


@router.get(
    "/admin/editorial/{task_id}",
    response_class=HTMLResponse,
    tags=["admin"],
    dependencies=[Depends(verify_admin_basic_auth)],
)
def admin_editorial_page(task_id: str, session: Session = Depends(get_db_session)) -> str:
    review = EditorialReviewRepository(session).get_latest_by_task_id(task_id)
    html = render_template(
        "admin/editorial.html",
        task_id=task_id,
        review=review,
    )
    return render_admin_page(html, "editorial")
