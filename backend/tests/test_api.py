from collections.abc import AsyncIterator

import pytest
from httpx2 import ASGITransport, AsyncClient

from app.main import app

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


async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "clipflow-api"}


async def test_analyze_youtube_url_returns_mocked_preview(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/analyze",
        json={"url": "https://www.youtube.com/watch?v=demo"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "platform": "youtube",
        "title": "Preview demonstrativo",
        "author": "Canal",
        "duration": 0,
        "thumbnail": None,
    }


async def test_analyze_valid_unknown_platform(client: AsyncClient) -> None:
    response = await client.post(
        "/api/analyze",
        json={"url": "https://example.com/media/123"},
    )

    assert response.status_code == 200
    assert response.json()["platform"] == "unknown"


async def test_analyze_rejects_invalid_url(client: AsyncClient) -> None:
    response = await client.post("/api/analyze", json={"url": "not-a-url"})

    assert response.status_code == 422
