from fastapi import APIRouter, HTTPException, status

from app.schemas import AnalyzeRequest, AnalyzeResponse, HealthResponse
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


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="clipflow-api")


@router.post("/api/analyze", response_model=AnalyzeResponse, tags=["media"])
def analyze_media(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        media = analyze_youtube(payload.url)
    except InvalidYouTubeUrlError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Informe uma URL válida de um vídeo do YouTube.",
        ) from error
    except UnsupportedPlatformError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta plataforma ainda não é suportada. Use um link do YouTube.",
        ) from error
    except PrivateVideoError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este vídeo é privado e não pode ser analisado.",
        ) from error
    except RemovedVideoError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Este vídeo foi removido e não está mais disponível.",
        ) from error
    except VideoUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Este vídeo não existe ou não está disponível.",
        ) from error
    except YouTubeServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="O YouTube não pôde concluir a análise agora. Tente novamente mais tarde.",
        ) from error
    except UnexpectedYouTubeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível analisar o vídeo devido a um erro inesperado.",
        ) from error

    return AnalyzeResponse(
        success=True,
        platform="youtube",
        media=media,
    )
