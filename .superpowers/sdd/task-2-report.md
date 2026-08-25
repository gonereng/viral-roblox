# Task 2 Report: Settings, jobs, Docker, README for Gemini force-align

## Status

**DONE**

## Summary

Wired `WHISPER_ALIGN_LANGUAGE` / `WHISPER_ALIGN_MODEL` through `Settings.from_env()` into `JobManager.run_job` Gemini TTS construction. Updated Docker env + `HF_HOME` cache path and README. TDD per brief; no align logic changes.

## Changes

### `src/roblox_viral/web/config.py`

- Added `whisper_align_language: str = "de"` and `whisper_align_model: str = "base"` with field defaults.
- `from_env` reads `WHISPER_ALIGN_LANGUAGE` / `WHISPER_ALIGN_MODEL` with strip-or-fallback.

### `src/roblox_viral/web/jobs.py`

- Passes `align_language=settings.whisper_align_language` and `align_model=settings.whisper_align_model` to `GeminiTTSProvider`.

### `docker-compose.yml`

- Added `WHISPER_ALIGN_LANGUAGE`, `WHISPER_ALIGN_MODEL`, `HF_HOME: /app/media/.cache/huggingface`.

### `README.md`

- Documented whisper align env vars, stable-ts force-align note for Gemini karaoke, first-run model download into `media/.cache/huggingface`.

### Tests

- `tests/web/test_config.py`: `test_whisper_align_defaults`, `test_whisper_align_from_env`
- `tests/web/test_jobs.py`: `test_run_job_gemini_passes_align_settings`; updated `fake_gemini_init` in `test_run_job_gemini_uses_gemini_provider`

## TDD Steps Executed

| Step | Action | Result |
|------|--------|--------|
| 1 | Added failing tests | RED — missing Settings fields; align defaults not passed |
| 2 | Ran focused tests | 3 failed (expected) |
| 3 | Implemented Settings + jobs + Docker + README | — |
| 4 | Covering suite | **54/54 PASS** |
| 5 | Full suite | **245/245 PASS** |
| 6 | Commit | `4537150 feat(web): wire whisper align language/model settings` |

## Commit

```
4537150 feat(web): wire whisper align language/model settings
```

Files committed: `config.py`, `jobs.py`, `docker-compose.yml`, `README.md`, `test_config.py`, `test_jobs.py`

## Self-Review

| Spec | Status |
|------|--------|
| Settings env vars | ✓ |
| jobs pass settings | ✓ |
| Docker HF cache + env | ✓ |
| README | ✓ |
| Existing Settings(...) valid | ✓ field defaults |
| align_fn two-arg contract | ✓ unchanged |
| No align logic rework | ✓ |

## Test Results

```
pytest tests/test_gemini_tts.py tests/web/test_config.py tests/web/test_jobs.py -q  → 54 passed
pytest -q                                                                           → 245 passed
```

## Concerns

None blocking. First Gemini job in Docker downloads Whisper model (~150MB) into persisted `./media/.cache/huggingface`.
