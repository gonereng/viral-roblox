# Task 2 Report: Wire Gemini Pass 1 / Pass 2 in `jobs.py`

## Status

**DONE**

## Summary

Gemini TTS jobs now force Pass 1 render/plan at `video_speed=100`, then call `tempo_finished_video` from Task 1 when `record.video_speed != 100`. Edge TTS behavior is unchanged. Implemented TDD per the task brief.

## Changes

### `src/roblox_viral/web/jobs.py`

- Imported `tempo_finished_video` from `roblox_viral.render`.
- Before media planning/render, compute `render_video_speed` (100 for Gemini, else configured speed).
- Use `render_video_speed` in `plan_reddit_sentence_clips` and `render_video`.
- When Gemini + speed ≠ 100, Pass 1 writes to `job_dir/render_1x.mp4`; otherwise writes directly to final output.
- After successful Pass 1, call `tempo_finished_video` with configured speed and mode, then delete `render_1x.mp4`.
- Picture mode uses the same `pass1_path` / `needs_tempo` logic via `render_still`.

### `tests/web/test_jobs.py`

Added 4 tests:

- `test_run_job_gemini_forces_render_video_speed_100` — Pass 1 at 100, no tempo
- `test_run_job_gemini_tempos_when_video_speed_not_100` — render_1x → tempo → final, cleanup
- `test_run_job_edge_still_passes_configured_video_speed` — Edge regression
- `test_run_job_gemini_reddit_plans_at_100_then_tempos` — plan/render at 100, tempo at 200 with mode=reddit

Reddit test adapted hook story to `"One line only - here.\n"` (existing reddit tests require dash in hook).

## TDD Steps Executed

| Step | Action | Result |
|------|--------|--------|
| 1 | Added 4 failing job tests | Tests written (would fail pre-implementation) |
| 2 | Implemented jobs wiring | 5/5 focused tests PASS |
| 3 | Full regression | **236/236 PASS** |

## Commit

```
7fc360f feat(jobs): Gemini video_speed via post-render tempo
```

Files committed: `src/roblox_viral/web/jobs.py`, `tests/web/test_jobs.py`

## Self-Review

### Spec coverage

| Requirement | Status |
|-------------|--------|
| Gemini-only post tempo | ✓ `needs_tempo` gated on `tts_provider == "gemini"` |
| Pass 1 forced `video_speed=100` | ✓ `render_video_speed` |
| Skip Pass 2 at 100% | ✓ no `tempo_finished_video` call |
| Edge unchanged | ✓ regression test passes |
| Delete `render_1x` on success | ✓ `pass1_path.unlink(missing_ok=True)` |
| Reddit plan at 100, tempo at configured | ✓ reddit test |
| No new job status / no UI | ✓ unchanged |

### Correctness

- `output_name` still points at final (sped) file.
- No status change between passes.
- `tempo_finished_video` receives `mode=record.mode` for reddit vs single validation.

### Minor adaptation

- Reddit test story uses hook-with-dash per existing `test_run_job_reddit_*` convention (brief's plain story would fail `split_hook` validation at create).

## Test Results

```
pytest tests/web/test_jobs.py::test_run_job_gemini_* ... test_run_job_passes_video_speed_to_render -v  → 5 passed
pytest -q                                                                                                 → 236 passed
```

## Concerns

None blocking.

---

## Final-review fix: Picture `video_speed` coercion (option 3)

**Status:** DONE

**Decision:** Force `video_speed=100` at job **create** for all providers when `mode == "picture"`. Generate may still post a stale slider value; stored job always uses 100. `run_job` also skips Pass 2 tempo for picture even on legacy records.

### Changes

- `JobManager.create`: after `normalize_mode`, picture → `video_speed = DEFAULT_VIDEO_SPEED`; else `validate_video_speed`.
- `run_job`: `needs_tempo` excludes picture (`record.mode != "picture"`).

### Tests added

- `test_create_picture_forces_video_speed_100` — Edge picture + 175 → stored 100
- `test_create_picture_gemini_forces_video_speed_100` — Gemini picture + 160 → stored 100
- `test_run_job_gemini_picture_skips_tempo` — legacy `video_speed=175` on record; no `tempo_finished_video`; `render_still` writes final output

### Test evidence

```
pytest tests/web/test_jobs.py::test_create_picture_forces_video_speed_100 \
     tests/web/test_jobs.py::test_create_picture_gemini_forces_video_speed_100 \
     tests/web/test_jobs.py::test_run_job_gemini_picture_skips_tempo \
     tests/web/test_jobs.py::test_run_job_gemini_* \
     tests/web/test_jobs.py::test_run_picture_job_calls_render_still -v  → 8 passed
pytest -q                                                                 → 239 passed
```

### Commit

`fix(jobs): force picture video_speed to 100 at create` (see git log on branch)
