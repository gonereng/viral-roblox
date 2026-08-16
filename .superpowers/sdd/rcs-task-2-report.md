# Task 2 Report: Persist `title_card_name` + serve PNG from `/media/outputs`

**Branch:** `feat/reddit-card-scale-download`  
**Date:** 2026-08-16  
**Status:** DONE

## Summary

Added `JobRecord.title_card_name`, copy Reddit card PNG to `outputs/` as `{stem}-card.png` on success, hydrate from `status.json`, and fixed `/media/outputs` MIME via `media_type_for_name`. Preserved pre-existing `video_speed` plan-target scaling in the same commit.

## Changes

| File | Action |
|------|--------|
| `src/roblox_viral/web/jobs.py` | `title_card_name` field; hydrate; `shutil.copy2` after Reddit render; plan_target × video_speed/100 |
| `src/roblox_viral/web/app.py` | `media_output` uses `media_type_for_name(safe)` |
| `tests/web/test_jobs.py` | `test_run_reddit_copies_title_card_to_outputs`; `test_run_reddit_scales_plan_target_by_video_speed` |
| `tests/web/test_api.py` | `test_media_output_serves_png` |

## TDD

1. **RED:** targeted tests — 2 failed (`title_card_name` missing; Content-Type `video/mp4`)
2. **GREEN:** targeted + MP4 auth test — 3 passed
3. **Full suite:** `pytest -v` — 171 passed

## Commit

- `1c85fa5` — `feat(web): persist and serve Reddit title card PNG downloads`

## Self-review

- Card naming follows `{Path(output_name).stem}-card.png` exactly.
- Non-Reddit jobs leave `title_card_name` as `None`.
- `GET /api/jobs/{id}` exposes field via existing `asdict(record)`.
- MP4 output serving unchanged (`test_media_output_requires_auth_and_serves_file` passes).
- Unrelated `.superpowers/sdd/*` left unstaged.

## Concerns

- UI download button (Task 3) not wired yet — field and `/media/outputs` route ready.
- Card PNG not listed in `list_outputs` (MP4-only); intentional per spec.
