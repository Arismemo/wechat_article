from fastapi import APIRouter

from app.api.admin_factors import router as admin_factors_router
from app.api.admin_monitor import router as admin_monitor_router
from app.api.admin_settings import router as admin_settings_router
from app.api.feedback import router as feedback_router
from app.api.ingest import router as ingest_router
from app.api.pipeline import router as pipeline_router
from app.api.tasks import router as tasks_router
from app.api.topic_admin import router as topic_admin_router

api_router = APIRouter()
api_router.include_router(ingest_router, tags=["ingest"])
api_router.include_router(tasks_router, tags=["tasks"])
api_router.include_router(feedback_router, tags=["feedback"])
api_router.include_router(admin_factors_router, tags=["admin-factors"])
api_router.include_router(admin_monitor_router, tags=["admin-monitor"])
api_router.include_router(admin_settings_router, tags=["admin-settings"])
api_router.include_router(pipeline_router, tags=["admin-pipeline"])
api_router.include_router(topic_admin_router, tags=["admin-topics"])
