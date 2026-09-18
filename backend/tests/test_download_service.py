from pathlib import Path
from typing import Any

import pytest
from yt_dlp.utils import DownloadError

from app.services import download
from app.services.download import (
    DownloadLimitExceededError,
    FFmpegUnavailableError,
    QualityUnavailableError,
    download_youtube_mp4,
    sanitize_download_filename,
    select_mp4_formats,
)
from app.services.ffmpeg import MediaTools
from app.services.youtube import YouTubeServiceError


def progressive_info(**overrides: object) -> dict[str, Any]:
    info: dict[str, Any] = {
        "id": "video-id",
        "title": "Título de teste",
        "duration": 90,
        "webpage_url": "https://www.youtube.com/watch?v=video-id",
        "formats": [
            {
                "format_id": "18",
                "ext": "mp4",
                "height": 360,
                "vcodec": "avc1.42001E",
                "acodec": "mp4a.40.2",
                "filesize": 1_024,
                "tbr": 500,
            }
        ],
    }
    info.update(overrides)
    return info


def split_info(**overrides: object) -> dict[str, Any]:
    info: dict[str, Any] = {
        "id": "video-id",
        "title": "Título de teste",
        "duration": 90,
        "webpage_url": "https://www.youtube.com/watch?v=video-id",
        "formats": [
            {
                "format_id": "137",
                "ext": "mp4",
                "height": 1080,
                "vcodec": "avc1.640028",
                "acodec": "none",
                "filesize": 4_096,
                "tbr": 4_000,
            },
            {
                "format_id": "248",
                "ext": "webm",
                "height": 1080,
                "vcodec": "vp9",
                "acodec": "none",
                "filesize": 3_000,
                "tbr": 3_000,
            },
            {
                "format_id": "140",
                "ext": "m4a",
                "vcodec": "none",
                "acodec": "mp4a.40.2",
                "filesize": 512,
                "abr": 128,
            },
        ],
    }
    info.update(overrides)
    return info


def test_select_mp4_formats_uses_exact_progressive_quality() -> None:
    selection = select_mp4_formats(progressive_info()["formats"], 360)

    assert selection.selector == "18"
    assert selection.requires_ffmpeg is False
    assert selection.estimated_filesize == 1_024


def test_select_mp4_formats_combines_compatible_video_and_audio() -> None:
    selection = select_mp4_formats(split_info()["formats"], 1080)

    assert selection.selector == "137+140"
    assert selection.requires_ffmpeg is True
    assert selection.estimated_filesize == 4_608


def test_select_mp4_formats_rejects_unavailable_quality() -> None:
    with pytest.raises(QualityUnavailableError):
        select_mp4_formats(progressive_info()["formats"], 1080)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ('  Vídeo: teste / capítulo?  ', "Vídeo teste capítulo.mp4"),
        ("CON", "clipflow-con.mp4"),
        ("../\\\x00", "clipflow-video.mp4"),
        (None, "clipflow-video.mp4"),
    ],
)
def test_sanitize_download_filename(title: str | None, expected: str) -> None:
    assert sanitize_download_filename(title) == expected


def test_download_mp4_writes_only_inside_temporary_directory_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            calls["options"] = options

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def extract_info(self, url: str, download: bool) -> dict[str, object]:
            calls["url"] = url
            calls["download"] = download
            options = calls["options"]
            assert isinstance(options, dict)
            output_template = options["outtmpl"]
            assert isinstance(output_template, str)
            output_path = Path(output_template.replace("%(ext)s", "mp4"))
            output_path.write_bytes(b"mock-mp4")
            return progressive_info()

    monkeypatch.setattr(download, "extract_youtube_info", lambda _: progressive_info())
    monkeypatch.setattr(download, "YoutubeDL", FakeYoutubeDL)

    artifact = download_youtube_mp4("https://youtu.be/video-id", 360)
    temporary_root = artifact.path.parent

    assert calls["download"] is True
    assert artifact.path.read_bytes() == b"mock-mp4"
    assert artifact.filename == "Título de teste.mp4"
    assert temporary_root.exists()
    artifact.cleanup()
    assert not temporary_root.exists()


def test_download_rejects_video_above_duration_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        download,
        "extract_youtube_info",
        lambda _: progressive_info(duration=30 * 60 + 1),
    )

    with pytest.raises(DownloadLimitExceededError):
        download_youtube_mp4("https://youtu.be/video-id", 360)


def test_download_requires_ffmpeg_for_split_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(download, "extract_youtube_info", lambda _: split_info())
    monkeypatch.setattr(
        download,
        "detect_media_tools",
        lambda: MediaTools(ffmpeg=None, ffprobe=None),
    )

    with pytest.raises(FFmpegUnavailableError):
        download_youtube_mp4("https://youtu.be/video-id", 1080)


def test_download_maps_yt_dlp_error_and_removes_temporary_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_root: Path | None = None

    class BrokenYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            nonlocal created_root
            output_template = options["outtmpl"]
            assert isinstance(output_template, str)
            created_root = Path(output_template).parent

        def __enter__(self) -> "BrokenYoutubeDL":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def extract_info(self, _: str, download: bool) -> dict[str, object]:
            assert download is True
            raise DownloadError("external extractor failure")

    monkeypatch.setattr(download, "extract_youtube_info", lambda _: progressive_info())
    monkeypatch.setattr(download, "YoutubeDL", BrokenYoutubeDL)

    with pytest.raises(YouTubeServiceError):
        download_youtube_mp4("https://youtu.be/video-id", 360)

    assert created_root is not None
    assert not created_root.exists()
