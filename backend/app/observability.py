import contextvars
import json
import logging
import re
import time
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.config import Settings
from app.services.rate_limit import InMemoryRateLimiter


request_id_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        for key in ("method", "path", "status_code", "duration_ms", "platform", "job_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def resolve_client_id(request: Request, settings: Settings) -> str:
    peer = request.client.host if request.client else "unknown"
    if peer in settings.trusted_proxy_ips:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",", maxsplit=1)[0].strip()
        if first:
            return first[:128]
    return peer


class ProductionMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: object,
        *,
        settings: Settings,
        limiter: InMemoryRateLimiter,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.settings = settings
        self.limiter = limiter
        self.logger = logging.getLogger("clipflow.http")

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        supplied_request_id = request.headers.get("x-request-id", "")
        request_id = (
            supplied_request_id
            if REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else str(uuid4())
        )
        token = request_id_context.set(request_id)
        request.state.request_id = request_id
        request.state.client_id = resolve_client_id(request, self.settings)
        started_at = time.monotonic()
        response: Response
        try:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.settings.max_request_body_bytes:
                response = JSONResponse(
                    {"detail": "Request body is too large."},
                    status_code=413,
                )
            else:
                response = self._rate_limit_response(request) or await call_next(request)
        except ValueError:
            response = JSONResponse({"detail": "Invalid request."}, status_code=400)
        except Exception:
            self.logger.exception("Unhandled request error")
            response = JSONResponse(
                {"detail": "An unexpected server error occurred."},
                status_code=500,
            )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        duration_ms = round((time.monotonic() - started_at) * 1000, 2)
        self.logger.info(
            "Request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        request_id_context.reset(token)
        return response

    def _rate_limit_response(self, request: Request) -> Response | None:
        if request.method != "POST":
            return None
        limits = {
            "/api/analyze": ("analyze", self.settings.analyze_rate_limit),
            "/api/download/jobs": (
                "download-jobs",
                self.settings.download_rate_limit,
            ),
            "/api/download": (
                "download-jobs",
                self.settings.download_rate_limit,
            ),
        }
        configured = limits.get(request.url.path)
        if configured is None:
            return None
        bucket, limit = configured
        decision = self.limiter.check(
            request.state.client_id, bucket, limit
        )
        if decision.allowed:
            return None
        return JSONResponse(
            {"detail": "Too many requests. Please try again shortly."},
            status_code=429,
            headers={"Retry-After": str(decision.retry_after)},
        )
