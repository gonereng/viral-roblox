# Task 1 Review: `tempo_finished_video` helper

**Reviewer:** Task-scoped gate review  
**Base:** `d4976a12c614f7fa14effb9da198aef0caa1f4dc`  
**Head:** `7d3137f420b40a9bb253b2140f154d2ffa6c0e42`  
**Scope:** Helpers only (jobs wiring deferred to Task 2)

---

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| **Spec compliance** | ✅ |
| **Code quality** | **Approved** |

---

## Spec compliance

### Requirements met

- **Deliverables:** Both `build_atempo_filters` and `tempo_finished_video` are implemented in `render.py` with the signatures specified in the task brief.
- **Scope:** Only `render.py` and `tests/test_render.py` were changed; `jobs.py` was not touched (correct for Task 1).
- **Pitch preservation:** Audio uses chained `atempo` filters only; no `asetrate`.
- **Video timing:** Uses `setpts=100/{video_speed}*PTS`, consistent with existing `_playback_setpts`.
- **100% fast path:** When `video_speed == 100`, copies (or no-ops when src/out resolve to the same path) without calling `require_ffmpeg` or `subprocess.run`.
- **Mode-aware validation:** `tempo_finished_video` delegates to `validate_video_speed(..., mode=...)`, covering Single 50–200 and Reddit 100–500.
- **Re-encode profile:** H.264 (`libx264`, preset `medium`, CRF 18), AAC 192k, `+faststart` — matches existing final render commands in `render.py`.
- **Failure handling:** Missing input raises `RenderError`; ffmpeg non-zero exit raises `RenderError` with stderr/stdout included.
- **Tests:** All 10 tests from the brief are present and match the specified assertions (including reddit 500% chained atempo count and 100% no-ffmpeg guard).

### Gaps

None blocking for Task 1 scope.

- **Untested implemented paths** (acceptable deferrals, noted by implementer):
  - Missing input file → `RenderError("Video not found: …")`
  - 100% when `src.resolve() == out.resolve()` (skip copy)
- **Runtime assumption:** Finished MP4 must have an audio stream; ffmpeg fails otherwise. Acceptable for v1 helper scope; Gemini finals always mux A+V.

### Extras (non-blocking)

- **`atempo=2.0` formatting branch:** Brief specified `f"atempo={remaining:.10g}"`; Python formats exactly `2.0` as `"2"`, breaking the 200% test. The explicit `remaining ≈ 2.0` branch is a justified pragmatic fix; ffmpeg accepts both, but test/spec string literals expect `2.0`.
- **`build_atempo_filters` int/positive validation:** Duplicates a subset of `validate_video_speed` when called via `tempo_finished_video`; harmless and matches the brief’s standalone helper contract.

### Global constraints

| Constraint | Status |
|------------|--------|
| Gemini-only feature; helpers only | ✅ No job wiring |
| Existing `video_speed` ranges | ✅ Via `validate_video_speed` |
| Pitch-preserving `atempo` | ✅ |
| Skip at 100% without ffmpeg | ✅ Tested |
| Design spec Pass 2 helper shape | ✅ |

---

## Code quality

### Critical

None.

### Important

None blocking approval.

1. **Untested error paths:** `Video not found` and same-path 100% no-op are implemented but not covered by tests. Low risk given straightforward logic; worth a follow-up test if the helper grows callers in Task 2.

### Minor

1. **Dead `anull` fallback:** `audio_chain = ",".join(atempo) if atempo else "anull"` is unreachable when `video_speed != 100` (early return at 100). Matches brief verbatim; could be simplified later without behavior change.
2. **Reddit 500% test is partial:** Asserts three `atempo=` occurrences and correct `setpts`, but not the exact chain `["atempo=2.0", "atempo=2.0", "atempo=1.25"]`. Covered fully by the unit test on `build_atempo_filters`.
3. **No direct tests for `build_atempo_filters` invalid input** (non-int, non-positive). Brief did not require them; validation mirrors `validate_video_speed` style.

---

## Strengths

- **TDD discipline:** Report and diff show tests-first workflow; all brief-specified cases included.
- **Consistent integration:** Placed adjacent to `_playback_setpts`; reuses `validate_video_speed`, `require_ffmpeg`, `RenderError`, and encoding flags already used in `render_video`.
- **Correct atempo decomposition:** Greedy chaining handles Single 50% and Reddit 500% within ffmpeg’s [0.5, 2.0] per-filter bounds; 500% case matches spec example.
- **Clean 100% path:** Path resolution guard avoids redundant copy when input and output are the same file.
- **Focused diff:** 86 lines of production code, no unrelated refactors; commit message matches repo style.

---

## Summary

Task 1 fully delivers the Pass 2 ffmpeg helper specified in the design doc and task brief. Behavior aligns with global constraints (atempo-only, mode validation, 100% no-ffmpeg skip, helpers-only scope). Implementation quality is solid with minor test-coverage gaps that do not block Task 2 integration.

**Gate recommendation:** Proceed to Task 2 (jobs wiring).
