from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "clipflow-api"}


def test_analyze_youtube_url_returns_mocked_preview() -> None:
    response = client.post(
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


def test_analyze_valid_unknown_platform() -> None:
    response = client.post(
        "/api/analyze",
        json={"url": "https://example.com/media/123"},
    )

    assert response.status_code == 200
    assert response.json()["platform"] == "unknown"


def test_analyze_rejects_invalid_url() -> None:
    response = client.post("/api/analyze", json={"url": "not-a-url"})

    assert response.status_code == 422

