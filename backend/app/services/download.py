import gc
import logging
import math
import re
import tempfile
import time
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import HttpUrl
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.config import (
    DOWNLOAD_SOCKET_TIMEOUT_SECONDS,
    MAX_DOWNLOAD_DURATION_SECONDS,
    MAX_DOWNLOAD_FILESIZE_BYTES,
    MAX_FILENAME_STEM_LENGTH,
    SUPPORTED_MP3_BITRATES,
)
from app.schemas import MediaInfo
from app.services.ffmpeg import detect_media_tools
from app.services.instagram import (
    extract_instagram_info,
    map_instagram_download_error,
    prepare_instagram_info,
)
from app.services.platforms import MediaPlatform, detect_platform
from app.services.temporary import create_download_temp_directory
from app.services.tiktok import extract_tiktok_info
from app.services.twitter import (
    extract_twitter_info,
    map_twitter_download_error,
    prepare_twitter_info,
)
from app.services.youtube import (
    UnexpectedYouTubeError,
    YouTubeServiceError,
    extract_youtube_info,
    map_download_error,
    normalize_media_info,
    normalize_video_info,
)

logger = logging.getLogger(__name__)

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
MP4_VIDEO_CODECS = ("avc1", "h264", "av01", "vp9", "hev1", "hvc1")
MP4_AUDIO_CODECS = ("mp4a", "aac")


class YouTubeDownloadError(Exception):
    """Base exception for predictable media download failures."""


class QualityUnavailableError(YouTubeDownloadError):
    pass


class DownloadLimitExceededError(YouTubeDownloadError):
    pass


class FFmpegUnavailableError(YouTubeDownloadError):
    pass


class IncompatibleMediaError(YouTubeDownloadError):
    pass


class DownloadProcessingError(YouTubeDownloadError):
    pass


class UnsupportedBitrateError(YouTubeDownloadError):
    pass


class AudioUnavailableError(YouTubeDownloadError):
    pass


class DownloadCancelledError(YouTubeDownloadError):
    pass


@dataclass(frozen=True)
class FormatSelection:
    selector: str
    requires_ffmpeg: bool
    estimated_filesize: int | None


@dataclass
class DownloadArtifact:
    path: Path
    filename: str
    _temporary_directory: tempfile.TemporaryDirectory[str]

    def cleanup(self) -> None:
        _cleanup_temporary_directory(self._temporary_directory)


@dataclass(frozen=True)
class DownloadProgress:
    status: Literal["downloading", "processing"]
    stage: str
    progress: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed: float | None = None
    eta: int | None = None


ProgressCallback = Callable[[DownloadProgress], None]
CancellationCheck = Callable[[], bool]


def _cleanup_temporary_directory(
    temporary_directory: tempfile.TemporaryDirectory[str],
) -> None:
    retry_delays = (0.0, 0.1, 0.25, 0.5, 1.0, 2.0)
    for index, delay in enumerate(retry_delays):
        if delay:
            time.sleep(delay)
        try:
            temporary_directory.cleanup()
            return
        except OSError:
            gc.collect()
            if index == len(retry_delays) - 1:
                logger.warning("Temporary media cleanup is still pending")


def _extract_media(options: dict[str, object], requested_url: str) -> None:
    """Keep yt-dlp references out of the cleanup frame for Windows file handles."""
    with YoutubeDL(options) as ydl:
        ydl.extract_info(requested_url, download=True)


def sanitize_download_filename(
    title: str | None,
    extension: str = "mp4",
) -> str:
    if extension not in {"mp3", "mp4"}:
        raise ValueError("Unsupported filename extension")

    normalized = unicodedata.normalize("NFKC", title or "")
    without_controls = "".join(
        character for character in normalized if unicodedata.category(character)[0] != "C"
    )
    safe = re.sub(r'[<>:"/\\|?*]', " ", without_controls)
    safe = re.sub(r"\s+", " ", safe).strip(" .")
    safe = safe[:MAX_FILENAME_STEM_LENGTH].rstrip(" .")

    if not safe:
        safe = "clipflow-audio" if extension == "mp3" else "clipflow-video"

    if safe.upper() in WINDOWS_RESERVED_NAMES:
        safe = f"clipflow-{safe.lower()}"

    return f"{safe}.{extension}"


def _clean_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return int(value)


def _has_video(raw_format: Mapping[str, Any]) -> bool:
    return (_clean_string(raw_format.get("vcodec")) or "none") != "none"


def _has_audio(raw_format: Mapping[str, Any]) -> bool:
    return (_clean_string(raw_format.get("acodec")) or "none") != "none"


def _format_filesize(raw_format: Mapping[str, Any]) -> int | None:
    return _positive_int(raw_format.get("filesize")) or _positive_int(
        raw_format.get("filesize_approx")
    )


def _codec_rank(codec: str | None, preferred: tuple[str, ...]) -> int:
    if codec is None:
        return -1
    lowered = codec.lower()
    for index, prefix in enumerate(preferred):
        if lowered.startswith(prefix):
            return len(preferred) - index
    return -1


def _video_score(raw_format: Mapping[str, Any]) -> tuple[object, ...]:
    extension = (_clean_string(raw_format.get("ext")) or "").lower()
    codec = _clean_string(raw_format.get("vcodec"))
    protocol = (_clean_string(raw_format.get("protocol")) or "").lower()
    return (
        extension == "mp4",
        _codec_rank(codec, MP4_VIDEO_CODECS),
        protocol in {"http", "https"},
        float(raw_format.get("fps") or 0),
        float(raw_format.get("tbr") or 0),
        _format_filesize(raw_format) or 0,
    )


def _audio_score(raw_format: Mapping[str, Any]) -> tuple[object, ...]:
    extension = (_clean_string(raw_format.get("ext")) or "").lower()
    codec = _clean_string(raw_format.get("acodec"))
    protocol = (_clean_string(raw_format.get("protocol")) or "").lower()
    return (
        extension in {"m4a", "mp4"},
        _codec_rank(codec, MP4_AUDIO_CODECS),
        protocol in {"http", "https"},
        float(raw_format.get("abr") or raw_format.get("tbr") or 0),
        _format_filesize(raw_format) or 0,
    )


def _source_audio_score(raw_format: Mapping[str, Any]) -> tuple[object, ...]:
    protocol = (_clean_string(raw_format.get("protocol")) or "").lower()
    return (
        protocol in {"http", "https"},
        float(raw_format.get("abr") or raw_format.get("tbr") or 0),
        float(raw_format.get("asr") or 0),
        int(raw_format.get("audio_channels") or 0),
        _format_filesize(raw_format) or 0,
    )


def _valid_format_id(raw_format: Mapping[str, Any]) -> str | None:
    value = _clean_string(raw_format.get("format_id"))
    if value is None or not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        return None
    return value


def select_mp4_formats(
    raw_formats: object,
    quality: int | None,
    platform: MediaPlatform = "youtube",
) -> FormatSelection:
    if not isinstance(raw_formats, list):
        raise QualityUnavailableError

    video_formats = [
        item
        for item in raw_formats
        if isinstance(item, Mapping)
        and _has_video(item)
        and _valid_format_id(item) is not None
        and _positive_int(item.get("height")) is not None
    ]
    selected_quality = quality
    if selected_quality is None and video_formats:
        selected_quality = max(
            height
            for item in video_formats
            if (height := _positive_int(item.get("height"))) is not None
        )
    exact_video_formats = [
        item
        for item in video_formats
        if _positive_int(item.get("height")) == selected_quality
    ]
    if not exact_video_formats:
        raise QualityUnavailableError

    progressive_mp4 = [
        item
        for item in exact_video_formats
        if (_clean_string(item.get("ext")) or "").lower() == "mp4"
        and _has_audio(item)
        and _codec_rank(_clean_string(item.get("vcodec")), MP4_VIDEO_CODECS) >= 0
        and _codec_rank(_clean_string(item.get("acodec")), MP4_AUDIO_CODECS) >= 0
    ]
    if progressive_mp4:
        selected = max(progressive_mp4, key=_video_score)
        return FormatSelection(
            selector=_valid_format_id(selected) or "",
            requires_ffmpeg=False,
            estimated_filesize=_format_filesize(selected),
        )

    # Social providers commonly expose either a complete MP4, separate MP4/M4A
    # streams, or a silent MP4. Container information from the provider is
    # sufficient here; requiring YouTube's usual codec labels rejects valid
    # media whose codecs are missing or represented differently.
    if platform in {"instagram", "twitter"}:
        combined_mp4 = [
            item
            for item in exact_video_formats
            if (_clean_string(item.get("ext")) or "").lower() == "mp4"
            and _has_audio(item)
        ]
        if combined_mp4:
            selected = max(combined_mp4, key=_video_score)
            return FormatSelection(
                selector=_valid_format_id(selected) or "",
                requires_ffmpeg=False,
                estimated_filesize=_format_filesize(selected),
            )

        provider_video_only = [
            item
            for item in exact_video_formats
            if not _has_audio(item)
            and (_clean_string(item.get("ext")) or "").lower() == "mp4"
        ]
        provider_audio_only = [
            item
            for item in raw_formats
            if isinstance(item, Mapping)
            and _has_audio(item)
            and not _has_video(item)
            and _valid_format_id(item) is not None
            and (_clean_string(item.get("ext")) or "").lower() in {"m4a", "mp4"}
        ]
        if provider_video_only and provider_audio_only:
            selected_video = max(provider_video_only, key=_video_score)
            selected_audio = max(provider_audio_only, key=_audio_score)
            sizes = [_format_filesize(selected_video), _format_filesize(selected_audio)]
            return FormatSelection(
                selector=(
                    f"{_valid_format_id(selected_video)}+"
                    f"{_valid_format_id(selected_audio)}"
                ),
                requires_ffmpeg=True,
                estimated_filesize=(
                    sum(size for size in sizes if size is not None)
                    if all(size is not None for size in sizes)
                    else None
                ),
            )

        has_any_audio = any(
            isinstance(item, Mapping) and _has_audio(item) for item in raw_formats
        )
        if provider_video_only and not has_any_audio:
            selected = max(provider_video_only, key=_video_score)
            return FormatSelection(
                selector=_valid_format_id(selected) or "",
                requires_ffmpeg=False,
                estimated_filesize=_format_filesize(selected),
            )

    video_only = [
        item
        for item in exact_video_formats
        if not _has_audio(item)
        and _codec_rank(_clean_string(item.get("vcodec")), MP4_VIDEO_CODECS) >= 0
    ]
    audio_only = [
        item
        for item in raw_formats
        if isinstance(item, Mapping)
        and _has_audio(item)
        and not _has_video(item)
        and _valid_format_id(item) is not None
        and _codec_rank(_clean_string(item.get("acodec")), MP4_AUDIO_CODECS) >= 0
    ]
    if not video_only or not audio_only:
        raise IncompatibleMediaError

    selected_video = max(video_only, key=_video_score)
    selected_audio = max(audio_only, key=_audio_score)
    video_id = _valid_format_id(selected_video)
    audio_id = _valid_format_id(selected_audio)
    if video_id is None or audio_id is None:
        raise IncompatibleMediaError

    sizes = [_format_filesize(selected_video), _format_filesize(selected_audio)]
    estimated_filesize = sum(size for size in sizes if size is not None)
    if any(size is None for size in sizes):
        estimated_filesize = None

    return FormatSelection(
        selector=f"{video_id}+{audio_id}",
        requires_ffmpeg=True,
        estimated_filesize=estimated_filesize,
    )


def select_best_audio_format(raw_formats: object) -> FormatSelection:
    if not isinstance(raw_formats, list):
        raise IncompatibleMediaError

    audio_formats = [
        item
        for item in raw_formats
        if isinstance(item, Mapping)
        and _has_audio(item)
        and _valid_format_id(item) is not None
    ]
    if not audio_formats:
        raise IncompatibleMediaError

    selected = max(
        audio_formats,
        key=lambda item: (not _has_video(item), *_source_audio_score(item)),
    )
    return FormatSelection(
        selector=_valid_format_id(selected) or "",
        requires_ffmpeg=True,
        estimated_filesize=_format_filesize(selected),
    )


def _ensure_within_limits(
    duration: int | None,
    estimated_filesize: int | None,
) -> None:
    if duration is None or duration > MAX_DOWNLOAD_DURATION_SECONDS:
        raise DownloadLimitExceededError
    if (
        estimated_filesize is not None
        and estimated_filesize > MAX_DOWNLOAD_FILESIZE_BYTES
    ):
        raise DownloadLimitExceededError


def _base_download_options(
    temporary_path: Path,
    selector: str,
) -> dict[str, object]:
    return {
        "cachedir": False,
        "extractor_retries": 1,
        "fragment_retries": 1,
        "format": selector,
        "ignoreconfig": True,
        "js_runtimes": {"node": {}},
        "max_filesize": MAX_DOWNLOAD_FILESIZE_BYTES,
        "noplaylist": True,
        "noprogress": True,
        "no_warnings": True,
        "outtmpl": str(temporary_path / "media.%(ext)s"),
        "paths": {"home": str(temporary_path), "temp": str(temporary_path)},
        "quiet": True,
        "retries": 1,
        "socket_timeout": DOWNLOAD_SOCKET_TIMEOUT_SECONDS,
        "writethumbnail": False,
        "writeinfojson": False,
    }


def _non_negative_number(value: object) -> float | None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        return None
    return float(value)


def _non_negative_int(value: object) -> int | None:
    number = _non_negative_number(value)
    return int(number) if number is not None else None


def _progress_hooks(
    selection: FormatSelection,
    extension: str,
    on_progress: ProgressCallback | None,
    is_cancelled: CancellationCheck | None,
    platform: MediaPlatform = "youtube",
) -> tuple[list[Callable[[dict[str, Any]], None]], list[Callable[[dict[str, Any]], None]]]:
    if on_progress is None and is_cancelled is None:
        return [], []

    selected_ids = selection.selector.split("+")
    completed_format_ids: set[str] = set()
    processing_stage = (
        "Converting to MP3"
        if extension == "mp3"
        else "Merging video and audio"
    )

    def ensure_not_cancelled(data: Mapping[str, Any] | None = None) -> bool:
        if is_cancelled is not None and is_cancelled():
            info = data.get("info_dict") if data is not None else None
            protocol = (
                (_clean_string(info.get("protocol")) or "").lower()
                if isinstance(info, Mapping)
                else ""
            )
            status = data.get("status") if data is not None else None
            if status == "downloading" and (
                "m3u8" in protocol or "dash_segments" in protocol
            ):
                return False
            raise DownloadCancelledError("ClipFlow download cancelled")
        return True

    def progress_hook(data: dict[str, Any]) -> None:
        if not ensure_not_cancelled(data):
            return
        status = data.get("status")

        if status == "downloading":
            downloaded_bytes = _non_negative_int(data.get("downloaded_bytes"))
            total_bytes = _non_negative_int(data.get("total_bytes")) or _non_negative_int(
                data.get("total_bytes_estimate")
            )
            progress = None
            if downloaded_bytes is not None and total_bytes:
                progress = min(100.0, max(0.0, downloaded_bytes / total_bytes * 100))

            current_format = data.get("info_dict")
            format_id = (
                _clean_string(current_format.get("format_id"))
                if isinstance(current_format, Mapping)
                else None
            )
            stage = (
                "Downloading media"
                if platform != "youtube" and extension == "mp4"
                else "Downloading audio"
                if extension == "mp3"
                else "Downloading video"
            )
            if (
                platform == "youtube"
                and extension == "mp4"
                and len(selected_ids) > 1
                and format_id == selected_ids[-1]
            ):
                stage = "Downloading audio"

            if on_progress is not None:
                on_progress(
                    DownloadProgress(
                        status="downloading",
                        stage=stage,
                        progress=progress,
                        downloaded_bytes=downloaded_bytes,
                        total_bytes=total_bytes,
                        speed=_non_negative_number(data.get("speed")),
                        eta=_non_negative_int(data.get("eta")),
                    )
                )
        elif status == "finished" and on_progress is not None:
            if selection.requires_ffmpeg:
                current_format = data.get("info_dict")
                format_id = (
                    _clean_string(current_format.get("format_id"))
                    if isinstance(current_format, Mapping)
                    else None
                )
                if len(selected_ids) > 1:
                    if format_id is not None:
                        completed_format_ids.add(format_id)
                    if not set(selected_ids).issubset(completed_format_ids):
                        return
                on_progress(DownloadProgress(status="processing", stage=processing_stage))
            else:
                on_progress(
                    DownloadProgress(
                        status="downloading",
                        stage="Finalizing download",
                        progress=100.0,
                    )
                )

    def postprocessor_hook(data: dict[str, Any]) -> None:
        ensure_not_cancelled(data)
        if on_progress is not None and data.get("status") in {"started", "processing"}:
            on_progress(DownloadProgress(status="processing", stage=processing_stage))

    return [progress_hook], [postprocessor_hook]


def _mp4_download_options(
    temporary_path: Path,
    selection: FormatSelection,
) -> dict[str, object]:
    return {
        **_base_download_options(temporary_path, selection.selector),
        "merge_output_format": "mp4",
    }


def _mp3_download_options(
    temporary_path: Path,
    selection: FormatSelection,
    audio_quality: int,
) -> dict[str, object]:
    return {
        **_base_download_options(temporary_path, selection.selector),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(audio_quality),
            }
        ],
    }


def _is_processing_error(error: DownloadError) -> bool:
    message = str(error).lower()
    return any(
        marker in message
        for marker in ("ffmpeg", "postprocess", "conversion failed", "audio conversion")
    )


def _run_download(
    requested_url: str,
    title: str,
    video_id: str,
    options_factory: Callable[[Path], dict[str, object]],
    extension: str,
    log_context: dict[str, object],
    selection: FormatSelection,
    platform: MediaPlatform,
    on_progress: ProgressCallback | None = None,
    is_cancelled: CancellationCheck | None = None,
) -> DownloadArtifact:
    temporary_directory = create_download_temp_directory()
    temporary_path = Path(temporary_directory.name)
    options = options_factory(temporary_path)
    progress_hooks, postprocessor_hooks = _progress_hooks(
        selection,
        extension,
        on_progress,
        is_cancelled,
        platform,
    )
    if progress_hooks:
        options["progress_hooks"] = progress_hooks
    if postprocessor_hooks:
        options["postprocessor_hooks"] = postprocessor_hooks
    logger.info(
        "Starting %s %s download",
        platform,
        extension.upper(),
        extra={"video_id": video_id, **log_context},
    )

    try:
        if is_cancelled is not None and is_cancelled():
            raise DownloadCancelledError("ClipFlow download cancelled")
        _extract_media(options, requested_url)

        if is_cancelled is not None and is_cancelled():
            raise DownloadCancelledError("ClipFlow download cancelled")

        output_path = temporary_path / f"media.{extension}"
        if not output_path.is_file() or output_path.stat().st_size <= 0:
            raise DownloadProcessingError

        logger.info(
            "%s %s download completed",
            platform,
            extension.upper(),
            extra={"video_id": video_id, **log_context},
        )
        return DownloadArtifact(
            path=output_path,
            filename=sanitize_download_filename(title, extension),
            _temporary_directory=temporary_directory,
        )
    except DownloadError as error:
        _cleanup_temporary_directory(temporary_directory)
        if "clipflow download cancelled" in str(error).lower():
            raise DownloadCancelledError from error
        if _is_processing_error(error):
            logger.warning("%s media post-processing failed", platform)
            raise DownloadProcessingError from error
        mapped_error = (
            map_instagram_download_error(error)
            if platform == "instagram"
            else map_twitter_download_error(error)
            if platform == "twitter"
            else map_download_error(error)
        )
        logger.warning(
            "%s media download failed: %s",
            platform,
            mapped_error.__class__.__name__,
        )
        raise mapped_error from error
    except YouTubeDownloadError:
        _cleanup_temporary_directory(temporary_directory)
        raise
    except (OSError, ValueError) as error:
        _cleanup_temporary_directory(temporary_directory)
        logger.exception("Media file processing failed")
        raise DownloadProcessingError from error
    except Exception as error:
        _cleanup_temporary_directory(temporary_directory)
        logger.exception(
            "Unexpected media download failure",
            extra={"platform": platform},
        )
        raise UnexpectedYouTubeError from error


def _extract_download_source(
    requested_url: str,
) -> tuple[MediaPlatform, Mapping[str, Any], MediaInfo]:
    platform = detect_platform(requested_url)
    extractors = {
        "youtube": extract_youtube_info,
        "tiktok": extract_tiktok_info,
        "instagram": extract_instagram_info,
        "twitter": extract_twitter_info,
    }
    raw_info = extractors[platform](requested_url)
    if platform == "youtube":
        media = normalize_video_info(raw_info, requested_url)
    elif platform == "instagram":
        raw_info = prepare_instagram_info(raw_info, requested_url)
        media = normalize_media_info(raw_info, requested_url, platform="instagram")
    elif platform == "twitter":
        raw_info = prepare_twitter_info(raw_info, requested_url)
        media = normalize_media_info(raw_info, requested_url, platform="twitter")
    else:
        media = normalize_media_info(raw_info, requested_url, platform="tiktok")
    return platform, raw_info, media


def _download_title(
    raw_info: Mapping[str, Any],
    platform: MediaPlatform,
    extension: Literal["mp3", "mp4"] = "mp4",
    normalized_title: str = "",
) -> str:
    if platform in {"instagram", "twitter"}:
        prefix = "instagram" if platform == "instagram" else "x"
        fallback = f"{prefix}-audio" if extension == "mp3" else f"{prefix}-video"
        return _clean_string(normalized_title) or fallback
    return (
        _clean_string(raw_info.get("title"))
        or _clean_string(raw_info.get("description"))
        or f"clipflow-{platform}"
    )


def download_youtube_mp4(
    url: HttpUrl | str,
    quality: int,
    *,
    on_progress: ProgressCallback | None = None,
    is_cancelled: CancellationCheck | None = None,
) -> DownloadArtifact:
    if is_cancelled is not None and is_cancelled():
        raise DownloadCancelledError
    requested_url = str(url)
    platform, raw_info, media = _extract_download_source(requested_url)
    if is_cancelled is not None and is_cancelled():
        raise DownloadCancelledError
    selection = select_mp4_formats(raw_info.get("formats"), quality, platform)
    _ensure_within_limits(media.duration, selection.estimated_filesize)

    if selection.requires_ffmpeg and not detect_media_tools().available:
        raise FFmpegUnavailableError

    return _run_download(
        requested_url=requested_url,
        title=_download_title(raw_info, platform, "mp4", media.title),
        video_id=media.id,
        options_factory=lambda temporary_path: _mp4_download_options(
            temporary_path, selection
        ),
        extension="mp4",
        log_context={"quality": quality},
        selection=selection,
        platform=platform,
        on_progress=on_progress,
        is_cancelled=is_cancelled,
    )


def download_youtube_mp3(
    url: HttpUrl | str,
    audio_quality: int,
    *,
    on_progress: ProgressCallback | None = None,
    is_cancelled: CancellationCheck | None = None,
) -> DownloadArtifact:
    if audio_quality not in SUPPORTED_MP3_BITRATES:
        raise UnsupportedBitrateError
    if is_cancelled is not None and is_cancelled():
        raise DownloadCancelledError

    requested_url = str(url)
    platform, raw_info, media = _extract_download_source(requested_url)
    if is_cancelled is not None and is_cancelled():
        raise DownloadCancelledError
    if not any(media_format.type == "audio" for media_format in media.formats):
        raise AudioUnavailableError
    selection = select_best_audio_format(raw_info.get("formats"))

    estimated_mp3_size = None
    if media.duration is not None:
        estimated_mp3_size = (audio_quality * 1_000 * media.duration) // 8
    known_sizes = [
        size
        for size in (selection.estimated_filesize, estimated_mp3_size)
        if size is not None
    ]
    _ensure_within_limits(media.duration, max(known_sizes, default=None))

    if not detect_media_tools().available:
        raise FFmpegUnavailableError

    return _run_download(
        requested_url=requested_url,
        title=_download_title(raw_info, platform, "mp3", media.title),
        video_id=media.id,
        options_factory=lambda temporary_path: _mp3_download_options(
            temporary_path, selection, audio_quality
        ),
        extension="mp3",
        log_context={"audio_quality": audio_quality},
        selection=selection,
        platform=platform,
        on_progress=on_progress,
        is_cancelled=is_cancelled,
    )


# Public generic names. The YouTube-prefixed functions remain as compatibility
# aliases for existing callers while both platforms share the same pipeline.
download_media_mp4 = download_youtube_mp4
download_media_mp3 = download_youtube_mp3
