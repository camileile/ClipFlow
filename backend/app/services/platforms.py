from typing import Literal, TypeAlias
from urllib.parse import urlparse


MediaPlatform: TypeAlias = Literal["youtube", "tiktok", "instagram", "twitter"]

YOUTUBE_HOSTS = {"youtube.com", "youtu.be", "youtube-nocookie.com"}
TIKTOK_HOSTS = {"tiktok.com"}
INSTAGRAM_HOSTS = {"instagram.com"}
TWITTER_HOSTS = {"twitter.com", "x.com"}


class InvalidMediaUrlError(Exception):
    pass


class UnsupportedPlatformError(Exception):
    pass


def _matches_host(hostname: str, allowed_hosts: set[str]) -> bool:
    return any(
        hostname == host or hostname.endswith(f".{host}") for host in allowed_hosts
    )


def detect_platform(url: str) -> MediaPlatform:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")

    if parsed.scheme not in {"http", "https"} or not hostname:
        raise InvalidMediaUrlError

    try:
        port = parsed.port
    except ValueError as error:
        raise InvalidMediaUrlError from error

    if parsed.username or parsed.password or port not in {None, 80, 443}:
        raise InvalidMediaUrlError

    if _matches_host(hostname, YOUTUBE_HOSTS):
        return "youtube"
    if _matches_host(hostname, TIKTOK_HOSTS):
        return "tiktok"
    if _matches_host(hostname, INSTAGRAM_HOSTS):
        return "instagram"
    if _matches_host(hostname, TWITTER_HOSTS):
        return "twitter"
    raise UnsupportedPlatformError
