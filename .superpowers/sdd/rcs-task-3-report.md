# Task 3 Report: Generate UI — Download title card link

**Branch:** `feat/reddit-card-scale-download`  
**Date:** 2026-08-16  
**Status:** DONE

## Summary

Added hidden `#download-card` link to the Generate result panel. `showResult` now accepts optional `titleCardName` and reveals the link when `job.title_card_name` is set after a Reddit job completes. Non-Reddit jobs keep the link hidden.

## Changes

| File | Action |
|------|--------|
| `src/roblox_viral/web/templates/generate.html` | `#download-card` anchor in result section (hidden by default) |
| `src/roblox_viral/web/static/app.js` | `showResult(outputName, titleCardName)`; poll passes `job.title_card_name` |
| `tests/web/test_api.py` | `test_generate_page_has_hidden_title_card_download` |
| `README.md` | Reddit bullet: ~2× card downloadable from result panel |

## TDD

1. **RED:** `test_generate_page_has_hidden_title_card_download` — failed (missing `download-card`)
2. **GREEN:** targeted test — passed
3. **Full suite:** `pytest -q` — 172 passed

## Commit

- `e532eee` — `feat(web): add Download title card link for Reddit jobs`

## Self-review

- Link uses `/media/outputs/{title_card_name}` with `encodeURIComponent`.
- No card links added to Recent outputs list (spec constraint).
- `downloadCard.removeAttribute` clears stale href on non-Reddit jobs.
- `.superpowers/sdd/*` left unstaged.

## Concerns

- No browser E2E test for poll → link visibility; smoke test covers template only.
- Card link shares `<p>` with MP4 download; spacing is browser-default.
