# Task 2 Review: Wire Gemini Pass 1 / Pass 2 in `jobs.py`

**Reviewer:** Code review (task-scoped gate)  
**Base:** `7d3137f420b40a9bb253b2140f154d2ffa6c0e42`  
**Head:** `7fc360f2df4607b54f247d53936d77d6ca3488d1`  
**Spec:** `docs/superpowers/specs/2026-08-25-gemini-video-speed-post-render-design.md`

## Verdicts

| Gate | Result |
|------|--------|
| **Spec compliance** | ✅ |
| **Code quality** | **Approved** |

---

## Scope

Task 2 wires Gemini-only two-pass video speed in `jobs.py`: Pass 1 always renders/plans at `video_speed=100`; Pass 2 calls `tempo_finished_video` when configured speed ≠ 100. Edge behavior must remain unchanged. No UI or job-status changes.

Files in diff: `src/roblox_viral/web/jobs.py`, `tests/web/test_jobs.py`.

---

## Spec Compliance

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Gemini-only post tempo | ✅ | `needs_tempo` gated on `record.tts_provider == "gemini" and record.video_speed != 100` |
| Pass 1 forced to 100% | ✅ | `render_video_speed = 100 if record.tts_provider == "gemini" else record.video_speed`; used in `plan_reddit_sentence_clips` and `render_video` |
| Skip Pass 2 at 100% | ✅ | `needs_tempo` is false when `video_speed == 100`; no `tempo_finished_video` call; boom test passes |
| Pitch-preserving tempo via Task 1 helper | ✅ | Imports and calls `tempo_finished_video` with `record.video_speed` and `mode=record.mode` |
| Edge unchanged | ✅ | Edge uses `render_video_speed == record.video_speed`; `pass1_path == output_path`; no tempo call; regression test asserts render gets 175 |
| Stay on `"rendering"` through both passes | ✅ | Status set to `"rendering"` once before Pass 1; Pass 2 runs without intermediate status update; `"done"` only after both succeed |
| No Generate UI changes | ✅ | No UI/template/static files touched |
| Delete `render_1x.mp4` on success | ✅ | `pass1_path.unlink(missing_ok=True)` after successful tempo; asserted in tempo test |
| Reddit plan at 100, tempo at configured | ✅ | Reddit test asserts `plan_speed == 100`, render 100, tempo 200 with `mode="reddit"` |
| Persist configured `video_speed` on record | ✅ | `record.video_speed` never overwritten; only used for Pass 2 |
| Picture mode same pass logic | ✅ | `render_still` receives `pass1_path`; shared `needs_tempo` block applies tempo after still render |

All task-scoped spec requirements are met.

---

## Findings by Severity

### Critical
None.

### High
None.

### Medium
None.

### Low

1. **Gemini picture + speed ≠ 100 is untested.** The brief’s self-review notes this path is covered by shared `needs_tempo` / `pass1_path` logic on `render_still`, and the wiring is correct in code. A dedicated test would tighten confidence but is not required by the brief.

2. **Reddit Gemini test omits `render_1x` cleanup assertion.** The single-mode tempo test asserts `render_1x.mp4` is deleted after success; the reddit test does not. Behavior is the same code path; this is a test-completeness nit, not a functional gap.

### Nit

3. **No Pass 2 failure integration test.** The design spec says tempo failure should land in `"error"` without marking `"done"`. The existing `try/except` in `run_job` would handle this correctly, but Task 2’s brief did not require a failure test. Acceptable for this task gate.

---

## Strengths

- **Minimal, focused diff.** ~25 lines of production logic; no unrelated refactors.
- **Matches brief structure exactly.** Variable names (`render_video_speed`, `needs_tempo`, `pass1_path`) and placement (after `"rendering"` status, before media resolution) follow the task spec verbatim.
- **Correct kwargs split.** Pass 1 passes `render_video_speed` into `render_video`; Pass 2 passes `record.video_speed` into `tempo_finished_video` — the core behavioral change is implemented cleanly.
- **Edge regression guarded.** Explicit test with `boom_tempo` ensures Edge never enters the post-render path.
- **Good TDD signal.** Four new tests cover the primary matrix: Gemini@100 (no tempo), Gemini@160 (tempo + cleanup), Edge@175 (unchanged), Gemini reddit@200 (plan/render/tempo split).
- **Sensible reddit adaptation.** Hook story `"One line only - here.\n"` aligns with existing `split_hook` validation — appropriate deviation from brief’s placeholder story.
- **Failure semantics preserved.** Tempo runs inside the existing `try` block; failure prevents `"done"` and leaves cleanup to the success-only unlink path per spec.

---

## Code Quality Notes

**Approved.** The implementation is readable, follows existing `jobs.py` patterns, and reuses Task 1’s `tempo_finished_video` without over-abstraction. The `try/except OSError` around unlink matches the brief and avoids failing a successful job on cleanup edge cases.

Optional follow-ups (non-blocking):
- Add `test_run_job_gemini_picture_tempos_when_video_speed_not_100` if picture+Gemini becomes a common path.
- Mirror the `render_1x` deletion assertion in the reddit test for symmetry.

---

## Conclusion

Task 2 correctly wires Gemini two-pass video speed in `jobs.py` per the approved design and task brief. Edge jobs are unaffected. Tests cover the required scenarios; implementer report of 236/236 passing is consistent with the change surface. **Approve for merge from a task-scoped perspective.**
