from pathlib import Path
from typing import Any

import pytest
from yt_dlp.utils import DownloadError

from app.services import twitter
from app.services.twitter import (
    TwitterAuthenticationRequiredError,
    TwitterMultipleMediaError,
    TwitterNoVideoError,
    TwitterRateLimitedError,
    TwitterServiceError,
    analyze_twitter,
    normalize_twitter_info,
    validate_twitter_url,
)
from app.services.youtube import RemovedVideoError, VideoUnavailableError


def twitter_info(**overrides: object) -> dict[str, Any]:
    info: dict[str, Any] = {
        "id": "1234567890",
        "title": "ClipFlow test post",
        "description": "A public video post",
        "uploader": "ClipFlow",
        "uploader_id": "clipflow",
        "duration": 16.8,
        "webpage_url": "https://x.com/clipflow/status/1234567890",
        "thumbnail": "https://pbs.twimg.com/ext_tw_video_thumb/123/pu/img/test.jpg",
        "formats": [
            {
                "format_id": "http-832000",
                "ext": "mp4",
                "height": 720,
                "width": 1280,
                "vcodec": "h264",
                "acodec": "aac",
                "protocol": "https",
                "tbr": 832,
            },
            {
                "format_id": "http-256000",
                "ext": "mp4",
                "height": 360,
                "width": 640,
                "vcodec": "h264",
                "acodec": "aac",
                "protocol": "https",
                "tbr": 256,
            },
        ],
    }
    info.update(overrides)
    return info


def test_normalize_twitter_video_metadata_and_resolutions() -> None:
    media = normalize_twitter_info(
        twitter_info(),
        "https://x.com/clipflow/status/1234567890",
    )

    assert media.id == "1234567890"
    assert media.title == "ClipFlow test post"
    assert media.author == "ClipFlow"
    assert media.duration == 16
    assert media.qualities == [720, 360]
    assert str(media.thumbnail).startswith("https://pbs.twimg.com/")
    assert any(item.type == "audio" for item in media.formats)


def test_normalize_twitter_falls_back_without_title_or_author() -> None:
    media = normalize_twitter_info(
        twitter_info(title=None, description=None, uploader=None, channel=None),
        "https://twitter.com/clipflow/status/1234567890",
    )
    assert media.title == "X video"
    assert media.author is None


def test_normalize_twitter_uses_author_fallback_and_missing_thumbnail() -> None:
    media = normalize_twitter_info(
        twitter_info(title=None, description=None, thumbnail=None),
        "https://x.com/clipflow/status/1234567890",
    )
    assert media.title == "Post by ClipFlow"
    assert media.thumbnail is None


def test_normalize_twitter_rejects_post_without_video() -> None:
    with pytest.raises(TwitterNoVideoError):
        normalize_twitter_info(
            twitter_info(formats=[]),
            "https://x.com/clipflow/status/1234567890",
        )


def test_normalize_twitter_rejects_multiple_video_entries() -> None:
    with pytest.raises(TwitterMultipleMediaError):
        normalize_twitter_info(
            {
                "_type": "playlist",
                "id": "1234567890",
                "entries": [twitter_info(id="one"), twitter_info(id="two")],
            },
            "https://x.com/clipflow/status/1234567890",
        )


def test_normalize_twitter_accepts_single_playlist_entry() -> None:
    media = normalize_twitter_info(
        {
            "_type": "playlist",
            "title": "Post text",
            "uploader": "ClipFlow",
            "entries": [twitter_info(title=None, uploader=None)],
        },
        "https://twitter.com/clipflow/status/1234567890",
    )
    assert media.title == "Post text"
    assert media.author == "ClipFlow"


def test_normalize_twitter_recognizes_extractor_http_and_hls_audio_capabilities() -> None:
    media = normalize_twitter_info(
        twitter_info(
            formats=[
                {
                    "format_id": "hls-audio-128000-Audio",
                    "ext": "mp4",
                    "vcodec": "none",
                    "acodec": None,
                    "protocol": "m3u8_native",
                    "tbr": 128,
                },
                {
                    "format_id": "http-2176",
                    "ext": "mp4",
                    "height": 720,
                    "width": 1280,
                    "vcodec": None,
                    "acodec": None,
                    "protocol": "https",
                    "tbr": 2176,
                },
            ]
        ),
        "https://x.com/clipflow/status/1234567890",
    )

    assert media.qualities == [720]
    assert any(item.type == "audio" for item in media.formats)


def test_normalize_twitter_keeps_animated_media_silent() -> None:
    media = normalize_twitter_info(
        twitter_info(
            formats=[
                {
                    "format_id": "http-832",
                    "ext": "mp4",
                    "height": 720,
                    "width": 1280,
                    "vcodec": None,
                    "acodec": None,
                    "protocol": "https",
                },
                {
                    "format_id": "hls-832",
                    "ext": "mp4",
                    "height": 720,
                    "width": 1280,
                    "vcodec": "h264",
                    "acodec": "none",
                    "protocol": "m3u8_native",
                },
            ]
        ),
        "https://x.com/clipflow/status/1234567890",
    )

    assert media.qualities == [720]
    assert all(item.type != "audio" for item in media.formats)


@pytest.mark.parametrize(
    "url",
    [
        "https://x.com/user/status/1234567890",
        "https://twitter.com/i/web/status/1234567890?ref_src=test",
        "https://mobile.twitter.com/user/status/1234567890/video/1",
    ],
)
def test_validate_twitter_accepts_status_urls(url: str) -> None:
    validate_twitter_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://x.com/user",
        "https://twitter.com/i/spaces/1OwxWwQOPlNxQ",
        "https://x.com/user/status/not-a-number",
    ],
)
def test_validate_twitter_rejects_non_post_urls(url: str) -> None:
    with pytest.raises(TwitterNoVideoError):
        validate_twitter_url(url)


def test_analyze_twitter_uses_yt_dlp_without_downloading(
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
            return twitter_info()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(twitter, "YoutubeDL", FakeYoutubeDL)
    media = analyze_twitter("https://x.com/clipflow/status/1234567890")

    assert media.id == "1234567890"
    assert calls["download"] is False
    assert isinstance(calls["options"], dict)
    assert calls["options"]["skip_download"] is True
    assert calls["options"]["noplaylist"] is False
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("message", "expected_error"),
    [
        ("This is a protected tweet; login required", TwitterAuthenticationRequiredError),
        ("HTTP Error 429: Too Many Requests", TwitterRateLimitedError),
        ("No video could be found in this tweet", TwitterNoVideoError),
        ("This post has been removed", RemovedVideoError),
        ("Requested tweet is unavailable", VideoUnavailableError),
        ("Unexpected extractor response", TwitterServiceError),
    ],
)
def test_analyze_twitter_maps_expected_extractor_errors(
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

    monkeypatch.setattr(twitter, "YoutubeDL", BrokenYoutubeDL)
    with pytest.raises(expected_error):
        analyze_twitter("https://x.com/clipflow/status/1234567890")
