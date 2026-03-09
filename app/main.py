from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.admin_console import router as admin_console_router
from app.api.internal import router as internal_router
from app.api.router import api_router
from app.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="wechat_artical",
        version="1.1.1",
        docs_url="/docs" if settings.app_env != "prod" else None,
        redoc_url="/redoc" if settings.app_env != "prod" else None,
    )

    @app.get("/healthz", tags=["system"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(internal_router, prefix="/internal/v1", tags=["internal"])
    app.include_router(admin_router)
    app.include_router(admin_console_router)
    return app


app = create_app()
