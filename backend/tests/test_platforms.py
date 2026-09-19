import pytest

from app.services.platforms import (
    InvalidMediaUrlError,
    UnsupportedPlatformError,
    detect_platform,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=video-id",
        "https://youtu.be/video-id",
        "https://music.youtube.com/watch?v=video-id",
    ],
)
def test_detect_platform_recognizes_youtube(url: str) -> None:
    assert detect_platform(url) == "youtube"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.tiktok.com/@creator/video/1234567890",
        "https://m.tiktok.com/v/1234567890.html",
        "https://vm.tiktok.com/ZMshort/",
    ],
)
def test_detect_platform_recognizes_tiktok_and_short_links(url: str) -> None:
    assert detect_platform(url) == "tiktok"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/reel/ABC123/",
        "https://instagram.com/p/ABC123/",
    ],
)
def test_detect_platform_recognizes_instagram_video_urls(url: str) -> None:
    assert detect_platform(url) == "instagram"


@pytest.mark.parametrize(
    "url",
    [
        "https://x.com/clipflow/status/1234567890",
        "https://www.twitter.com/clipflow/status/1234567890?ref_src=test",
        "https://mobile.twitter.com/clipflow/status/1234567890",
    ],
)
def test_detect_platform_recognizes_x_and_twitter_hosts(url: str) -> None:
    assert detect_platform(url) == "twitter"


@pytest.mark.parametrize(
    "url",
    [
        "https://tiktok.com.example.org/@creator/video/123",
        "https://instagram.com.evil.example/reel/ABC123/",
        "https://twitter.com.evil.example/user/status/123",
        "https://x.com.evil.example/user/status/123",
        "https://example.com/video/123",
    ],
)
def test_detect_platform_rejects_unsupported_hosts(url: str) -> None:
    with pytest.raises(UnsupportedPlatformError):
        detect_platform(url)


@pytest.mark.parametrize(
    "url",
    ["ftp://www.tiktok.com/video/123", "https://user@www.tiktok.com/video/123"],
)
def test_detect_platform_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(InvalidMediaUrlError):
        detect_platform(url)
