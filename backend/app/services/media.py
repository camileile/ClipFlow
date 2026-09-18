from collections.abc import Mapping
from typing import Any

from pydantic import HttpUrl

from app.schemas import MediaInfo
from app.services.platforms import MediaPlatform, detect_platform
from app.services.tiktok import analyze_tiktok, extract_tiktok_info
from app.services.youtube import analyze_youtube, extract_youtube_info


def analyze_media(url: HttpUrl | str) -> tuple[MediaPlatform, MediaInfo]:
    requested_url = str(url)
    platform = detect_platform(requested_url)
    if platform == "youtube":
        return platform, analyze_youtube(requested_url)
    return platform, analyze_tiktok(requested_url)


def extract_media_info(
    url: HttpUrl | str,
) -> tuple[MediaPlatform, Mapping[str, Any]]:
    requested_url = str(url)
    platform = detect_platform(requested_url)
    if platform == "youtube":
        return platform, extract_youtube_info(requested_url)
    return platform, extract_tiktok_info(requested_url)
