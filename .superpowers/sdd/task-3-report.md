# Task 3 Report: Generate page sliders

## Status
**Complete**

## Changes
- `generate.html`: Added pitch (-50..50, default 15) and speed (50..200, default 130) range inputs after voice select.
- `app.js`: Live label sync (`+15%` / `130%` format); payload includes `pitch` and `speed` as integers.
- `app.css`: Minimal `.slider-field` styles for full-width range inputs and tabular-nums labels.

## Commit
```
feat(web): pitch and speed sliders on Generate
```
Files: `generate.html`, `app.js`, `app.css` only.

## Tests
```
pytest tests/web/test_api.py tests/web/test_jobs.py tests/test_voice.py -q
26 passed in 4.15s
```

## Manual verification
- Open Generate page: defaults show +15% pitch, 130% speed.
- Sliders update labels on input.
- Submit sends pitch/speed in JSON payload (API from Task 2 accepts them).

## Concerns
None. No backend/voice/caption changes in this task.
