# Task 2 Report: `plan_reddit_clips` planner

**Branch:** `feat/generate-single-reddit`  
**Date:** 2026-08-15  
**Status:** DONE

## Summary

Added `ClipSegment` dataclass and `plan_reddit_clips` planner that shuffles source paths without replacement, reshuffles when the bag is exhausted, and trims the final segment to hit the target duration.

## TDD Evidence

### RED — Step 2 (failing test before implementation)

Command:

```text
pytest tests/test_reddit_clips.py -v
```

Result: **FAIL** (exit code 2)

```text
ModuleNotFoundError: No module named 'roblox_viral.reddit_clips'
```

### GREEN — Step 4 (full reddit_clips suite)

Command:

```text
pytest tests/test_reddit_clips.py -v
```

Result: **PASS** (exit code 0) — **3 passed in 0.03s**

| Test | Result |
|------|--------|
| `test_plan_trims_last_clip` | PASSED |
| `test_plan_reshuffles_when_exhausted` | PASSED |
| `test_plan_empty_pool_errors` | PASSED |

## Changes

### `src/roblox_viral/reddit_clips.py`

- `ClipSegment` frozen dataclass: `path`, `start_s` (always 0), `duration_s`.
- `plan_reddit_clips`: validates non-empty paths and positive target; shuffles bag via injectable `rng`; reshuffles when bag empty; trims last clip with `min(duration, remaining)`.
- Uses injected `durations` map when provided; otherwise falls back to `probe_duration_seconds`.

### `tests/test_reddit_clips.py`

- Trim last clip to exact target total.
- Reshuffle single-path pool for multi-segment fill.
- Empty pool raises `ValueError`.

## Commit

`36d0d66` — `feat: add reddit clip planner (shuffle, reshuffle, trim)`

## Concerns

- `d <= 0` raises `ValueError` (brief says "skip / error"; chose error to avoid infinite loop).
- No test for `target_seconds <= 0` or missing duration keys when `durations` provided.
