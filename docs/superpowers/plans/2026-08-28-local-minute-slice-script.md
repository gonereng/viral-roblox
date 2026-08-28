# Local 1-minute Slice Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repo-root script that splits a local video into complete 1-minute Library clips in `MEDIA_ROOT/sources`.

**Architecture:** Thin argparse CLI in `slice_local.py` builds `Settings` from `MEDIA_ROOT` only (no `.env`, no `APP_PASSWORD`) and calls existing `slice_into_minute_parts`. Stem is the source filename stem. Original file is not copied or deleted.

**Tech Stack:** Python 3.10+, existing `roblox_viral.web.library.slice_into_minute_parts`, pytest

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-28-local-minute-slice-script-design.md`
- Entry point: `slice_local.py` at repository root
- Usage: `python slice_local.py path\to\video.mp4`
- Stem from filename only (`long-game.mp4` → `long-game-1.mp4`); no `--stem`
- Destination: `MEDIA_ROOT/sources` (default `media/sources` relative to cwd); create dir if missing
- Do not load `.env`; only process env `MEDIA_ROOT`
- Do not require `APP_PASSWORD` / `APP_SECRET`
- Same slice rules as Library: 60s complete parts; leftover <1 min discarded; <1 min video errors
- Leave original file in place; overwrite existing `stem-N.mp4` (ffmpeg `-y` inside extractor)
- Reuse `slice_into_minute_parts` (do not duplicate ffmpeg)
- Print created names + dest dir on success (exit 0); print error and exit 1 on failure

## File map

| File | Responsibility |
|------|----------------|
| `slice_local.py` | CLI + `media_settings()` + `run()` |
| `tests/test_slice_local.py` | Arg handling, wiring, missing file, under-1-min, source not deleted |
| `README.md` | One usage line for the script |

Do not change `src/roblox_viral/web/library.py`. Existing `tests/web/test_library.py` already covers slice counting and ffmpeg extraction.

---

### Task 1: `slice_local.py` CLI

**Files:**
- Create: `slice_local.py`
- Create: `tests/test_slice_local.py`
- Modify: `README.md` (Usage section, after the `roblox-viral` command table)

**Interfaces:**
- Consumes: `slice_into_minute_parts(settings, uploaded_path, base_stem) -> list[SourceVideo]` from `roblox_viral.web.library`; `Settings` from `roblox_viral.web.config`; `RenderError` from `roblox_viral.render`
- Produces:

```python
def media_settings() -> Settings: ...
def run(argv: list[str] | None = None) -> int: ...
def main() -> None: ...
```

- [ ] **Step 1: Write failing tests**

Create `tests/test_slice_local.py`. Load the root script by path so pytest does not need `.` on `pythonpath`:

```python
import importlib.util
from pathlib import Path

import pytest
from roblox_viral.web.library import SourceVideo

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("slice_local", ROOT / "slice_local.py")
assert _spec is not None and _spec.loader is not None
slice_local = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slice_local)


def test_run_missing_file_exits_1(tmp_path, capsys):
    missing = tmp_path / "nope.mp4"
    assert slice_local.run([str(missing)]) == 1
    err = capsys.readouterr().err
    assert "not found" in err.lower() or "nope.mp4" in err


def test_run_uses_filename_stem_and_sources_dir(tmp_path, monkeypatch, capsys):
    src = tmp_path / "long-game.mp4"
    src.write_bytes(b"vid")
    media = tmp_path / "media"
    monkeypatch.setenv("MEDIA_ROOT", str(media))
    seen = {}

    def fake_slice(settings, uploaded_path, base_stem):
        seen["sources_dir"] = settings.sources_dir
        seen["uploaded_path"] = Path(uploaded_path)
        seen["base_stem"] = base_stem
        dest = settings.sources_dir / f"{base_stem}-1.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"slice")
        return [SourceVideo(dest.name, dest, dest.stat().st_size)]

    monkeypatch.setattr(slice_local, "slice_into_minute_parts", fake_slice)
    assert slice_local.run([str(src)]) == 0
    assert seen["uploaded_path"] == src
    assert seen["base_stem"] == "long-game"
    assert seen["sources_dir"] == media.resolve() / "sources"
    assert src.is_file() and src.read_bytes() == b"vid"
    out = capsys.readouterr().out
    assert "long-game-1.mp4" in out
    assert str(media.resolve() / "sources") in out or "sources" in out


def test_run_under_one_minute_exits_1(tmp_path, monkeypatch, capsys):
    src = tmp_path / "short.mp4"
    src.write_bytes(b"vid")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))

    def boom(settings, uploaded_path, base_stem):
        raise ValueError(
            "Video must be at least 1 minute long "
            "(shorter leftover segments are discarded)"
        )

    monkeypatch.setattr(slice_local, "slice_into_minute_parts", boom)
    assert slice_local.run([str(src)]) == 1
    err = capsys.readouterr().err
    assert "at least 1 minute" in err


def test_media_settings_ignores_app_password(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("APP_SECRET", raising=False)
    s = slice_local.media_settings()
    assert s.media_root == (tmp_path / "media").resolve()
    assert s.require_password is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_slice_local.py -v`

Expected: FAIL collecting or importing (`slice_local.py` missing / `ModuleNotFoundError`).

- [ ] **Step 3: Implement `slice_local.py`**

Create `slice_local.py` at the repository root:

```python
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
```

In `README.md`, insert this block after the Usage options table and before `## Pipeline`:

Split a local gameplay file into Library 1-minute clips (`MEDIA_ROOT/sources`, default `media/sources`):

    python slice_local.py path/to/gameplay.mp4

(Use a bash fenced code block around that command in README.) Then:

Names follow the filename stem (`gameplay-1.mp4`, `gameplay-2.mp4`, …). A leftover shorter than 60 seconds is discarded. Requires ffmpeg and `pip install -e .`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_slice_local.py tests/web/test_library.py -v`

Expected: all selected tests PASS (library tests may skip ffmpeg-backed ones if ffmpeg is missing).

- [ ] **Step 5: Commit**

```bash
git add slice_local.py tests/test_slice_local.py README.md
git commit -m "feat: add local 1-minute library slice script"
```
