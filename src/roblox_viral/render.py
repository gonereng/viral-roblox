"""ffmpeg-based video render: loop, crop to 9:16, burn captions, mux TTS."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from roblox_viral.voice import validate_video_speed


OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
OVERLAY_DURATION_S = 3.5
OVERLAY_MAX_W = OUTPUT_WIDTH
OVERLAY_MAX_H = OUTPUT_HEIGHT
OVERLAY_CHROMA_COLOR = "0x00FE00"
OVERLAY_CHROMA_SIMILARITY = "0.30"
OVERLAY_CHROMA_BLEND = "0.10"

KEN_BURNS_ZOOM = 1.20
KEN_BURNS_FPS = 30


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


def _playback_setpts(video_speed: int) -> str | None:
    validate_video_speed(video_speed)
    if video_speed == 100:
        return None
    return f"setpts=100/{video_speed}*PTS"


def render_video(
    *,
    video_path: Path | str,
    audio_path: Path | str,
    ass_path: Path | str,
    output_path: Path | str,
    keep_temp: bool = False,
    work_dir: Path | str | None = None,
    overlay_path: Path | str | None = None,
    video_speed: int = 100,
) -> Path:
    """
    Mute + loop gameplay to match narration, crop to 1080x1920, burn ASS, mux TTS.

    When overlay_path is set, chromakey the first OVERLAY_DURATION_S of that clip and
    composite it centered (fit inside full frame) over captions at the start.

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

    overlay: Path | None = None
    if overlay_path is not None:
        overlay = Path(overlay_path)
        if not overlay.is_file():
            raise RenderError(f"Overlay video not found: {overlay}")

    out.parent.mkdir(parents=True, exist_ok=True)
    if work_dir is not None:
        Path(work_dir).mkdir(parents=True, exist_ok=True)

    audio_duration = probe_duration_seconds(audio)
    ass_escaped = _ass_filter_path(ass)
    setpts = _playback_setpts(video_speed)

    if overlay is None:
        parts = [
            f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase",
            f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}",
        ]
        if setpts:
            parts.append(setpts)
        parts.append(f"ass='{ass_escaped}'")
        vf = ",".join(parts)
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
    else:
        base_parts = [
            f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase",
            f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}",
        ]
        if setpts:
            base_parts.append(setpts)
        base = ",".join(base_parts)
        fc = (
            f"[0:v]{base}[base];"
            f"[base]ass='{ass_escaped}'[cap];"
            f"[2:v]chromakey={OVERLAY_CHROMA_COLOR}:{OVERLAY_CHROMA_SIMILARITY}:{OVERLAY_CHROMA_BLEND},"
            f"format=yuva420p,scale={OVERLAY_MAX_W}:{OVERLAY_MAX_H}:force_original_aspect_ratio=decrease[ov];"
            f"[cap][ov]overlay=(W-w)/2:(H-h)/2:enable='lte(t,{OVERLAY_DURATION_S})':eof_action=pass[outv]"
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
            f"{OVERLAY_DURATION_S}",
            "-i",
            str(overlay),
            "-t",
            f"{audio_duration:.3f}",
            "-filter_complex",
            fc,
            "-map",
            "[outv]",
            "-map",
            "1:a:0",
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


def render_still(
    *,
    image_path: Path | str,
    audio_path: Path | str,
    ass_path: Path | str,
    output_path: Path | str,
    ken_burns: bool = False,
    work_dir: Path | str | None = None,
) -> Path:
    """Hold (or Ken-Burns zoom) an image for TTS duration; burn ASS; mux TTS. No overlay."""
    ffmpeg = require_ffmpeg()
    image = Path(image_path)
    audio = Path(audio_path)
    ass = Path(ass_path)
    out = Path(output_path)

    if not image.is_file():
        raise RenderError(f"Image not found: {image}")
    if not audio.is_file():
        raise RenderError(f"Audio not found: {audio}")
    if not ass.is_file():
        raise RenderError(f"Captions not found: {ass}")

    out.parent.mkdir(parents=True, exist_ok=True)
    if work_dir is not None:
        Path(work_dir).mkdir(parents=True, exist_ok=True)

    audio_duration = probe_duration_seconds(audio)
    ass_escaped = _ass_filter_path(ass)

    if ken_burns:
        cover_w = int(OUTPUT_WIDTH * KEN_BURNS_ZOOM)
        cover_h = int(OUTPUT_HEIGHT * KEN_BURNS_ZOOM)
        frames = max(1, round(audio_duration * KEN_BURNS_FPS))
        zoom_delta = KEN_BURNS_ZOOM - 1.0
        vf = (
            f"scale={cover_w}:{cover_h}:force_original_aspect_ratio=increase,"
            f"crop={cover_w}:{cover_h},"
            f"zoompan=z='min(1+{zoom_delta}*on/{frames},{KEN_BURNS_ZOOM})':"
            f"d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:fps={KEN_BURNS_FPS},"
            f"ass='{ass_escaped}'"
        )
    else:
        vf = (
            f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},"
            f"ass='{ass_escaped}'"
        )

    cmd = [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-framerate",
        str(KEN_BURNS_FPS),
        "-i",
        str(image),
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
        "-pix_fmt",
        "yuv420p",
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
