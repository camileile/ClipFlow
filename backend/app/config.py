import os
import tempfile
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from typing import Literal, Mapping, TypeAlias, cast
from urllib.parse import urlparse


MP3Bitrate: TypeAlias = Literal[128, 192, 256, 320]
SUPPORTED_MP3_BITRATES: tuple[MP3Bitrate, ...] = (128, 192, 256, 320)


def _integer(
    values: Mapping[str, str],
    name: str,
    default: int,
    *,
    minimum: int = 1,
) -> int:
    raw = values.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        parsed = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if parsed < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return parsed


def _origins(raw: str) -> tuple[str, ...]:
    origins: list[str] = []
    for candidate in raw.split(","):
        origin = candidate.strip().rstrip("/")
        if not origin:
            continue
        parsed = urlparse(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("CORS_ALLOWED_ORIGINS contains an invalid origin")
        origins.append(origin)
    return tuple(dict.fromkeys(origins))


def _trusted_proxy_ips(raw: str) -> frozenset[str]:
    values: set[str] = set()
    for candidate in raw.split(","):
        value = candidate.strip()
        if value:
            values.add(str(ip_address(value)))
    return frozenset(values)


def _log_level(raw: str) -> str:
    level = raw.strip().upper() or "INFO"
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("LOG_LEVEL is invalid")
    return level


@dataclass(frozen=True)
class Settings:
    app_env: Literal["development", "test", "production"]
    app_version: str
    frontend_origin: str | None
    cors_allowed_origins: tuple[str, ...]
    max_duration_seconds: int
    max_filesize_bytes: int
    max_concurrent_jobs: int
    max_jobs_per_client: int
    analyze_rate_limit: int
    download_rate_limit: int
    ready_job_ttl_seconds: int
    failed_job_ttl_seconds: int
    log_level: str
    trusted_proxy_ips: frozenset[str]
    temp_dir: Path
    max_url_length: int
    max_request_body_bytes: int

    @property
    def production(self) -> bool:
        return self.app_env == "production"


def load_settings(values: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if values is None else values
    app_env = env.get("APP_ENV", "development").lower()
    if app_env not in {"development", "test", "production"}:
        raise ValueError("APP_ENV must be development, test, or production")

    raw_frontend_origin = env.get("FRONTEND_ORIGIN", "").strip()
    frontend_origin = (
        _origins(raw_frontend_origin)[0] if raw_frontend_origin else None
    )
    default_origins = (
        frontend_origin
        if app_env == "production" and frontend_origin
        else "http://localhost:3000,http://127.0.0.1:3000"
    )
    allowed_origins = _origins(env.get("CORS_ALLOWED_ORIGINS", default_origins))
    if frontend_origin and frontend_origin not in allowed_origins:
        allowed_origins = (*allowed_origins, frontend_origin)

    configured_temp = env.get("CLIPFLOW_TEMP_DIR", "").strip()
    temp_dir = (
        Path(configured_temp).expanduser()
        if configured_temp
        else Path(tempfile.gettempdir()) / "clipflow"
    )

    return Settings(
        app_env=cast(Literal["development", "test", "production"], app_env),
        app_version=env.get("APP_VERSION", "0.10.0").strip() or "0.10.0",
        frontend_origin=frontend_origin,
        cors_allowed_origins=allowed_origins,
        max_duration_seconds=_integer(env, "MAX_DURATION_SECONDS", 30 * 60),
        max_filesize_bytes=_integer(
            env, "MAX_FILESIZE_BYTES", 750 * 1024 * 1024
        ),
        max_concurrent_jobs=_integer(env, "MAX_CONCURRENT_JOBS", 3),
        max_jobs_per_client=_integer(env, "MAX_JOBS_PER_CLIENT", 2),
        analyze_rate_limit=_integer(env, "RATE_LIMIT", 20),
        download_rate_limit=_integer(env, "DOWNLOAD_JOB_RATE_LIMIT", 5),
        ready_job_ttl_seconds=_integer(env, "READY_JOB_TTL", 15 * 60),
        failed_job_ttl_seconds=_integer(env, "FAILED_JOB_TTL", 5 * 60),
        log_level=_log_level(env.get("LOG_LEVEL", "INFO")),
        trusted_proxy_ips=_trusted_proxy_ips(env.get("TRUSTED_PROXY_IPS", "")),
        temp_dir=temp_dir.resolve(),
        max_url_length=_integer(env, "MAX_URL_LENGTH", 2048, minimum=256),
        max_request_body_bytes=_integer(
            env, "MAX_REQUEST_BODY_BYTES", 16 * 1024, minimum=1024
        ),
    )


settings = load_settings()

MAX_DOWNLOAD_DURATION_SECONDS = settings.max_duration_seconds
MAX_DOWNLOAD_FILESIZE_BYTES = settings.max_filesize_bytes
DOWNLOAD_SOCKET_TIMEOUT_SECONDS = 30
MAX_FILENAME_STEM_LENGTH = 120

DOWNLOAD_PROGRESS_THROTTLE_SECONDS = 0.25
DOWNLOAD_JOB_KEEPALIVE_SECONDS = 10.0
DOWNLOAD_JOB_READY_TTL_SECONDS = settings.ready_job_ttl_seconds
DOWNLOAD_JOB_TERMINAL_TTL_SECONDS = settings.failed_job_ttl_seconds
DOWNLOAD_JOB_CLEANUP_INTERVAL_SECONDS = 30.0
JOB_CAPACITY_RETRY_AFTER_SECONDS = 10
