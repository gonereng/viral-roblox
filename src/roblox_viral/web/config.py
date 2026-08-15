from __future__ import annotations

import os
import secrets
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def resolve_overlay_video_path(
    media_root: Path | None = None,
    overlay_video: str | None = None,
) -> Path | None:
    """Return greenscreen overlay path if the file exists."""
    env_path = (
        overlay_video
        if overlay_video is not None
        else os.environ.get("OVERLAY_VIDEO", "")
    ).strip()
    if env_path:
        path = Path(env_path).expanduser()
        return path if path.is_file() else None
    root = media_root if media_root is not None else Path(os.environ.get("MEDIA_ROOT", "media"))
    default = Path(root) / "overlay.mp4"
    if default.is_file():
        return default
    packaged = Path(__file__).resolve().parent.parent / "assets" / "overlay.mp4"
    return packaged if packaged.is_file() else None


@dataclass(frozen=True)
class Settings:
    media_root: Path
    app_password: str
    app_secret: str
    require_password: bool = True
    gemini_api_key: str = ""
    overlay_video: str = ""
    api_key: str = ""

    @property
    def sources_dir(self) -> Path:
        return self.media_root / "sources"

    @property
    def videos_dir(self) -> Path:
        return self.media_root / "videos"

    @property
    def images_dir(self) -> Path:
        return self.media_root / "images"

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
    def overlay_video_path(self) -> Path | None:
        """Greenscreen intro overlay MP4, if configured or present under media/."""
        return resolve_overlay_video_path(self.media_root, self.overlay_video)

    def ensure_media_dirs(self) -> None:
        for d in (
            self.sources_dir,
            self.videos_dir,
            self.images_dir,
            self.outputs_dir,
            self.jobs_dir,
        ):
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
        overlay_video = os.environ.get("OVERLAY_VIDEO", "")
        api_key = os.environ.get("API_KEY", "")
        return cls(
            media_root=media,
            app_password=password,
            app_secret=secret,
            require_password=require,
            gemini_api_key=gemini_api_key,
            overlay_video=overlay_video,
            api_key=api_key,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
