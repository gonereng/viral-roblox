# Local 1-minute slice script — Design

**Date:** 2026-08-28  
**Status:** Approved (conversation)  
**Builds on:** Library 1-minute clip slicing (`slice_into_minute_parts` in `src/roblox_viral/web/library.py`)

## Goal

Add a repo-root script so a video already on disk can be split into complete 1-minute Library clips without using the web upload UI.

## Product decisions

- **Entry point:** `slice_local.py` at the repository root.
- **Usage:** `python slice_local.py path\to\video.mp4` (any container ffmpeg can read; outputs are always `.mp4`).
- **Stem:** taken from the source filename (`long-game.mp4` → `long-game-1.mp4`, `long-game-2.mp4`, …). No `--stem` flag.
- **Destination:** `MEDIA_ROOT/sources` (default `media/sources` relative to the working directory). Create the dir if missing. Clips appear on Library → 1-minute clips and on Generate → Single background. Do not load `.env`; only the process environment’s `MEDIA_ROOT` is used.
- **Slice rules:** identical to Library upload — complete 60-second parts only; leftover shorter than 1 minute is discarded; video shorter than 1 minute is an error.
- **Original file:** left in place (not copied or deleted).
- **Overwrite:** existing `stem-N.mp4` files with the same names are overwritten (ffmpeg `-y`, same as current extractor).
- **ffmpeg:** must be on PATH. Stream-copy first, re-encode fallback — reuse `_extract_minute_slice` via `slice_into_minute_parts`.
- **Auth env:** do not require `APP_PASSWORD` / `APP_SECRET`. Build `Settings` from `MEDIA_ROOT` only (plus dummy unused auth fields if the dataclass requires them).

## Out of scope

- PowerShell/ffmpeg duplicate of the slice pipeline
- `roblox-viral slice` CLI subcommand
- Optional output directory or `--stem`
- Changing Library upload behavior

## Errors

| Case | Behavior |
|------|----------|
| Missing / not a file | Print error, exit 1 |
| Under 1 minute | Same `ValueError` text as Library, exit 1 |
| ffmpeg failure | Surface existing `RenderError` / `ValueError` message, exit 1 |

Print created clip names and destination dir on success; exit 0.

## Testing

Thin tests for the script’s argument handling and wiring into `slice_into_minute_parts` (mocked ffmpeg / probe). Do not re-test ffmpeg extraction; existing `tests/web/test_library.py` covers slice counting and naming.
