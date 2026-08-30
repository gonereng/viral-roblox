# Senior Final Review: Reddit BREAK Dual Video

**Date:** 2026-08-29  
**Base:** `ea3da85912248c796d6bed278d38ca317980a2d9`  
**HEAD:** `2229bfcbac9e63d3a7bd4d0d0c8cd7d96023eb53`  
**Commits:** `3e5b9c6` → `f5400ee` → `2229bfc`  
**Reviewer verification:** `pytest -q` → **263 passed** (17.4s); feature subset 14/14 passed

---

## Overall Verdict: **Approve**

The three-task stack implements the approved design end-to-end. Spec constraints are met, regressions on Single/Picture/Reddit single-pass paths are absent, and the full suite is green. No Critical or Important blockers for merge.

---

## Spec Coverage

| Spec requirement | Status | Evidence |
|------------------|--------|----------|
| Reddit-only split on own-line exact `BREAK` | ✅ | `reddit_break.py`; 6 unit tests |
| Empty/missing Part B → single Part A | ✅ | `test_break_empty_after_means_no_b`; `test_run_job_reddit_without_break_single_output` |
| Hook validation on Part A only | ✅ | `create` splits before `split_hook`; create tests |
| Part B: no card/cover, no `split_hook` | ✅ | `include_title_card=False`; render assert `title_card_path is None` |
| Sequential dual render, separate work files | ✅ | `_render_story_part` + `work_suffix`; 2 renders asserted |
| `output_name` / `output_name_b` (`-b.mp4`) / `title_card_name` | ✅ | JobRecord + run_job; job + API tests |
| `BREAK` stripped (not spoken) | ✅ | Split removes delimiter line before TTS |
| Non-Reddit + `BREAK` unchanged | ✅ | Split only when `mode == "reddit"` in create/run_job |
| Part B failure after A → job `error` | ✅ | Single try/except in `run_job`; no partial `done` (by design, untested) |
| API: status, download, download-b, cover | ✅ | `api_v1.py`; 3 new API tests |
| GUI: hint + second download link | ✅ | `generate.html`, `app.js`; HTML tests |
| README | ✅ | BREAK + `download-b` documented |

---

## Critical Must-Fix

**None.**

Checked explicitly:

- Single X-card path preserved (`include_title_card` + `mode == "single"` branch in helper).
- Picture mode unchanged (single render, no card branch).
- Part B render receives `title_card_path=None`.
- `download-b` serves Part B bytes only; absent Part B returns 404 `"Part B not found"`.
- Status/error ordering on `download-b` mirrors primary download (422 error → 409 not ready → 404 no Part B).

---

## Important Must-Fix

**None.**

- Refactor scope is contained; no behavioral drift found in non-Reddit modes.
- Path traversal guards and `FileResponse` handling match existing download endpoints.
- `output_name_b` hydrated in `_load` and persisted via `asdict` (no round-trip test, but pattern matches proven `title_card_name` path).

---

## Deferred Minors — OK to Defer?

| Deferred item | Assessment |
|---------------|------------|
| No dual Gemini tempo test | **OK.** `_render_story_part` runs tempo per part; existing single-part Gemini reddit test still passes. Add when Gemini+dual-BREAK is exercised in prod. |
| Recent outputs omit Part B link | **OK.** Out of v1 scope. Part B MP4s still appear as separate `-b.mp4` rows via `list_outputs`; operators can play/download from there. Grouping under Part A is polish. |
| `download-b` 422/409 untested | **OK.** Logic is a faithful clone of `download_video`; primary download tests cover status mapping. Low regression risk. |
| Endpoint duplication (~25 lines) | **OK.** Brief explicitly requested clone; DRY helper premature until a fourth variant exists. |

Additional nits from task reviews (also OK): no `output_name_b` disk-hydration test; status oscillates synthesizing→captioning→rendering twice on dual jobs (brief allows); no JS runtime test for `showResult` toggle (matches title-card pattern); result player shows Part A only (design intent).

---

## Strengths

1. **Clean extraction** — `_render_story_part` centralizes the pipeline without mode regressions; `include_title_card` cleanly separates Part A card behavior from Part B.
2. **Correct isolation** — Three focused commits (helper → jobs → API/UI) with task-scoped diffs; easy to review and revert.
3. **Work-file suffixing** — `narration_b.mp3`, `captions_b.ass`, `reddit_bg_b.mp4`, etc. prevent Part A/B collisions in one job dir.
4. **Minimal helper** — `split_reddit_story` is small, well-tested, and preserves newlines for `split_sentences`.
5. **API consistency** — `download-b` follows the same auth, status, traversal, and content-type patterns as existing endpoints; n8n consumers get predictable semantics.
6. **UI parity** — Part B download mirrors `#download-card` show/hide; poll site passes `output_name_b`; Reddit hint documents `BREAK` inline.
7. **Test depth** — Unit tests for split edge cases; integration tests for dual render, hook-on-A-only, API 200/404, and HTML presence; full suite green.

---

## Post-Merge Notes (non-blocking)

- Consider a follow-up test for Part B render failure → `status=error` with Part A file on disk (documents v1 “no partial done” contract).
- If operators rely on Recent outputs, a grouped Part A + Part B row would improve discoverability without API changes.
- Story starting with `BREAK` only (empty Part A) fails at create with “Story is empty” — acceptable but undocumented edge case.

---

## Summary

| Dimension | Verdict |
|-----------|---------|
| Spec compliance | **PASS** |
| Regressions (Single / Picture / Reddit single) | **None** |
| Critical / Important blockers | **None** |
| Deferred minors | **Acceptable for v1 merge** |
| **Overall** | **Approve** |
