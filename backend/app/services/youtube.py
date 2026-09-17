import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlparse

from pydantic import HttpUrl
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.schemas import MediaFormat, MediaInfo

logger = logging.getLogger(__name__)

YOUTUBE_HOSTS = {"youtube.com", "youtu.be", "youtube-nocookie.com"}

YDL_OPTIONS: dict[str, object] = {
    "cachedir": False,
    "extract_flat": False,
    "extractor_retries": 1,
    "fragment_retries": 1,
    "ignoreconfig": True,
    "js_runtimes": {"node": {}},
    "noplaylist": True,
    "no_warnings": True,
    "quiet": True,
    "retries": 1,
    "skip_download": True,
    "socket_timeout": 10,
    "writeinfojson": False,
    "writethumbnail": False,
}


class YouTubeAnalysisError(Exception):
    """Base exception for predictable YouTube analysis failures."""


class InvalidYouTubeUrlError(YouTubeAnalysisError):
    pass


class UnsupportedPlatformError(YouTubeAnalysisError):
    pass


class PrivateVideoError(YouTubeAnalysisError):
    pass


class RemovedVideoError(YouTubeAnalysisError):
    pass


class VideoUnavailableError(YouTubeAnalysisError):
    pass


class YouTubeServiceError(YouTubeAnalysisError):
    pass


class UnexpectedYouTubeError(YouTubeAnalysisError):
    pass


def validate_youtube_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")

    if parsed.scheme not in {"http", "https"} or not hostname:
        raise InvalidYouTubeUrlError

    try:
        port = parsed.port
    except ValueError as error:
        raise InvalidYouTubeUrlError from error

    if parsed.username or parsed.password or port not in {None, 80, 443}:
        raise InvalidYouTubeUrlError

    if not any(hostname == host or hostname.endswith(f".{host}") for host in YOUTUBE_HOSTS):
        raise UnsupportedPlatformError


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    return cleaned or None


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    return int(value) if value >= 0 else None


def _positive_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    return float(value) if value > 0 else None


def _safe_http_url(value: object) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None

    return cleaned


def _extract_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    if hostname == "youtu.be" or hostname.endswith(".youtu.be"):
        return _clean_text(parsed.path.strip("/").split("/")[0])

    query_id = parse_qs(parsed.query).get("v", [None])[0]
    if query_id:
        return _clean_text(query_id)

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
        return _clean_text(path_parts[1])

    return None


def _select_thumbnail(info: Mapping[str, Any]) -> str | None:
    thumbnails = info.get("thumbnails")
    candidates: list[tuple[tuple[float, float, int], str]] = []

    if isinstance(thumbnails, list):
        for index, item in enumerate(thumbnails):
            if not isinstance(item, Mapping):
                continue

            url = _safe_http_url(item.get("url"))
            if url is None:
                continue

            width = _positive_number(item.get("width")) or 0
            height = _positive_number(item.get("height")) or 0
            preference = _positive_number(item.get("preference")) or 0
            candidates.append(((width * height, preference, index), url))

    if candidates:
        return max(candidates, key=lambda candidate: candidate[0])[1]

    return _safe_http_url(info.get("thumbnail"))


def _format_from_raw(raw_format: Mapping[str, Any]) -> MediaFormat | None:
    format_id = _clean_text(raw_format.get("format_id"))
    video_codec = _clean_text(raw_format.get("vcodec"))
    audio_codec = _clean_text(raw_format.get("acodec"))
    has_video = video_codec is not None and video_codec != "none"
    has_audio = audio_codec is not None and audio_codec != "none"

    if format_id is None or not (has_video or has_audio):
        return None

    quality_value = _positive_number(raw_format.get("height")) if has_video else None
    if has_video and quality_value is None:
        return None

    bitrate_value = raw_format.get("abr") if not has_video else raw_format.get("tbr")
    bitrate = _non_negative_int(bitrate_value)
    filesize = _non_negative_int(
        raw_format.get("filesize") or raw_format.get("filesize_approx")
    )

    return MediaFormat(
        format_id=format_id,
        type="video" if has_video else "audio",
        extension=_clean_text(raw_format.get("ext")),
        quality=int(quality_value) if quality_value is not None else None,
        fps=_positive_number(raw_format.get("fps")),
        bitrate=bitrate,
        filesize=filesize,
    )


def _format_score(media_format: MediaFormat, has_audio: bool) -> tuple[object, ...]:
    return (
        media_format.extension == "mp4",
        has_audio,
        media_format.fps or 0,
        media_format.bitrate or 0,
        media_format.filesize or 0,
    )


def normalize_formats(raw_formats: object) -> list[MediaFormat]:
    if not isinstance(raw_formats, list):
        return []

    video_formats: dict[int, tuple[tuple[object, ...], MediaFormat]] = {}
    audio_formats: dict[str, tuple[tuple[object, ...], MediaFormat]] = {}

    for raw_format in raw_formats:
        if not isinstance(raw_format, Mapping):
            continue

        normalized = _format_from_raw(raw_format)
        if normalized is None:
            continue

        audio_codec = _clean_text(raw_format.get("acodec"))
        has_audio = audio_codec is not None and audio_codec != "none"
        score = _format_score(normalized, has_audio)

        if normalized.type == "video" and normalized.quality is not None:
            current = video_formats.get(normalized.quality)
            if current is None or score > current[0]:
                video_formats[normalized.quality] = (score, normalized)
            continue

        extension_key = normalized.extension or "unknown"
        current = audio_formats.get(extension_key)
        if current is None or score > current[0]:
            audio_formats[extension_key] = (score, normalized)

    videos = [
        video_formats[quality][1]
        for quality in sorted(video_formats, reverse=True)
    ]
    audios = [
        item[1]
        for item in sorted(
            audio_formats.values(),
            key=lambda item: item[0],
            reverse=True,
        )[:2]
    ]

    return videos + audios


def normalize_video_info(info: Mapping[str, Any], requested_url: str) -> MediaInfo:
    if info.get("_type") in {"playlist", "multi_video"}:
        raise InvalidYouTubeUrlError

    formats = normalize_formats(info.get("formats"))
    qualities = [
        media_format.quality
        for media_format in formats
        if media_format.type == "video" and media_format.quality is not None
    ]
    video_id = _clean_text(info.get("id")) or _extract_video_id(requested_url)
    canonical_url = (
        _safe_http_url(info.get("webpage_url"))
        or _safe_http_url(info.get("original_url"))
        or requested_url
    )

    return MediaInfo(
        id=video_id or "unknown",
        title=_clean_text(info.get("title")) or "Vídeo do YouTube",
        author=(
            _clean_text(info.get("channel"))
            or _clean_text(info.get("uploader"))
            or _clean_text(info.get("creator"))
        ),
        duration=_non_negative_int(info.get("duration")),
        thumbnail=_select_thumbnail(info),
        original_url=canonical_url,
        qualities=qualities,
        formats=formats,
    )


def map_download_error(error: DownloadError) -> YouTubeAnalysisError:
    message = str(error).lower()

    if "private video" in message or "granted access" in message:
        return PrivateVideoError()
    if "removed" in message or "has been deleted" in message:
        return RemovedVideoError()
    if "unavailable" in message or "not available" in message:
        return VideoUnavailableError()
    if "unsupported url" in message or "not a valid url" in message:
        return InvalidYouTubeUrlError()

    return YouTubeServiceError()


def extract_youtube_info(url: HttpUrl | str) -> Mapping[str, Any]:
    requested_url = str(url)
    validate_youtube_url(requested_url)
    logger.info("Starting YouTube metadata analysis")

    try:
        with YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(requested_url, download=False)
    except DownloadError as error:
        mapped_error = map_download_error(error)
        logger.warning(
            "YouTube metadata analysis failed: %s",
            mapped_error.__class__.__name__,
        )
        raise mapped_error from error
    except Exception as error:
        logger.exception("Unexpected YouTube metadata extractor failure")
        raise UnexpectedYouTubeError from error

    if not isinstance(info, Mapping):
        logger.error("YouTube extractor returned an invalid payload")
        raise YouTubeServiceError

    return info


def analyze_youtube(url: HttpUrl | str) -> MediaInfo:
    requested_url = str(url)
    info = extract_youtube_info(requested_url)

    media = normalize_video_info(info, requested_url)
    logger.info("YouTube metadata analysis completed", extra={"video_id": media.id})
    return media
