# Task 2 Report: Jobs dual render + `output_name_b`

## Status
**Complete**

## Commits
- `feat(jobs): Reddit BREAK dual render on one job`

## Changes

### `src/roblox_viral/web/jobs.py`
- Added `JobRecord.output_name_b: str | None = None`; hydrated from `status.json` on disk load.
- Reddit `create`: validates hook via `split_reddit_story` → Part A only (`split_sentences` + `split_hook`); full story still stored in `_stories`.
- Non-reddit `create`: unchanged validation (`split_sentences` on full story, no BREAK split).
- Refactored `run_job` → `_render_story_part` helper with `work_suffix` (`""` / `"_b"`) and `include_title_card`.
  - Part A: `include_title_card=True` — reddit card+cover or single x_card as before.
  - Part B (reddit + BREAK): second render, `{stem}-b.mp4`, work files suffixed `_b`, no title card.
- Single and picture modes unchanged (single render, full story).

### `tests/web/test_jobs.py`
- `test_create_reddit_validates_hook_on_part_a_only` — Part B line without dash allowed.
- `test_create_reddit_rejects_bad_hook_even_with_break` — bad Part A hook still rejected.
- `test_run_job_reddit_break_writes_two_outputs` — two renders, card only on first.
- `test_run_job_reddit_without_break_single_output` — one render, `output_name_b` None.
- Shared `_reddit_break_mocks` helper mirroring existing reddit test patterns.

## Test Summary
- `pytest tests/web/test_jobs.py -q` → **44 passed**
- `pytest -q` (full suite) → **259 passed**

## Concerns / Notes
- Part B gemini + `video_speed != 100` runs tempo per part (same helper logic); no dedicated dual-part gemini tempo test yet — existing single-part gemini reddit test still passes.
- API/UI download for Part B (`output_name_b`) deferred to Task 3.
- `output_name_b` persisted via `asdict` automatically; no schema migration needed.

## Verification
TDD: new tests written first (2 render tests failed on missing field), implementation added, full suite green before commit.
