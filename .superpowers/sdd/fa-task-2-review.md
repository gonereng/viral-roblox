# Task 2 Review: Settings, jobs, Docker, README

**Reviewer:** Task-scoped gate review  
**Base:** `21e53d16713621eed622d2e18bfdbce355c6b144`  
**Head:** `45371505f5f1ca266d73fa6b74324c7f6c3dae9d`  
**Brief:** `.superpowers/sdd/task-2-brief.md`  
**Scope:** `config.py`, `jobs.py`, `docker-compose.yml`, `README.md`, `tests/web/test_config.py`, `tests/web/test_jobs.py`

---

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| **Spec compliance** | ✅ |
| **Code quality** | **Approved** |

---

## Spec compliance

### Task brief requirements

| Requirement | Status | Evidence |
|-------------|--------|----------|
| `whisper_align_language: str = "de"` field default | ✅ | `config.py` L41 |
| `whisper_align_model: str = "base"` field default | ✅ | `config.py` L42 |
| `from_env` reads `WHISPER_ALIGN_*` with strip-or-fallback | ✅ | `config.py` L105–110 |
| Jobs pass `align_language` / `align_model` to `GeminiTTSProvider` | ✅ | `jobs.py` L276–281 |
| Docker: `WHISPER_ALIGN_LANGUAGE` default `de` | ✅ | `docker-compose.yml` L12 |
| Docker: `WHISPER_ALIGN_MODEL` default `base` | ✅ | `docker-compose.yml` L13 |
| Docker: `HF_HOME: /app/media/.cache/huggingface` | ✅ | `docker-compose.yml` L14 |
| README env table rows for align vars | ✅ | `README.md` L106–107 |
| README stable-ts force-align note (German default) | ✅ | `README.md` L119 |
| README first-run model download note | ✅ | `README.md` L180 |
| `test_whisper_align_defaults` | ✅ | `tests/web/test_config.py` L60–68 |
| `test_whisper_align_from_env` | ✅ | `tests/web/test_config.py` L71–79 |
| `test_run_job_gemini_passes_align_settings` | ✅ | `tests/web/test_jobs.py` L523–567 |
| Updated `fake_gemini_init` in existing gemini test | ✅ | `tests/web/test_jobs.py` L573 |
| Commit message / files | ✅ | `4537150 feat(web): wire whisper align language/model settings`; six files only |

### Global constraints

| Constraint | Status |
|------------|--------|
| `WHISPER_ALIGN_LANGUAGE` default `de` | ✅ Field default, `from_env`, compose |
| `WHISPER_ALIGN_MODEL` default `base` | ✅ Field default, `from_env`, compose |
| `HF_HOME` under media cache | ✅ `/app/media/.cache/huggingface` on bind-mounted `./media` |
| Jobs pass align kwargs | ✅ Only Gemini branch; kwargs match Task 1 provider signature |
| Edge unchanged | ✅ `EdgeTTSProvider` call site identical (rate/pitch only) |
| No align logic rework | ✅ `gemini_tts.py` untouched in this diff |

### Design spec (Task 2 slice)

| Decision | Status |
|----------|--------|
| Settings env vars wired to provider | ✅ |
| Persist model cache via `HF_HOME` in Docker | ✅ |
| Document env vars + first-run download | ✅ |
| Existing `Settings(...)` constructors remain valid | ✅ New fields have defaults at end of dataclass |

### Gaps

None blocking for Task 2 scope.

- **Empty-string env fallback untested.** `from_env` uses `.strip() or "de"/"base"` for whitespace-only values; brief tests cover unset and explicit values only. Behavior is correct and defensive.
- **Non-Docker local runs.** `HF_HOME` is set only in compose; local dev without Docker relies on default Hugging Face cache location. Acceptable — brief targets Docker persistence via `./media` volume.

---

## Code quality

### Critical

None.

### Important

None blocking approval.

### Minor

1. **README cache path wording.** Documents `media/.cache/huggingface`; Docker sets `HF_HOME=/app/media/.cache/huggingface`. Equivalent via bind mount; no action required.
2. **`get_settings()` cache unchanged.** Tests and job paths use `Settings.from_env()` via injected `settings`; `@lru_cache` on `get_settings()` is pre-existing. Align env changes at runtime would not propagate through cached singleton — not introduced or worsened by this task.
3. **No validation of align model/language strings.** Provider and stable-ts will fail at runtime on invalid values; consistent with other env-backed string settings in this codebase.

---

## Strengths

- **Minimal, focused diff.** 88 lines across six files; wires Task 1 provider knobs without touching align logic.
- **TDD discipline.** Report documents RED → GREEN; new tests match brief templates verbatim.
- **Backward compatible.** Dataclass field defaults preserve direct `Settings(...)` construction; existing Gemini job mocks updated with default kwargs so older tests keep passing.
- **Edge isolation.** Only the Gemini branch in `run_job` changed; pitch/speed remain Edge-only as documented in README.
- **Docker ops clarity.** Compose defaults mirror app defaults; `HF_HOME` under persisted volume avoids re-download on container restart.

---

## Test coverage assessment

| Area | Covered |
|------|---------|
| Settings defaults when env unset | ✅ `test_whisper_align_defaults` |
| Settings from env override | ✅ `test_whisper_align_from_env` |
| JobManager threads settings into provider init | ✅ `test_run_job_gemini_passes_align_settings` |
| Existing gemini provider test still passes | ✅ Updated `fake_gemini_init` signature |
| Task 1 + web covering suite | ✅ 54/54 pass (re-run in review) |
| Full project suite | ✅ 245/245 pass (re-run in review) |

---

## Summary

Task 2 fully wires `WHISPER_ALIGN_LANGUAGE` / `WHISPER_ALIGN_MODEL` from environment through `Settings` into `JobManager` Gemini construction, with Docker cache path and README documentation. All global constraints hold: defaults `de`/`base`, `HF_HOME` under media cache, align kwargs on Gemini only, Edge path untouched. Implementation is clean and test-backed. **Gate recommendation:** Task 2 complete; proceed to final integration review / merge.
