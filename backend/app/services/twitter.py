import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

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

TWITTER_YDL_OPTIONS = {**YDL_OPTIONS, "noplaylist": False}


class TwitterMediaError(Exception):
    """Base exception for predictable X/Twitter failures."""


class TwitterNoVideoError(TwitterMediaError):
    pass


class TwitterAuthenticationRequiredError(TwitterMediaError):
    pass


class TwitterRateLimitedError(TwitterMediaError):
    pass


class TwitterMultipleMediaError(TwitterMediaError):
    pass


class TwitterServiceError(TwitterMediaError):
    pass


def validate_twitter_url(url: str) -> None:
    if detect_platform(url) != "twitter":
        raise UnsupportedPlatformError

    path_parts = [part for part in urlparse(url).path.split("/") if part]
    try:
        status_index = next(
            index for index, part in enumerate(path_parts) if part in {"status", "statuses"}
        )
        post_id = path_parts[status_index + 1]
    except (StopIteration, IndexError) as error:
        raise TwitterNoVideoError from error
    if not post_id.isdigit():
        raise TwitterNoVideoError


def map_twitter_download_error(error: DownloadError) -> Exception:
    message = str(error).lower()
    if any(
        marker in message
        for marker in (
            "login required",
            "not authorized",
            "protected tweet",
            "protected post",
            "requires authentication",
        )
    ):
        return TwitterAuthenticationRequiredError()
    if any(
        marker in message
        for marker in (
            "rate limit",
            "rate-limit",
            "too many requests",
            "http error 429",
            "temporarily rejected",
        )
    ):
        return TwitterRateLimitedError()
    if any(
        marker in message
        for marker in (
            "no video could be found",
            "does not contain video",
            "no supported media",
        )
    ):
        return TwitterNoVideoError()
    if any(marker in message for marker in ("deleted", "removed", "not found")):
        return RemovedVideoError()
    if any(
        marker in message
        for marker in ("unavailable", "not available", "geo-restricted", "geographic")
    ):
        return VideoUnavailableError()
    return TwitterServiceError()


def _short_text(value: object, limit: int = 160) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1].rstrip()}…"


def _has_video_format(info: Mapping[str, Any]) -> bool:
    formats = info.get("formats")
    if not isinstance(formats, list):
        return False
    return any(
        isinstance(item, Mapping)
        and (
            (isinstance(item.get("vcodec"), str) and item["vcodec"].lower() != "none")
            or isinstance(item.get("height"), (int, float))
        )
        for item in formats
    )


def prepare_twitter_info(
    info: Mapping[str, Any],
    requested_url: str,
) -> Mapping[str, Any]:
    prepared: dict[str, Any]
    if info.get("_type") in {"playlist", "multi_video"}:
        entries = [entry for entry in info.get("entries") or [] if isinstance(entry, Mapping)]
        if not entries:
            raise TwitterNoVideoError
        if len(entries) != 1:
            raise TwitterMultipleMediaError
        prepared = dict(entries[0])
        for key in (
            "channel",
            "creator",
            "description",
            "thumbnail",
            "thumbnails",
            "title",
            "uploader",
        ):
            if prepared.get(key) is None and info.get(key) is not None:
                prepared[key] = info[key]
        prepared["webpage_url"] = requested_url
    else:
        prepared = dict(info)

    if not _has_video_format(prepared):
        raise TwitterNoVideoError

    raw_formats = prepared.get("formats")
    if isinstance(raw_formats, list):
        has_explicit_audio = any(
            isinstance(item, Mapping)
            and (
                (
                    isinstance(item.get("acodec"), str)
                    and item["acodec"].lower() != "none"
                )
                or "audio" in str(item.get("format_id") or "").lower()
            )
            for item in raw_formats
        )
        prepared_formats: list[object] = []
        for item in raw_formats:
            if not isinstance(item, Mapping):
                prepared_formats.append(item)
                continue
            prepared_format = dict(item)
            format_id = str(prepared_format.get("format_id") or "").lower()
            protocol = str(prepared_format.get("protocol") or "").lower()
            extension = str(prepared_format.get("ext") or "").lower()
            has_height = isinstance(prepared_format.get("height"), (int, float))

            if has_height and prepared_format.get("vcodec") is None:
                prepared_format["vcodec"] = "unknown"
            if (
                has_height
                and prepared_format.get("acodec") is None
                and extension == "mp4"
                and protocol in {"http", "https"}
                and has_explicit_audio
            ):
                prepared_format["acodec"] = "unknown"
            if (
                prepared_format.get("vcodec") == "none"
                and prepared_format.get("acodec") is None
                and "audio" in format_id
            ):
                prepared_format["acodec"] = "unknown"
            prepared_formats.append(prepared_format)
        prepared["formats"] = prepared_formats

    author = (
        _short_text(prepared.get("channel"), 80)
        or _short_text(prepared.get("uploader"), 80)
        or _short_text(prepared.get("creator"), 80)
    )
    title = _short_text(prepared.get("title")) or _short_text(
        prepared.get("description")
    )
    prepared["title"] = title or (f"Post by {author}" if author else "X video")
    return prepared


def normalize_twitter_info(
    info: Mapping[str, Any],
    requested_url: str,
) -> MediaInfo:
    return normalize_media_info(
        prepare_twitter_info(info, requested_url),
        requested_url,
        platform="twitter",
    )


def extract_twitter_info(url: HttpUrl | str) -> Mapping[str, Any]:
    requested_url = str(url)
    validate_twitter_url(requested_url)
    logger.info("Starting X/Twitter metadata analysis")
    try:
        with YoutubeDL(TWITTER_YDL_OPTIONS) as ydl:
            info = ydl.extract_info(requested_url, download=False)
    except DownloadError as error:
        mapped_error = map_twitter_download_error(error)
        logger.warning(
            "X/Twitter metadata analysis failed: %s",
            mapped_error.__class__.__name__,
        )
        raise mapped_error from error
    except Exception as error:
        logger.exception("Unexpected X/Twitter metadata extractor failure")
        raise UnexpectedYouTubeError from error

    if not isinstance(info, Mapping):
        logger.error("X/Twitter extractor returned an invalid payload")
        raise TwitterServiceError
    return info


def analyze_twitter(url: HttpUrl | str) -> MediaInfo:
    requested_url = str(url)
    media = normalize_twitter_info(extract_twitter_info(requested_url), requested_url)
    logger.info("X/Twitter metadata analysis completed", extra={"media_id": media.id})
    return media
