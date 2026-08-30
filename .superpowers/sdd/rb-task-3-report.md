# Task 3 Report: API `download-b` + Generate UI + README

## Status
**Complete**

## Commits
- `feat(api): download-b and Generate UI for Reddit Part B`

## Changes

### `src/roblox_viral/web/api_v1.py`
- Added `GET /api/v1/videos/{video_id}/download-b` — serves Part B MP4 from `output_name_b`.
- Same 422 (error) / 409 (not ready) as primary download; 404 `"Part B not found"` when done without Part B.

### `src/roblox_viral/web/templates/generate.html`
- `#reddit-hook-hint` documents optional `BREAK` line and Part B behavior.
- Added hidden `#download-b` link next to primary download.

### `src/roblox_viral/web/static/app.js`
- `showResult(outputName, titleCardName, outputNameB)` shows/hides Part B download.
- Poll handler passes `job.output_name_b || null`.

### `README.md`
- Reddit `BREAK` split documented; n8n notes `download-b` endpoint.

### Tests
- `tests/web/test_api_v1.py`: `test_download_b_404_when_no_part_b`, `test_download_b_returns_part_b_file`, `test_get_video_includes_output_name_b`.
- `tests/web/test_api.py`: BREAK in hint; `test_generate_page_has_hidden_part_b_download`.

## Test Summary
- `pytest tests/web/test_api_v1.py tests/web/test_api.py -q` → **70 passed**
- `pytest -q` (full suite) → **263 passed**

## Concerns / Notes
- Recent outputs list does not show Part B link (brief scoped to result section only).
- No dedicated test for download-b 422/409 (inherits same pattern as primary download; primary tests cover status mapping).

## Verification
TDD: API tests written first, endpoint + UI implemented, full suite green before commit.
