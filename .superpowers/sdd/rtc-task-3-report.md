# Task 3 Report: render_video title-card overlay

**Branch:** `feat/reddit-title-card`  
**Date:** 2026-08-16  
**Status:** DONE

## Summary

Added validated title-card inputs to `render_video` and a timed FFmpeg overlay after base scaling/cropping, playback timing, and ASS captions. Existing plain `-vf` and greenscreen-only paths remain unchanged.

## Changes

- `src/roblox_viral/render.py`: validates title-card path/duration, adds the image input, and builds the ordered filter graph.
- `tests/test_render.py`: covers filter order/expression, input placement, mapping, missing cards, and invalid durations.

## TDD and Verification

- RED: targeted test failed with `unexpected keyword argument 'title_card_path'`.
- GREEN: render suite passed: `17 passed in 0.41s`.
- Regression: full suite passed: `162 passed in 6.93s`.
- IDE lint check found no errors in modified Python files.

## Commit

- `041ecc2` — `feat: overlay timed Reddit title card in render_video`
