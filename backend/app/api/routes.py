import asyncio
import json
from collections.abc import AsyncIterator
from typing import Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask

from app.config import DOWNLOAD_JOB_KEEPALIVE_SECONDS, JOB_CAPACITY_RETRY_AFTER_SECONDS
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DownloadJobCreated,
    DownloadJobState,
    DownloadRequest,
    HealthResponse,
    ReadinessResponse,
)
from app.services.download import (
    AudioUnavailableError,
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
    ClientJobCapacityError,
    JobCapacityError,
    JobManager,
    JobNotFoundError,
    JobNotReadyError,
    JobStatus,
    JobsShuttingDownError,
    job_manager,
    start_download_job,
)
from app.services.ffmpeg import detect_media_tools
from app.services.instagram import (
    InstagramAuthenticationRequiredError,
    InstagramCarouselError,
    InstagramMediaError,
    InstagramNoVideoError,
    InstagramRateLimitedError,
    InstagramServiceError,
)
from app.services.media import analyze_media as analyze_media_url
from app.services.temporary import ensure_temp_root
from app.services.twitter import (
    TwitterAuthenticationRequiredError,
    TwitterMediaError,
    TwitterMultipleMediaError,
    TwitterNoVideoError,
    TwitterRateLimitedError,
    TwitterServiceError,
)
from app.services.youtube import (
    InvalidYouTubeUrlError,
    PrivateVideoError,
    RemovedVideoError,
    UnexpectedYouTubeError,
    UnsupportedPlatformError,
    VideoUnavailableError,
    YouTubeServiceError,
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


def _raise_media_http_error(
    error: Exception,
    operation: Literal["analysis", "download"],
) -> NoReturn:
    passive_action = "analisado" if operation == "analysis" else "baixado"
    operation_name = "a análise" if operation == "analysis" else "o download"
    action = "analisar" if operation == "analysis" else "baixar"

    if isinstance(error, InvalidYouTubeUrlError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Informe uma URL válida do YouTube, TikTok, Instagram ou X/Twitter.",
        ) from error
    if isinstance(error, UnsupportedPlatformError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta plataforma ainda não é suportada. Use YouTube, TikTok, Instagram ou X/Twitter.",
        ) from error
    if isinstance(error, InstagramNoVideoError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Este post do Instagram não contém um vídeo compatível.",
        ) from error
    if isinstance(error, InstagramCarouselError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Carrosséis do Instagram ainda não são suportados.",
        ) from error
    if isinstance(error, InstagramAuthenticationRequiredError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta mídia do Instagram é privada ou exige login.",
        ) from error
    if isinstance(error, InstagramRateLimitedError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="O Instagram bloqueou temporariamente a solicitação. Tente novamente mais tarde.",
        ) from error
    if isinstance(error, InstagramServiceError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"O Instagram não pôde concluir {operation_name} agora. Tente novamente mais tarde.",
        ) from error
    if isinstance(error, TwitterNoVideoError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Este post do X/Twitter não contém um vídeo compatível.",
        ) from error
    if isinstance(error, TwitterMultipleMediaError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Posts do X/Twitter com múltiplos vídeos ainda não são suportados.",
        ) from error
    if isinstance(error, TwitterAuthenticationRequiredError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este post do X/Twitter é protegido ou exige login.",
        ) from error
    if isinstance(error, TwitterRateLimitedError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="O X/Twitter rejeitou temporariamente a solicitação. Tente novamente mais tarde.",
        ) from error
    if isinstance(error, TwitterServiceError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"O X/Twitter não pôde concluir {operation_name} agora. Tente novamente mais tarde.",
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
            detail=f"A plataforma não pôde concluir {operation_name} agora. Tente novamente mais tarde.",
        ) from error
    if isinstance(error, UnexpectedYouTubeError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Não foi possível {action} o vídeo devido a um erro inesperado.",
        ) from error


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="clipflow-api")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
    tags=["system"],
)
def readiness_check(request: Request, response: Response) -> ReadinessResponse:
    app_settings = request.app.state.settings
    tools = detect_media_tools()
    temp_available = True
    try:
        ensure_temp_root(app_settings.temp_dir)
    except OSError:
        temp_available = False
    checks = {
        "ffmpeg": tools.ffmpeg is not None,
        "ffprobe": tools.ffprobe is not None,
        "temp": temp_available,
    }
    ready = all(checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        service="clipflow-api",
        version=app_settings.app_version,
        checks=checks,
    )


@router.post("/api/analyze", response_model=AnalyzeResponse, tags=["media"])
def analyze_media_endpoint(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        platform, media = analyze_media_url(payload.url)
    except (
        InvalidYouTubeUrlError,
        InstagramMediaError,
        PrivateVideoError,
        RemovedVideoError,
        UnexpectedYouTubeError,
        UnsupportedPlatformError,
        VideoUnavailableError,
        YouTubeServiceError,
        TwitterMediaError,
    ) as error:
        _raise_media_http_error(error, "analysis")

    return AnalyzeResponse(
        success=True,
        platform=platform,
        media=media,
    )


@router.post(
    "/api/download/jobs",
    response_model=DownloadJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["media"],
)
async def create_download_job(
    payload: DownloadRequest,
    request: Request,
) -> DownloadJobCreated:
    try:
        state = start_download_job(
            payload,
            client_id=getattr(request.state, "client_id", None),
        )
    except ClientJobCapacityError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Você já possui o máximo de downloads ativos permitido.",
            headers={"Retry-After": str(JOB_CAPACITY_RETRY_AFTER_SECONDS)},
        ) from error
    except (JobCapacityError, JobsShuttingDownError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="O servidor está ocupado. Tente novamente em instantes.",
            headers={"Retry-After": str(JOB_CAPACITY_RETRY_AFTER_SECONDS)},
        ) from error
    except (
        InvalidYouTubeUrlError,
        InstagramMediaError,
        TwitterMediaError,
        UnsupportedPlatformError,
    ) as error:
        _raise_media_http_error(error, "download")
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
    except AudioUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Esta mídia não contém uma faixa de áudio.",
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
        InstagramMediaError,
        PrivateVideoError,
        RemovedVideoError,
        UnexpectedYouTubeError,
        UnsupportedPlatformError,
        VideoUnavailableError,
        YouTubeServiceError,
        TwitterMediaError,
    ) as error:
        _raise_media_http_error(error, "download")

    return FileResponse(
        path=artifact.path,
        filename=artifact.filename,
        media_type=media_type,
        background=BackgroundTask(artifact.cleanup),
    )
