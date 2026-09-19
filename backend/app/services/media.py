from collections.abc import Mapping
from typing import Any

from pydantic import HttpUrl

from app.schemas import MediaInfo
from app.services.instagram import analyze_instagram, extract_instagram_info
from app.services.platforms import MediaPlatform, detect_platform
from app.services.tiktok import analyze_tiktok, extract_tiktok_info
from app.services.twitter import analyze_twitter, extract_twitter_info
from app.services.youtube import analyze_youtube, extract_youtube_info


ANALYZERS = {
    "youtube": analyze_youtube,
    "tiktok": analyze_tiktok,
    "instagram": analyze_instagram,
    "twitter": analyze_twitter,
}

EXTRACTORS = {
    "youtube": extract_youtube_info,
    "tiktok": extract_tiktok_info,
    "instagram": extract_instagram_info,
    "twitter": extract_twitter_info,
}


def analyze_media(url: HttpUrl | str) -> tuple[MediaPlatform, MediaInfo]:
    requested_url = str(url)
    platform = detect_platform(requested_url)
    return platform, ANALYZERS[platform](requested_url)


def extract_media_info(
    url: HttpUrl | str,
) -> tuple[MediaPlatform, Mapping[str, Any]]:
    requested_url = str(url)
    platform = detect_platform(requested_url)
    return platform, EXTRACTORS[platform](requested_url)
