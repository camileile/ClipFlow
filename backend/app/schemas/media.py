from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class AnalyzeRequest(BaseModel):
    url: HttpUrl = Field(description="Public YouTube URL to analyze")


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
