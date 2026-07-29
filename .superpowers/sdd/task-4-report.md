# Task 4 Report: Job store + single-flight pipeline worker

## Status

**DONE**

## Commits

- `feat(web): single-flight render job manager` (after BASE `37c0b83`)

Files:
- `src/roblox_viral/web/jobs.py` (created)
- `tests/web/test_jobs.py` (created)

## What was implemented

- `JobStatus` literal: `queued | synthesizing | captioning | rendering | done | error`
- `JobRecord` dataclass with `id`, `status`, `error`, `source_name`, `voice`, `output_name`, `created_at`
- `BusyError` when an active job already exists
- `JobManager.create` / `get` / `run_job`
- Thread-safe `_lock` + `_active_id` single-flight; cleared in `finally` when the job finishes (done or error)
- Status persisted to `settings.jobs_dir / job_id / status.json` after every status change
- Pipeline stages in order: synthesizing (Edge TTS) → captioning (`write_ass`) → rendering (`render_video`) → done
- On exception: status `error` + message; lock still cleared in `finally`
- Story via `split_sentences`; empty story raises `ValueError`
- Source resolved with `library.resolve_source`; output written to `outputs/{job_id}.mp4`

## Tests

Command: `pytest tests/web/test_jobs.py -v`

Result: **2 passed**

- `test_single_flight_rejects_second_job` — second `create` raises `BusyError`
- `test_run_job_updates_statuses` — mocked `EdgeTTSProvider.synthesize`, `write_ass`, `render_video`; asserts `done`, `.mp4` output name, and `status.json` present

TDD: tests written first (import failed RED), then implementation (GREEN).

## Concerns

- `run_job` swallows exceptions after setting `error` (does not re-raise). Fine for a background worker; callers must poll status for failures.
- Single-flight is process-local (in-memory). Multiple workers/processes would need shared locking.
- `create` holds the active slot even before `run_job` starts; abandoned queued jobs without a worker would block forever until restart (or a future cancel API).

## Review fix (Important findings)

### Changes

1. **`create()` post-lock setup rollback** — If `mkdir` / `_persist` fails after setting `_active_id`, clear `_active_id` and remove the in-memory job + story so the manager is not permanently busy. Removed unused `Path` import.
2. **Lock-clear tests** — `test_create_succeeds_after_done` and `test_create_succeeds_after_error` assert a second `create` succeeds after `done` and after a mocked failure ending in `error`.

### Test re-run

Command: `python -m pytest tests/web/test_jobs.py -v`

```
============================= test session starts =============================
platform win32 -- Python 3.10.0, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Roland\AppData\Local\Programs\Python\Python310\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Roland\Projects\roblox-viral
configfile: pyproject.toml
plugins: anyio-4.12.1, asyncio-1.4.0
asyncio: mode=auto, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 4 items

tests/web/test_jobs.py::test_single_flight_rejects_second_job PASSED     [ 25%]
tests/web/test_jobs.py::test_run_job_updates_statuses PASSED             [ 50%]
tests/web/test_jobs.py::test_create_succeeds_after_done PASSED           [ 75%]
tests/web/test_jobs.py::test_create_succeeds_after_error PASSED          [100%]

============================== 4 passed in 0.10s ==============================
```

Result: **4 passed**
