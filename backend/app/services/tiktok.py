import logging
from collections.abc import Mapping
from typing import Any

from pydantic import HttpUrl
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.schemas import MediaInfo
from app.services.platforms import UnsupportedPlatformError, detect_platform
from app.services.youtube import (
    UnexpectedYouTubeError,
    YouTubeServiceError,
    YDL_OPTIONS,
    map_download_error,
    normalize_media_info,
)

logger = logging.getLogger(__name__)


def validate_tiktok_url(url: str) -> None:
    if detect_platform(url) != "tiktok":
        raise UnsupportedPlatformError


def extract_tiktok_info(url: HttpUrl | str) -> Mapping[str, Any]:
    requested_url = str(url)
    validate_tiktok_url(requested_url)
    logger.info("Starting TikTok metadata analysis")

    try:
        with YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(requested_url, download=False)
    except DownloadError as error:
        mapped_error = map_download_error(error)
        logger.warning(
            "TikTok metadata analysis failed: %s",
            mapped_error.__class__.__name__,
        )
        raise mapped_error from error
    except Exception as error:
        logger.exception("Unexpected TikTok metadata extractor failure")
        raise UnexpectedYouTubeError from error

    if not isinstance(info, Mapping):
        logger.error("TikTok extractor returned an invalid payload")
        raise YouTubeServiceError

    return info


def analyze_tiktok(url: HttpUrl | str) -> MediaInfo:
    requested_url = str(url)
    media = normalize_media_info(
        extract_tiktok_info(requested_url),
        requested_url,
        platform="tiktok",
    )
    logger.info("TikTok metadata analysis completed", extra={"media_id": media.id})
    return media
