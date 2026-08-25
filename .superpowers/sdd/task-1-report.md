# Task 1 Report: stable-ts force-align in `gemini_tts`

## Status

**DONE**

## Summary

Replaced faster-whisper free transcription with stable-ts `model.align()` for Gemini karaoke word timings. Added `DEFAULT_ALIGN_LANGUAGE` / `DEFAULT_ALIGN_MODEL`, configurable `align_language` / `align_model` on `GeminiTTSProvider`, and preserved two-arg `align_fn(out, script)` injectability for existing mocks.

## Changes

### `pyproject.toml`

- Added `stable-ts>=2.13.3` dependency (kept `faster-whisper>=1.0.0`).

### `src/roblox_viral/gemini_tts.py`

- Imported `stable_whisper`; added `DEFAULT_ALIGN_LANGUAGE = "de"`, `DEFAULT_ALIGN_MODEL = "base"`.
- Rewrote `align_words_with_whisper` to call `stable_whisper.load_faster_whisper(...).align(...)` with language/model kwargs.
- Word extraction uses `WhisperResult.all_words()` when available; falls back to flattening `segment.words`.
- Updated `GeminiTTSProvider.__init__` to accept/store `align_language` and `align_model`; `_align_fn` is optional (None → default align).
- `synthesize` calls `align_fn(out, script)` when injected; otherwise passes language/model to `align_words_with_whisper`.

### `tests/test_gemini_tts.py`

Added 3 tests:
- `test_align_words_force_uses_stable_ts_align` — mocks stable-ts load/align, asserts WordTiming conversion
- `test_align_words_raises_when_empty` — RuntimeError when align returns no words
- `test_provider_passes_language_model_to_default_align` — provider threads align_language/model to default align

## TDD Steps Executed

| Step | Action | Result |
|------|--------|--------|
| 1 | Added `stable-ts` dependency | Installed stable-ts 2.19.1 |
| 2 | Added failing tests | RED — no `stable_whisper` import; unknown `align_language` kwarg |
| 3 | Ran focused tests | 2 failed (expected) |
| 4 | Implemented force-align + provider changes | — |
| 5 | Ran `tests/test_gemini_tts.py` | **7/7 PASS** |
| 6 | Full suite | **242/242 PASS** |
| 7 | Commit | `21e53d1 feat(gemini): force-align karaoke with stable-ts` |

## Commit

```
21e53d1 feat(gemini): force-align karaoke with stable-ts
```

Files committed: `pyproject.toml`, `src/roblox_viral/gemini_tts.py`, `tests/test_gemini_tts.py`

## Self-Review

### Correctness

- Force-align uses known script text instead of free transcription — fixes karaoke desync root cause.
- Empty script raises `ValueError("TTS text is empty")` before model load.
- Gap-filling logic preserved (extend word end to next word start when needed).
- `align_fn` two-arg contract preserved for `test_gemini_tts_synthesize_mocked` and jobs mocks.

### Scope adherence

- Did not touch `config.py`, `jobs.py`, `docker-compose`, or README (Task 2).
- Only committed the three task files.

### Word accessor

Used `result.all_words()` (stable-ts WhisperResult API); fallback to segment.words documented in one-line comment.

## Test Results

```
pytest tests/test_gemini_tts.py::test_align_words_force_uses_stable_ts_align tests/test_gemini_tts.py::test_provider_passes_language_model_to_default_align -v  → 2 passed (after impl)
pytest tests/test_gemini_tts.py -v  → 7 passed
pytest -q  → 242 passed
```

## Concerns

None blocking. First real Gemini job will download the Whisper base model (~150MB); cache wiring is Task 2.
