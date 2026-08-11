# Task 2 Report: Jobs + API pitch/speed

## Status
Complete

## Commit
`feat(web): pass pitch and speed through jobs API`

## Changes
- `JobRecord`: added `pitch` / `speed` fields (defaults from `voice.py`)
- `JobManager.create`: accepts and validates pitch/speed; persists to `status.json`
- `JobManager.get`: hydrates pitch/speed from disk with backward-compatible defaults
- `JobManager.run_job`: passes formatted rate/pitch to `EdgeTTSProvider`
- `CreateJobBody` + `POST /api/jobs`: optional pitch/speed; validates before create

## Tests
```
pytest tests/web/test_api.py tests/web/test_jobs.py tests/test_voice.py -q
26 passed
```

New tests:
- `test_create_job_accepts_pitch_and_speed`
- `test_create_job_rejects_bad_pitch`
- `test_run_job_passes_pitch_and_speed_to_tts`

## Concerns
- None. Existing jobs without pitch/speed in `status.json` hydrate with defaults (15/130).
- Generate HTML/JS unchanged (Task 3).
