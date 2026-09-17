from app.services import ffmpeg


def test_detect_media_tools_requires_ffmpeg_and_ffprobe(
    monkeypatch,
) -> None:
    paths = {
        "ffmpeg": "C:/tools/ffmpeg.exe",
        "ffprobe": "C:/tools/ffprobe.exe",
    }
    monkeypatch.setattr(ffmpeg.shutil, "which", paths.get)

    tools = ffmpeg.detect_media_tools()

    assert tools.available is True
    assert tools.ffmpeg == "C:/tools/ffmpeg.exe"
    assert tools.ffprobe == "C:/tools/ffprobe.exe"


def test_detect_media_tools_reports_partial_installation_as_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        ffmpeg.shutil,
        "which",
        lambda executable: "C:/tools/ffmpeg.exe" if executable == "ffmpeg" else None,
    )

    assert ffmpeg.detect_media_tools().available is False

