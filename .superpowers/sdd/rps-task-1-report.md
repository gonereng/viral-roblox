# Task 1 Report: `sentence_durations_s` + `plan_reddit_sentence_clips`

## Status
**Complete**

## TDD Cycle

### RED
Ran:
```
pytest tests/test_reddit_clips.py::test_sentence_durations_s_from_word_groups tests/test_reddit_clips.py::test_plan_one_video_per_sentence -v
```
Result: `ImportError: cannot import name 'plan_reddit_sentence_clips'` (expected).

### GREEN
Ran:
```
pytest tests/test_reddit_clips.py -v
```
Result: **8 passed** (3 legacy + 5 new).

### Full suite
```
pytest -v
```
Result: **178 passed**.

## Changes

### `src/roblox_viral/reddit_clips.py`
- Added `sentence_durations_s()` — derives wall-clock seconds per sentence via `partition_words_by_sentences`.
- Added `plan_reddit_sentence_clips()` — one shuffled video pick per sentence; loops short files within a sentence; scales source by `video_speed`.
- Kept existing `plan_reddit_clips()` unchanged.

### `tests/test_reddit_clips.py`
- Added 5 tests from brief (sentence durations, one-video-per-sentence, short-file loop, video_speed scaling, reshuffle when pool exhausted).

## Commit
```
feat: plan Reddit background clips per sentence
```
Hash: `6f70631`

## Concerns / Notes
- Production still uses `plan_reddit_clips` (total-target); wiring to `plan_reddit_sentence_clips` is deferred to later tasks.
- Short-file looping always uses `start_s=0.0` (v1 behavior per `ClipSegment` docstring).
- No validation tests for empty paths / zero durations in sentence planner yet (brief did not require them).
