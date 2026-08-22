# Task 3 Report: Cover API + README + n8n reddit stories

**Date:** 2026-08-18  
**Status:** DONE

## Summary

Added `GET /api/v1/videos/{video_id}/cover` mirroring `/download` status mapping with `media_type="image/png"`. Seven new API v1 tests cover auth, done PNG, 409/422/404 paths, and Reddit hook validation. README updated for hook cover PNG and n8n cover download.

## TDD Evidence

### RED — Step 2 (failing tests before implementation)

Command:

```text
python -m pytest tests/web/test_api_v1.py -k "cover or reddit" -v
```

Result: **FAIL** (exit code 1) — 4 failed, 6 passed

```text
test_cover_requires_api_key - assert 404 == 401
test_cover_done_returns_png - assert 404 == 200
test_cover_not_ready_409 - assert 404 == 409
test_cover_error_422 - assert 404 == 422
```

Reddit hook tests and `test_cover_single_done_404` / `test_cover_unknown_404` already passed (Task 2 hook validation; 404 expected without route).

### GREEN — Step 4 (targeted + full suite)

Commands:

```text
python -m pytest tests/web/test_api_v1.py -k "cover or reddit" -v
python -m pytest tests/web/test_api_v1.py tests/web/test_jobs.py tests/test_hook_cover.py tests/test_reddit_card.py -v
python -m pytest -q
```

Result: **PASS** — 10/10 cover+reddit, 75/75 targeted, **189 passed, 2 skipped**

New tests:

| Test | Result |
|------|--------|
| `test_create_reddit_rejects_story_without_hook_dash` | PASSED |
| `test_cover_requires_api_key` | PASSED |
| `test_cover_done_returns_png` | PASSED |
| `test_cover_not_ready_409` | PASSED |
| `test_cover_error_422` | PASSED |
| `test_cover_single_done_404` | PASSED |
| `test_cover_unknown_404` | PASSED |

## Implementation

### `api_v1.py`

- `GET /videos/{video_id}/cover` after `download_video`
- Uses `title_card_name`, same auth via `require_api_key`
- Status: 404 unknown/missing cover, 409 not done, 422 error, 200 PNG

### `README.md`

- Reddit paragraph: Snoo template cover PNG, `phrase - phrase` hook, n8n cover URL
- n8n API: cover download bullet after video download

## Commit

```text
8f7474d feat(web): n8n cover download endpoint for Reddit hook PNG
```

Files: `api_v1.py`, `test_api_v1.py`, `README.md`

## Brief Checklist

| Requirement | Status |
|-------------|--------|
| GET cover endpoint | ✓ |
| Mirror /download status mapping | ✓ |
| image/png response | ✓ |
| Cover tests (7) | ✓ |
| Reddit hook dash rejection test | ✓ |
| README Reddit + n8n updates | ✓ |

## Concerns / Follow-ups

- None.
