import logging
import shutil
import tempfile
from pathlib import Path

from app.config import settings


logger = logging.getLogger(__name__)
TEMP_PREFIX = "job-"


def ensure_temp_root(root: Path = settings.temp_dir) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="readiness-", dir=root):
        pass
    return root


def create_download_temp_directory() -> tempfile.TemporaryDirectory[str]:
    root = ensure_temp_root()
    return tempfile.TemporaryDirectory(prefix=TEMP_PREFIX, dir=root)


def cleanup_orphan_temp_directories(root: Path = settings.temp_dir) -> int:
    """Remove only ClipFlow-owned job directories below the configured root."""
    if not root.exists():
        ensure_temp_root(root)
        return 0
    removed = 0
    for candidate in root.iterdir():
        if candidate.is_dir() and candidate.name.startswith(TEMP_PREFIX):
            shutil.rmtree(candidate, ignore_errors=True)
            if not candidate.exists():
                removed += 1
    if removed:
        logger.info("Removed orphaned temporary directories", extra={"count": removed})
    return removed
