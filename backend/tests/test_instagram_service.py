import base64
import json
from pathlib import Path
from typing import Any

import pytest
from yt_dlp.utils import DownloadError

from app.services import instagram
from app.services.instagram import (
    InstagramAuthenticationRequiredError,
    InstagramCarouselError,
    InstagramNoVideoError,
    InstagramRateLimitedError,
    InstagramServiceError,
    analyze_instagram,
    normalize_instagram_info,
)
from app.services.youtube import RemovedVideoError


def instagram_info(**overrides: object) -> dict[str, Any]:
    info: dict[str, Any] = {
        "id": "C1234567890",
        "description": "Um Reel público de teste",
        "uploader": "@clipflow",
        "duration": 12.9,
        "webpage_url": "https://www.instagram.com/reel/C1234567890/",
        "thumbnail": "https://scontent.cdninstagram.com/preview.jpg",
        "formats": [
            {
                "format_id": "dash-720",
                "ext": "mp4",
                "height": 720,
                "width": 1280,
                "filesize_approx": 2_000_000,
            },
            {
                "format_id": "dash-1080",
                "ext": "mp4",
                "height": 1080,
                "width": 1920,
            },
        ],
    }
    info.update(overrides)
    return info


def test_normalize_instagram_reel_metadata_and_qualities() -> None:
    media = normalize_instagram_info(
        instagram_info(),
        "https://www.instagram.com/reel/C1234567890/",
    )

    assert media.id == "C1234567890"
    assert media.title == "Um Reel público de teste"
    assert media.author == "@clipflow"
    assert media.duration == 12
    assert media.qualities == [1080, 720]
    assert str(media.thumbnail) == "https://scontent.cdninstagram.com/preview.jpg"
    assert any(item.type == "audio" for item in media.formats)


def test_normalize_instagram_post_with_single_video() -> None:
    media = normalize_instagram_info(
        instagram_info(webpage_url="https://www.instagram.com/p/C1234567890/"),
        "https://www.instagram.com/p/C1234567890/",
    )
    assert media.qualities == [1080, 720]


def test_normalize_instagram_handles_missing_optional_metadata() -> None:
    media = normalize_instagram_info(
        instagram_info(
            title=None,
            description=None,
            uploader=None,
            duration=None,
            thumbnail=None,
            formats=[instagram_info()["formats"][0]],
        ),
        "https://www.instagram.com/reel/C1234567890/",
    )

    assert media.title == "Instagram Reel"
    assert media.author is None
    assert media.duration is None
    assert media.thumbnail is None
    assert media.qualities == [720]


def test_normalize_instagram_recovers_duration_from_extractor_format_metadata() -> None:
    metadata = base64.urlsafe_b64encode(json.dumps({"duration_s": 13}).encode()).decode()
    media = normalize_instagram_info(
        instagram_info(
            duration=None,
            formats=[
                {
                    "format_id": "dash-720",
                    "ext": "mp4",
                    "height": 720,
                    "vcodec": "h264",
                    "acodec": "aac",
                    "url": f"https://cdninstagram.com/video.mp4?efg={metadata}",
                }
            ],
        ),
        "https://www.instagram.com/reel/C1234567890/",
    )

    assert media.duration == 13


def test_normalize_instagram_rejects_image_only_post() -> None:
    with pytest.raises(InstagramNoVideoError):
        normalize_instagram_info(
            instagram_info(
                formats=[{"format_id": "image", "ext": "jpg", "vcodec": "none"}]
            ),
            "https://www.instagram.com/p/C1234567890/",
        )


def test_normalize_instagram_rejects_carousel() -> None:
    with pytest.raises(InstagramCarouselError):
        normalize_instagram_info(
            instagram_info(_type="playlist", entries=[instagram_info()]),
            "https://www.instagram.com/p/C1234567890/",
        )


def test_analyze_instagram_uses_yt_dlp_without_downloading(
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
            return instagram_info()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(instagram, "YoutubeDL", FakeYoutubeDL)

    media = analyze_instagram("https://www.instagram.com/reel/C1234567890/")

    assert media.id == "C1234567890"
    assert calls["download"] is False
    assert isinstance(calls["options"], dict)
    assert calls["options"]["skip_download"] is True
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("message", "expected_error"),
    [
        ("Login required to view this private media", InstagramAuthenticationRequiredError),
        ("HTTP Error 429: Too Many Requests", InstagramRateLimitedError),
        ("This post has been removed", RemovedVideoError),
        ("Unexpected extractor response", InstagramServiceError),
    ],
)
def test_analyze_instagram_maps_expected_extractor_errors(
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

    monkeypatch.setattr(instagram, "YoutubeDL", BrokenYoutubeDL)

    with pytest.raises(expected_error):
        analyze_instagram("https://www.instagram.com/reel/C1234567890/")
