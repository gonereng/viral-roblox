# Task 3 Report: Wire Reddit run_job to sentence planner

## Done
- Reddit `run_job` uses `sentence_durations_s(sentences, words)` + `plan_reddit_sentence_clips(..., video_speed=...)`.
- Removed `narration_duration`, `plan_target`, and `plan_reddit_clips` from Reddit branch.
- Replaced `test_run_reddit_scales_plan_target_by_video_speed` with `test_run_reddit_plans_by_sentence_durations`.
- All Reddit success-path tests patch `plan_reddit_sentence_clips`.

## Tests
- `pytest tests/web/test_jobs.py -k reddit -v` — 6 passed
- `pytest -v` — 185 passed

## Commit
`feat(web): Reddit background one clip per sentence` — `jobs.py`, `test_jobs.py`
