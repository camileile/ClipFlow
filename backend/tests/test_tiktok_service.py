from pathlib import Path
from typing import Any

import pytest
from yt_dlp.utils import DownloadError

from app.services import tiktok
from app.services.tiktok import analyze_tiktok
from app.services.youtube import (
    PrivateVideoError,
    RemovedVideoError,
    VideoUnavailableError,
    normalize_media_info,
)


def tiktok_info(**overrides: object) -> dict[str, Any]:
    info: dict[str, Any] = {
        "id": "7412345678901234567",
        "description": "Descrição pública do TikTok",
        "uploader": "@clipflow",
        "duration": 18.8,
        "webpage_url": "https://www.tiktok.com/@clipflow/video/7412345678901234567",
        "thumbnail": "https://p16-sign.tiktokcdn-us.com/preview.jpeg",
        "formats": [
            {
                "format_id": "download_addr-0",
                "vcodec": "h264",
                "acodec": "aac",
                "ext": "mp4",
                "height": 720,
                "width": 1280,
                "fps": 30,
                "tbr": 1400,
                "filesize_approx": 2_500_000,
            },
            {
                "format_id": "play_addr-0",
                "vcodec": "h264",
                "acodec": "aac",
                "ext": "mp4",
                "height": 576,
                "width": 1024,
                "fps": 30,
                "tbr": 900,
            },
        ],
    }
    info.update(overrides)
    return info


def test_normalize_tiktok_metadata_and_qualities() -> None:
    media = normalize_media_info(
        tiktok_info(),
        "https://vm.tiktok.com/ZMshort/",
        platform="tiktok",
    )

    assert media.id == "7412345678901234567"
    assert media.title == "Descrição pública do TikTok"
    assert media.author == "@clipflow"
    assert media.duration == 18
    assert media.qualities == [720, 576]
    assert str(media.thumbnail) == "https://p16-sign.tiktokcdn-us.com/preview.jpeg"
    assert any(item.type == "audio" for item in media.formats)


def test_normalize_tiktok_handles_missing_optional_metadata() -> None:
    media = normalize_media_info(
        {"id": "123", "formats": []},
        "https://www.tiktok.com/@clipflow/video/123",
        platform="tiktok",
    )

    assert media.title == "Vídeo do TikTok"
    assert media.author is None
    assert media.duration is None
    assert media.thumbnail is None
    assert media.qualities == []


def test_analyze_tiktok_uses_yt_dlp_without_downloading(
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

        def extract_info(self, url: str, download: bool) -> dict[str, Any]:
            calls["url"] = url
            calls["download"] = download
            return tiktok_info()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tiktok, "YoutubeDL", FakeYoutubeDL)

    media = analyze_tiktok("https://vm.tiktok.com/ZMshort/")

    assert media.id == "7412345678901234567"
    assert calls["download"] is False
    assert isinstance(calls["options"], dict)
    assert calls["options"]["skip_download"] is True
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("message", "expected_error"),
    [
        ("This video is private", PrivateVideoError),
        ("This video has been deleted", RemovedVideoError),
        ("Video unavailable", VideoUnavailableError),
    ],
)
def test_analyze_tiktok_maps_expected_extractor_errors(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
    expected_error: type[Exception],
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
            raise DownloadError(message)

    monkeypatch.setattr(tiktok, "YoutubeDL", BrokenYoutubeDL)

    with pytest.raises(expected_error):
        analyze_tiktok("https://www.tiktok.com/@clipflow/video/123")
