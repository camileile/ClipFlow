from collections.abc import AsyncIterator

import pytest
from httpx2 import ASGITransport, AsyncClient

from app.api import routes
from app.main import app
from app.schemas import MediaFormat, MediaInfo
from app.services.youtube import UnexpectedYouTubeError, VideoUnavailableError

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
    monkeypatch.setattr(routes, "analyze_youtube", lambda _: sample_media)

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
        "detail": "Esta plataforma ainda não é suportada. Use um link do YouTube."
    }


async def test_analyze_handles_unavailable_video(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_: object) -> MediaInfo:
        raise VideoUnavailableError

    monkeypatch.setattr(routes, "analyze_youtube", unavailable)

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

    monkeypatch.setattr(routes, "analyze_youtube", unexpected)

    response = await client.post(
        "/api/analyze",
        json={"url": "https://www.youtube.com/shorts/dQw4w9WgXcQ"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Não foi possível analisar o vídeo devido a um erro inesperado."
    }
    assert "internal extractor detail" not in response.text
