# Task 1 Report: `split_reddit_story` helper

## Status

**Complete** — TDD cycle finished; all tests pass; commit on `feat/reddit-break-dual-video`.

## Commits

| Hash | Message |
|------|---------|
| `3e5b9c6` | feat: split Reddit stories on BREAK line |

## Files Added

- `src/roblox_viral/reddit_break.py` — `split_reddit_story(story) -> tuple[str, str | None]`
- `tests/test_reddit_break.py` — 6 unit tests

## TDD Steps

1. **Failing tests** — Created `tests/test_reddit_break.py` with 6 cases from brief.
2. **Run (fail)** — `pytest tests/test_reddit_break.py -v` → `ModuleNotFoundError: roblox_viral.reddit_break` (expected).
3. **Implement** — Added `reddit_break.py` per brief spec (`BREAK_TOKEN`, line-exact split, preserve newlines).
4. **Run (pass)** — All 6 tests passed in 0.04s.
5. **Commit** — Staged only the two task files; committed with specified message.

## Test Summary

```
tests/test_reddit_break.py::test_no_break_returns_full_story PASSED
tests/test_reddit_break.py::test_break_splits_parts PASSED
tests/test_reddit_break.py::test_break_empty_after_means_no_b PASSED
tests/test_reddit_break.py::test_break_must_be_own_line_exact PASSED
tests/test_reddit_break.py::test_break_case_sensitive PASSED
tests/test_reddit_break.py::test_break_with_surrounding_spaces_on_line PASSED

6 passed in 0.04s
```

## Behavior Notes

- Splits on first line where `line.strip() == "BREAK"` (case-sensitive).
- Inline `BREAK` in prose does not trigger split.
- Whitespace-only content after BREAK → `part_b` is `None`.
- Original newlines preserved in both parts for downstream `split_sentences`.
- `None` input coerced to empty string (defensive; not covered by tests).

## Scope

Did **not** modify `jobs.py`, API, or UI per task constraints.

## Concerns

None. Ready for Task 2 integration.
