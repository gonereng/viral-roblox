# Task 4 Report: JobManager `single` / `reddit` modes

**Branch:** `feat/generate-single-reddit`  
**Date:** 2026-08-15  
**Status:** DONE

## Summary

Added normalized `single`, `picture`, and `reddit` JobManager modes while retaining `roblox` as a legacy alias for `single`. Single jobs now resolve only from the sources library, Reddit jobs require a non-empty videos pool, and legacy disk records hydrate as `single`.

Reddit execution now probes narration and source durations, plans clips, builds `job_dir/reddit_bg.mp4`, and renders it with the existing overlay and configured video speed.

## TDD Evidence

### RED

Command:

```text
python -m pytest tests/web/test_jobs.py -q
```

Result: **FAIL** — **8 failed, 17 passed**. Failures showed the missing `single`/`reddit` modes, normalizer, Reddit validation, hydration normalization, and Reddit pipeline.

A focused output-path test also failed before the final implementation adjustment:

```text
python -m pytest tests/web/test_jobs.py::test_run_reddit_builds_background_and_renders -q
```

Result: **FAIL** because `render_video` received `None` instead of `job_dir/reddit_bg.mp4` when the mocked builder returned no value.

### GREEN

Full verification:

```text
python -m pytest -q
```

Result: **PASS** — **147 passed in 6.10s**

IDE lint diagnostics: no errors in the four changed Python files.

## Changes

- `src/roblox_viral/web/jobs.py`: mode normalization, single-source resolution, Reddit pool validation/planning/background generation, and legacy hydration.
- `tests/web/test_jobs.py`: coverage for normalization, validation, hydration, and Reddit rendering.
- `tests/web/test_api.py`, `tests/web/test_api_v1.py`: updated mode expectations and source-library behavior from `roblox` to `single`.

## Commit

`ad795c7` — `feat(web): job modes single and reddit with concat background`

## Concerns

- Reddit rendering is tested with mocked probing/build/render functions; real ffmpeg integration remains covered at the lower-level render helper.
- Existing unrelated working-tree changes were left untouched.
