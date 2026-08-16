# Task 1 Report: Overlay 2× fit-in-frame

**Branch:** `feat/generate-single-reddit`  
**Date:** 2026-08-15  
**Status:** DONE

## Summary

Replaced half-height overlay scaling (`scale=-2:960`) with fit-inside full-frame scaling (`scale=1080:1920:force_original_aspect_ratio=decrease`) after chromakey. Overlay centering and duration enable unchanged.

## TDD Evidence

### RED — Step 2 (failing test before implementation)

Command:

```text
pytest tests/test_render.py::test_render_video_overlay_fits_full_frame -v
```

Result: **FAIL** (exit code 1)

```text
assert 'scale=1080:1920:force_original_aspect_ratio=decrease' in fc
# actual filter still had scale=-2:960
```

### GREEN — Step 4 (full render suite)

Command:

```text
pytest tests/test_render.py -v
```

Result: **PASS** (exit code 0) — **10 passed in 0.09s**

New test:

| Test | Result |
|------|--------|
| `test_render_video_overlay_fits_full_frame` | PASSED |

## Changes

### `src/roblox_viral/render.py`

- Replaced `OVERLAY_HEIGHT = OUTPUT_HEIGHT // 2` with `OVERLAY_MAX_W = OUTPUT_WIDTH`, `OVERLAY_MAX_H = OUTPUT_HEIGHT`.
- Overlay filter: `scale={OVERLAY_MAX_W}:{OVERLAY_MAX_H}:force_original_aspect_ratio=decrease` after chromakey + yuva420p.
- Docstring updated: overlay fits inside full frame, not half height.

### `tests/test_render.py`

- Added `test_render_video_overlay_fits_full_frame` asserting new scale idiom, absence of `scale=-2:`, and `lte(t,3.5)`.

## Commit

```text
b1e15b4 feat: scale greenscreen overlay to fit full frame (2x)
```

Files committed: `render.py`, `tests/test_render.py`

## Self-Review

| Check | OK? | Notes |
|-------|-----|-------|
| Uses fit-inside WxH after chromakey | ✓ | `force_original_aspect_ratio=decrease` |
| Old half-height pattern removed | ✓ | No `OVERLAY_HEIGHT` or `scale=-2:` |
| Center overlay unchanged | ✓ | `(W-w)/2:(H-h)/2` + `lte(t,3.5)` |
| Scope limited to render scale | ✓ | No jobs/CLI/UI changes |
| All render tests pass | ✓ | 10/10 |

**Concerns:** None. Real ffmpeg integration not exercised in unit tests (mocked subprocess as existing tests do). Visual QA with actual greenscreen clips deferred to later Single/Reddit wiring tasks.

## Follow-ups (later tasks)

- Wire overlay path through Single and Reddit generate flows per plan.
