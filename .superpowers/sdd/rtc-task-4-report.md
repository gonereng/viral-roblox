# Task 4 Report: Wire Reddit `run_job`

**Branch:** `feat/reddit-title-card`  
**Date:** 2026-08-16  
**Status:** DONE

## Summary

Reddit jobs now render a title card after TTS/ASS, pass it to `render_video` with `first_sentence_end_s` timing, and disable the subscribe greenscreen overlay. Single/ephemeral video jobs keep the existing overlay behavior.

## Changes

- `src/roblox_viral/web/jobs.py`: after captioning in reddit mode, compute `T`, write `reddit_card.png`, call `render_video` with `overlay_path=None`, `title_card_path`, `title_card_until_s`.
- `tests/web/test_jobs.py`: updated reddit integration test; added title-card/no-overlay and single greenscreen tests.

## TDD and Verification

- RED: 2 new reddit tests failed (overlay still set, card not rendered).
- GREEN: `27 passed` in `tests/web/test_jobs.py`.
- Regression: `164 passed in 8.67s`.

## Commit

- `ab59cce` — `feat(web): attach Reddit title card and disable subscribe overlay`
