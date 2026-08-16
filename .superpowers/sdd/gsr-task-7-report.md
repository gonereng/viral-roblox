# Task 7 Report: n8n API types single/reddit

**Branch:** `feat/generate-single-reddit`  
**Date:** 2026-08-15  
**Status:** DONE

## Summary

n8n `POST /api/v1/videos` now accepts `type=single|reddit|leni`. `roblox` returns 400 with migration hint. Reddit needs only story/voice/type (rejects media); single keeps media XOR source_name. README and `scripts/test-n8n-api.ps1` updated.

## TDD

**RED:** `test_create_roblox_type_400`, `test_create_reddit_with_story_voice_type`, `test_create_single_video_returns_id` failed (3/4).  
**GREEN:** `pytest tests/web/test_api_v1.py -v` → **22 passed**.

## Commit

`feat(api): n8n types single and reddit; reject roblox`
