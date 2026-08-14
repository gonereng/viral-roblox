# Task 2 Report: `render_still`

## Status: DONE

## Summary

Added `render_still` to `src/roblox_viral/render.py` with static and Ken Burns modes for turning a still image + TTS + ASS into a 1080×1920 MP4. Three new tests in `tests/test_render.py`. Existing overlay tests unchanged and passing.

## TDD Evidence

### RED — tests added before implementation

Added import of `render_still` and three tests per brief. Ran:

```
python -m pytest tests/test_render.py -v
```

Result (collection error — expected):

```
ImportError: cannot import name 'render_still' from 'roblox_viral.render'
```

Existing overlay tests could not run until import fixed; failure reason confirms missing symbol, not typo.

### GREEN — implementation added

Implemented `KEN_BURNS_ZOOM`, `KEN_BURNS_FPS`, and `render_still` per brief. Ran:

```
python -m pytest tests/test_render.py -v
```

Result: **6 passed** (3 existing overlay + 3 new still tests).

### Full suite (pre-commit)

```
python -m pytest -v
```

Result: **88 passed, 2 skipped** in 5.22s.

## Commit

- `5ffa84e` — feat: render still images to vertical storytime video
- Files: `src/roblox_viral/render.py`, `tests/test_render.py` only

## Self-Review

| Requirement | Met |
|---|---|
| `KEN_BURNS_ZOOM = 1.20`, `KEN_BURNS_FPS = 30` | Yes |
| `render_still(...)` signature with `ken_burns`, `work_dir` | Yes |
| No overlay argument | Yes |
| Static vf: scale/crop 1080×1920 + ass | Yes |
| Ken Burns: cover 1296×2304, zoompan 1.0→1.20, ass | Yes |
| `-loop 1`, `-framerate 30`, two inputs, `-t` from audio | Yes |
| Missing image → `RenderError` with "Image" | Yes |
| `render_video` unchanged | Yes — diff only appends after `render_video` |
| Overlay tests green | Yes |

### Notes

- `work_dir` creates directory when provided but does not write intermediates (matches brief; no temp files needed for still render).
- Ken Burns frame count uses `max(1, round(duration * 30))` as specified.
- No integration test with real ffmpeg (consistent with existing `render_video` unit tests that mock subprocess).

## Files Changed

- `src/roblox_viral/render.py` — +96 lines (`render_still`, constants)
- `tests/test_render.py` — +101 lines (3 tests)
