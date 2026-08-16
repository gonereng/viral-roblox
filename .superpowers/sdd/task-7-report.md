# Task 7 Report: n8n API `video_speed` + raw `source_name`

**Date:** 2026-08-15  
**Status:** DONE

## Summary

Added optional `video_speed` form field to `POST /api/v1/videos` (parsed via `_optional_int`, validated 50–200, default 100). Raw library videos in `videos/` resolve via existing `JobManager.create` → `resolve_roblox_media`. Updated README and `scripts/test-n8n-api.ps1`.

## TDD Evidence

### RED

```text
pytest tests/web/test_api_v1.py::test_create_accepts_video_speed \
  tests/web/test_api_v1.py::test_create_resolves_raw_library_video \
  tests/web/test_api_v1.py::test_create_invalid_video_speed_400 -v
```

Result: **FAIL** — `video_speed` ignored (default 100); invalid `9` returned 200.

### GREEN

```text
pytest tests/web/test_api_v1.py -v
```

Result: **PASS** — 19 passed.

## Commit

```text
feat(api): optional video_speed and raw library source_name for n8n
```

## Concerns

- None. Raw `source_name` resolution was already wired in `JobManager`; this task only needed API exposure and tests.
