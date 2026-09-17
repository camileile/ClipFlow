from pathlib import Path
from typing import Any

import pytest

from app.services import youtube
from app.services.youtube import (
    UnexpectedYouTubeError,
    UnsupportedPlatformError,
    analyze_youtube,
    normalize_video_info,
    validate_youtube_url,
)


def test_validate_youtube_url_accepts_common_variants() -> None:
    valid_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
    ]

    for url in valid_urls:
        validate_youtube_url(url)


def test_validate_youtube_url_rejects_lookalike_domain() -> None:
    with pytest.raises(UnsupportedPlatformError):
        validate_youtube_url("https://youtube.com.example.org/watch?v=test")


def test_normalize_video_info_deduplicates_and_orders_qualities() -> None:
    info: dict[str, Any] = {
        "id": "video-id",
        "title": "Título",
        "channel": "Canal",
        "duration": 241.9,
        "webpage_url": "https://www.youtube.com/watch?v=video-id",
        "thumbnails": [
            {"url": "https://i.ytimg.com/small.jpg", "width": 320, "height": 180},
            {"url": "https://i.ytimg.com/large.jpg", "width": 1280, "height": 720},
        ],
        "formats": [
            {
                "format_id": "248",
                "vcodec": "vp9",
                "acodec": "none",
                "ext": "webm",
                "height": 1080,
                "fps": 30,
            },
            {
                "format_id": "137",
                "vcodec": "avc1",
                "acodec": "none",
                "ext": "mp4",
                "height": 1080,
                "fps": 30,
            },
            {
                "format_id": "22",
                "vcodec": "avc1",
                "acodec": "mp4a",
                "ext": "mp4",
                "height": 720,
                "fps": 30,
            },
            {
                "format_id": "18",
                "vcodec": "avc1",
                "acodec": "mp4a",
                "ext": "mp4",
                "height": 360,
                "fps": 30,
            },
            {
                "format_id": "140",
                "vcodec": "none",
                "acodec": "mp4a",
                "ext": "m4a",
                "abr": 129,
            },
        ],
    }

    media = normalize_video_info(
        info,
        "https://www.youtube.com/watch?v=video-id",
    )

    assert media.qualities == [1080, 720, 360]
    assert [item.quality for item in media.formats if item.type == "video"] == [
        1080,
        720,
        360,
    ]
    assert media.formats[0].extension == "mp4"
    assert str(media.thumbnail) == "https://i.ytimg.com/large.jpg"
    assert media.duration == 241


def test_normalize_video_info_accepts_missing_thumbnail_and_duration() -> None:
    media = normalize_video_info(
        {"id": "video-id", "title": "Título", "formats": []},
        "https://youtu.be/video-id",
    )

    assert media.thumbnail is None
    assert media.duration is None
    assert media.author is None
    assert media.qualities == []


def test_analyze_youtube_never_downloads_media(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
            return {"id": "video-id", "title": "Título", "formats": []}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(youtube, "YoutubeDL", FakeYoutubeDL)

    media = analyze_youtube("https://youtu.be/video-id")

    assert media.id == "video-id"
    assert calls["download"] is False
    assert isinstance(calls["options"], dict)
    assert calls["options"]["skip_download"] is True
    assert list(tmp_path.iterdir()) == []


def test_analyze_youtube_maps_unexpected_extractor_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenYoutubeDL:
        def __init__(self, _: dict[str, object]) -> None:
            pass

        def __enter__(self) -> "BrokenYoutubeDL":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def extract_info(self, _: str, download: bool) -> dict[str, object]:
            assert download is False
            raise RuntimeError("sensitive internal failure")

    monkeypatch.setattr(youtube, "YoutubeDL", BrokenYoutubeDL)

    with pytest.raises(UnexpectedYouTubeError):
        analyze_youtube("https://www.youtube.com/watch?v=video-id")
