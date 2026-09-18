import asyncio
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from app.config import (
    DOWNLOAD_JOB_READY_TTL_SECONDS,
    DOWNLOAD_JOB_TERMINAL_TTL_SECONDS,
    DOWNLOAD_PROGRESS_THROTTLE_SECONDS,
)
from app.schemas import DownloadJobState, DownloadRequest
from app.services.download import (
    DownloadArtifact,
    DownloadCancelledError,
    DownloadLimitExceededError,
    DownloadProcessingError,
    DownloadProgress,
    FFmpegUnavailableError,
    IncompatibleMediaError,
    QualityUnavailableError,
    UnsupportedBitrateError,
    download_youtube_mp3,
    download_youtube_mp4,
)
from app.services.youtube import (
    InvalidYouTubeUrlError,
    PrivateVideoError,
    RemovedVideoError,
    UnsupportedPlatformError,
    VideoUnavailableError,
    YouTubeServiceError,
)

logger = logging.getLogger(__name__)


class JobStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = {
    JobStatus.READY,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
}
ACTIVE_STATUSES = {
    JobStatus.QUEUED,
    JobStatus.DOWNLOADING,
    JobStatus.PROCESSING,
}


class JobNotFoundError(Exception):
    pass


class JobNotReadyError(Exception):
    pass


class JobFileAlreadyClaimedError(Exception):
    pass


@dataclass
class DownloadJob:
    id: UUID
    status: JobStatus
    stage: str
    created_at: datetime
    progress: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed: float | None = None
    eta: int | None = None
    filename: str | None = None
    mime_type: Literal["video/mp4", "audio/mpeg"] | None = None
    error: str | None = None
    completed_at: datetime | None = None
    artifact: DownloadArtifact | None = None
    file_claimed: bool = False
    version: int = 0
    cancelled: threading.Event = field(default_factory=threading.Event)


@dataclass(frozen=True)
class JobFile:
    path: str
    filename: str
    mime_type: Literal["video/mp4", "audio/mpeg"]


Clock = Callable[[], datetime]


class JobManager:
    def __init__(
        self,
        *,
        clock: Clock | None = None,
        ready_ttl_seconds: float = DOWNLOAD_JOB_READY_TTL_SECONDS,
        terminal_ttl_seconds: float = DOWNLOAD_JOB_TERMINAL_TTL_SECONDS,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._ready_ttl = timedelta(seconds=ready_ttl_seconds)
        self._terminal_ttl = timedelta(seconds=terminal_ttl_seconds)
        self._jobs: dict[UUID, DownloadJob] = {}
        self._condition = threading.Condition(threading.RLock())

    def create(self) -> DownloadJobState:
        self.cleanup_expired()
        with self._condition:
            job = DownloadJob(
                id=uuid4(),
                status=JobStatus.QUEUED,
                stage="Preparing",
                created_at=self._clock(),
            )
            self._jobs[job.id] = job
            return self._state(job)

    def get(self, job_id: UUID) -> DownloadJobState:
        self.cleanup_expired()
        with self._condition:
            return self._state(self._require(job_id))

    def get_versioned(self, job_id: UUID) -> tuple[DownloadJobState, int]:
        self.cleanup_expired()
        with self._condition:
            job = self._require(job_id)
            return self._state(job), job.version

    def wait_for_change(
        self,
        job_id: UUID,
        version: int,
        timeout: float,
    ) -> tuple[DownloadJobState, int] | None:
        with self._condition:
            job = self._require(job_id)
            if job.version > version:
                return self._state(job), job.version

            self._condition.wait_for(
                lambda: job_id not in self._jobs
                or self._jobs[job_id].version > version,
                timeout=timeout,
            )
            if job_id not in self._jobs:
                raise JobNotFoundError
            job = self._jobs[job_id]
            if job.version <= version:
                return None
            return self._state(job), job.version

    def start(self, job_id: UUID) -> bool:
        with self._condition:
            job = self._require(job_id)
            if job.status is not JobStatus.QUEUED:
                return False
            job.status = JobStatus.DOWNLOADING
            job.stage = "Preparing"
            self._changed(job)
            return True

    def update_progress(self, job_id: UUID, update: DownloadProgress) -> bool:
        with self._condition:
            job = self._require(job_id)
            if job.status not in ACTIVE_STATUSES or job.cancelled.is_set():
                return False

            job.status = JobStatus(update.status)
            job.stage = update.stage
            job.progress = update.progress
            job.downloaded_bytes = update.downloaded_bytes
            job.total_bytes = update.total_bytes
            job.speed = update.speed
            job.eta = update.eta
            self._changed(job)
            return True

    def is_cancelled(self, job_id: UUID) -> bool:
        with self._condition:
            job = self._jobs.get(job_id)
            return job is None or job.cancelled.is_set()

    def ready(
        self,
        job_id: UUID,
        artifact: DownloadArtifact,
        mime_type: Literal["video/mp4", "audio/mpeg"],
    ) -> bool:
        with self._condition:
            job = self._require(job_id)
            if job.cancelled.is_set() or job.status is JobStatus.CANCELLED:
                artifact.cleanup()
                return False

            job.status = JobStatus.READY
            job.stage = "Ready"
            job.progress = None
            job.downloaded_bytes = None
            job.total_bytes = None
            job.speed = None
            job.eta = None
            job.filename = artifact.filename
            job.mime_type = mime_type
            job.artifact = artifact
            job.completed_at = self._clock()
            self._changed(job)
            return True

    def fail(self, job_id: UUID, message: str) -> bool:
        with self._condition:
            job = self._require(job_id)
            if job.status is JobStatus.CANCELLED:
                return False
            job.status = JobStatus.FAILED
            job.stage = "Failed"
            job.error = message
            job.progress = None
            job.speed = None
            job.eta = None
            job.completed_at = self._clock()
            self._changed(job)
            return True

    def cancel(self, job_id: UUID) -> DownloadJobState:
        artifact: DownloadArtifact | None = None
        with self._condition:
            job = self._require(job_id)
            if job.status is JobStatus.CANCELLED:
                return self._state(job)
            if job.status is JobStatus.FAILED:
                return self._state(job)

            job.cancelled.set()
            job.status = JobStatus.CANCELLED
            job.stage = "Cancelled"
            job.progress = None
            job.downloaded_bytes = None
            job.total_bytes = None
            job.speed = None
            job.eta = None
            job.completed_at = self._clock()
            artifact = job.artifact
            job.artifact = None
            self._changed(job)
            state = self._state(job)

        if artifact is not None:
            artifact.cleanup()
        return state

    def claim_file(self, job_id: UUID) -> JobFile:
        self.cleanup_expired()
        with self._condition:
            job = self._require(job_id)
            if job.status is not JobStatus.READY or job.artifact is None:
                raise JobNotReadyError
            if job.file_claimed:
                raise JobFileAlreadyClaimedError
            if not job.artifact.path.is_file():
                raise JobNotReadyError

            job.file_claimed = True
            return JobFile(
                path=str(job.artifact.path),
                filename=job.artifact.filename,
                mime_type=job.mime_type or "video/mp4",
            )

    def complete_file_delivery(self, job_id: UUID) -> None:
        artifact: DownloadArtifact | None = None
        with self._condition:
            job = self._jobs.pop(job_id, None)
            if job is not None:
                artifact = job.artifact
                job.artifact = None
                self._condition.notify_all()
        if artifact is not None:
            artifact.cleanup()

    def cleanup_expired(self) -> int:
        now = self._clock()
        artifacts: list[DownloadArtifact] = []
        with self._condition:
            expired_ids: list[UUID] = []
            for job_id, job in self._jobs.items():
                if job.status not in TERMINAL_STATUSES or job.completed_at is None:
                    continue
                if job.file_claimed:
                    continue
                ttl = (
                    self._ready_ttl
                    if job.status is JobStatus.READY
                    else self._terminal_ttl
                )
                if now - job.completed_at >= ttl:
                    expired_ids.append(job_id)

            for job_id in expired_ids:
                job = self._jobs.pop(job_id)
                if job.artifact is not None:
                    artifacts.append(job.artifact)
                    job.artifact = None
            if expired_ids:
                self._condition.notify_all()

        for artifact in artifacts:
            artifact.cleanup()
        return len(expired_ids)

    def clear(self) -> None:
        artifacts: list[DownloadArtifact] = []
        with self._condition:
            jobs = list(self._jobs.values())
            self._jobs.clear()
            for job in jobs:
                job.cancelled.set()
                if job.artifact is not None:
                    artifacts.append(job.artifact)
            self._condition.notify_all()
        for artifact in artifacts:
            artifact.cleanup()

    def _require(self, job_id: UUID) -> DownloadJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError
        return job

    @staticmethod
    def _state(job: DownloadJob) -> DownloadJobState:
        return DownloadJobState(
            job_id=job.id,
            status=job.status.value,
            stage=job.stage,
            progress=job.progress,
            downloaded_bytes=job.downloaded_bytes,
            total_bytes=job.total_bytes,
            speed=job.speed,
            eta=job.eta,
            filename=job.filename,
            mime_type=job.mime_type,
            error=job.error,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )

    def _changed(self, job: DownloadJob) -> None:
        job.version += 1
        self._condition.notify_all()


def _friendly_error(error: Exception, media_format: str) -> str:
    if isinstance(error, QualityUnavailableError):
        return "A qualidade selecionada não está disponível para este vídeo."
    if isinstance(error, DownloadLimitExceededError):
        return "Este vídeo excede o limite atual de download do ClipFlow."
    if isinstance(error, FFmpegUnavailableError):
        return "O FFmpeg é necessário para criar este arquivo, mas não está disponível no servidor."
    if isinstance(error, UnsupportedBitrateError):
        return "O bitrate selecionado não é suportado."
    if isinstance(error, IncompatibleMediaError):
        return (
            "Não foi possível encontrar áudio compatível para este vídeo."
            if media_format == "mp3"
            else "Não foi possível criar um MP4 compatível nesta qualidade."
        )
    if isinstance(error, DownloadProcessingError):
        return (
            "O arquivo MP3 não pôde ser convertido. Tente novamente."
            if media_format == "mp3"
            else "O arquivo MP4 não pôde ser preparado. Tente outra qualidade."
        )
    if isinstance(error, InvalidYouTubeUrlError):
        return "Informe uma URL válida de um vídeo do YouTube."
    if isinstance(error, UnsupportedPlatformError):
        return "Esta plataforma ainda não é suportada. Use um link do YouTube."
    if isinstance(error, PrivateVideoError):
        return "Este vídeo é privado e não pode ser baixado."
    if isinstance(error, RemovedVideoError):
        return "Este vídeo foi removido e não está mais disponível."
    if isinstance(error, VideoUnavailableError):
        return "Este vídeo não existe ou não está disponível."
    if isinstance(error, YouTubeServiceError):
        return "O YouTube não pôde concluir o download agora. Tente novamente mais tarde."
    return "Não foi possível concluir o download devido a um erro inesperado."


def process_download_job(
    manager: JobManager,
    job_id: UUID,
    request: DownloadRequest,
    *,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    if not manager.start(job_id):
        return

    last_emit_at = float("-inf")
    last_state: tuple[str, str] | None = None

    def publish(update: DownloadProgress) -> None:
        nonlocal last_emit_at, last_state
        now = monotonic()
        state = (update.status, update.stage)
        important = state != last_state or update.progress == 100.0
        if important or now - last_emit_at >= DOWNLOAD_PROGRESS_THROTTLE_SECONDS:
            manager.update_progress(job_id, update)
            last_emit_at = now
            last_state = state

    try:
        if request.format == "mp4":
            artifact = download_youtube_mp4(
                request.url,
                request.quality,
                on_progress=publish,
                is_cancelled=lambda: manager.is_cancelled(job_id),
            )
            mime_type: Literal["video/mp4", "audio/mpeg"] = "video/mp4"
        else:
            artifact = download_youtube_mp3(
                request.url,
                request.audio_quality,
                on_progress=publish,
                is_cancelled=lambda: manager.is_cancelled(job_id),
            )
            mime_type = "audio/mpeg"

        manager.ready(job_id, artifact, mime_type)
    except DownloadCancelledError:
        logger.info("Download job cancelled", extra={"job_id": str(job_id)})
        if not manager.is_cancelled(job_id):
            manager.cancel(job_id)
    except Exception as error:
        logger.warning(
            "Download job failed: %s",
            error.__class__.__name__,
            extra={"job_id": str(job_id)},
        )
        manager.fail(job_id, _friendly_error(error, request.format))


job_manager = JobManager()
_worker_tasks: set[asyncio.Task[None]] = set()


def start_download_job(request: DownloadRequest) -> DownloadJobState:
    state = job_manager.create()
    task = asyncio.create_task(
        asyncio.to_thread(process_download_job, job_manager, state.job_id, request)
    )
    _worker_tasks.add(task)
    task.add_done_callback(_worker_tasks.discard)
    return state
