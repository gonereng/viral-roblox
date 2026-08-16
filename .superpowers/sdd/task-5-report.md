# Task 5 Report: Remove YouTube

**Date:** 2026-08-15  
**Status:** DONE

## Summary

Removed the YouTube endpoint, downloader module, background job methods, cookie settings, `yt-dlp` dependency, tests, documentation, and Library UI/JavaScript. The Library upload flow and render jobs remain intact.

## TDD Evidence

### RED

```text
python -m pytest tests/web/test_youtube_removed.py -v
```

Result: **FAIL** — expected 404, received 200 from the existing endpoint.

### GREEN

```text
python -m pytest tests/web/test_youtube_removed.py tests/web/test_jobs.py tests/web/test_api.py -v
python -m pytest tests/web -v
```

Result: **PASS** — 42 targeted tests passed; all 98 web tests passed.

## Implementation

- `POST /api/library/youtube` now returns 404.
- Deleted `youtube.py`, YouTube job methods, old YouTube tests, and YouTube-only `library.js`.
- Removed YouTube cookie settings and updated all `Settings(...)` test constructions.
- Removed `yt-dlp` and all product-facing YouTube documentation/UI.
- Kept optional legacy `JobRecord` fields so old `status.json` files remain readable.

## Commit

```text
ab946b6 feat(web): remove YouTube library import and yt-dlp
```

## Concerns

- None. Existing unrelated `.superpowers/sdd` working-tree changes were not included in the commit.
