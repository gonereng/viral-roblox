# Task 1 Report: Image library helpers

## What was implemented

- **`Settings.images_dir`** property returning `media_root / "images"`, included in `ensure_media_dirs()`.
- **Image library helpers** in `library.py`:
  - `SourceImage` dataclass
  - `MAX_IMAGE_UPLOAD_BYTES = 20_000_000`
  - `list_images`, `resolve_image`, `save_image`, `delete_image`
  - Safe filename validation for `.jpg`, `.jpeg`, `.png`, `.webp`
  - Collision handling via `{stem}-{uuid8}{suffix}`
  - Atomic temp write + rename with temp cleanup on failure
- **Tests** for config dir creation, CRUD flow, collision, oversize/unsafe rejection, and separation from video sources.

## What was tested and results

| Scope | Command | Result |
|-------|---------|--------|
| Focused (task) | `python -m pytest tests/web/test_config.py::test_ensure_media_dirs tests/web/test_library.py -v` | 10 passed, 2 skipped |
| Full suite | `python -m pytest -v` | 84 passed, 2 skipped |

## TDD Evidence

### RED

```text
python -m pytest tests/web/test_config.py::test_ensure_media_dirs tests/web/test_library.py -v
```

```
FAILED tests/web/test_config.py::test_ensure_media_dirs - AttributeError: 'Settings' object has no attribute 'images_dir'
FAILED tests/web/test_library.py::test_save_list_delete_image - AttributeError: module 'roblox_viral.web.library' has no attribute 'save_image'
FAILED tests/web/test_library.py::test_save_image_unique_on_collision - AttributeError: module 'roblox_viral.web.library' has no attribute 'save_image'
FAILED tests/web/test_library.py::test_save_image_rejects_oversize_and_unsafe - AttributeError: ... has no attribute 'MAX_IMAGE_UPLOAD_BYTES'
FAILED tests/web/test_library.py::test_images_not_listed_as_video_sources - AttributeError: module 'roblox_viral.web.library' has no attribute 'save_image'
=================== 5 failed, 5 passed, 2 skipped in 0.75s ====================
```

### GREEN

```text
python -m pytest tests/web/test_config.py::test_ensure_media_dirs tests/web/test_library.py -v
```

```
======================== 10 passed, 2 skipped in 0.27s ========================
```

## Files changed

- `src/roblox_viral/web/config.py`
- `src/roblox_viral/web/library.py`
- `tests/web/test_config.py`
- `tests/web/test_library.py`

## Self-review findings

- Implementation mirrors existing video helper patterns (`_safe_name`, `resolve_source`, `save_upload` temp/rename).
- `list_images` returns empty list when `images_dir` is missing (defensive, not required by tests but harmless).
- Images and video sources remain in separate directories; no cross-listing.
- No HTTP routes, `render_still`, or out-of-scope changes added.
- Commit excludes `.superpowers/sdd/` and plan doc as instructed.

## Issues or concerns

- None blocking. Two ffmpeg-dependent upload tests skipped (no ffmpeg on PATH); pre-existing behavior.
- `resolve_image` raises `ValueError` for bad extensions (via `_safe_image_name`) rather than a distinct error type; matches video helper behavior and satisfies tests.

## Review fix: TOCTOU collision on concurrent save

### What changed

- Replaced `dest.exists()` + `temp.replace(dest)` with `_commit_image_upload()`, which uses `os.link(temp, dest)` to atomically place the temp file. `os.link` fails with `FileExistsError` if `dest` already exists, so concurrent same-name uploads never overwrite each other; losers retry with `{stem}-{8hex}{suffix}`.
- Added `test_save_image_concurrent_same_name` — 8 threads save `"photo.jpg"` simultaneously; asserts 8 unique names, exactly one `photo.jpg`, and each file retains its payload.

### Covering tests

- `test_save_list_delete_image`
- `test_save_image_unique_on_collision`
- `test_save_image_concurrent_same_name` (new)
- `test_save_image_rejects_oversize_and_unsafe`
- `test_images_not_listed_as_video_sources`
- `test_ensure_media_dirs`

### Command and output

```text
python -m pytest tests/web/test_library.py tests/web/test_config.py::test_ensure_media_dirs -v
```

```
======================== 11 passed, 2 skipped in 0.42s ========================
```

Commit: `fix(web): atomically reserve image dest on save`
