from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["clipflow-api"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    service: Literal["clipflow-api"]
    version: str
    checks: dict[str, bool]
