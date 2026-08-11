from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

YOUTUBE_FORMAT = (
    "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/"
    "b[height<=1080][ext=mp4]/b[height<=1080]/b"
)

# Prefer non-web clients; YouTube often 403s default web progressive URLs.
_YOUTUBE_EXTRACTOR_ARGS = {
    "youtube": {"player_client": ["android", "ios", "web"]}
}
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}

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


def download_youtube(
    url: str,
    dest: Path,
    *,
    cookies_path: Path | None = None,
) -> Path:
    """Download best ≤1080p MP4 to dest. Raises RuntimeError on failure."""
    safe_url = validate_youtube_url(url)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Force an extension placeholder so yt-dlp does not write a bare stem path.
    outtmpl = str(dest.parent / f"{dest.stem}.%(ext)s")
    opts: dict = {
        "format": YOUTUBE_FORMAT,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "extractor_args": _YOUTUBE_EXTRACTOR_ARGS,
        "http_headers": _HTTP_HEADERS,
    }
    if cookies_path is not None:
        cookie_file = Path(cookies_path)
        if not cookie_file.is_file():
            raise RuntimeError(f"YouTube cookies file not found: {cookie_file}")
        opts["cookiefile"] = str(cookie_file)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([safe_url])
    except Exception as exc:
        msg = str(exc)
        if "Sign in to confirm" in msg or "not a bot" in msg.lower():
            raise RuntimeError(
                "YouTube bot check blocked the download. Export browser cookies to "
                "media/youtube_cookies.txt (or set YOUTUBE_COOKIES to that file path), "
                "then retry. See README."
            ) from exc
        raise RuntimeError(f"YouTube download failed: {exc}") from exc

    produced = _find_download_product(dest)
    if produced is None:
        raise RuntimeError("YouTube download produced no file")
    if produced != dest:
        produced.replace(dest)
    if not dest.is_file() or dest.stat().st_size == 0:
        raise RuntimeError("YouTube download produced no file")
    return dest


def _find_download_product(dest: Path) -> Path | None:
    """Locate the file yt-dlp wrote for this dest stem."""
    candidates: list[Path] = []
    for path in (
        dest,
        dest.with_suffix(".mp4"),
        dest.with_suffix(".mkv"),
        dest.with_suffix(".webm"),
        dest.parent / dest.stem,  # bare name without extension
    ):
        if path.is_file() and path.stat().st_size > 0:
            candidates.append(path)
    for path in sorted(dest.parent.glob(dest.stem + ".*")):
        if path.is_file() and path.stat().st_size > 0 and path not in candidates:
            candidates.append(path)
    return candidates[0] if candidates else None
