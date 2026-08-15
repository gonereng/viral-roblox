# Task 8 Report: README polish + full regression

**Date:** 2026-08-15  
**Status:** DONE

## Summary

Polished README Web app section: documented Library three tabs (1-minute clips, Videos, Images), Generate **Video speed** slider for Roblox mode, and corrected Picture flow (images from Library, not uploaded on Generate). Verified no YouTube/yt-dlp/cookies references remain. n8n `video_speed` was already documented from Task 7.

## README changes

- Added Library tabs table with directories (`media/sources/`, `media/videos/`, `media/images/`)
- Documented labeled Roblox source dropdown `(1m)` / `(video)` and Video speed 50–200% default 100%
- Fixed outdated Picture upload-on-Generate wording
- Confirmed clean: no YouTube, yt-dlp, or cookies mentions

## Tests

```text
python -m pytest -q
```

Result: **132 passed** in 9.17s

## Commit

```text
d615319 docs: document library tabs and video_speed
```

## Concerns

- None.

---

## Final review nits (2026-08-15)

Addressed whole-branch review feedback on `feat/library-tabs-video-speed`:

1. **`.visually-hidden` CSS** — Added clip/absolute/overflow rule to `src/roblox_viral/web/static/app.css` so Library delete buttons hide duplicate filenames for screen readers only.
2. **`video_speed` default assert** — `test_create_defaults_pitch_and_speed` now asserts `video_speed == 100`.
3. **Cold hydrate for `video_speed`** — `test_create_job_persists_video_speed` loads via fresh `JobManager()` to exercise `status.json` hydrate.

### Tests

```text
pytest tests/web/test_api_v1.py tests/web/test_jobs.py tests/web/test_library.py -q  → 55 passed
pytest -q  → 132 passed
```

### Commit

```text
fix: address library-tabs video-speed review nits
```
