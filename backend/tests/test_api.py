from collections.abc import AsyncIterator
import tempfile
from pathlib import Path

import pytest
from httpx2 import ASGITransport, AsyncClient

from app.api import routes
from app.main import app
from app.schemas import MediaFormat, MediaInfo
from app.services.download import (
    AudioUnavailableError,
    DownloadArtifact,
    DownloadLimitExceededError,
    FFmpegUnavailableError,
    QualityUnavailableError,
)
from app.services.twitter import (
    TwitterAuthenticationRequiredError,
    TwitterMultipleMediaError,
    TwitterNoVideoError,
    TwitterRateLimitedError,
)
from app.services.instagram import (
    InstagramAuthenticationRequiredError,
    InstagramNoVideoError,
    InstagramRateLimitedError,
)
from app.services.youtube import (
    UnexpectedYouTubeError,
    UnsupportedPlatformError,
    VideoUnavailableError,
    YouTubeServiceError,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client


@pytest.fixture
def sample_media() -> MediaInfo:
    return MediaInfo(
        id="dQw4w9WgXcQ",
        title="Vídeo real de teste",
        author="Canal de teste",
        duration=213,
        thumbnail="https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        original_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        qualities=[1080, 720, 360],
        formats=[
            MediaFormat(
                format_id="137",
                type="video",
                extension="mp4",
                quality=1080,
                fps=30,
            )
        ],
    )


async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "clipflow-api"}


async def test_analyze_youtube_url_returns_real_contract(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_media: MediaInfo,
) -> None:
    monkeypatch.setattr(
        routes,
        "analyze_media_url",
        lambda _: ("youtube", sample_media),
    )

    response = await client.post(
        "/api/analyze",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "platform": "youtube",
        "media": {
            "id": "dQw4w9WgXcQ",
            "title": "Vídeo real de teste",
            "author": "Canal de teste",
            "duration": 213,
            "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
            "original_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "qualities": [1080, 720, 360],
            "formats": [
                {
                    "format_id": "137",
                    "type": "video",
                    "extension": "mp4",
                    "quality": 1080,
                    "fps": 30.0,
                    "bitrate": None,
                    "filesize": None,
                }
            ],
        },
    }


async def test_analyze_tiktok_url_returns_shared_contract(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media = MediaInfo(
        id="7412345678901234567",
        title="TikTok público",
        author="@clipflow",
        duration=18,
        thumbnail=None,
        original_url="https://www.tiktok.com/@clipflow/video/7412345678901234567",
        qualities=[720],
        formats=[],
    )
    monkeypatch.setattr(
        routes,
        "analyze_media_url",
        lambda _: ("tiktok", media),
    )

    response = await client.post(
        "/api/analyze",
        json={"url": "https://vm.tiktok.com/ZMshort/"},
    )

    assert response.status_code == 200
    assert response.json()["platform"] == "tiktok"
    assert response.json()["media"]["title"] == "TikTok público"


async def test_analyze_instagram_url_returns_shared_contract(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media = MediaInfo(
        id="C1234567890",
        title="Instagram Reel",
        author="@clipflow",
        duration=12,
        thumbnail=None,
        original_url="https://www.instagram.com/reel/C1234567890/",
        qualities=[720],
        formats=[],
    )
    monkeypatch.setattr(routes, "analyze_media_url", lambda _: ("instagram", media))

    response = await client.post(
        "/api/analyze",
        json={"url": "https://www.instagram.com/reel/C1234567890/"},
    )

    assert response.status_code == 200
    assert response.json()["platform"] == "instagram"
    assert response.json()["media"]["author"] == "@clipflow"


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (
            InstagramNoVideoError(),
            422,
            "Este post do Instagram não contém um vídeo compatível.",
        ),
        (
            InstagramAuthenticationRequiredError(),
            403,
            "Esta mídia do Instagram é privada ou exige login.",
        ),
        (
            InstagramRateLimitedError(),
            429,
            "O Instagram bloqueou temporariamente a solicitação. Tente novamente mais tarde.",
        ),
    ],
)
async def test_analyze_instagram_maps_safe_errors(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status_code: int,
    detail: str,
) -> None:
    def fail(_: object) -> MediaInfo:
        raise error

    monkeypatch.setattr(routes, "analyze_media_url", fail)

    response = await client.post(
        "/api/analyze",
        json={"url": "https://www.instagram.com/p/C1234567890/"},
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


async def test_analyze_twitter_url_returns_shared_contract(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media = MediaInfo(
        id="1234567890",
        title="Public X video",
        author="@clipflow",
        duration=16,
        thumbnail=None,
        original_url="https://x.com/clipflow/status/1234567890",
        qualities=[720, 360],
        formats=[],
    )
    monkeypatch.setattr(routes, "analyze_media_url", lambda _: ("twitter", media))

    response = await client.post(
        "/api/analyze",
        json={"url": "https://x.com/clipflow/status/1234567890"},
    )

    assert response.status_code == 200
    assert response.json()["platform"] == "twitter"
    assert response.json()["media"]["qualities"] == [720, 360]


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (
            TwitterNoVideoError(),
            422,
            "Este post do X/Twitter não contém um vídeo compatível.",
        ),
        (
            TwitterMultipleMediaError(),
            422,
            "Posts do X/Twitter com múltiplos vídeos ainda não são suportados.",
        ),
        (
            TwitterAuthenticationRequiredError(),
            403,
            "Este post do X/Twitter é protegido ou exige login.",
        ),
        (
            TwitterRateLimitedError(),
            429,
            "O X/Twitter rejeitou temporariamente a solicitação. Tente novamente mais tarde.",
        ),
    ],
)
async def test_analyze_twitter_maps_safe_errors(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status_code: int,
    detail: str,
) -> None:
    def fail(_: object) -> MediaInfo:
        raise error

    monkeypatch.setattr(routes, "analyze_media_url", fail)
    response = await client.post(
        "/api/analyze",
        json={"url": "https://twitter.com/clipflow/status/1234567890"},
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


async def test_analyze_rejects_malformed_url(client: AsyncClient) -> None:
    response = await client.post("/api/analyze", json={"url": "not-a-url"})

    assert response.status_code == 422


async def test_analyze_rejects_unsupported_domain(client: AsyncClient) -> None:
    response = await client.post(
        "/api/analyze",
        json={"url": "https://example.com/media/123"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Esta plataforma ainda não é suportada. Use YouTube, TikTok, Instagram ou X/Twitter."
    }


async def test_analyze_handles_unavailable_video(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_: object) -> MediaInfo:
        raise VideoUnavailableError

    monkeypatch.setattr(
        routes,
        "analyze_media_url",
        lambda url: ("youtube", unavailable(url)),
    )

    response = await client.post(
        "/api/analyze",
        json={"url": "https://youtu.be/unavailable"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Este vídeo não existe ou não está disponível."
    }


async def test_analyze_hides_unexpected_extractor_error(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected(_: object) -> MediaInfo:
        raise UnexpectedYouTubeError("internal extractor detail")

    monkeypatch.setattr(
        routes,
        "analyze_media_url",
        lambda url: ("youtube", unexpected(url)),
    )

    response = await client.post(
        "/api/analyze",
        json={"url": "https://www.youtube.com/shorts/dQw4w9WgXcQ"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Não foi possível analisar o vídeo devido a um erro inesperado."
    }
    assert "internal extractor detail" not in response.text


async def test_download_mp4_returns_binary_headers_and_cleans_up(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temporary_directory = tempfile.TemporaryDirectory(prefix="clipflow-test-")
    temporary_root = Path(temporary_directory.name)
    output_path = temporary_root / "media.mp4"
    output_path.write_bytes(b"mock-mp4-content")

    monkeypatch.setattr(
        routes,
        "download_youtube_mp4",
        lambda _url, quality: DownloadArtifact(
            path=output_path,
            filename="Vídeo seguro.mp4",
            _temporary_directory=temporary_directory,
        ),
    )

    response = await client.post(
        "/api/download",
        json={
            "url": "https://www.youtube.com/watch?v=video-id",
            "format": "mp4",
            "quality": 720,
        },
    )

    assert response.status_code == 200
    assert response.content == b"mock-mp4-content"
    assert response.headers["content-type"] == "video/mp4"
    assert "attachment" in response.headers["content-disposition"]
    assert "filename*=utf-8''V%C3%ADdeo%20seguro.mp4" in response.headers[
        "content-disposition"
    ]
    assert not temporary_root.exists()


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            QualityUnavailableError(),
            400,
            "A qualidade selecionada não está disponível para este vídeo.",
        ),
        (
            DownloadLimitExceededError(),
            413,
            "Este vídeo excede o limite atual de download do ClipFlow.",
        ),
        (
            FFmpegUnavailableError(),
            503,
            "O FFmpeg é necessário para criar este arquivo, mas não está disponível no servidor.",
        ),
        (
            VideoUnavailableError(),
            404,
            "Este vídeo não existe ou não está disponível.",
        ),
        (
            YouTubeServiceError("sensitive yt-dlp detail"),
            502,
            "A plataforma não pôde concluir o download agora. Tente novamente mais tarde.",
        ),
    ],
)
async def test_download_maps_predictable_errors(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    def fail(*_: object) -> DownloadArtifact:
        raise error

    monkeypatch.setattr(routes, "download_youtube_mp4", fail)

    response = await client.post(
        "/api/download",
        json={
            "url": "https://youtu.be/video-id",
            "format": "mp4",
            "quality": 1080,
        },
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert "sensitive yt-dlp detail" not in response.text


async def test_download_rejects_malformed_url(client: AsyncClient) -> None:
    response = await client.post(
        "/api/download",
        json={"url": "not-a-url", "format": "mp4", "quality": 720},
    )

    assert response.status_code == 422


async def test_download_rejects_unsupported_domain(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unsupported(*_: object) -> DownloadArtifact:
        raise UnsupportedPlatformError

    monkeypatch.setattr(routes, "download_youtube_mp4", unsupported)

    response = await client.post(
        "/api/download",
        json={
            "url": "https://example.com/video",
            "format": "mp4",
            "quality": 720,
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Esta plataforma ainda não é suportada. Use YouTube, TikTok, Instagram ou X/Twitter."
    }


async def test_download_mp3_rejects_silent_media(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_audio(*_: object) -> DownloadArtifact:
        raise AudioUnavailableError

    monkeypatch.setattr(routes, "download_youtube_mp3", no_audio)
    response = await client.post(
        "/api/download",
        json={
            "url": "https://x.com/clipflow/status/1234567890",
            "format": "mp3",
            "audio_quality": 192,
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Esta mídia não contém uma faixa de áudio."}


async def test_download_rejects_mp3(client: AsyncClient) -> None:
    response = await client.post(
        "/api/download",
        json={
            "url": "https://youtu.be/video-id",
            "format": "mp3",
            "quality": 720,
        },
    )

    assert response.status_code == 422


async def test_download_mp3_returns_binary_headers_and_cleans_up(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temporary_directory = tempfile.TemporaryDirectory(prefix="clipflow-test-")
    temporary_root = Path(temporary_directory.name)
    output_path = temporary_root / "media.mp3"
    output_path.write_bytes(b"mock-mp3-content")

    monkeypatch.setattr(
        routes,
        "download_youtube_mp3",
        lambda _url, audio_quality: DownloadArtifact(
            path=output_path,
            filename="Áudio seguro.mp3",
            _temporary_directory=temporary_directory,
        ),
    )

    response = await client.post(
        "/api/download",
        json={
            "url": "https://www.youtube.com/watch?v=video-id",
            "format": "mp3",
            "audio_quality": 192,
        },
    )

    assert response.status_code == 200
    assert response.content == b"mock-mp3-content"
    assert response.headers["content-type"] == "audio/mpeg"
    assert "attachment" in response.headers["content-disposition"]
    assert "filename*=utf-8''%C3%81udio%20seguro.mp3" in response.headers[
        "content-disposition"
    ]
    assert not temporary_root.exists()


@pytest.mark.parametrize(
    "payload",
    [
        {
            "url": "https://youtu.be/video-id",
            "format": "mp3",
            "audio_quality": 160,
        },
        {"url": "https://youtu.be/video-id", "format": "mp3"},
        {
            "url": "https://youtu.be/video-id",
            "format": "mp3",
            "audio_quality": 192,
            "quality": 720,
        },
        {
            "url": "https://youtu.be/video-id",
            "format": "mp4",
            "quality": 720,
            "audio_quality": 192,
        },
    ],
)
async def test_download_rejects_invalid_format_field_combinations(
    client: AsyncClient,
    payload: dict[str, object],
) -> None:
    response = await client.post(
        "/api/download",
        json=payload,
    )

    assert response.status_code == 422


async def test_download_mp3_maps_unavailable_video(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_: object) -> DownloadArtifact:
        raise VideoUnavailableError

    monkeypatch.setattr(routes, "download_youtube_mp3", unavailable)

    response = await client.post(
        "/api/download",
        json={
            "url": "https://youtu.be/unavailable",
            "format": "mp3",
            "audio_quality": 128,
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Este vídeo não existe ou não está disponível."
    }
