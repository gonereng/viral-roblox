# Final Code Review — Gemini Karaoke Force-Align (stable-ts)

**Reviewer:** Senior Code Reviewer (final pre-merge)  
**Date:** 2026-08-25  
**Base (merge-base origin/main):** `ad0de8db714d41847f0e9743285550aa27bd8541`  
**Head:** `45371505f5f1ca266d73fa6b74324c7f6c3dae9d`  
**Spec:** `docs/superpowers/specs/2026-08-25-gemini-force-align-design.md`  
**Plan:** `docs/superpowers/plans/2026-08-25-gemini-force-align.md`  
**Force-align commits:** `21e53d1`, `4537150`

## Verdict

**Approve** — force-align work is spec-complete, test-backed, and ready to merge. No Critical or Important must-fix items. All previously noted minors are safe to defer.

## Scope reviewed

Force-align commits only (plus integration with existing branch context):

| Commit | Files |
|--------|-------|
| `21e53d1` | `pyproject.toml`, `src/roblox_viral/gemini_tts.py`, `tests/test_gemini_tts.py` |
| `4537150` | `src/roblox_viral/web/config.py`, `src/roblox_viral/web/jobs.py`, `docker-compose.yml`, `README.md`, `tests/web/test_config.py`, `tests/web/test_jobs.py` |

Out of scope for blocking findings: post-render tempo / picture `video_speed` commits (`7fc360f`, `3b8f5c0`, etc.) — reviewed only for regressions against align wiring; none found.

Read-only review. Verification run locally:

```
pytest tests/test_gemini_tts.py tests/web/test_config.py::test_whisper_align_* tests/web/test_jobs.py::test_run_job_gemini_passes_align_settings -q  → 10 passed
pytest -q                                                                                                                                    → 245 passed
```

---

## Spec conformance

| Spec requirement | Status | Evidence |
|------------------|--------|----------|
| Replace free faster-whisper transcription with stable-ts force-align | ✅ | `align_words_with_whisper` calls `model.align(str(audio_path), script, language=lang)` instead of `transcribe(..., initial_prompt=...)` |
| Script = full TTS text | ✅ | `synthesize` passes same `script` to align; jobs use `join_for_tts(sentences)` |
| `WHISPER_ALIGN_LANGUAGE`, default `de` | ✅ | `DEFAULT_ALIGN_LANGUAGE`, Settings field, `from_env`, compose default |
| `WHISPER_ALIGN_MODEL`, default `base` | ✅ | `DEFAULT_ALIGN_MODEL`, Settings field, `from_env`, compose default |
| CPU / `int8` | ✅ | `load_faster_whisper(..., device="cpu", compute_type="int8")` |
| RuntimeError when align returns no words | ✅ | L155–156; `test_align_words_raises_when_empty` |
| Edge path unchanged | ✅ | `EdgeTTSProvider` call site in `jobs.py` unchanged (rate/pitch only) |
| Post-render tempo unchanged / orthogonal | ✅ | Align runs on `narration.mp3` before render; tempo scales finished A+V together |
| Settings threaded into provider from `run_job` | ✅ | `jobs.py` L276–281 |
| Docker env passthrough + HF cache | ✅ | `docker-compose.yml` L12–14; `./media` volume persists cache |
| README documents env vars + force-align note | ✅ | Env table L106–107; n8n note L119; first-download note L180 |
| Mocked stable-ts tests | ✅ | Three align tests in `test_gemini_tts.py`; settings + jobs tests |
| Injectable `align_fn(out, script)` preserved | ✅ | Two-arg contract; `test_gemini_tts_synthesize_mocked` unchanged |
| Per-job language / UI control | ⏭ Out of scope v1 | As designed |

---

## Findings

### Critical (must-fix before merge)

None.

### Important (must-fix before merge)

None.

No regressions identified in force-align wiring relative to the approved design. Align failures (empty words, library exceptions, model download errors) propagate through existing `run_job` `try/except` into job `"error"` status — consistent with spec and pre-change behavior.

---

## Deferred minors (safe to ship)

These were flagged in task reviews or self-review; none block merge:

| Item | Notes |
|------|-------|
| **Stale module docstring** | L1 still says “faster-whisper word alignment”; implementation is stable-ts force-align. One-line fix when convenient. |
| **Untested `segment.words` fallback** | Defensive branch when `all_words()` absent (L136–144); primary path mocked in tests. |
| **Model reload per align call** | `load_faster_whisper` on every `align_words_with_whisper` invocation — same pattern as prior per-call `WhisperModel("tiny")`. Acceptable v1; cache singleton follow-up if latency matters. |
| **Empty-string env fallback untested** | `from_env` uses `.strip() or "de"/"base"` for whitespace-only values; only unset/explicit values tested. Behavior is correct. |
| **README cache path wording** | Documents `media/.cache/huggingface`; Docker sets `HF_HOME=/app/media/.cache/huggingface`. Equivalent via bind mount. |
| **Top-level `stable_whisper` import** | Adds ~2.5s to process startup (`import stable_whisper`); prior code lazy-imported inside align. Web always imports `gemini_tts` via `jobs.py`. Functional trade-off, not a correctness issue. |
| **Gap-fill logic untested** | Preserved from pre-change aligner (extend word end to next start, L157–163). Existing behavior, not regressed. |
| **No validation of language/model strings** | Invalid values fail at stable-ts runtime; consistent with other env-backed string settings. |
| **Helper name `align_words_with_whisper`** | Name predates stable-ts; cosmetic rename optional. |

### Operational note (not a code defect)

Default align language is **German** (`de`). English (or other) stories require `WHISPER_ALIGN_LANGUAGE=en` (or appropriate code). README and n8n docs state this; misconfiguration would degrade alignment quality, not crash silently.

---

## Strengths

- **Fixes the root cause.** Swaps free transcription + `initial_prompt` for true force-align of the known script — directly addresses observed karaoke desync (late first word, timestamp pile-ups).
- **Faithful to approved design.** stable-ts + faster-whisper backend, `de`/`base` defaults, CPU `int8`, Settings → jobs → provider threading, Docker `HF_HOME` under persisted `./media`.
- **TDD discipline.** Task 1 and Task 2 reports and diffs show tests-first workflow; all brief-specified cases present and passing.
- **Minimal, reviewable commits.** `21e53d1` (align logic + dep + tests), `4537150` (wiring + ops docs) — clean separation of concerns.
- **Backward-compatible test/mocks.** `align_fn` two-arg injection preserved; existing Gemini job tests updated with default kwargs only where needed.
- **Robust word parsing.** Handles `word` vs `text` attributes, strips tokens, ms conversion, minimum 1 ms duration, gap-fill — sensible carry-forward.
- **Edge isolation.** Only the Gemini branch in `run_job` receives align settings; pitch/speed remain Edge-only per README.
- **Full suite green.** 245/245 tests pass including new align, config, and jobs integration coverage.

---

## Integration check (force-align × branch context)

| Concern | Result |
|---------|--------|
| Align timings vs post-render tempo | ✅ Align on 1× `narration.mp3`; ASS burned at Pass 1 `video_speed=100`; Pass 2 tempo scales muxed A+V — captions stay in sync |
| Picture / video_speed commits | ✅ No interaction with align kwargs; no new regression flagged |
| Dependency addition | ✅ `stable-ts>=2.13.3` alongside existing `faster-whisper>=1.0.0` |

---

## Summary

Both force-align commits fully deliver the approved design: Gemini karaoke uses stable-ts force-align of the known script with configurable language/model (defaults `de` / `base`), wired through Settings and Docker, with mocked unit/integration tests and README documentation. Code quality is solid; all task-scoped gate reviews align with this final assessment.

**Gate recommendation:** Approve for merge.
