# Task 4 Report: Generate UI — labeled sources, video speed slider, drop image upload

**Date:** 2026-08-15  
**Status:** DONE

## Summary

Updated Generate page to list Roblox sources via `list_roblox_sources` with `(1m)` / `(video)` labels, added a video speed slider (Roblox tab only) wired into job POST as `video_speed`, and removed image upload/delete controls from Picture mode (select + Ken Burns only; empty state points to Library).

## Implementation

### `generate.html`

- Source `<option>` labels: `(1m)` for slices, `(video)` for raw videos
- Picture empty state: `No images — upload in Library`
- Removed upload file input, Upload/Delete buttons, and image error paragraph
- Added `#video_speed` range slider (50–200, default 100) after voice speed

### `app.js`

- Sync `#video-speed-value` with slider input
- `setMode`: hide `#video-speed-field` in Picture, show in Roblox
- Job POST payload includes `video_speed: Number(...)`
- Removed image upload/delete fetch handlers and related helpers

### `app.py`

- `generate_page`: `sources = list_roblox_sources(settings)`

## Verification

```text
pytest tests/web/test_api.py::test_generate_page_lists_sources_and_default_voice -q  PASSED
pytest tests/web/test_api.py::test_image_upload_list_on_generate_and_delete -q   PASSED
pytest tests/web/test_api.py::test_generate_page_has_picture_tab_controls -q       FAILED (expects removed upload/delete IDs)
```

Manual checks: template renders labeled options, video speed field present, Picture block has no upload UI, `app.js` posts `video_speed`.

## Commit

```text
3078897 feat(web): Generate video_speed slider and labeled roblox sources
```

Files: `generate.html`, `app.js`, `app.py`

## Brief Checklist

| Requirement | Status |
|-------------|--------|
| Labeled source options `(1m)` / `(video)` | ✓ |
| `list_roblox_sources` on generate page | ✓ |
| Video speed slider after voice speed | ✓ |
| Hidden in Picture mode | ✓ |
| POST includes `video_speed` | ✓ |
| No image upload/delete on Generate | ✓ |

## Concerns / Follow-ups

- ~~`test_generate_page_has_picture_tab_controls` still asserts `image-file` / `image-delete-btn`; update in a follow-up test pass (out of Task 4 file scope).~~ Fixed — see Review fix below.

## Review fix (Task 4 blocking finding)

Updated `test_generate_page_has_picture_tab_controls` to match Library-only image upload:

- Asserts tabs, `image_name`, listed image, `ken_burns` still present
- Asserts `image-file`, `image-upload-btn`, `image-delete-btn` are **absent**
- Empty-state GET (no images): `No images — upload in Library`; page does not say "upload below"
- With seeded Roblox source: `#video_speed` present; `(video)` or `(1m)` label on source option

```text
pytest tests/web/test_api.py -k "picture_tab or generate_page or video_speed" -v

tests/web/test_api.py::test_generate_page_lists_recent_outputs PASSED
tests/web/test_api.py::test_generate_page_lists_sources_and_default_voice PASSED
tests/web/test_api.py::test_generate_page_has_picture_tab_controls PASSED
tests/web/test_api.py::test_api_jobs_accepts_video_speed PASSED
tests/web/test_api.py::test_api_jobs_rejects_video_speed PASSED

5 passed, 17 deselected in 1.15s
```

Commit: `test(web): update Generate picture controls for Library-only images`
