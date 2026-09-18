from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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
    audio_quality: Literal[128, 192, 256, 320] = Field(
        description="Target MP3 bitrate in kbps"
    )


DownloadRequest = Annotated[
    MP4DownloadRequest | MP3DownloadRequest,
    Field(discriminator="format"),
]


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
