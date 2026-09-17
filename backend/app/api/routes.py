from typing import Literal, NoReturn

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.schemas import AnalyzeRequest, AnalyzeResponse, DownloadRequest, HealthResponse
from app.services.download import (
    DownloadLimitExceededError,
    DownloadProcessingError,
    FFmpegUnavailableError,
    IncompatibleMediaError,
    QualityUnavailableError,
    download_youtube_mp4,
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
    "/api/download",
    response_class=FileResponse,
    responses={200: {"content": {"video/mp4": {}}}},
    tags=["media"],
)
def download_media(payload: DownloadRequest) -> Response:
    try:
        artifact = download_youtube_mp4(payload.url, payload.quality)
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
            detail="O FFmpeg é necessário para este download, mas não está disponível no servidor.",
        ) from error
    except IncompatibleMediaError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Não foi possível criar um MP4 compatível nesta qualidade.",
        ) from error
    except DownloadProcessingError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="O arquivo MP4 não pôde ser preparado. Tente outra qualidade.",
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
        media_type="video/mp4",
        background=BackgroundTask(artifact.cleanup),
    )
