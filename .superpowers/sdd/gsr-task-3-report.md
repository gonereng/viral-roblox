# Task 3 Report: `build_reddit_background` concat helper

**Branch:** `feat/generate-single-reddit`  
**Date:** 2026-08-15  
**Status:** DONE

## Summary

Added `build_reddit_background` to trim `ClipSegment` inputs and concatenate their video streams in one ffmpeg invocation. The helper resets segment timestamps, discards source audio, re-encodes to H.264/yuv420p, creates requested output/work directories, and raises `RenderError` with ffmpeg stderr on failure.

## TDD Evidence

### RED

Command:

```text
python -m pytest tests/test_render.py -k build_reddit_background -q
```

Result: **FAIL** (exit code 2), as expected before implementation:

```text
ImportError: cannot import name 'build_reddit_background' from 'roblox_viral.render'
```

### GREEN

Focused command:

```text
python -m pytest tests/test_render.py -k build_reddit_background -q
```

Result: **PASS** — **2 passed, 10 deselected**

Full verification:

```text
python -m pytest -q
```

Result: **PASS** — **141 passed in 5.47s**

IDE lint diagnostics: no errors in `render.py` or `test_render.py`.

## Changes

- `src/roblox_viral/render.py`: added the typed concat helper using ffmpeg `filter_complex`, H.264 re-encoding, silent output, directory setup, and failure translation.
- `tests/test_render.py`: added monkeypatch coverage for trimmed concat command construction, output return, work directory creation, and ffmpeg failure handling.

## Commit

`b6c0b07` — `feat: build concat background from reddit clip segments`

## Concerns

- Tests monkeypatch ffmpeg, matching existing render tests; no real-media integration test was added.
- The concat filter expects compatible input video geometry. The current Reddit source pool is expected to contain consistent gameplay clips; mixed resolutions would need per-input normalization.
