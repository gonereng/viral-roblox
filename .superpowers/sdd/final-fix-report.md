# Final Fix Report

**Status:** DONE  
**Branch:** `feature/webapp`  
**Commit:** `fix(web): job status reload, upload limit, and job JSON validation`

## Fixes

1. **JobManager.get() hydrates from disk** — Validates `job_id` as 32-char hex; loads `jobs_dir / job_id / status.json` into a `JobRecord` and caches in memory. Path checked with `is_relative_to`.
2. **Bound uploads** — Cap `MAX_UPLOAD_BYTES = 500_000_000`; stream-read in 1 MiB chunks and reject oversize with HTTP 400 / template error.
3. **POST /api/jobs invalid JSON → 400** — `CreateJobBody` + `model_validate_json`; decode/validation errors return 400 `"Invalid JSON body"`.
4. **Minors** — `path.is_relative_to(base)` in library/media routes; `app.js` prepends new output into Recent outputs on job done.

## Test results

```text
python -m pytest tests/web -v
26 passed in 1.43s

python -m pytest -q
36 passed in 1.34s
```

**Result:** PASS

## Picture Generation Addendum

### Changes

- Added `-pix_fmt yuv420p` to `render_still` so static and Ken Burns renders use browser-compatible chroma subsampling.
- Asserted `ass=` and `yuv420p` in both `render_still` command tests.
- Replaced hard-link-based image upload commits with exclusive `xb` file creation, collision retries, and partial-file cleanup on write failure.
- Added a regression test proving image uploads do not require hard-link support.

### Tests

- `python -m pytest tests/test_render.py tests/web/test_library.py -v`
  - `17 passed, 2 skipped in 0.34s`
- `python -m pytest -v`
  - `102 passed, 2 skipped, 1 warning in 5.38s`
  - Warning: upstream Starlette deprecation warning from `fastapi.testclient`.

`python -m pytest` was used because the standalone `pytest` command is not on this shell's `PATH`.
