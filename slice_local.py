"""Split a local video into 1-minute Library clips (media/sources)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from roblox_viral.render import RenderError
from roblox_viral.web.config import Settings
from roblox_viral.web.library import slice_into_minute_parts


def media_settings() -> Settings:
    media = Path(os.environ.get("MEDIA_ROOT", "media")).resolve()
    return Settings(
        media_root=media,
        app_password="",
        app_secret="unused",
        require_password=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Split a local video into complete 1-minute clips in MEDIA_ROOT/sources "
            "(default: media/sources)."
        )
    )
    parser.add_argument(
        "video",
        type=Path,
        help="Path to a local video (any container ffmpeg can read)",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    video: Path = args.video.expanduser()
    if not video.is_file():
        print(f"error: video not found: {video}", file=sys.stderr)
        return 1

    settings = media_settings()
    settings.ensure_media_dirs()
    try:
        created = slice_into_minute_parts(settings, video, video.stem)
    except (ValueError, FileNotFoundError, RenderError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    dest = settings.sources_dir
    print(f"Wrote {len(created)} clip(s) to {dest}:")
    for item in created:
        print(f"  {item.name}")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
