from fastapi import APIRouter

from app.api.feedback import router as feedback_router
from app.api.ingest import router as ingest_router
from app.api.tasks import router as tasks_router

api_router = APIRouter()
api_router.include_router(ingest_router, tags=["ingest"])
api_router.include_router(tasks_router, tags=["tasks"])
api_router.include_router(feedback_router, tags=["feedback"])
