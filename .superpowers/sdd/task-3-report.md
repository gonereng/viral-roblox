# Task 3 Report: JobManager `video_speed` + roblox resolve

**Date:** 2026-08-15  
**Status:** DONE

## Summary

Wired `video_speed` through `JobRecord`, `JobManager.create`/`run_job`, and `POST /api/jobs`. Non-ephemeral Roblox jobs now resolve media via `resolve_roblox_media` (sources first, videos fallback). `render_video` receives `video_speed=record.video_speed`. Value is validated (50–200), persisted in `status.json`, and hydrated on disk reload.

## TDD Evidence

### RED — Step 2 (failing tests before implementation)

Command:

```text
pytest tests/web/test_jobs.py tests/web/test_api.py -k video_speed -v
```

Result: **FAIL** (exit code 1) — 5 failed

```text
TypeError: JobManager.create() got an unexpected keyword argument 'video_speed'
KeyError: 'video_speed'
assert 200 == 400  (invalid video_speed not rejected)
```

### GREEN — Step 4 (targeted + full suite)

Command:

```text
pytest tests/web/test_jobs.py tests/web/test_api.py -k video_speed -v
pytest tests/web/test_jobs.py tests/web/test_api.py -v
```

Result: **PASS** (exit code 0) — **5 passed** (targeted), **41 passed in 2.04s** (full suite)

New tests:

| Test | Result |
|------|--------|
| `test_create_job_persists_video_speed` | PASSED |
| `test_create_job_rejects_bad_video_speed` | PASSED |
| `test_run_job_passes_video_speed_to_render` | PASSED |
| `test_api_jobs_accepts_video_speed` | PASSED |
| `test_api_jobs_rejects_video_speed` | PASSED |

## Implementation

### `jobs.py`

- Import `DEFAULT_VIDEO_SPEED`, `validate_video_speed`, `resolve_roblox_media`
- `JobRecord.video_speed: int = DEFAULT_VIDEO_SPEED`
- `create(..., video_speed=...)` validates and persists; non-ephemeral roblox uses `resolve_roblox_media`
- `get()` hydrates `video_speed` from `status.json` (defaults to 100 if missing)
- `run_job` resolves roblox via `resolve_roblox_media`; passes `video_speed=record.video_speed` to `render_video`

### `app.py`

- `CreateJobBody.video_speed: int | None = None`
- Handler defaults to `DEFAULT_VIDEO_SPEED`, validates with `validate_video_speed`, returns 400 on invalid

## Commit

```text
3d52243 feat(web): persist and apply job video_speed for Roblox renders
```

Files: `jobs.py`, `app.py`, `test_jobs.py`, `test_api.py`

## Brief Checklist

| Requirement | Status |
|-------------|--------|
| `JobRecord.video_speed` field | ✓ |
| `create` validates + uses `resolve_roblox_media` | ✓ |
| `run_job` passes `video_speed` to `render_video` | ✓ |
| Persist/load in `status.json` | ✓ |
| `CreateJobBody` + API validation | ✓ |
| 5 new tests | ✓ |

## Concerns / Follow-ups

- HTML form `video_speed` wiring is Task 4 (not in scope here).
- Existing jobs without `video_speed` in `status.json` default to 100 on hydrate.
