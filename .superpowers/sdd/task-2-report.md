# Task 2 Report: `videos_dir` + raw video library helpers

**Date:** 2026-08-15  
**Status:** DONE

## Summary

Added `Settings.videos_dir` (`media_root / "videos"`), extended `ensure_media_dirs`, and implemented raw video library helpers (`save_video`, `list_videos`, `resolve_video`, `delete_video`, `resolve_roblox_media`, `list_roblox_sources`) plus `RobloxSource` dataclass. Raw uploads are stored as-is with exclusive-create collision handling (mirrors images); no slicing.

## TDD Evidence

### RED — Step 2 (failing tests before implementation)

Command:

```text
pytest tests/web/test_library.py -k "save_video or resolve_roblox or list_roblox" -v
```

Result: **FAIL** (exit code 1) — 4 failed

```text
AttributeError: module 'roblox_viral.web.library' has no attribute 'save_video'
AttributeError: 'Settings' object has no attribute 'videos_dir'
```

### GREEN — Step 4 (targeted + full suite)

Command:

```text
pytest tests/web/test_library.py -k "save_video or resolve_roblox or list_roblox" -v
pytest tests/web/test_library.py -v
```

Result: **PASS** (exit code 0) — **4 passed** (targeted), **17 passed in 3.50s** (full suite)

New tests:

| Test | Result |
|------|--------|
| `test_save_video_stores_as_is_no_slice` | PASSED |
| `test_resolve_roblox_media_sources_win` | PASSED |
| `test_resolve_roblox_media_falls_back_to_videos` | PASSED |
| `test_list_roblox_sources_labels_kinds` | PASSED |

## Changes

### `src/roblox_viral/web/config.py`

- `videos_dir` property → `media_root / "videos"`
- `ensure_media_dirs` now creates `videos_dir` alongside sources/images/outputs/jobs

### `src/roblox_viral/web/library.py`

- `@dataclass(frozen=True) class RobloxSource` with `kind` in `{"slice","video"}`
- `_commit_video_upload` — exclusive create with UUID suffix on collision
- `list_videos`, `resolve_video`, `save_video`, `delete_video`
- `resolve_roblox_media` — sources first, fallback to videos on `FileNotFoundError`
- `list_roblox_sources` — all slices (sorted) then all videos (sorted)

## Commit

```text
fc88918 feat(web): add media/videos library helpers for raw uploads
```

Files committed: `config.py`, `library.py`, `tests/web/test_library.py`

## Self-Review

| Check | OK? | Notes |
|-------|-----|-------|
| `videos_dir` path matches brief | ✓ | `media_root / "videos"` |
| `ensure_media_dirs` includes videos | ✓ | All five dirs created |
| Raw upload, no slice | ✓ | `save_video` never calls `slice_into_minute_parts` |
| Size limit uses `MAX_UPLOAD_BYTES` | ✓ | Same as `save_upload` |
| Exclusive create like images | ✓ | `_commit_video_upload` mirrors `_commit_image_upload` |
| Sources win over videos on name clash | ✓ | `resolve_roblox_media` tries `resolve_source` first |
| `list_roblox_sources` order | ✓ | Slices then videos, each sorted |
| No UI/routes/jobs added | ✓ | Library helpers only |

## Concerns

None. Ready for downstream tasks (UI/routes/jobs).
