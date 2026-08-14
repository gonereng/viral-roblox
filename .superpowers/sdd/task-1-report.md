# Task 1 Report: JobManager ephemeral input

## What was implemented

- **`JobRecord.ephemeral: bool = False`** persisted in `status.json`.
- **`JobManager.create(..., ephemeral=False)`** skips `resolve_source` / `resolve_image` when `ephemeral=True`; validates basename-only names via `validate_video_filename` / `validate_image_filename`.
- **`JobManager.get()`** hydrates `ephemeral` from disk (`bool(data.get("ephemeral", False))`).
- **`run_job`** resolves media from `jobs_dir/<job_id>/<source_name>` for ephemeral jobs (path must stay under job dir and exist).
- **`library.py`**: public `validate_video_filename` / `validate_image_filename` wrapping `_safe_name` / `_safe_image_name`.

## What was tested and results

| Scope | Command | Result |
|-------|---------|--------|
| Focused (task) | `python -m pytest tests/web/test_jobs.py -k ephemeral -v` | 2 passed |
| Full suite (jobs) | `python -m pytest tests/web/test_jobs.py -q` | 16 passed |

## TDD Evidence

### RED

```text
python -m pytest tests/web/test_jobs.py -k ephemeral -v
```

```
TypeError: JobManager.create() got an unexpected keyword argument 'ephemeral'
2 failed
```

### GREEN

```text
python -m pytest tests/web/test_jobs.py -q
```

```
16 passed in 0.44s
```

## Files changed

- `src/roblox_viral/web/jobs.py`
- `src/roblox_viral/web/library.py`
- `tests/web/test_jobs.py`

## Self-review findings

- Ephemeral create still validates mode and filename regex; roblox mode clears `ken_burns` like non-ephemeral path.
- `run_job` uses `is_relative_to` guard before reading job-local media.
- No `api_v1` changes (deferred to later tasks).

## Issues or concerns

- No dedicated test for ephemeral picture mode or hydration of `ephemeral` from `status.json` (brief only specified roblox create + run tests).
- API layer must write uploaded bytes to job dir before `run_job` (Task 2+).
