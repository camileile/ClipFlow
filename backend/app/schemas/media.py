from datetime import datetime
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.config import MP3Bitrate


class AnalyzeRequest(BaseModel):
    url: HttpUrl = Field(description="Public YouTube URL to analyze")


class MP4DownloadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl = Field(description="Public YouTube URL to download")
    format: Literal["mp4"]
    quality: int = Field(ge=1, le=4320, description="Exact video height in pixels")


class MP3DownloadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl = Field(description="Public YouTube URL to download")
    format: Literal["mp3"]
    audio_quality: MP3Bitrate = Field(description="Target MP3 bitrate in kbps")


DownloadRequest = Annotated[
    MP4DownloadRequest | MP3DownloadRequest,
    Field(discriminator="format"),
]

DownloadJobStatus: TypeAlias = Literal[
    "queued",
    "downloading",
    "processing",
    "ready",
    "failed",
    "cancelled",
]


class DownloadJobCreated(BaseModel):
    job_id: UUID
    status: Literal["queued"]


class DownloadJobState(BaseModel):
    job_id: UUID
    status: DownloadJobStatus
    stage: str
    progress: float | None = Field(default=None, ge=0, le=100)
    downloaded_bytes: int | None = Field(default=None, ge=0)
    total_bytes: int | None = Field(default=None, ge=0)
    speed: float | None = Field(default=None, ge=0)
    eta: int | None = Field(default=None, ge=0)
    filename: str | None = None
    mime_type: Literal["video/mp4", "audio/mpeg"] | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class MediaFormat(BaseModel):
    format_id: str
    type: Literal["video", "audio"]
    extension: str | None = None
    quality: int | None = Field(default=None, ge=1)
    fps: float | None = Field(default=None, gt=0)
    bitrate: int | None = Field(default=None, ge=0)
    filesize: int | None = Field(default=None, ge=0)


class MediaInfo(BaseModel):
    id: str
    title: str
    author: str | None
    duration: int | None = Field(default=None, ge=0)
    thumbnail: HttpUrl | None
    original_url: HttpUrl
    qualities: list[int]
    formats: list[MediaFormat]


class AnalyzeResponse(BaseModel):
    success: Literal[True]
    platform: Literal["youtube"]
    media: MediaInfo
