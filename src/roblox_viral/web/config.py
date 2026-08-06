from __future__ import annotations

import os
import secrets
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    media_root: Path
    app_password: str
    app_secret: str
    require_password: bool = True
    gemini_api_key: str = ""
    youtube_cookies: str = ""
    overlay_video: str = ""

    @property
    def sources_dir(self) -> Path:
        return self.media_root / "sources"

    @property
    def outputs_dir(self) -> Path:
        return self.media_root / "outputs"

    @property
    def jobs_dir(self) -> Path:
        return self.media_root / "jobs"

    @property
    def prompt_path(self) -> Path:
        return self.media_root / "prompt.txt"

    @property
    def youtube_cookies_path(self) -> Path | None:
        """Netscape cookies file for yt-dlp, if configured or present under media/."""
        if self.youtube_cookies.strip():
            path = Path(self.youtube_cookies).expanduser()
            return path if path.is_file() else None
        default = self.media_root / "youtube_cookies.txt"
        return default if default.is_file() else None

    @property
    def overlay_video_path(self) -> Path | None:
        """Greenscreen intro overlay MP4, if configured or present under media/."""
        if self.overlay_video.strip():
            path = Path(self.overlay_video).expanduser()
            return path if path.is_file() else None
        default = self.media_root / "overlay.mp4"
        return default if default.is_file() else None

    def ensure_media_dirs(self) -> None:
        for d in (self.sources_dir, self.outputs_dir, self.jobs_dir):
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> Settings:
        media = Path(os.environ.get("MEDIA_ROOT", "media")).resolve()
        password = os.environ.get("APP_PASSWORD", "")
        secret = os.environ.get("APP_SECRET", "")
        require = os.environ.get("APP_REQUIRE_PASSWORD", "1") not in ("0", "false", "False")
        if require and not password:
            raise RuntimeError("APP_PASSWORD is required")
        if not secret:
            secret = secrets.token_hex(32)
            warnings.warn("APP_SECRET unset; using ephemeral secret (sessions reset on restart)", stacklevel=2)
        gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        youtube_cookies = os.environ.get("YOUTUBE_COOKIES", "")
        overlay_video = os.environ.get("OVERLAY_VIDEO", "")
        return cls(
            media_root=media,
            app_password=password,
            app_secret=secret,
            require_password=require,
            gemini_api_key=gemini_api_key,
            youtube_cookies=youtube_cookies,
            overlay_video=overlay_video,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
