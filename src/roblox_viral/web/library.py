from __future__ import annotations

import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from roblox_viral.render import RenderError, probe_duration_seconds, require_ffmpeg
from roblox_viral.web.config import Settings

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._ ()-]+\.(mp4|mov|webm|mkv)$", re.I)
_SAFE_IMAGE_NAME = re.compile(r"^[A-Za-z0-9._ -]+\.(jpg|jpeg|png|webp)$", re.I)
MAX_UPLOAD_BYTES = 500_000_000
MAX_IMAGE_UPLOAD_BYTES = 20_000_000
SLICE_SECONDS = 60

_MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def media_type_for_name(name: str) -> str:
    return _MEDIA_TYPES.get(Path(name).suffix.lower(), "application/octet-stream")


@dataclass(frozen=True)
class SourceVideo:
    name: str
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class SourceImage:
    name: str
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class RobloxSource:
    name: str
    kind: str  # "slice" | "video"
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class OutputVideo:
    name: str
    path: Path
    size_bytes: int


def _safe_name(name: str) -> str:
    base = Path(name).name
    if base != name or not _SAFE_NAME.match(base):
        raise ValueError(f"Invalid video filename: {name!r}")
    return base


def _safe_image_name(name: str) -> str:
    base = Path(name).name
    if base != name or not _SAFE_IMAGE_NAME.match(base):
        raise ValueError(f"Invalid image filename: {name!r}")
    return base


def validate_video_filename(name: str) -> str:
    return _safe_name(name)


def validate_image_filename(name: str) -> str:
    return _safe_image_name(name)


def _commit_image_upload(images_dir: Path, safe: str, data: bytes) -> Path:
    """Exclusively create an image; suffix on name collision."""
    stem = Path(safe).stem
    suffix = Path(safe).suffix.lower()
    dest = images_dir / safe
    while True:
        try:
            with open(dest, "xb") as fh:
                fh.write(data)
        except FileExistsError:
            dest = images_dir / f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
            continue
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
        return dest


def _commit_video_upload(videos_dir: Path, safe: str, data: bytes) -> Path:
    stem = Path(safe).stem
    suffix = Path(safe).suffix.lower()
    dest = videos_dir / safe
    while True:
        try:
            with open(dest, "xb") as fh:
                fh.write(data)
        except FileExistsError:
            dest = videos_dir / f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
            continue
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
        return dest


def plan_full_minute_count(duration_seconds: float) -> int:
    """How many complete 1-minute slices to keep (tail under 60s discarded)."""
    if duration_seconds < 0:
        return 0
    return int(duration_seconds // SLICE_SECONDS)


def slice_part_name(stem: str, part: int) -> str:
    """e.g. gameplay + 1 → gameplay-1.mp4"""
    return f"{stem}-{part}.mp4"


def make_output_name(source_name: str, when: datetime | None = None) -> str:
    """
    <uploaded-slice-stem>-<YYYY-MM-DD_HHMMSS>.mp4
    e.g. gameplay-1-2026-07-30_194512.mp4
    """
    stem = Path(source_name).stem
    stamp = (when or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    return f"{stem}-{stamp}.mp4"


def list_sources(settings: Settings) -> list[SourceVideo]:
    items: list[SourceVideo] = []
    for path in sorted(settings.sources_dir.iterdir()):
        if path.is_file() and _SAFE_NAME.match(path.name) and not path.name.startswith("."):
            items.append(SourceVideo(path.name, path, path.stat().st_size))
    return items


def list_videos(settings: Settings) -> list[SourceVideo]:
    items: list[SourceVideo] = []
    if not settings.videos_dir.is_dir():
        return items
    for path in sorted(settings.videos_dir.iterdir()):
        if path.is_file() and _SAFE_NAME.match(path.name) and not path.name.startswith("."):
            items.append(SourceVideo(path.name, path, path.stat().st_size))
    return items


def list_images(settings: Settings) -> list[SourceImage]:
    items: list[SourceImage] = []
    if not settings.images_dir.is_dir():
        return items
    for path in sorted(settings.images_dir.iterdir()):
        if path.is_file() and _SAFE_IMAGE_NAME.match(path.name) and not path.name.startswith("."):
            items.append(SourceImage(path.name, path, path.stat().st_size))
    return items


def list_outputs(settings: Settings, *, limit: int = 10) -> list[OutputVideo]:
    paths = [
        p
        for p in settings.outputs_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".mp4"
    ]
    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [OutputVideo(p.name, p, p.stat().st_size) for p in paths[:limit]]


def resolve_source(settings: Settings, name: str) -> Path:
    safe = _safe_name(name)
    path = (settings.sources_dir / safe).resolve()
    if not path.is_relative_to(settings.sources_dir.resolve()):
        raise ValueError("Invalid path")
    if not path.is_file():
        raise FileNotFoundError(safe)
    return path


def resolve_video(settings: Settings, name: str) -> Path:
    safe = _safe_name(name)
    path = (settings.videos_dir / safe).resolve()
    if not path.is_relative_to(settings.videos_dir.resolve()):
        raise ValueError("Invalid path")
    if not path.is_file():
        raise FileNotFoundError(safe)
    return path


def resolve_image(settings: Settings, name: str) -> Path:
    safe = _safe_image_name(name)
    path = (settings.images_dir / safe).resolve()
    if not path.is_relative_to(settings.images_dir.resolve()):
        raise ValueError("Invalid path")
    if not path.is_file():
        raise FileNotFoundError(safe)
    return path


def _extract_minute_slice(src: Path, dest: Path, start_seconds: float) -> None:
    ffmpeg = require_ffmpeg()
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{start_seconds:.3f}",
        "-i",
        str(src),
        "-t",
        str(SLICE_SECONDS),
        "-c",
        "copy",
        str(dest),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0 or not dest.is_file() or dest.stat().st_size == 0:
        # Some containers need a re-encode for clean cuts
        cmd_re = [
            ffmpeg,
            "-y",
            "-ss",
            f"{start_seconds:.3f}",
            "-i",
            str(src),
            "-t",
            str(SLICE_SECONDS),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(dest),
        ]
        result = subprocess.run(cmd_re, check=False, capture_output=True, text=True)
        if result.returncode != 0 or not dest.is_file():
            raise RenderError(
                "ffmpeg slice failed:\n"
                + (result.stderr[-1500:] if result.stderr else "no stderr")
            )


def slice_into_minute_parts(
    settings: Settings, uploaded_path: Path, base_stem: str
) -> list[SourceVideo]:
    """
    Split uploaded_path into <stem>-1.mp4, <stem>-2.mp4, ...
    Discard a trailing remainder shorter than one minute.
    """
    try:
        duration = probe_duration_seconds(uploaded_path)
    except RenderError as exc:
        raise ValueError(str(exc)) from exc

    count = plan_full_minute_count(duration)
    if count < 1:
        raise ValueError(
            "Video must be at least 1 minute long "
            "(shorter leftover segments are discarded)"
        )

    created: list[SourceVideo] = []
    for part in range(1, count + 1):
        name = slice_part_name(base_stem, part)
        dest = settings.sources_dir / name
        start = (part - 1) * SLICE_SECONDS
        try:
            _extract_minute_slice(uploaded_path, dest, float(start))
        except RenderError as exc:
            for prev in created:
                prev.path.unlink(missing_ok=True)
            raise ValueError(str(exc)) from exc
        created.append(SourceVideo(name, dest, dest.stat().st_size))
    return created


def save_upload(settings: Settings, filename: str, data: bytes) -> list[SourceVideo]:
    """
    Save upload, slice into 1-minute parts named <stem>-<n>.mp4,
    discard a final part shorter than 1 minute. Original upload is not kept.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"Upload exceeds maximum size of {MAX_UPLOAD_BYTES} bytes"
        )
    safe = _safe_name(filename)
    stem = Path(safe).stem
    suffix = Path(safe).suffix.lower() or ".mp4"
    temp = settings.sources_dir / f".upload-{uuid.uuid4().hex}{suffix}"
    try:
        temp.write_bytes(data)
        return slice_into_minute_parts(settings, temp, stem)
    finally:
        temp.unlink(missing_ok=True)


def save_video(settings: Settings, filename: str, data: bytes) -> SourceVideo:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"Upload exceeds maximum size of {MAX_UPLOAD_BYTES} bytes"
        )
    safe = _safe_name(filename)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    dest = _commit_video_upload(settings.videos_dir, safe, data)
    return SourceVideo(dest.name, dest, dest.stat().st_size)


def save_image(settings: Settings, filename: str, data: bytes) -> SourceImage:
    if len(data) > MAX_IMAGE_UPLOAD_BYTES:
        raise ValueError(
            f"Upload exceeds maximum size of {MAX_IMAGE_UPLOAD_BYTES} bytes"
        )
    safe = _safe_image_name(filename)
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    dest = _commit_image_upload(settings.images_dir, safe, data)
    return SourceImage(dest.name, dest, dest.stat().st_size)


def delete_source(settings: Settings, name: str) -> None:
    resolve_source(settings, name).unlink()


def delete_video(settings: Settings, name: str) -> None:
    resolve_video(settings, name).unlink()


def delete_image(settings: Settings, name: str) -> None:
    resolve_image(settings, name).unlink()


def resolve_roblox_media(settings: Settings, name: str) -> Path:
    try:
        return resolve_source(settings, name)
    except FileNotFoundError:
        return resolve_video(settings, name)


def list_roblox_sources(settings: Settings) -> list[RobloxSource]:
    out: list[RobloxSource] = []
    for s in list_sources(settings):
        out.append(RobloxSource(s.name, "slice", s.path, s.size_bytes))
    for v in list_videos(settings):
        out.append(RobloxSource(v.name, "video", v.path, v.size_bytes))
    return out
