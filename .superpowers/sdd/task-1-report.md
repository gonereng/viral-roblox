# Task 1 Report: `validate_video_speed` + `render_video` setpts

**Branch:** `feat/library-tabs-video-speed`  
**Date:** 2026-08-15  
**Status:** DONE

## Summary

Added `validate_video_speed` and constants in `voice.py`, wired optional ffmpeg `setpts` into `render_video` via `_playback_setpts`, and covered both plain `-vf` and overlay `filter_complex` paths with tests.

## TDD Evidence

### RED — Step 2 (failing tests before implementation)

Command:

```text
pytest tests/test_voice.py::test_validate_video_speed_ok tests/test_render.py::test_render_video_speed_200_inserts_setpts -v
```

Result: **FAIL** (exit code 4)

```text
ImportError: cannot import name 'DEFAULT_VIDEO_SPEED' from 'roblox_viral.voice'
```

Voice test collection failed on missing exports; render test would fail on missing `video_speed` kwarg once voice imports resolved.

### GREEN — Step 4 (full voice + render suites)

Command:

```text
pytest tests/test_voice.py tests/test_render.py -v
```

Result: **PASS** (exit code 0) — **16 passed in 0.17s**

New tests:

| Test | Result |
|------|--------|
| `test_validate_video_speed_ok` | PASSED |
| `test_validate_video_speed_rejects` | PASSED |
| `test_render_video_default_speed_omits_setpts` | PASSED |
| `test_render_video_speed_200_inserts_setpts` | PASSED |
| `test_render_video_overlay_includes_setpts_on_base` | PASSED |

## Changes

### `src/roblox_viral/voice.py`

- `DEFAULT_VIDEO_SPEED = 100`
- `VIDEO_SPEED_MIN, VIDEO_SPEED_MAX = 50, 200`
- `validate_video_speed(percent: int) -> int` — rejects non-int/bool and out-of-range values with `ValueError`; returns valid percent unchanged.

### `src/roblox_viral/render.py`

- Import `validate_video_speed` from `voice`.
- `_playback_setpts(video_speed)` — validates, returns `None` at 100%, else `setpts=100/{S}*PTS`.
- `render_video(..., video_speed: int = 100)` — builds filter chain with optional setpts after crop, before `ass`:
  - **No overlay:** `-vf` chain: scale → crop → [setpts] → ass
  - **With overlay:** `filter_complex` base leg: `[0:v]scale,crop[,setpts][base]` then ass on base; overlay chromakey/enable unchanged.

## Commit

```text
3820b08 feat: apply optional setpts for gameplay video_speed
```

Files committed: `voice.py`, `render.py`, `tests/test_voice.py`, `tests/test_render.py`

## Self-Review

| Check | OK? | Notes |
|-------|-----|-------|
| Constants match brief verbatim | ✓ | 100 default, 50–200 range |
| Validation mirrors pitch/speed helpers | ✓ | Same int/bool guard pattern |
| setpts only when speed ≠ 100 | ✓ | Default path omits setpts |
| setpts after crop, before ass | ✓ | Both vf and overlay base chain |
| Overlay `-t 3.5` unchanged | ✓ | Existing overlay duration preserved |
| No scope creep (jobs/UI/API) | ✓ | Render-only change |
| Existing tests still pass | ✓ | 16/16 |

**Concerns:** None. `render_still` intentionally unchanged (brief scope). Real ffmpeg integration not exercised in unit tests (mocked subprocess as existing tests do).

## Follow-ups (later tasks)

- Wire `video_speed` through jobs, CLI, web API, and UI per plan.
