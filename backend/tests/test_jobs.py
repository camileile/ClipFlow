import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from app.api.routes import job_event_stream
from app.schemas import MP3DownloadRequest, MP4DownloadRequest
from app.services import jobs
from app.services.download import (
    DownloadArtifact,
    DownloadCancelledError,
    DownloadProgress,
    FormatSelection,
    _progress_hooks,
)
from app.services.jobs import JobManager, JobNotFoundError, JobNotReadyError


def make_artifact(extension: str = "mp4", content: bytes = b"media") -> DownloadArtifact:
    temporary_directory = tempfile.TemporaryDirectory(prefix="clipflow-job-test-")
    path = Path(temporary_directory.name) / f"media.{extension}"
    path.write_bytes(content)
    return DownloadArtifact(
        path=path,
        filename=f"arquivo.{extension}",
        _temporary_directory=temporary_directory,
    )


def parse_sse_data(event: str) -> dict[str, object]:
    data_line = next(line for line in event.splitlines() if line.startswith("data: "))
    return json.loads(data_line.removeprefix("data: "))


def test_job_creation_uses_uuid_and_starts_queued() -> None:
    manager = JobManager()

    state = manager.create()

    assert UUID(str(state.job_id)).version == 4
    assert state.status == "queued"
    assert state.stage == "Preparing"


def test_progress_hook_calculates_real_percentage_speed_and_eta() -> None:
    updates: list[DownloadProgress] = []
    hooks, _ = _progress_hooks(
        FormatSelection("137+140", requires_ffmpeg=True, estimated_filesize=1_000),
        "mp4",
        updates.append,
        lambda: False,
    )

    hooks[0](
        {
            "status": "downloading",
            "downloaded_bytes": 250,
            "total_bytes": 1_000,
            "speed": 3_240_000,
            "eta": 12,
            "info_dict": {"format_id": "137"},
        }
    )

    assert updates == [
        DownloadProgress(
            status="downloading",
            stage="Downloading video",
            progress=25.0,
            downloaded_bytes=250,
            total_bytes=1_000,
            speed=3_240_000.0,
            eta=12,
        )
    ]


def test_progress_hook_uses_null_percentage_without_total() -> None:
    updates: list[DownloadProgress] = []
    hooks, _ = _progress_hooks(
        FormatSelection("251", requires_ffmpeg=True, estimated_filesize=None),
        "mp3",
        updates.append,
        lambda: False,
    )

    hooks[0](
        {
            "status": "downloading",
            "downloaded_bytes": 250,
            "info_dict": {"format_id": "251"},
        }
    )

    assert updates[0].progress is None
    assert updates[0].total_bytes is None
    assert updates[0].stage == "Downloading audio"


def test_progress_hook_switches_to_processing_without_fake_percentage() -> None:
    updates: list[DownloadProgress] = []
    hooks, postprocessor_hooks = _progress_hooks(
        FormatSelection("251", requires_ffmpeg=True, estimated_filesize=None),
        "mp3",
        updates.append,
        lambda: False,
    )

    hooks[0]({"status": "finished"})
    postprocessor_hooks[0]({"status": "started"})

    assert all(update.status == "processing" for update in updates)
    assert all(update.stage == "Converting to MP3" for update in updates)
    assert all(update.progress is None for update in updates)


def test_progress_hook_interrupts_when_cancelled() -> None:
    hooks, _ = _progress_hooks(
        FormatSelection("18", requires_ffmpeg=False, estimated_filesize=100),
        "mp4",
        None,
        lambda: True,
    )

    with pytest.raises(DownloadCancelledError):
        hooks[0]({"status": "downloading"})


def test_progress_hook_defers_fragmented_stream_cancellation_until_safe_point() -> None:
    hooks, _ = _progress_hooks(
        FormatSelection("311", requires_ffmpeg=False, estimated_filesize=None),
        "mp4",
        None,
        lambda: True,
    )

    hooks[0](
        {
            "status": "downloading",
            "info_dict": {"format_id": "311", "protocol": "m3u8_native"},
        }
    )
    with pytest.raises(DownloadCancelledError):
        hooks[0](
            {
                "status": "finished",
                "info_dict": {"format_id": "311", "protocol": "m3u8_native"},
            }
        )


def test_tiktok_progress_uses_generic_media_stage() -> None:
    updates: list[DownloadProgress] = []
    hooks, _ = _progress_hooks(
        FormatSelection("download_addr-0", requires_ffmpeg=False, estimated_filesize=100),
        "mp4",
        updates.append,
        lambda: False,
        platform="tiktok",
    )

    hooks[0](
        {
            "status": "downloading",
            "downloaded_bytes": 50,
            "total_bytes": 100,
            "info_dict": {"format_id": "download_addr-0"},
        }
    )

    assert updates[0].stage == "Downloading media"
    assert updates[0].progress == 50.0


def test_instagram_progress_uses_generic_media_stage() -> None:
    updates: list[DownloadProgress] = []
    hooks, _ = _progress_hooks(
        FormatSelection("dash-720", requires_ffmpeg=False, estimated_filesize=100),
        "mp4",
        updates.append,
        lambda: False,
        platform="instagram",
    )
    hooks[0](
        {
            "status": "downloading",
            "downloaded_bytes": 25,
            "total_bytes": 100,
            "speed": 50,
            "eta": 2,
            "info_dict": {"format_id": "dash-720"},
        }
    )

    assert updates[0].stage == "Downloading media"
    assert updates[0].progress == 25.0
    assert updates[0].eta == 2


def test_worker_throttles_repeated_progress_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager()
    state = manager.create()
    artifact = make_artifact()

    def fake_download(
        _url: object,
        _quality: int,
        *,
        on_progress: object,
        is_cancelled: object,
    ) -> DownloadArtifact:
        assert callable(on_progress)
        assert callable(is_cancelled)
        for progress in (10.0, 20.0, 30.0, 40.0):
            on_progress(
                DownloadProgress(
                    status="downloading",
                    stage="Downloading video",
                    progress=progress,
                )
            )
        return artifact

    times = iter((0.0, 0.05, 0.1, 0.3))
    monkeypatch.setattr(jobs, "download_youtube_mp4", fake_download)
    request = MP4DownloadRequest(
        url="https://youtu.be/video-id", format="mp4", quality=720
    )

    jobs.process_download_job(
        manager,
        state.job_id,
        request,
        monotonic=lambda: next(times),
    )

    result, version = manager.get_versioned(state.job_id)
    assert result.status == "ready"
    assert version == 4  # start, first update, throttled update at 300 ms, ready
    manager.complete_file_delivery(state.job_id)


def test_tiktok_job_uses_shared_worker_and_keeps_platform_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager()
    state = manager.create("tiktok")
    artifact = make_artifact()
    seen: dict[str, object] = {}

    def fake_download(
        url: object,
        quality: int,
        **_: object,
    ) -> DownloadArtifact:
        seen["url"] = str(url)
        seen["quality"] = quality
        return artifact

    monkeypatch.setattr(jobs, "download_youtube_mp4", fake_download)
    jobs.process_download_job(
        manager,
        state.job_id,
        MP4DownloadRequest(
            url="https://vm.tiktok.com/ZMshort/",
            format="mp4",
            quality=720,
        ),
    )

    result = manager.get(state.job_id)
    assert result.status == "ready"
    assert result.platform == "tiktok"
    assert seen == {"url": "https://vm.tiktok.com/ZMshort/", "quality": 720}
    manager.complete_file_delivery(state.job_id)


def test_instagram_job_uses_shared_worker_and_keeps_platform_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager()
    state = manager.create("instagram")
    artifact = make_artifact()
    monkeypatch.setattr(jobs, "download_youtube_mp4", lambda *_args, **_kwargs: artifact)

    jobs.process_download_job(
        manager,
        state.job_id,
        MP4DownloadRequest(
            url="https://www.instagram.com/reel/C1234567890/",
            format="mp4",
            quality=720,
        ),
    )

    result = manager.get(state.job_id)
    assert result.status == "ready"
    assert result.platform == "instagram"
    manager.complete_file_delivery(state.job_id)


@pytest.mark.anyio
async def test_sse_emits_progress_then_ready() -> None:
    manager = JobManager()
    state = manager.create()
    stream = job_event_stream(state.job_id, manager=manager, keepalive_seconds=0.1)

    initial = await anext(stream)
    assert initial.startswith("event: progress")
    assert parse_sse_data(initial)["status"] == "queued"

    manager.start(state.job_id)
    progress = await anext(stream)
    assert parse_sse_data(progress)["status"] == "downloading"

    artifact = make_artifact()
    manager.ready(state.job_id, artifact, "video/mp4")
    ready = await anext(stream)
    assert ready.startswith("event: ready")
    assert parse_sse_data(ready)["filename"] == "arquivo.mp4"
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    manager.complete_file_delivery(state.job_id)


@pytest.mark.anyio
async def test_sse_emits_error_and_cancelled_events() -> None:
    failed_manager = JobManager()
    failed = failed_manager.create()
    failed_manager.fail(failed.job_id, "Falha segura")
    failed_stream = job_event_stream(failed.job_id, manager=failed_manager)
    assert (await anext(failed_stream)).startswith("event: error")

    cancelled_manager = JobManager()
    cancelled = cancelled_manager.create()
    cancelled_manager.cancel(cancelled.job_id)
    cancelled_stream = job_event_stream(cancelled.job_id, manager=cancelled_manager)
    event = await anext(cancelled_stream)
    assert event.startswith("event: cancelled")
    assert parse_sse_data(event)["status"] == "cancelled"


@pytest.mark.anyio
async def test_sse_sends_keepalive_without_state_change() -> None:
    manager = JobManager()
    state = manager.create()
    stream = job_event_stream(state.job_id, manager=manager, keepalive_seconds=0.01)

    await anext(stream)

    assert await anext(stream) == ": keepalive\n\n"
    await stream.aclose()


def test_file_cannot_be_claimed_before_ready() -> None:
    manager = JobManager()
    state = manager.create()

    with pytest.raises(JobNotReadyError):
        manager.claim_file(state.job_id)


@pytest.mark.parametrize(
    ("extension", "mime_type"),
    [("mp4", "video/mp4"), ("mp3", "audio/mpeg")],
)
def test_ready_file_preserves_type_filename_and_cleans_after_delivery(
    extension: str,
    mime_type: str,
) -> None:
    manager = JobManager()
    state = manager.create()
    artifact = make_artifact(extension)
    temporary_root = artifact.path.parent
    manager.ready(state.job_id, artifact, mime_type)  # type: ignore[arg-type]

    claimed = manager.claim_file(state.job_id)

    assert claimed.filename == f"arquivo.{extension}"
    assert claimed.mime_type == mime_type
    assert temporary_root.exists()
    manager.complete_file_delivery(state.job_id)
    assert not temporary_root.exists()
    with pytest.raises(JobNotFoundError):
        manager.get(state.job_id)


def test_cancel_queued_and_downloading_jobs() -> None:
    manager = JobManager()
    queued = manager.create()
    downloading = manager.create()
    manager.start(downloading.job_id)

    assert manager.cancel(queued.job_id).status == "cancelled"
    assert manager.cancel(downloading.job_id).status == "cancelled"
    assert manager.is_cancelled(queued.job_id)
    assert manager.is_cancelled(downloading.job_id)


def test_worker_cancellation_does_not_publish_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager()
    state = manager.create()

    def cancelled_download(
        _url: object,
        _quality: int,
        *,
        on_progress: object,
        is_cancelled: object,
    ) -> DownloadArtifact:
        manager.cancel(state.job_id)
        assert callable(is_cancelled) and is_cancelled()
        raise DownloadCancelledError

    monkeypatch.setattr(jobs, "download_youtube_mp4", cancelled_download)
    jobs.process_download_job(
        manager,
        state.job_id,
        MP4DownloadRequest(
            url="https://youtu.be/video-id", format="mp4", quality=720
        ),
    )

    assert manager.get(state.job_id).status == "cancelled"
    with pytest.raises(JobNotReadyError):
        manager.claim_file(state.job_id)


def test_pipeline_error_becomes_safe_failed_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager()
    state = manager.create()

    def fail(*_: object, **__: object) -> DownloadArtifact:
        raise RuntimeError("sensitive internal detail")

    monkeypatch.setattr(jobs, "download_youtube_mp3", fail)
    jobs.process_download_job(
        manager,
        state.job_id,
        MP3DownloadRequest(
            url="https://youtu.be/video-id", format="mp3", audio_quality=192
        ),
    )

    failed = manager.get(state.job_id)
    assert failed.status == "failed"
    assert failed.error == "Não foi possível concluir o download devido a um erro inesperado."
    assert "sensitive" not in failed.error


def test_cleanup_uses_ready_and_terminal_ttls() -> None:
    now = datetime(2026, 9, 17, tzinfo=UTC)
    current_time = [now]
    manager = JobManager(
        clock=lambda: current_time[0],
        ready_ttl_seconds=900,
        terminal_ttl_seconds=300,
    )
    ready = manager.create()
    failed = manager.create()
    artifact = make_artifact()
    temporary_root = artifact.path.parent
    manager.ready(ready.job_id, artifact, "video/mp4")
    manager.fail(failed.job_id, "Falha")

    current_time[0] += timedelta(seconds=301)
    assert manager.cleanup_expired() == 1
    with pytest.raises(JobNotFoundError):
        manager.get(failed.job_id)
    assert manager.get(ready.job_id).status == "ready"

    current_time[0] += timedelta(seconds=600)
    assert manager.cleanup_expired() == 1
    assert not temporary_root.exists()
    with pytest.raises(JobNotFoundError):
        manager.get(ready.job_id)


def test_two_jobs_keep_state_files_and_cancellation_isolated() -> None:
    manager = JobManager()
    first = manager.create()
    second = manager.create()
    first_artifact = make_artifact("mp4", b"first")
    second_artifact = make_artifact("mp3", b"second")

    manager.cancel(first.job_id)
    manager.ready(second.job_id, second_artifact, "audio/mpeg")

    assert manager.get(first.job_id).status == "cancelled"
    assert manager.get(second.job_id).status == "ready"
    assert manager.claim_file(second.job_id).path != str(first_artifact.path)
    first_artifact.cleanup()
    manager.complete_file_delivery(second.job_id)
