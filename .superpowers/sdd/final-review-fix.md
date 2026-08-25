# Final-Review Fix Re-Review — Picture `video_speed` Coercion

**Reviewer:** Senior Code Reviewer (re-review)  
**Date:** 2026-08-25  
**Base:** `7fc360f2df4607b54f247d53936d77d6ca3488d1`  
**Head:** `3b8f5c006e1cff31bf7ae9b66ab4292cdd5ec5f4`  
**Prior review:** `.superpowers/sdd/final-review.md` (Finding 1 blocker)

Read-only review. No checkout mutation.

## Verdict

**Approve**

## What changed

Two lines in `src/roblox_viral/web/jobs.py`, three tests in `tests/web/test_jobs.py`:

| Layer | Change |
|---|---|
| `JobManager.create` | After `normalize_mode`, picture mode assigns `video_speed = DEFAULT_VIDEO_SPEED` (100) instead of validating caller input |
| `run_job` | `needs_tempo` adds `record.mode != "picture"` guard |
| Tests | Create coercion (Edge + Gemini); run defense for legacy records with stale speed |

## Silent stale-slider issue — closed

Final-review Finding 1 is resolved.

**Repro (Generate UI):** Single → drag Video speed to 175% → switch to Picture tab (slider hidden, value retained) → Gemini → Generate.

| Stage | Before fix | After fix |
|---|---|---|
| Stored job | `video_speed=175` | `video_speed=100` (coerced at create) |
| Gemini render | Pass 2 tempo → 1.75× output | No tempo; `render_still` writes 1× final |
| Edge picture | Already 1× (ignored speed) | Still 1×; stored speed now 100 |

Defense-in-depth: `test_run_job_gemini_picture_skips_tempo` mutates a freshly created record back to 175 and confirms `tempo_finished_video` is never called and output lands directly at the final path. Covers pre-fix job JSON on disk.

API layers (`app.py`, `api_v1.py`) still accept and validate the posted slider value, but all paths delegate to `JobManager.create`, which overwrites it for picture. No separate bypass.

## Spec / prior review alignment

Matches option 3 from Finding 1 recommendation and implementer notes in `task-2-report.md`:

- Force 100 at create for all providers when `mode == "picture"`
- Skip Pass 2 tempo for picture in `run_job`
- No Generate-page / UI change required

## Verification

```
pytest tests/web/test_jobs.py::test_create_picture_forces_video_speed_100 \
     tests/web/test_jobs.py::test_create_picture_gemini_forces_video_speed_100 \
     tests/web/test_jobs.py::test_run_job_gemini_picture_skips_tempo \
     ... (3 related gemini/picture tests) -q  → 6 passed
```

Implementer reports 239/239 full suite pass.

## Remaining findings

**Critical:** none  
**Important:** none

Deferred minors from the original final review (unreachable `anull` branch, `-shortest` omission, Pass 2 fps, partial-file-on-error, provider semantics tooltip) remain deferred and are unchanged by this fix. No new issues introduced.

## Strengths

- Minimal, targeted diff — exactly the guard + create coercion the prior review requested
- Legacy-record defense tested explicitly, not only the happy create path
- Edge and Gemini picture behavior now consistent regardless of hidden slider state
