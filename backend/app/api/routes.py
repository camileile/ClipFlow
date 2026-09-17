from typing import Literal

from fastapi import APIRouter
from pydantic import HttpUrl

from app.schemas import AnalyzeRequest, AnalyzeResponse, HealthResponse

router = APIRouter()


def _identify_platform(url: HttpUrl) -> Literal["youtube", "unknown"]:
    hostname = (url.host or "").lower()

    if hostname == "youtu.be" or hostname == "youtube.com" or hostname.endswith(
        ".youtube.com"
    ):
        return "youtube"

    return "unknown"


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="clipflow-api")


@router.post("/api/analyze", response_model=AnalyzeResponse, tags=["media"])
def analyze_media(payload: AnalyzeRequest) -> AnalyzeResponse:
    platform = _identify_platform(payload.url)

    return AnalyzeResponse(
        success=True,
        platform=platform,
        title="Preview demonstrativo",
        author="Canal",
        duration=0,
        thumbnail=None,
    )

