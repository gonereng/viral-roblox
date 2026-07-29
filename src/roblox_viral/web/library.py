from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from roblox_viral.web.config import Settings

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._ -]+\.(mp4|mov|webm|mkv)$", re.I)
MAX_UPLOAD_BYTES = 500_000_000


@dataclass(frozen=True)
class SourceVideo:
    name: str
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


def list_sources(settings: Settings) -> list[SourceVideo]:
    items: list[SourceVideo] = []
    for path in sorted(settings.sources_dir.iterdir()):
        if path.is_file() and _SAFE_NAME.match(path.name):
            items.append(SourceVideo(path.name, path, path.stat().st_size))
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


def save_upload(settings: Settings, filename: str, data: bytes) -> SourceVideo:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"Upload exceeds maximum size of {MAX_UPLOAD_BYTES} bytes"
        )
    safe = _safe_name(filename)
    path = settings.sources_dir / safe
    path.write_bytes(data)
    return SourceVideo(safe, path, path.stat().st_size)


def delete_source(settings: Settings, name: str) -> None:
    resolve_source(settings, name).unlink()
