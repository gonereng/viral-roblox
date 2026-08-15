# Task 6 Report: Generate frontend three tabs

**Branch:** `feat/generate-single-reddit`  
**Date:** 2026-08-15  
**Status:** DONE

## Summary

Generate now provides Single background video, Picture, and Reddit tabs. Mode-specific inventory controls submit availability, video speed visibility, and the API payload; Reddit uses the Library Videos pool and sends an empty `source_name`.

## TDD

**RED:** updated HTML assertions failed on the missing `tab-single`.  
**GREEN:** `pytest tests/web/test_api.py -q` → **25 passed**.  
**Verification:** `pytest -q` → **150 passed**; `node --check src/roblox_viral/web/static/app.js` → exit 0.

## Commit

`feat(web): Generate tabs for Single, Picture, and Reddit`
