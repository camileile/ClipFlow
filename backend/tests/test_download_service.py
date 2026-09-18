import tempfile
from pathlib import Path
from typing import Any

import pytest
from yt_dlp.utils import DownloadError

from app.services import download
from app.services.download import (
    DownloadArtifact,
    DownloadProcessingError,
    DownloadLimitExceededError,
    FFmpegUnavailableError,
    IncompatibleMediaError,
    QualityUnavailableError,
    UnsupportedBitrateError,
    download_youtube_mp3,
    download_youtube_mp4,
    sanitize_download_filename,
    select_best_audio_format,
    select_mp4_formats,
)
from app.services.ffmpeg import MediaTools
from app.services.youtube import VideoUnavailableError, YouTubeServiceError


def tiktok_combined_info(duration: int = 18) -> dict[str, Any]:
    return {
        "id": "7412345678901234567",
        "description": "TikTok teste",
        "uploader": "@clipflow",
        "duration": duration,
        "webpage_url": "https://www.tiktok.com/@clipflow/video/7412345678901234567",
        "formats": [
            {
                "format_id": "download_addr-0",
                "vcodec": "h264",
                "acodec": "aac",
                "ext": "mp4",
                "height": 720,
                "fps": 30,
                "tbr": 1400,
                "filesize_approx": 2_500_000,
            }
        ],
    }


def instagram_combined_info(duration: int = 12) -> dict[str, Any]:
    return {
        "id": "C1234567890",
        "description": "Instagram Reel",
        "uploader": "@clipflow",
        "duration": duration,
        "webpage_url": "https://www.instagram.com/reel/C1234567890/",
        "formats": [
            {
                "format_id": "dash-720",
                "ext": "mp4",
                "height": 720,
                "width": 1280,
                "filesize_approx": 2_000_000,
            }
        ],
    }


def test_temporary_cleanup_retries_windows_file_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temporary_directory = tempfile.TemporaryDirectory(prefix="clipflow-test-")
    temporary_root = Path(temporary_directory.name)
    original_cleanup = temporary_directory.cleanup
    attempts = 0

    def flaky_cleanup() -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("file is temporarily locked")
        original_cleanup()

    monkeypatch.setattr(temporary_directory, "cleanup", flaky_cleanup)
    monkeypatch.setattr(download.time, "sleep", lambda _: None)

    DownloadArtifact(
        path=temporary_root / "media.mp4",
        filename="media.mp4",
        _temporary_directory=temporary_directory,
    ).cleanup()

    assert attempts == 3
    assert not temporary_root.exists()


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


def audio_info(**overrides: object) -> dict[str, Any]:
    info: dict[str, Any] = {
        "id": "audio-id",
        "title": "Áudio: teste / capítulo?",
        "channel": "Canal de teste",
        "duration": 90,
        "webpage_url": "https://www.youtube.com/watch?v=audio-id",
        "formats": [
            {
                "format_id": "251",
                "ext": "webm",
                "vcodec": "none",
                "acodec": "opus",
                "abr": 135,
                "asr": 48_000,
                "audio_channels": 2,
                "filesize": 1_500_000,
            },
            {
                "format_id": "140",
                "ext": "m4a",
                "vcodec": "none",
                "acodec": "mp4a.40.2",
                "abr": 129,
                "asr": 44_100,
                "audio_channels": 2,
                "filesize": 1_400_000,
            },
            {
                "format_id": "137",
                "ext": "mp4",
                "height": 1080,
                "vcodec": "avc1.640028",
                "acodec": "none",
                "tbr": 4_000,
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


def test_select_mp4_formats_prefers_direct_https_over_fragmented_stream() -> None:
    info = split_info()
    info["formats"].insert(
        0,
        {
            "format_id": "311",
            "ext": "mp4",
            "protocol": "m3u8_native",
            "height": 1080,
            "vcodec": "avc1.640028",
            "acodec": "none",
            "tbr": 8_000,
        },
    )
    info["formats"][1]["protocol"] = "https"

    selection = select_mp4_formats(info["formats"], 1080)

    assert selection.selector == "137+140"


def test_select_mp4_formats_rejects_unavailable_quality() -> None:
    with pytest.raises(QualityUnavailableError):
        select_mp4_formats(progressive_info()["formats"], 1080)


def test_select_instagram_mp4_accepts_combined_video_and_audio() -> None:
    selection = select_mp4_formats(
        [
            {
                "format_id": "ig-muxed",
                "ext": "mp4",
                "height": 720,
                "vcodec": "unknown-video-codec",
                "acodec": "unknown-audio-codec",
            }
        ],
        720,
        "instagram",
    )

    assert selection.selector == "ig-muxed"
    assert selection.requires_ffmpeg is False


def test_select_instagram_mp4_accepts_combined_1280p() -> None:
    selection = select_mp4_formats(
        [
            {
                "format_id": "ig-1280",
                "ext": "mp4",
                "height": 1280,
                "vcodec": "h264",
                "acodec": "aac",
            }
        ],
        1280,
        "instagram",
    )

    assert selection.selector == "ig-1280"


def test_select_instagram_mp4_uses_requested_quality_among_multiple() -> None:
    formats = [
        {
            "format_id": f"ig-{height}",
            "ext": "mp4",
            "height": height,
            "vcodec": "h264",
            "acodec": "aac",
        }
        for height in (720, 1080, 1280)
    ]

    assert select_mp4_formats(formats, 1080, "instagram").selector == "ig-1080"


def test_select_instagram_mp4_best_available_uses_highest_height() -> None:
    formats = [
        {
            "format_id": f"ig-{height}",
            "ext": "mp4",
            "height": height,
            "vcodec": "h264",
            "acodec": "aac",
        }
        for height in (720, 1280, 1080)
    ]

    assert select_mp4_formats(formats, None, "instagram").selector == "ig-1280"


def test_select_instagram_mp4_merges_separate_mp4_and_m4a_streams() -> None:
    selection = select_mp4_formats(
        [
            {
                "format_id": "ig-video",
                "ext": "mp4",
                "height": 1280,
                "vcodec": "provider-specific-video",
                "acodec": "none",
            },
            {
                "format_id": "ig-audio",
                "ext": "m4a",
                "vcodec": "none",
                "acodec": "provider-specific-audio",
            },
        ],
        1280,
        "instagram",
    )

    assert selection.selector == "ig-video+ig-audio"
    assert selection.requires_ffmpeg is True


def test_select_instagram_mp4_rejects_absence_of_compatible_container() -> None:
    with pytest.raises(IncompatibleMediaError):
        select_mp4_formats(
            [
                {
                    "format_id": "webm-only",
                    "ext": "webm",
                    "height": 1280,
                    "vcodec": "vp9",
                    "acodec": "opus",
                }
            ],
            1280,
            "instagram",
        )


def test_select_instagram_mp4_accepts_silent_video() -> None:
    selection = select_mp4_formats(
        [
            {
                "format_id": "ig-silent",
                "ext": "mp4",
                "height": 1280,
                "vcodec": "avc1.4d401f",
                "acodec": "none",
            }
        ],
        1280,
        "instagram",
    )

    assert selection.selector == "ig-silent"
    assert selection.requires_ffmpeg is False


def test_select_instagram_mp4_rejects_unavailable_quality() -> None:
    with pytest.raises(QualityUnavailableError):
        select_mp4_formats(
            [
                {
                    "format_id": "ig-720",
                    "ext": "mp4",
                    "height": 720,
                    "vcodec": "h264",
                    "acodec": "aac",
                }
            ],
            1280,
            "instagram",
        )


def test_select_best_audio_format_ignores_video_and_prefers_best_audio() -> None:
    selection = select_best_audio_format(audio_info()["formats"])

    assert selection.selector == "251"
    assert selection.requires_ffmpeg is True
    assert selection.estimated_filesize == 1_500_000


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


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Faixa / demo?", "Faixa demo.mp3"),
        ("NUL", "clipflow-nul.mp3"),
        (None, "clipflow-audio.mp3"),
    ],
)
def test_sanitize_mp3_filename(title: str | None, expected: str) -> None:
    assert sanitize_download_filename(title, "mp3") == expected


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


@pytest.mark.parametrize("audio_quality", [128, 192, 256, 320])
def test_download_mp3_uses_selected_bitrate_and_audio_only_stream(
    monkeypatch: pytest.MonkeyPatch,
    audio_quality: int,
) -> None:
    calls: dict[str, object] = {}

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            calls["options"] = options

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def extract_info(self, _: str, download: bool) -> dict[str, object]:
            assert download is True
            options = calls["options"]
            assert isinstance(options, dict)
            output_template = options["outtmpl"]
            assert isinstance(output_template, str)
            Path(output_template.replace("%(ext)s", "mp3")).write_bytes(b"mock-mp3")
            return audio_info()

    monkeypatch.setattr(download, "extract_youtube_info", lambda _: audio_info())
    monkeypatch.setattr(download, "YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(
        download,
        "detect_media_tools",
        lambda: MediaTools(
            ffmpeg="C:/tools/ffmpeg.exe",
            ffprobe="C:/tools/ffprobe.exe",
        ),
    )

    artifact = download_youtube_mp3("https://youtu.be/audio-id", audio_quality)
    temporary_root = artifact.path.parent
    options = calls["options"]

    assert isinstance(options, dict)
    assert options["format"] == "251"
    assert options["noprogress"] is True
    assert options["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": str(audio_quality),
        }
    ]
    assert artifact.path.read_bytes() == b"mock-mp3"
    assert artifact.filename == "Áudio teste capítulo.mp3"
    artifact.cleanup()
    assert not temporary_root.exists()


def test_download_mp3_rejects_unsupported_bitrate() -> None:
    with pytest.raises(UnsupportedBitrateError):
        download_youtube_mp3("https://youtu.be/audio-id", 160)


def test_download_mp3_requires_ffmpeg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(download, "extract_youtube_info", lambda _: audio_info())
    monkeypatch.setattr(
        download,
        "detect_media_tools",
        lambda: MediaTools(ffmpeg=None, ffprobe=None),
    )

    with pytest.raises(FFmpegUnavailableError):
        download_youtube_mp3("https://youtu.be/audio-id", 192)


def test_download_mp3_rejects_video_above_duration_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        download,
        "extract_youtube_info",
        lambda _: audio_info(duration=30 * 60 + 1),
    )

    with pytest.raises(DownloadLimitExceededError):
        download_youtube_mp3("https://youtu.be/audio-id", 192)


def test_download_mp3_rejects_estimated_file_above_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(download, "MAX_DOWNLOAD_FILESIZE_BYTES", 100)
    monkeypatch.setattr(download, "extract_youtube_info", lambda _: audio_info())

    with pytest.raises(DownloadLimitExceededError):
        download_youtube_mp3("https://youtu.be/audio-id", 320)


def test_download_mp3_preserves_unavailable_video_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_: object) -> dict[str, Any]:
        raise VideoUnavailableError

    monkeypatch.setattr(download, "extract_youtube_info", unavailable)

    with pytest.raises(VideoUnavailableError):
        download_youtube_mp3("https://youtu.be/audio-id", 192)


def test_download_mp3_maps_conversion_error_and_cleans_up(
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
            raise DownloadError("Postprocessing: audio conversion failed")

    monkeypatch.setattr(download, "extract_youtube_info", lambda _: audio_info())
    monkeypatch.setattr(download, "YoutubeDL", BrokenYoutubeDL)
    monkeypatch.setattr(
        download,
        "detect_media_tools",
        lambda: MediaTools(
            ffmpeg="C:/tools/ffmpeg.exe",
            ffprobe="C:/tools/ffprobe.exe",
        ),
    )

    with pytest.raises(DownloadProcessingError):
        download_youtube_mp3("https://youtu.be/audio-id", 192)

    assert created_root is not None
    assert not created_root.exists()


def test_download_tiktok_mp4_reuses_shared_pipeline(
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

        def extract_info(self, _: str, download: bool) -> dict[str, Any]:
            assert download is True
            options = calls["options"]
            assert isinstance(options, dict)
            output_template = options["outtmpl"]
            assert isinstance(output_template, str)
            Path(output_template.replace("%(ext)s", "mp4")).write_bytes(b"tiktok-mp4")
            return tiktok_combined_info()

    monkeypatch.setattr(download, "extract_tiktok_info", lambda _: tiktok_combined_info())
    monkeypatch.setattr(download, "YoutubeDL", FakeYoutubeDL)

    artifact = download.download_media_mp4(
        "https://www.tiktok.com/@clipflow/video/7412345678901234567",
        720,
    )
    temporary_root = artifact.path.parent

    assert artifact.path.read_bytes() == b"tiktok-mp4"
    assert artifact.filename == "TikTok teste.mp4"
    assert isinstance(calls["options"], dict)
    assert calls["options"]["format"] == "download_addr-0"
    artifact.cleanup()
    assert not temporary_root.exists()


def test_download_tiktok_mp3_accepts_combined_audio_source(
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

        def extract_info(self, _: str, download: bool) -> dict[str, Any]:
            assert download is True
            options = calls["options"]
            assert isinstance(options, dict)
            output_template = options["outtmpl"]
            assert isinstance(output_template, str)
            Path(output_template.replace("%(ext)s", "mp3")).write_bytes(b"tiktok-mp3")
            return tiktok_combined_info()

    monkeypatch.setattr(download, "extract_tiktok_info", lambda _: tiktok_combined_info())
    monkeypatch.setattr(download, "YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(
        download,
        "detect_media_tools",
        lambda: MediaTools(
            ffmpeg="C:/tools/ffmpeg.exe",
            ffprobe="C:/tools/ffprobe.exe",
        ),
    )

    artifact = download.download_media_mp3(
        "https://vm.tiktok.com/ZMshort/",
        192,
    )
    temporary_root = artifact.path.parent

    assert artifact.path.read_bytes() == b"tiktok-mp3"
    assert artifact.filename == "TikTok teste.mp3"
    assert isinstance(calls["options"], dict)
    assert calls["options"]["format"] == "download_addr-0"
    assert calls["options"]["postprocessors"][0]["preferredquality"] == "192"
    artifact.cleanup()
    assert not temporary_root.exists()


def test_download_tiktok_applies_shared_duration_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        download,
        "extract_tiktok_info",
        lambda _: tiktok_combined_info(duration=30 * 60 + 1),
    )

    with pytest.raises(DownloadLimitExceededError):
        download.download_media_mp4("https://vm.tiktok.com/ZMshort/", 720)


def test_tiktok_filename_uses_platform_fallback_without_description() -> None:
    assert download._download_title({"title": None, "description": ""}, "tiktok") == (
        "clipflow-tiktok"
    )


@pytest.mark.parametrize(
    ("extension", "expected"),
    [("mp4", "Instagram Reel.mp4"), ("mp3", "Instagram Reel.mp3")],
)
def test_download_instagram_reuses_shared_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    extension: str,
    expected: str,
) -> None:
    calls: dict[str, object] = {}

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            calls["options"] = options

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def extract_info(self, _: str, download: bool) -> dict[str, Any]:
            assert download is True
            options = calls["options"]
            assert isinstance(options, dict)
            output_template = options["outtmpl"]
            assert isinstance(output_template, str)
            Path(output_template.replace("%(ext)s", extension)).write_bytes(b"instagram")
            return instagram_combined_info()

    monkeypatch.setattr(
        download, "extract_instagram_info", lambda _: instagram_combined_info()
    )
    monkeypatch.setattr(download, "YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(
        download,
        "detect_media_tools",
        lambda: MediaTools(
            ffmpeg="C:/tools/ffmpeg.exe",
            ffprobe="C:/tools/ffprobe.exe",
        ),
    )

    if extension == "mp4":
        artifact = download.download_media_mp4(
            "https://www.instagram.com/reel/C1234567890/", 720
        )
    else:
        artifact = download.download_media_mp3(
            "https://www.instagram.com/reel/C1234567890/", 192
        )

    temporary_root = artifact.path.parent
    assert artifact.path.read_bytes() == b"instagram"
    assert artifact.filename == expected
    assert isinstance(calls["options"], dict)
    assert calls["options"]["format"] == "dash-720"
    if extension == "mp3":
        assert calls["options"]["postprocessors"][0]["preferredquality"] == "192"
    artifact.cleanup()
    assert not temporary_root.exists()


def test_download_instagram_applies_shared_duration_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        download,
        "extract_instagram_info",
        lambda _: instagram_combined_info(duration=30 * 60 + 1),
    )

    with pytest.raises(DownloadLimitExceededError):
        download.download_media_mp4(
            "https://www.instagram.com/reel/C1234567890/", 720
        )
