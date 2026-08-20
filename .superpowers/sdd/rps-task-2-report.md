# Task 2 Report: Mode-aware `validate_video_speed`

## Status
**Complete** — mode-specific bounds implemented and wired through job creation paths.

## Changes

### `voice.py`
- Added `SINGLE_VIDEO_SPEED_MIN/MAX` (50–200) and `REDDIT_VIDEO_SPEED_MIN/MAX` (100–500).
- Kept `VIDEO_SPEED_MIN/MAX` as aliases to single bounds for backward compat.
- `validate_video_speed(percent, *, mode="single")` branches on normalized mode; `reddit` uses Reddit range, all others use Single range.

### Call sites
- **`jobs.py`**: normalize mode first, then `validate_video_speed(video_speed, mode=mode)`.
- **`app.py`**: resolve mode before validation in job-create handler.
- **`api_v1.py`**: pass `mode=mode` (already resolved from `type`).

### Tests
- **`test_voice.py`**: reddit allows 500 / rejects 99; single still 50–200; existing tests updated with `mode="single"`.
- **`test_api_v1.py`**: `test_create_accepts_reddit_video_speed_500` — reddit type + pool video + `video_speed=500` → 200.

## Verification

```bash
pytest tests/test_voice.py -k video_speed tests/web/test_api.py::test_api_jobs_rejects_video_speed tests/web/test_api_v1.py::test_create_invalid_video_speed_400 tests/web/test_api_v1.py::test_create_accepts_reddit_video_speed_500 -v
# 8 passed

pytest -v
# 182 passed
```

## Commit
`feat: mode-specific video_speed validation (Reddit 100-500)`

Files: `voice.py`, `test_voice.py`, `jobs.py`, `app.py`, `api_v1.py`, `test_api_v1.py`

## Notes
- ~~`render.py` still calls `validate_video_speed(video_speed)` without mode (defaults to single) — intentional; render receives already-validated values from jobs.~~
- `test_api.py` / `test_jobs.py` unchanged; existing single-mode rejection tests still pass.

---

## Review fix: render-time mode-aware validation

### Problem
`render_video` → `_playback_setpts` called `validate_video_speed(video_speed)` without mode, defaulting to Single 50–200. Reddit jobs with `video_speed` 201–500 failed at render time even though create accepted them.

### Fix
- Added `mode: str = "single"` to `render_video` and threaded it through `_playback_setpts`.
- `jobs.py` passes `mode=record.mode` into `render_video(...)`.
- Tests: `_playback_setpts(500, mode="reddit")` accepts; single mode still rejects 500; `render_video(..., video_speed=500, mode="reddit")` builds `setpts=100/500*PTS`.

### Verification

```bash
pytest tests/test_render.py -k video_speed -v
# 1 passed

pytest -q
# 185 passed
```

### Commit
`fix: pass mode into render video_speed validation` — `9ca9bfd`

Files: `render.py`, `jobs.py`, `test_render.py`
