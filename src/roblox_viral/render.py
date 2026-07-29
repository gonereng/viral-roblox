"""ffmpeg-based video render: loop, crop to 9:16, burn captions, mux TTS."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920


class RenderError(RuntimeError):
    """Raised when ffmpeg/ffprobe fails or is missing."""


def require_ffmpeg() -> str:
    """Return ffmpeg path or raise RenderError."""
    path = shutil.which("ffmpeg")
    if not path:
        raise RenderError(
            "ffmpeg not found on PATH. Install ffmpeg and ensure it is available in your shell."
        )
    return path


def require_ffprobe() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise RenderError(
            "ffprobe not found on PATH. Install ffmpeg (includes ffprobe) and try again."
        )
    return path


def probe_duration_seconds(media_path: Path | str) -> float:
    """Return media duration in seconds via ffprobe."""
    ffprobe = require_ffprobe()
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(media_path),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RenderError(f"ffprobe failed for {media_path}: {exc.stderr}") from exc

    data = json.loads(result.stdout or "{}")
    duration = float(data.get("format", {}).get("duration", 0) or 0)
    if duration <= 0:
        raise RenderError(f"Could not determine duration for {media_path}")
    return duration


def _ass_filter_path(ass_path: Path) -> str:
    """Escape path for ffmpeg ass filter (Windows-safe)."""
    p = ass_path.resolve().as_posix()
    p = p.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    return p


def render_video(
    *,
    video_path: Path | str,
    audio_path: Path | str,
    ass_path: Path | str,
    output_path: Path | str,
    keep_temp: bool = False,
    work_dir: Path | str | None = None,
) -> Path:
    """
    Mute + loop gameplay to match narration, crop to 1080x1920, burn ASS, mux TTS.

    Original video audio is discarded by mapping only the TTS audio stream.
    Intermediate files live under work_dir when provided; otherwise only final out is kept
    unless keep_temp is True (work_dir is then left for the caller).
    """
    del keep_temp  # reserved for CLI temp-dir lifecycle; render itself writes only `out`
    ffmpeg = require_ffmpeg()
    video = Path(video_path)
    audio = Path(audio_path)
    ass = Path(ass_path)
    out = Path(output_path)

    if not video.is_file():
        raise RenderError(f"Video not found: {video}")
    if not audio.is_file():
        raise RenderError(f"Audio not found: {audio}")
    if not ass.is_file():
        raise RenderError(f"Captions not found: {ass}")

    out.parent.mkdir(parents=True, exist_ok=True)
    if work_dir is not None:
        Path(work_dir).mkdir(parents=True, exist_ok=True)

    audio_duration = probe_duration_seconds(audio)
    ass_escaped = _ass_filter_path(ass)
    vf = (
        f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},"
        f"ass='{ass_escaped}'"
    )

    cmd = [
        ffmpeg,
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(video),
        "-i",
        str(audio),
        "-t",
        f"{audio_duration:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(out),
    ]

    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RenderError(
            "ffmpeg render failed:\n"
            + (result.stderr[-2000:] if result.stderr else "no stderr")
        )

    return out
