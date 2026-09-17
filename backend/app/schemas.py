from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["clipflow-api"]


class AnalyzeRequest(BaseModel):
    url: HttpUrl = Field(description="Public media URL to analyze")


class AnalyzeResponse(BaseModel):
    success: bool
    platform: Literal["youtube", "unknown"]
    title: str
    author: str
    duration: int = Field(ge=0)
    thumbnail: HttpUrl | None
