from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx2 import ASGITransport, AsyncClient
from starlette.requests import Request

from app.api import routes
from app.config import load_settings
from app.main import create_app
from app.observability import resolve_client_id
from app.schemas import MediaInfo
from app.services.ffmpeg import MediaTools
from app.services.jobs import (
    ClientJobCapacityError,
    JobCapacityError,
    JobManager,
)
from app.services.temporary import cleanup_orphan_temp_directories, ensure_temp_root


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def production_settings(tmp_path: Path, **overrides: str):
    values = {
        "APP_ENV": "production",
        "APP_VERSION": "test-version",
        "FRONTEND_ORIGIN": "https://clipflow.example",
        "CORS_ALLOWED_ORIGINS": "https://clipflow.example",
        "CLIPFLOW_TEMP_DIR": str(tmp_path),
        **overrides,
    }
    return load_settings(values)


async def app_client(settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


def test_config_defaults_are_safe_for_development() -> None:
    settings = load_settings({})

    assert settings.app_env == "development"
    assert settings.cors_allowed_origins == (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    assert settings.max_concurrent_jobs == 3
    assert settings.analyze_rate_limit == 20


def test_config_environment_overrides(tmp_path: Path) -> None:
    settings = production_settings(
        tmp_path,
        MAX_DURATION_SECONDS="60",
        MAX_FILESIZE_BYTES="1234",
        MAX_CONCURRENT_JOBS="1",
        RATE_LIMIT="7",
        READY_JOB_TTL="42",
        FAILED_JOB_TTL="12",
        LOG_LEVEL="WARNING",
    )

    assert settings.production
    assert settings.max_duration_seconds == 60
    assert settings.max_filesize_bytes == 1234
    assert settings.max_concurrent_jobs == 1
    assert settings.analyze_rate_limit == 7
    assert settings.ready_job_ttl_seconds == 42
    assert settings.failed_job_ttl_seconds == 12
    assert settings.log_level == "WARNING"


def test_forwarded_ip_is_used_only_for_trusted_proxy(tmp_path: Path) -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/health",
        "headers": [(b"x-forwarded-for", b"203.0.113.8, 10.0.0.1")],
        "client": ("10.0.0.1", 1234),
        "server": ("test", 80),
        "scheme": "http",
        "query_string": b"",
    }
    request = Request(scope)
    untrusted = production_settings(tmp_path)
    trusted = production_settings(tmp_path, TRUSTED_PROXY_IPS="10.0.0.1")

    assert resolve_client_id(request, untrusted) == "10.0.0.1"
    assert resolve_client_id(request, trusted) == "203.0.113.8"


async def test_development_cors_allows_localhost(tmp_path: Path) -> None:
    settings = load_settings({"CLIPFLOW_TEMP_DIR": str(tmp_path)})
    async for client in app_client(settings):
        response = await client.options(
            "/api/analyze",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_production_cors_restricts_origin(tmp_path: Path) -> None:
    async for client in app_client(production_settings(tmp_path)):
        allowed = await client.options(
            "/api/analyze",
            headers={
                "Origin": "https://clipflow.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        denied = await client.options(
            "/api/analyze",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert allowed.headers["access-control-allow-origin"] == "https://clipflow.example"
    assert "access-control-allow-origin" not in denied.headers


async def test_production_disables_interactive_api_schema(tmp_path: Path) -> None:
    async for client in app_client(production_settings(tmp_path)):
        docs = await client.get("/docs")
        schema = await client.get("/openapi.json")

    assert docs.status_code == 404
    assert schema.status_code == 404


async def test_rate_limit_returns_429_and_retry_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = MediaInfo(
        id="id",
        title="Title",
        author=None,
        duration=1,
        thumbnail=None,
        original_url="https://youtu.be/id",
        qualities=[360],
        formats=[],
    )
    monkeypatch.setattr(routes, "analyze_media_url", lambda _: ("youtube", media))
    settings = production_settings(tmp_path, RATE_LIMIT="1")
    async for client in app_client(settings):
        first = await client.post("/api/analyze", json={"url": "https://youtu.be/id"})
        limited = await client.post("/api/analyze", json={"url": "https://youtu.be/id"})

    assert first.status_code == 200
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1


async def test_request_id_is_preserved_or_generated(tmp_path: Path) -> None:
    async for client in app_client(production_settings(tmp_path)):
        supplied = await client.get("/health", headers={"X-Request-ID": "safe-id_123"})
        generated = await client.get("/health", headers={"X-Request-ID": "not valid!"})

    assert supplied.headers["x-request-id"] == "safe-id_123"
    assert generated.headers["x-request-id"] != "not valid!"
    assert len(generated.headers["x-request-id"]) == 36


async def test_readiness_reports_healthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "detect_media_tools", lambda: MediaTools("ffmpeg", "ffprobe")
    )
    async for client in app_client(production_settings(tmp_path)):
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["version"] == "test-version"


async def test_readiness_reports_missing_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routes, "detect_media_tools", lambda: MediaTools(None, None))
    async for client in app_client(production_settings(tmp_path)):
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["ffmpeg"] is False


async def test_url_length_is_limited(tmp_path: Path) -> None:
    async for client in app_client(production_settings(tmp_path)):
        response = await client.post(
            "/api/analyze", json={"url": "https://youtube.com/watch?v=" + "x" * 3000}
        )

    assert response.status_code == 422


async def test_declared_request_body_size_is_limited(tmp_path: Path) -> None:
    settings = production_settings(tmp_path, MAX_REQUEST_BODY_BYTES="1024")
    async for client in app_client(settings):
        response = await client.post(
            "/api/analyze",
            content=b"{}",
            headers={"Content-Type": "application/json", "Content-Length": "2048"},
        )

    assert response.status_code == 413


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(ClientJobCapacityError(), 429), (JobCapacityError(), 503)],
)
async def test_job_capacity_returns_controlled_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_status: int,
) -> None:
    def reject(*args, **kwargs):
        raise error

    monkeypatch.setattr(routes, "start_download_job", reject)
    async for client in app_client(production_settings(tmp_path)):
        response = await client.post(
            "/api/download/jobs",
            json={
                "url": "https://youtu.be/video-id",
                "format": "mp4",
                "quality": 720,
            },
        )

    assert response.status_code == expected_status
    assert response.headers["retry-after"] == "10"


def test_global_and_per_client_job_limits() -> None:
    global_manager = JobManager(max_concurrent_jobs=1, max_jobs_per_client=1)
    global_manager.create(client_id="a")
    with pytest.raises(JobCapacityError):
        global_manager.create(client_id="b")

    client_manager = JobManager(max_concurrent_jobs=3, max_jobs_per_client=1)
    client_manager.create(client_id="a")
    with pytest.raises(ClientJobCapacityError):
        client_manager.create(client_id="a")
    assert client_manager.create(client_id="b").status == "queued"


def test_orphan_cleanup_is_restricted_to_controlled_directories(tmp_path: Path) -> None:
    root = ensure_temp_root(tmp_path / "clipflow")
    orphan = root / "job-old"
    unrelated = root / "keep-me"
    orphan.mkdir()
    unrelated.mkdir()

    assert cleanup_orphan_temp_directories(root) == 1
    assert not orphan.exists()
    assert unrelated.exists()
