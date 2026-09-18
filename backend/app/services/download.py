import logging
import re
import tempfile
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from app.services.ffmpeg import detect_media_tools
from app.services.youtube import (
    UnexpectedYouTubeError,
    YouTubeServiceError,
    extract_youtube_info,
    map_download_error,
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
        self._temporary_directory.cleanup()


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
    return (
        extension == "mp4",
        _codec_rank(codec, MP4_VIDEO_CODECS),
        float(raw_format.get("fps") or 0),
        float(raw_format.get("tbr") or 0),
        _format_filesize(raw_format) or 0,
    )


def _audio_score(raw_format: Mapping[str, Any]) -> tuple[object, ...]:
    extension = (_clean_string(raw_format.get("ext")) or "").lower()
    codec = _clean_string(raw_format.get("acodec"))
    return (
        extension in {"m4a", "mp4"},
        _codec_rank(codec, MP4_AUDIO_CODECS),
        float(raw_format.get("abr") or raw_format.get("tbr") or 0),
        _format_filesize(raw_format) or 0,
    )


def _source_audio_score(raw_format: Mapping[str, Any]) -> tuple[object, ...]:
    return (
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


def select_mp4_formats(raw_formats: object, quality: int) -> FormatSelection:
    if not isinstance(raw_formats, list):
        raise QualityUnavailableError

    exact_video_formats = [
        item
        for item in raw_formats
        if isinstance(item, Mapping)
        and _has_video(item)
        and _positive_int(item.get("height")) == quality
        and _valid_format_id(item) is not None
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

    audio_only = [
        item
        for item in raw_formats
        if isinstance(item, Mapping)
        and _has_audio(item)
        and not _has_video(item)
        and _valid_format_id(item) is not None
    ]
    if not audio_only:
        raise IncompatibleMediaError

    selected = max(audio_only, key=_source_audio_score)
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
        "no_warnings": True,
        "outtmpl": str(temporary_path / "media.%(ext)s"),
        "paths": {"home": str(temporary_path), "temp": str(temporary_path)},
        "quiet": True,
        "retries": 1,
        "socket_timeout": DOWNLOAD_SOCKET_TIMEOUT_SECONDS,
        "writethumbnail": False,
        "writeinfojson": False,
    }


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
) -> DownloadArtifact:
    temporary_directory = tempfile.TemporaryDirectory(prefix="clipflow-")
    temporary_path = Path(temporary_directory.name)
    options = options_factory(temporary_path)
    logger.info(
        "Starting YouTube %s download",
        extension.upper(),
        extra={"video_id": video_id, **log_context},
    )

    try:
        with YoutubeDL(options) as ydl:
            ydl.extract_info(requested_url, download=True)

        output_path = temporary_path / f"media.{extension}"
        if not output_path.is_file() or output_path.stat().st_size <= 0:
            raise DownloadProcessingError

        logger.info(
            "YouTube %s download completed",
            extension.upper(),
            extra={"video_id": video_id, **log_context},
        )
        return DownloadArtifact(
            path=output_path,
            filename=sanitize_download_filename(title, extension),
            _temporary_directory=temporary_directory,
        )
    except DownloadError as error:
        temporary_directory.cleanup()
        if _is_processing_error(error):
            logger.warning("YouTube media post-processing failed")
            raise DownloadProcessingError from error
        mapped_error = map_download_error(error)
        logger.warning("YouTube media download failed: %s", mapped_error.__class__.__name__)
        raise mapped_error from error
    except YouTubeDownloadError:
        temporary_directory.cleanup()
        raise
    except (OSError, ValueError) as error:
        temporary_directory.cleanup()
        logger.exception("Media file processing failed")
        raise DownloadProcessingError from error
    except Exception as error:
        temporary_directory.cleanup()
        logger.exception("Unexpected YouTube media download failure")
        raise UnexpectedYouTubeError from error


def download_youtube_mp4(
    url: HttpUrl | str,
    quality: int,
) -> DownloadArtifact:
    requested_url = str(url)
    raw_info = extract_youtube_info(requested_url)
    media = normalize_video_info(raw_info, requested_url)
    selection = select_mp4_formats(raw_info.get("formats"), quality)
    _ensure_within_limits(media.duration, selection.estimated_filesize)

    if selection.requires_ffmpeg and not detect_media_tools().available:
        raise FFmpegUnavailableError

    return _run_download(
        requested_url=requested_url,
        title=media.title,
        video_id=media.id,
        options_factory=lambda temporary_path: _mp4_download_options(
            temporary_path, selection
        ),
        extension="mp4",
        log_context={"quality": quality},
    )


def download_youtube_mp3(
    url: HttpUrl | str,
    audio_quality: int,
) -> DownloadArtifact:
    if audio_quality not in SUPPORTED_MP3_BITRATES:
        raise UnsupportedBitrateError

    requested_url = str(url)
    raw_info = extract_youtube_info(requested_url)
    media = normalize_video_info(raw_info, requested_url)
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
        title=media.title,
        video_id=media.id,
        options_factory=lambda temporary_path: _mp3_download_options(
            temporary_path, selection, audio_quality
        ),
        extension="mp3",
        log_context={"audio_quality": audio_quality},
    )
