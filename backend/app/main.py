import asyncio
from contextlib import asynccontextmanager, suppress
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import DOWNLOAD_JOB_CLEANUP_INTERVAL_SECONDS
from app.services.jobs import job_manager

LOCAL_FRONTEND_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async def cleanup_expired_jobs() -> None:
        while True:
            await asyncio.sleep(DOWNLOAD_JOB_CLEANUP_INTERVAL_SECONDS)
            await asyncio.to_thread(job_manager.cleanup_expired)

    cleanup_task = asyncio.create_task(cleanup_expired_jobs())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task

app = FastAPI(
    title="ClipFlow API",
    description="YouTube analysis and job-based MP4/MP3 download API for ClipFlow.",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)

app.include_router(router)
