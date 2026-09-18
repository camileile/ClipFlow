from collections.abc import AsyncIterator, Iterator
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx2 import ASGITransport, AsyncClient

from app.api import routes
from app.main import app
from app.services.download import DownloadArtifact
from app.services.jobs import job_manager

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_job_manager() -> Iterator[None]:
    job_manager.clear()
    yield
    job_manager.clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client


def make_artifact(extension: str) -> tuple[DownloadArtifact, Path]:
    temporary_directory = tempfile.TemporaryDirectory(prefix="clipflow-api-job-test-")
    root = Path(temporary_directory.name)
    path = root / f"media.{extension}"
    path.write_bytes(f"mock-{extension}".encode())
    return (
        DownloadArtifact(
            path=path,
            filename=f"Mídia segura.{extension}",
            _temporary_directory=temporary_directory,
        ),
        root,
    )


async def test_create_download_job_returns_queued_uuid(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = job_manager.create()
    monkeypatch.setattr(routes, "start_download_job", lambda _: state)

    response = await client.post(
        "/api/download/jobs",
        json={
            "url": "https://youtu.be/video-id",
            "format": "mp4",
            "quality": 720,
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert UUID(response.json()["job_id"]).version == 4


async def test_job_events_returns_named_error_event(client: AsyncClient) -> None:
    state = job_manager.create()
    job_manager.fail(state.job_id, "Falha segura")

    response = await client.get(f"/api/download/jobs/{state.job_id}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: error" in response.text
    assert '"status":"failed"' in response.text
    assert "Falha segura" in response.text


async def test_file_before_ready_returns_conflict(client: AsyncClient) -> None:
    state = job_manager.create()

    response = await client.get(f"/api/download/jobs/{state.job_id}/file")

    assert response.status_code == 409


@pytest.mark.parametrize(
    ("extension", "mime_type", "content"),
    [
        ("mp4", "video/mp4", b"mock-mp4"),
        ("mp3", "audio/mpeg", b"mock-mp3"),
    ],
)
async def test_ready_job_returns_file_headers_and_cleans_up(
    client: AsyncClient,
    extension: str,
    mime_type: str,
    content: bytes,
) -> None:
    state = job_manager.create()
    artifact, temporary_root = make_artifact(extension)
    job_manager.ready(state.job_id, artifact, mime_type)  # type: ignore[arg-type]

    response = await client.get(f"/api/download/jobs/{state.job_id}/file")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == mime_type
    assert "attachment" in response.headers["content-disposition"]
    assert f"M%C3%ADdia%20segura.{extension}" in response.headers["content-disposition"]
    assert not temporary_root.exists()


async def test_cancel_endpoint_marks_job_cancelled_and_emits_event(
    client: AsyncClient,
) -> None:
    state = job_manager.create()
    job_manager.start(state.job_id)

    response = await client.delete(f"/api/download/jobs/{state.job_id}")
    events = await client.get(f"/api/download/jobs/{state.job_id}/events")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert "event: cancelled" in events.text


@pytest.mark.parametrize("suffix", ["events", "file"])
async def test_unknown_job_returns_not_found(
    client: AsyncClient,
    suffix: str,
) -> None:
    response = await client.get(f"/api/download/jobs/{uuid4()}/{suffix}")

    assert response.status_code == 404


async def test_cancel_unknown_job_returns_not_found(client: AsyncClient) -> None:
    response = await client.delete(f"/api/download/jobs/{uuid4()}")

    assert response.status_code == 404
