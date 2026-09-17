import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class MediaTools:
    ffmpeg: str | None
    ffprobe: str | None

    @property
    def available(self) -> bool:
        return self.ffmpeg is not None and self.ffprobe is not None


def detect_media_tools() -> MediaTools:
    """Locate the real FFmpeg executables without invoking a shell."""
    return MediaTools(
        ffmpeg=shutil.which("ffmpeg"),
        ffprobe=shutil.which("ffprobe"),
    )

