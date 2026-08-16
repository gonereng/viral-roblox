# Task 5 Report: UI jobs API + Generate page context

**Branch:** `feat/generate-single-reddit`  
**Date:** 2026-08-15  
**Status:** DONE

## Summary

`CreateJobBody.mode` defaults to `"single"`. UI `/api/jobs` normalizes via `normalize_mode` (`roblox`→`single`, 400 on invalid). Generate page passes `list_sources`, `videos`, `has_videos`, and `list_images` (no `list_roblox_sources`).

## TDD

**RED:** new tests for reddit POST, roblox→single map, slices-only generate context.  
**GREEN:** `pytest tests/web/test_api.py -q` → **25 passed**.

## Commit

`feat(web): API and generate context for single/reddit modes`

## Next

Task 6: three-tab Generate HTML/JS using `has_videos` and `single` mode labels.
