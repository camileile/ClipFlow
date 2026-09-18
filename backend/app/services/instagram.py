import base64
import json
import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlparse

from pydantic import HttpUrl
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.schemas import MediaInfo
from app.services.platforms import UnsupportedPlatformError, detect_platform
from app.services.youtube import (
    RemovedVideoError,
    UnexpectedYouTubeError,
    VideoUnavailableError,
    YDL_OPTIONS,
    normalize_media_info,
)

logger = logging.getLogger(__name__)


class InstagramMediaError(Exception):
    """Base exception for predictable Instagram failures."""


class InstagramNoVideoError(InstagramMediaError):
    pass


class InstagramAuthenticationRequiredError(InstagramMediaError):
    pass


class InstagramRateLimitedError(InstagramMediaError):
    pass


class InstagramCarouselError(InstagramMediaError):
    pass


class InstagramServiceError(InstagramMediaError):
    pass


def validate_instagram_url(url: str) -> None:
    if detect_platform(url) != "instagram":
        raise UnsupportedPlatformError

    path_parts = [part for part in urlparse(url).path.split("/") if part]
    if len(path_parts) < 2 or path_parts[0] not in {"p", "reel", "reels", "tv"}:
        raise InstagramNoVideoError


def map_instagram_download_error(error: DownloadError) -> Exception:
    message = str(error).lower()

    if any(
        marker in message
        for marker in (
            "login required",
            "log in",
            "login page",
            "requires authentication",
            "private",
        )
    ):
        return InstagramAuthenticationRequiredError()
    if any(
        marker in message
        for marker in (
            "rate-limit",
            "rate limit",
            "too many requests",
            "temporarily blocked",
            "challenge required",
            "checkpoint required",
        )
    ):
        return InstagramRateLimitedError()
    if any(marker in message for marker in ("no video", "does not contain a video")):
        return InstagramNoVideoError()
    if any(marker in message for marker in ("removed", "deleted", "not found")):
        return RemovedVideoError()
    if any(marker in message for marker in ("unavailable", "not available")):
        return VideoUnavailableError()
    return InstagramServiceError()


def _short_caption(value: object, limit: int = 160) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1].rstrip()}…"


def _is_video_format(raw_format: object) -> bool:
    if not isinstance(raw_format, Mapping):
        return False
    codec = raw_format.get("vcodec")
    if isinstance(codec, str):
        return codec.lower() != "none"
    return isinstance(raw_format.get("height"), (int, float))


def _duration_from_format_urls(raw_formats: list[object]) -> int | None:
    for item in raw_formats:
        if not isinstance(item, Mapping) or not isinstance(item.get("url"), str):
            continue
        encoded = parse_qs(urlparse(item["url"]).query).get("efg", [None])[0]
        if not encoded:
            continue
        try:
            padding = "=" * (-len(encoded) % 4)
            metadata = json.loads(base64.urlsafe_b64decode(encoded + padding))
            duration = metadata.get("duration_s")
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(duration, (int, float)) and not isinstance(duration, bool):
            if duration > 0:
                return int(duration)
    return None


def prepare_instagram_info(
    info: Mapping[str, Any],
    requested_url: str,
) -> Mapping[str, Any]:
    if info.get("_type") in {"playlist", "multi_video"}:
        raise InstagramCarouselError

    raw_formats = info.get("formats")
    if not isinstance(raw_formats, list) or not any(
        _is_video_format(item) for item in raw_formats
    ):
        raise InstagramNoVideoError

    prepared: dict[str, Any] = dict(info)
    prepared_formats: list[object] = []
    for item in raw_formats:
        if not isinstance(item, Mapping):
            prepared_formats.append(item)
            continue
        prepared_format = dict(item)
        if _is_video_format(item) and not prepared_format.get("vcodec"):
            prepared_format["vcodec"] = "unknown"
        if (
            _is_video_format(item)
            and prepared_format.get("acodec") is None
            and str(prepared_format.get("ext") or "").lower() == "mp4"
        ):
            prepared_format["acodec"] = "unknown"
        prepared_formats.append(prepared_format)
    prepared["formats"] = prepared_formats
    if prepared.get("duration") is None:
        prepared["duration"] = _duration_from_format_urls(raw_formats)

    title = _short_caption(info.get("title")) or _short_caption(
        info.get("description")
    )
    if title is None:
        first_path_part = next(
            (part for part in urlparse(requested_url).path.split("/") if part),
            "",
        )
        title = "Instagram Reel" if first_path_part in {"reel", "reels"} else "Instagram video"
    prepared["title"] = title

    return prepared


def normalize_instagram_info(
    info: Mapping[str, Any],
    requested_url: str,
) -> MediaInfo:
    prepared = prepare_instagram_info(info, requested_url)

    return normalize_media_info(prepared, requested_url, platform="instagram")


def extract_instagram_info(url: HttpUrl | str) -> Mapping[str, Any]:
    requested_url = str(url)
    validate_instagram_url(requested_url)
    logger.info("Starting Instagram metadata analysis")

    try:
        with YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(requested_url, download=False)
    except DownloadError as error:
        mapped_error = map_instagram_download_error(error)
        logger.warning(
            "Instagram metadata analysis failed: %s",
            mapped_error.__class__.__name__,
        )
        raise mapped_error from error
    except Exception as error:
        logger.exception("Unexpected Instagram metadata extractor failure")
        raise UnexpectedYouTubeError from error

    if not isinstance(info, Mapping):
        logger.error("Instagram extractor returned an invalid payload")
        raise InstagramServiceError

    return info


def analyze_instagram(url: HttpUrl | str) -> MediaInfo:
    requested_url = str(url)
    media = normalize_instagram_info(
        extract_instagram_info(requested_url),
        requested_url,
    )
    logger.info("Instagram metadata analysis completed", extra={"media_id": media.id})
    return media
