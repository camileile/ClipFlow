import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import DOWNLOAD_JOB_CLEANUP_INTERVAL_SECONDS, Settings, settings
from app.observability import ProductionMiddleware, configure_logging
from app.services.jobs import job_manager
from app.services.rate_limit import InMemoryRateLimiter
from app.services.temporary import cleanup_orphan_temp_directories, ensure_temp_root


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        ensure_temp_root()
        cleanup_orphan_temp_directories()
    except OSError:
        logger.exception("Temporary storage is not ready at startup")
    job_manager.set_accepting_jobs(True)

    async def cleanup_expired_jobs() -> None:
        while True:
            await asyncio.sleep(DOWNLOAD_JOB_CLEANUP_INTERVAL_SECONDS)
            await asyncio.to_thread(job_manager.cleanup_expired)

    cleanup_task = asyncio.create_task(cleanup_expired_jobs())
    try:
        yield
    finally:
        job_manager.set_accepting_jobs(False)
        job_manager.clear()
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


def create_app(app_settings: Settings = settings) -> FastAPI:
    configure_logging(app_settings.log_level)
    application = FastAPI(
        title="ClipFlow API",
        description="Multi-platform job-based MP4/MP3 download API for ClipFlow.",
        version=app_settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if not app_settings.production else None,
        openapi_url="/openapi.json" if not app_settings.production else None,
        redoc_url=None,
    )
    limiter = InMemoryRateLimiter()
    application.state.settings = app_settings
    application.state.rate_limiter = limiter

    application.add_middleware(
        ProductionMiddleware,
        settings=app_settings,
        limiter=limiter,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["Content-Disposition", "X-Request-ID", "Retry-After"],
    )
    application.include_router(router)
    return application


app = create_app()
