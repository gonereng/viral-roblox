# Task 3 Report: Picture-mode jobs

## Status: DONE

## Summary

Wired `JobManager` for picture-mode jobs: `JobRecord` gains `mode` and `ken_burns`, `create()` validates mode and resolves image vs video source, `run_job()` branches to `render_still` (no overlay) or existing `render_video` + overlay. Six new tests in `tests/web/test_jobs.py`.

## TDD Evidence

### RED — tests added before implementation

Appended six tests per brief. Ran:

```
python -m pytest tests/web/test_jobs.py -v -k "picture or ken_burns or unknown_mode or roblox_ignores"
```

Result: **6 failed** — expected `TypeError: JobManager.create() got an unexpected keyword argument 'mode'` / `'ken_burns'`; `render_still` not imported in `jobs.py`.

### GREEN — implementation added

Updated `src/roblox_viral/web/jobs.py` per brief. Ran:

```
python -m pytest tests/web/test_jobs.py -v
```

Result: **14 passed**.

### Full suite (pre-commit)

```
python -m pytest -v
```

Result: **94 passed, 2 skipped** in 4.99s.

## Commit

- `b536a1c` — feat(web): picture-mode jobs with optional Ken Burns
- Files: `src/roblox_viral/web/jobs.py`, `tests/web/test_jobs.py` only

## Self-Review

| Requirement | Met |
|---|---|
| `JobRecord.mode: str = "roblox"` | Yes |
| `JobRecord.ken_burns: bool = False` | Yes |
| `create(..., mode, ken_burns)` | Yes |
| Invalid mode → `ValueError` | Yes |
| Picture → `resolve_image`; roblox → `resolve_source`, `ken_burns=False` | Yes |
| `run_job`: picture → `render_still` without overlay | Yes |
| `run_job`: roblox → `render_video` + overlay | Yes |
| Hydrate `mode` / `ken_burns` from `status.json` | Yes |
| Single-flight unchanged (picture blocks roblox) | Yes |
| No HTTP routes or Generate UI | Yes |

### Notes

- Existing roblox job tests unchanged and green.
- `asdict(record)` persists new fields to `status.json` automatically.

## Files Changed

- `src/roblox_viral/web/jobs.py` — mode/ken_burns fields, create validation, run_job branching
- `tests/web/test_jobs.py` — +6 picture-mode tests
