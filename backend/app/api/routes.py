import asyncio
import json
from collections.abc import AsyncIterator
from typing import Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask

from app.config import DOWNLOAD_JOB_KEEPALIVE_SECONDS
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DownloadJobCreated,
    DownloadJobState,
    DownloadRequest,
    HealthResponse,
)
from app.services.download import (
    DownloadLimitExceededError,
    DownloadProcessingError,
    FFmpegUnavailableError,
    IncompatibleMediaError,
    QualityUnavailableError,
    UnsupportedBitrateError,
    download_youtube_mp3,
    download_youtube_mp4,
)
from app.services.jobs import (
    JobFileAlreadyClaimedError,
    JobManager,
    JobNotFoundError,
    JobNotReadyError,
    JobStatus,
    job_manager,
    start_download_job,
)
from app.services.youtube import (
    InvalidYouTubeUrlError,
    PrivateVideoError,
    RemovedVideoError,
    UnexpectedYouTubeError,
    UnsupportedPlatformError,
    VideoUnavailableError,
    YouTubeServiceError,
    analyze_youtube,
)

router = APIRouter()


def _job_event_name(state: DownloadJobState) -> str:
    if state.status == JobStatus.READY:
        return "ready"
    if state.status == JobStatus.FAILED:
        return "error"
    if state.status == JobStatus.CANCELLED:
        return "cancelled"
    return "progress"


def _serialize_job_event(state: DownloadJobState) -> str:
    payload = json.dumps(
        state.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"event: {_job_event_name(state)}\ndata: {payload}\n\n"


async def job_event_stream(
    job_id: UUID,
    *,
    manager: JobManager = job_manager,
    keepalive_seconds: float = DOWNLOAD_JOB_KEEPALIVE_SECONDS,
) -> AsyncIterator[str]:
    state, version = manager.get_versioned(job_id)
    yield _serialize_job_event(state)
    if state.status in {JobStatus.READY, JobStatus.FAILED, JobStatus.CANCELLED}:
        return

    while True:
        changed = await asyncio.to_thread(
            manager.wait_for_change,
            job_id,
            version,
            keepalive_seconds,
        )
        if changed is None:
            yield ": keepalive\n\n"
            continue

        state, version = changed
        yield _serialize_job_event(state)
        if state.status in {JobStatus.READY, JobStatus.FAILED, JobStatus.CANCELLED}:
            return


def _raise_youtube_http_error(
    error: Exception,
    operation: Literal["analysis", "download"],
) -> NoReturn:
    passive_action = "analisado" if operation == "analysis" else "baixado"
    operation_name = "a análise" if operation == "analysis" else "o download"
    action = "analisar" if operation == "analysis" else "baixar"

    if isinstance(error, InvalidYouTubeUrlError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Informe uma URL válida de um vídeo do YouTube.",
        ) from error
    if isinstance(error, UnsupportedPlatformError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta plataforma ainda não é suportada. Use um link do YouTube.",
        ) from error
    if isinstance(error, PrivateVideoError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Este vídeo é privado e não pode ser {passive_action}.",
        ) from error
    if isinstance(error, RemovedVideoError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Este vídeo foi removido e não está mais disponível.",
        ) from error
    if isinstance(error, VideoUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Este vídeo não existe ou não está disponível.",
        ) from error
    if isinstance(error, YouTubeServiceError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"O YouTube não pôde concluir {operation_name} agora. Tente novamente mais tarde.",
        ) from error
    if isinstance(error, UnexpectedYouTubeError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Não foi possível {action} o vídeo devido a um erro inesperado.",
        ) from error


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="clipflow-api")


@router.post("/api/analyze", response_model=AnalyzeResponse, tags=["media"])
def analyze_media(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        media = analyze_youtube(payload.url)
    except (
        InvalidYouTubeUrlError,
        PrivateVideoError,
        RemovedVideoError,
        UnexpectedYouTubeError,
        UnsupportedPlatformError,
        VideoUnavailableError,
        YouTubeServiceError,
    ) as error:
        _raise_youtube_http_error(error, "analysis")

    return AnalyzeResponse(
        success=True,
        platform="youtube",
        media=media,
    )


@router.post(
    "/api/download/jobs",
    response_model=DownloadJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["media"],
)
async def create_download_job(payload: DownloadRequest) -> DownloadJobCreated:
    state = start_download_job(payload)
    return DownloadJobCreated(job_id=state.job_id, status="queued")


@router.get(
    "/api/download/jobs/{job_id}/events",
    response_class=StreamingResponse,
    tags=["media"],
)
async def download_job_events(job_id: UUID) -> StreamingResponse:
    try:
        job_manager.get(job_id)
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download job not found.",
        ) from error

    return StreamingResponse(
        job_event_stream(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/api/download/jobs/{job_id}/file",
    response_class=FileResponse,
    responses={200: {"content": {"video/mp4": {}, "audio/mpeg": {}}}},
    tags=["media"],
)
def download_job_file(job_id: UUID) -> Response:
    try:
        job_file = job_manager.claim_file(job_id)
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download job not found.",
        ) from error
    except (JobNotReadyError, JobFileAlreadyClaimedError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The download file is not ready.",
        ) from error

    return FileResponse(
        path=job_file.path,
        filename=job_file.filename,
        media_type=job_file.mime_type,
        background=BackgroundTask(job_manager.complete_file_delivery, job_id),
    )


@router.delete(
    "/api/download/jobs/{job_id}",
    response_model=DownloadJobState,
    tags=["media"],
)
def cancel_download_job(job_id: UUID) -> DownloadJobState:
    try:
        return job_manager.cancel(job_id)
    except JobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download job not found.",
        ) from error


@router.post(
    "/api/download",
    response_class=FileResponse,
    responses={200: {"content": {"video/mp4": {}, "audio/mpeg": {}}}},
    tags=["media"],
)
def download_media(payload: DownloadRequest) -> Response:
    try:
        if payload.format == "mp4":
            artifact = download_youtube_mp4(payload.url, payload.quality)
            media_type = "video/mp4"
        else:
            artifact = download_youtube_mp3(payload.url, payload.audio_quality)
            media_type = "audio/mpeg"
    except QualityUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A qualidade selecionada não está disponível para este vídeo.",
        ) from error
    except DownloadLimitExceededError as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Este vídeo excede o limite atual de download do ClipFlow.",
        ) from error
    except FFmpegUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "O FFmpeg é necessário para criar este arquivo, "
                "mas não está disponível no servidor."
            ),
        ) from error
    except UnsupportedBitrateError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O bitrate selecionado não é suportado.",
        ) from error
    except IncompatibleMediaError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Não foi possível encontrar áudio compatível para este vídeo."
                if payload.format == "mp3"
                else "Não foi possível criar um MP4 compatível nesta qualidade."
            ),
        ) from error
    except DownloadProcessingError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "O arquivo MP3 não pôde ser convertido. Tente novamente."
                if payload.format == "mp3"
                else "O arquivo MP4 não pôde ser preparado. Tente outra qualidade."
            ),
        ) from error
    except (
        InvalidYouTubeUrlError,
        PrivateVideoError,
        RemovedVideoError,
        UnexpectedYouTubeError,
        UnsupportedPlatformError,
        VideoUnavailableError,
        YouTubeServiceError,
    ) as error:
        _raise_youtube_http_error(error, "download")

    return FileResponse(
        path=artifact.path,
        filename=artifact.filename,
        media_type=media_type,
        background=BackgroundTask(artifact.cleanup),
    )
