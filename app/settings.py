from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_base_url: str = Field(alias="APP_BASE_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    timezone: str = Field(default="Asia/Shanghai", alias="TIMEZONE")

    api_bearer_token: str = Field(alias="API_BEARER_TOKEN")
    api_hmac_secret: Optional[str] = Field(default=None, alias="API_HMAC_SECRET")
    admin_username: Optional[str] = Field(default=None, alias="ADMIN_USERNAME")
    admin_password: Optional[str] = Field(default=None, alias="ADMIN_PASSWORD")

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")

    llm_provider: str = Field(alias="LLM_PROVIDER")
    llm_api_base: Optional[str] = Field(default=None, alias="LLM_API_BASE")
    llm_api_key: str = Field(alias="LLM_API_KEY")
    llm_model_analyze: str = Field(alias="LLM_MODEL_ANALYZE")
    llm_model_write: str = Field(alias="LLM_MODEL_WRITE")
    llm_model_review: str = Field(alias="LLM_MODEL_REVIEW")
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")
    llm_write_timeout_seconds: int = Field(default=180, alias="LLM_WRITE_TIMEOUT_SECONDS")
    llm_review_timeout_seconds: int = Field(default=90, alias="LLM_REVIEW_TIMEOUT_SECONDS")

    search_provider: str = Field(alias="SEARCH_PROVIDER")
    search_api_base: Optional[str] = Field(default=None, alias="SEARCH_API_BASE")
    search_api_key: Optional[str] = Field(default=None, alias="SEARCH_API_KEY")
    search_timeout_seconds: int = Field(default=30, alias="SEARCH_TIMEOUT_SECONDS")
    search_engine: str = Field(default="search_std", alias="SEARCH_ENGINE")

    fetch_http_timeout_seconds: int = Field(default=25, alias="FETCH_HTTP_TIMEOUT_SECONDS")
    fetch_browser_timeout_seconds: int = Field(default=45, alias="FETCH_BROWSER_TIMEOUT_SECONDS")
    fetch_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger"
        ),
        alias="FETCH_USER_AGENT",
    )
    max_source_excerpt_chars: int = Field(default=1200, alias="MAX_SOURCE_EXCERPT_CHARS")
    playwright_headless: bool = Field(default=True, alias="PLAYWRIGHT_HEADLESS")
    playwright_browser_channels: str = Field(default="chromium,chrome", alias="PLAYWRIGHT_BROWSER_CHANNELS")
    playwright_viewport_width: int = Field(default=430, alias="PLAYWRIGHT_VIEWPORT_WIDTH")
    playwright_viewport_height: int = Field(default=932, alias="PLAYWRIGHT_VIEWPORT_HEIGHT")

    wechat_exporter_base_url: Optional[str] = Field(default=None, alias="WECHAT_EXPORTER_BASE_URL")
    wechat_exporter_request_timeout_seconds: int = Field(default=30, alias="WECHAT_EXPORTER_REQUEST_TIMEOUT_SECONDS")

    wechat_app_id: str = Field(alias="WECHAT_APP_ID")
    wechat_app_secret: str = Field(alias="WECHAT_APP_SECRET")
    wechat_api_base: str = Field(default="https://api.weixin.qq.com/cgi-bin", alias="WECHAT_API_BASE")
    wechat_token_cache_key: str = Field(default="wechat:token", alias="WECHAT_TOKEN_CACHE_KEY")
    wechat_enable_draft_push: bool = Field(default=False, alias="WECHAT_ENABLE_DRAFT_PUSH")
    wechat_default_author: Optional[str] = Field(default=None, alias="WECHAT_DEFAULT_AUTHOR")
    wechat_default_digest_prefix: Optional[str] = Field(default=None, alias="WECHAT_DEFAULT_DIGEST_PREFIX")
    wechat_request_timeout_seconds: int = Field(default=30, alias="WECHAT_REQUEST_TIMEOUT_SECONDS")
    wechat_inline_image_max_bytes: int = Field(default=1_000_000, alias="WECHAT_INLINE_IMAGE_MAX_BYTES")
    ingest_shortcut_auto_enqueue_phase4: bool = Field(default=True, alias="INGEST_SHORTCUT_AUTO_ENQUEUE_PHASE4")
    phase2_include_source_images: bool = Field(default=True, alias="PHASE2_INCLUDE_SOURCE_IMAGES")
    phase2_max_inline_images: int = Field(default=3, alias="PHASE2_MAX_INLINE_IMAGES")

    phase2_queue_key: str = Field(default="phase2:queue", alias="PHASE2_QUEUE_KEY")
    phase2_processing_key: str = Field(default="phase2:processing", alias="PHASE2_PROCESSING_KEY")
    phase2_pending_set_key: str = Field(default="phase2:pending", alias="PHASE2_PENDING_SET_KEY")
    phase2_worker_poll_timeout_seconds: int = Field(default=5, alias="PHASE2_WORKER_POLL_TIMEOUT_SECONDS")
    phase2_worker_idle_sleep_seconds: int = Field(default=1, alias="PHASE2_WORKER_IDLE_SLEEP_SECONDS")

    phase3_search_per_query: int = Field(default=5, alias="PHASE3_SEARCH_PER_QUERY")
    phase3_related_top_k: int = Field(default=5, alias="PHASE3_RELATED_TOP_K")
    phase3_queue_key: str = Field(default="phase3:queue", alias="PHASE3_QUEUE_KEY")
    phase3_processing_key: str = Field(default="phase3:processing", alias="PHASE3_PROCESSING_KEY")
    phase3_pending_set_key: str = Field(default="phase3:pending", alias="PHASE3_PENDING_SET_KEY")
    phase3_worker_poll_timeout_seconds: int = Field(default=5, alias="PHASE3_WORKER_POLL_TIMEOUT_SECONDS")
    phase3_worker_idle_sleep_seconds: int = Field(default=1, alias="PHASE3_WORKER_IDLE_SLEEP_SECONDS")
    phase4_queue_key: str = Field(default="phase4:queue", alias="PHASE4_QUEUE_KEY")
    phase4_processing_key: str = Field(default="phase4:processing", alias="PHASE4_PROCESSING_KEY")
    phase4_pending_set_key: str = Field(default="phase4:pending", alias="PHASE4_PENDING_SET_KEY")
    phase4_worker_poll_timeout_seconds: int = Field(default=5, alias="PHASE4_WORKER_POLL_TIMEOUT_SECONDS")
    phase4_worker_idle_sleep_seconds: int = Field(default=1, alias="PHASE4_WORKER_IDLE_SLEEP_SECONDS")
    phase4_review_pass_score: float = Field(default=75, alias="PHASE4_REVIEW_PASS_SCORE")
    phase4_similarity_max: float = Field(default=0.45, alias="PHASE4_SIMILARITY_MAX")
    phase4_policy_risk_max: float = Field(default=0.35, alias="PHASE4_POLICY_RISK_MAX")
    phase4_factual_risk_max: float = Field(default=0.40, alias="PHASE4_FACTUAL_RISK_MAX")
    phase4_max_auto_revisions: int = Field(default=1, alias="PHASE4_MAX_AUTO_REVISIONS")
    phase4_auto_push_wechat_draft: bool = Field(default=False, alias="PHASE4_AUTO_PUSH_WECHAT_DRAFT")
    feedback_sync_provider: str = Field(default="disabled", alias="FEEDBACK_SYNC_PROVIDER")
    feedback_sync_http_url: Optional[str] = Field(default=None, alias="FEEDBACK_SYNC_HTTP_URL")
    feedback_sync_api_key: Optional[str] = Field(default=None, alias="FEEDBACK_SYNC_API_KEY")
    feedback_sync_timeout_seconds: int = Field(default=30, alias="FEEDBACK_SYNC_TIMEOUT_SECONDS")
    feedback_sync_day_offsets: str = Field(default="1,3,7", alias="FEEDBACK_SYNC_DAY_OFFSETS")
    feedback_sync_queue_key: str = Field(default="feedback:queue", alias="FEEDBACK_SYNC_QUEUE_KEY")
    feedback_sync_processing_key: str = Field(default="feedback:processing", alias="FEEDBACK_SYNC_PROCESSING_KEY")
    feedback_sync_pending_set_key: str = Field(default="feedback:pending", alias="FEEDBACK_SYNC_PENDING_SET_KEY")
    feedback_sync_worker_poll_timeout_seconds: int = Field(default=5, alias="FEEDBACK_SYNC_WORKER_POLL_TIMEOUT_SECONDS")
    feedback_sync_worker_idle_sleep_seconds: int = Field(default=1, alias="FEEDBACK_SYNC_WORKER_IDLE_SLEEP_SECONDS")
    feedback_sync_recent_limit: int = Field(default=20, alias="FEEDBACK_SYNC_RECENT_LIMIT")

    local_storage_root: Path = Field(default=Path("./data"), alias="LOCAL_STORAGE_ROOT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
