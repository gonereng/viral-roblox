from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

YOUTUBE_FORMAT = (
    "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/"
    "b[height<=1080][ext=mp4]/b[height<=1080]"
)

_STEM_RE = re.compile(r"^[A-Za-z0-9._ -]+$")
_VIDEO_EXT = re.compile(r"\.(mp4|mov|webm|mkv)$", re.I)


def validate_youtube_url(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("YouTube URL is required")
    parsed = urlparse(cleaned)
    host = (parsed.netloc or "").lower()
    if "youtube.com" not in host and "youtu.be" not in host:
        raise ValueError("URL must be a YouTube link")
    return cleaned


def validate_stem(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("Name is required")
    if _VIDEO_EXT.search(cleaned):
        raise ValueError("Name must not include a file extension")
    if (
        not _STEM_RE.fullmatch(cleaned)
        or ".." in cleaned
        or "/" in cleaned
        or "\\" in cleaned
    ):
        raise ValueError("Invalid name (use letters, numbers, spaces, . _ -)")
    return cleaned


def download_youtube(url: str, dest: Path) -> Path:
    """Download best ≤1080p MP4 to dest. Raises RuntimeError on failure."""
    safe_url = validate_youtube_url(url)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": YOUTUBE_FORMAT,
        "outtmpl": str(dest.with_suffix("")),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([safe_url])
    except Exception as exc:
        raise RuntimeError(f"YouTube download failed: {exc}") from exc

    produced = dest if dest.is_file() else dest.with_suffix(".mp4")
    if not produced.is_file():
        candidates = list(dest.parent.glob(dest.stem + ".*"))
        if not candidates:
            raise RuntimeError("YouTube download produced no file")
        produced = candidates[0]
    if produced != dest:
        produced.replace(dest)
    if not dest.is_file() or dest.stat().st_size == 0:
        raise RuntimeError("YouTube download produced no file")
    return dest
