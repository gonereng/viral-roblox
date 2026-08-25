# Task 1 Review: stable-ts force-align in `gemini_tts`

**Reviewer:** Task-scoped gate review  
**Base:** `ccb4983af50d9035955dcb07d0ac3a538084cf2b`  
**Head:** `21e53d16713621eed622d2e18bfdbce355c6b144`  
**Spec:** `docs/superpowers/specs/2026-08-25-gemini-force-align-design.md`  
**Scope:** `pyproject.toml`, `gemini_tts.py`, `tests/test_gemini_tts.py` only (Settings/jobs/docker/README deferred to Task 2)

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
| Add `stable-ts>=2.13.3` | ✅ | `pyproject.toml` |
| Keep `faster-whisper>=1.0.0` | ✅ | Unchanged in dependencies |
| `DEFAULT_ALIGN_LANGUAGE = "de"` | ✅ | `gemini_tts.py` L19 |
| `DEFAULT_ALIGN_MODEL = "base"` | ✅ | `gemini_tts.py` L20 |
| `align_words_with_whisper(..., language=, model_size=)` | ✅ | Keyword-only kwargs with defaults |
| `stable_whisper.load_faster_whisper(size, device="cpu", compute_type="int8")` | ✅ | L131–133 |
| `model.align(audio, script, language=lang)` | ✅ | L134 |
| Word extraction via `all_words()` with segment fallback | ✅ | L136–144; one-line comment documents accessor |
| `GeminiTTSProvider` stores `align_language` / `align_model` | ✅ | L176–177, L185–186 |
| Default path passes language/model to align helper | ✅ | L197–201 |
| `align_fn(out, script)` two-arg when injected | ✅ | L195–196; existing mocked synthesize test unchanged |
| Three specified tests | ✅ | All present in `tests/test_gemini_tts.py` |
| Commit message / files | ✅ | `21e53d1 feat(gemini): force-align karaoke with stable-ts`; three files only |

### Design spec (Task 1 slice)

| Decision | Status |
|----------|--------|
| stable-ts `align()` over faster-whisper backend | ✅ Replaces free `transcribe()` |
| Default language `de` | ✅ Module constant + default kwarg |
| Default model `base` | ✅ Module constant + default kwarg |
| CPU / `int8` | ✅ Hard-coded in load call |
| RuntimeError when align returns no words | ✅ L155–156; tested |
| Edge path unchanged | ✅ No Edge code touched |
| Injectable `align_fn` for mocks | ✅ Preserved |
| Settings / Docker / README wiring | ⏭ Correctly out of scope (Task 2) |

### Global constraints

| Constraint | Status |
|------------|--------|
| Aligner: stable-ts + faster-whisper backend | ✅ |
| Defaults `de` / `base` | ✅ |
| CPU `int8` | ✅ |
| Preserve two-arg `align_fn` | ✅ |
| Do not change Settings/jobs/docker/README | ✅ Only three task files in diff |

### Gaps

None blocking for Task 1 scope.

- **Settings env vars (`WHISPER_ALIGN_LANGUAGE` / `WHISPER_ALIGN_MODEL`):** Design spec describes them; Task 1 correctly adds provider-level knobs only. Task 2 wires from `load_settings`.
- **Model cache / Docker:** First real job will download weights; cache mount is Task 2.
- **No test asserting default `de`/`base` when kwargs omitted on provider:** Brief tests explicit and custom values; defaults are covered implicitly via constants and the force-align test.

---

## Code quality

### Critical

None.

### Important

None blocking approval.

1. **Model loaded on every `align_words_with_whisper` call.** Same pattern as the prior `WhisperModel("tiny", ...)` per-call load; not a Task 1 regression. Long-lived caching or singleton model would be a follow-up if latency matters in production.

### Minor

1. **Module docstring stale.** Line 1 still says “faster-whisper word alignment”; implementation is now stable-ts force-align. Cosmetic only.
2. **`segment.words` fallback untested.** Defensive branch for API variance; primary path (`all_words()`) is mocked and asserted. Acceptable.
3. **Gap-filling logic untested in new tests.** Preserved from pre-change implementation (extend word end to next start); existing behavior, not regressed.
4. **No direct test for `ValueError` on empty script inside `align_words_with_whisper`.** `synthesize` validates empty text first; align helper also guards. Low risk.
5. **Deferred imports removed.** Top-level `import stable_whisper` increases import cost for any `gemini_tts` import; reasonable for a core dependency of the align path.

---

## Strengths

- **Root cause addressed.** Swaps free transcription + `initial_prompt` for true force-align of the known script — matches design intent for karaoke desync.
- **TDD discipline.** Report documents RED → GREEN on focused tests; all three brief-specified tests match the template (load params, WordTiming conversion, provider threading, empty-result error).
- **Backward compatible mocks.** `align_fn` injection unchanged; `test_gemini_tts_synthesize_mocked` and jobs tests that mock `synthesize` remain valid without Task 1 changes to `jobs.py`.
- **Robust word parsing.** Handles `word` vs `text` attributes, strips tokens, ms conversion, minimum 1 ms duration, and gap-fill — sensible carry-forward from prior aligner.
- **Focused diff.** 158 lines across three files; no unrelated refactors; commit message follows repo style.

---

## Test coverage assessment

| Area | Covered |
|------|---------|
| stable-ts load params (`base`, cpu, int8) | ✅ `test_align_words_force_uses_stable_ts_align` |
| `align()` language + script passed | ✅ Same test |
| WordTiming ms conversion | ✅ Same test |
| RuntimeError on empty word list | ✅ `test_align_words_raises_when_empty` |
| Provider threads `align_language` / `align_model` | ✅ `test_provider_passes_language_model_to_default_align` |
| Injectable two-arg `align_fn` | ✅ Pre-existing `test_gemini_tts_synthesize_mocked` |
| Full `test_gemini_tts.py` suite | ✅ Report: 7/7 pass |
| Full project suite | ✅ Report: 242/242 pass (not re-run in this review) |

---

## Summary

Task 1 fully delivers stable-ts force-align in `gemini_tts` per the task brief and the implementation slice of the approved design spec. The aligner uses `model.align()` with `de`/`base` defaults and CPU `int8`; provider knobs and two-arg `align_fn` injectability are correct; scope excludes Settings/jobs/docker as required. Code quality is solid with only minor nits (stale docstring, untested fallback branch). **Gate recommendation:** Proceed to Task 2 (Settings, jobs wiring, Docker cache, README).
