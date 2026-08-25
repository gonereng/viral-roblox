# Final Code Review — Gemini Video Speed via Post-Render

**Reviewer:** Senior Code Reviewer (final pre-merge)
**Date:** 2026-08-25
**Base (merge-base origin/main):** `ad0de8db714d41847f0e9743285550aa27bd8541`
**Head:** `7fc360f2df4607b54f247d53936d77d6ca3488d1`
**Spec:** `docs/superpowers/specs/2026-08-25-gemini-video-speed-post-render-design.md`
**Plan:** `docs/superpowers/plans/2026-08-25-gemini-video-speed-post-render.md`

## Verdict

**Request changes** — one small blocker (Finding 1, Picture mode). Everything else is either
already correct or safe to defer. The blocker is a one-line guard plus one test; the rest of the
change is faithful to the spec and ready.

## Scope reviewed

- `src/roblox_viral/render.py` — `build_atempo_filters`, `tempo_finished_video` (+86 lines)
- `src/roblox_viral/web/jobs.py` — Pass 1 / Pass 2 wiring in `run_job` (+28/-3)
- `tests/test_render.py` (+129), `tests/web/test_jobs.py` (+202)
- Docs: spec + plan (additive only)

Read-only review. No files mutated; `git status` and `git log -1` confirmed unchanged and at
head `7fc360f`. I ran two focused test selections only (no writes to tracked files):

```
pytest tests/test_render.py -k "atempo or tempo_finished" -q   → 10 passed
pytest tests/web/test_jobs.py -k "gemini or edge_still or video_speed" -q → 9 passed
```

## Spec conformance

| Spec requirement | Status | Evidence |
|---|---|---|
| Trigger on `tts_provider == "gemini"` only | ✅ | `jobs.py:308-313` |
| Pass 1 always renders as `video_speed=100` | ✅ | `render_video_speed` feeds `plan_reddit_sentence_clips` and `render_video` |
| Pass 2 only when configured `video_speed != 100` | ✅ | `needs_tempo` guard |
| Pass 1 output is final at 100% | ✅ | `pass1_path = output_path` when not tempoing |
| Pitch preserved via `atempo` (not `asetrate`) | ✅ | `build_atempo_filters` only emits `atempo=` |
| Video `setpts=100/{video_speed}*PTS` | ✅ | `render.py` tempo helper |
| atempo factors constrained to `[0.5, 2.0]` | ✅ | verified by hand for 50/150/200/300/400/500 |
| Same H.264/AAC final profile as today | ✅ | `libx264 / preset medium / crf 18 / aac / 192k / +faststart` matches `render_video` exactly |
| Validated with `validate_video_speed(..., mode=...)` | ✅ | same call and same `mode` used at `create()`, so Pass 2 validation can never fail late |
| Edge unchanged | ✅ | regression test asserts `video_speed == 175` reaches render and tempo is never called |
| Job stays on `"rendering"` across both passes | ✅ | no `_set_status` between passes |
| Pass 2 failure → job `"error"`, never `"done"` | ✅ | `RenderError` propagates before `record.output_name` is set |
| `render_1x.mp4` deleted on success | ✅ | `unlink(missing_ok=True)` guarded by `OSError` |
| No new job status | ✅ | — |
| No Generate-page change | ⚠️ | true literally, but see Finding 1 — an existing hidden control now has an effect |

Correctness of the atempo chain, verified by hand against the reachable range
(single 50–200, reddit 100–500):

| % | chain | product |
|---|---|---|
| 50 | `atempo=0.5` | 0.5 |
| 150 | `atempo=1.5` | 1.5 |
| 160 | `atempo=1.6` | 1.6 |
| 200 | `atempo=2.0` | 2.0 |
| 300 | `atempo=2.0, atempo=1.5` | 3.0 |
| 400 | `atempo=2.0, atempo=2.0` | 4.0 |
| 500 | `atempo=2.0, atempo=2.0, atempo=1.25` | 5.0 |

## Findings

### 1. IMPORTANT (blocker) — Picture mode: a hidden Video-speed control now silently changes output

`needs_tempo` does not exclude `record.mode == "picture"`:

```python
needs_tempo = (
    record.tts_provider == "gemini" and record.video_speed != 100
)
```

Combined with `render_still(output_path=pass1_path)`, a Gemini picture job with
`video_speed != 100` now gets a full Pass 2 tempo. Before this change, picture mode ignored
`video_speed` entirely (`render_still` has no `video_speed` parameter).

The problem is that the Generate page **hides** the Video speed control in Picture mode while
still submitting its value:

- `static/app.js:163` — `if (videoSpeedField) videoSpeedField.hidden = isPicture;`
- `static/app.js:143-155` — `clampVideoSpeedForMode` clamps to the single range (50–200) for
  picture; a value of e.g. 175 survives the mode switch untouched
- `static/app.js:324` — `video_speed: Number(document.getElementById("video_speed").value)` is
  posted unconditionally, for every mode

Reproducible flow, entirely within the normal UI: Single mode → drag Video speed to 175% →
switch to Picture tab (slider disappears, value stays 175) → pick Gemini → Generate. The job is
created with `mode="picture", video_speed=175` (passes `create()` validation, since picture uses
the single range), and the finished picture video plays at 1.75× with 1.75× narration. The user
never requested it and has no visible control to undo it. The same form state under Edge
produces a normal 1× picture video, so the behavior is now provider-dependent for identical
inputs.

Note this is intentional per the plan's self-review ("Picture mode: Pass 1 still → Pass 2 tempo
when Gemini + ≠100"), so the real conflict is plan-vs-UI rather than an implementation slip. It
still needs a decision before merge because the shipped result is a silently mis-timed render.

Recommended minimal fix (matches the UI, keeps Edge and Gemini picture behavior identical, and
respects the spec's "no Generate-page change"):

```python
needs_tempo = (
    record.tts_provider == "gemini"
    and record.mode != "picture"
    and record.video_speed != 100
)
```

…plus one job test asserting Gemini + picture + `video_speed=160` does not call
`tempo_finished_video` and writes straight to the final output. If instead the intent is to keep
picture tempo support, the slider must be shown (or reset to 100) for Picture mode, which is a
UI change and therefore a spec amendment.

### 2. MINOR — `anull` and `video_speed == 100` branches in `tempo_finished_video` are unreachable

`build_atempo_filters` returns `[]` only when `speed_percent == 100`, and the helper already
returns early at 100, so `audio_chain = ... if atempo else "anull"` can never take the `anull`
side. Likewise the `video_speed == 100` copy/same-path branch is unreachable from the only
caller, because `needs_tempo` guarantees `!= 100`.

Both are defensive code on a module-public helper with its own unit tests
(`test_tempo_finished_video_100_copies_without_ffmpeg`), which is a reasonable contract for a
reusable function. Keep as-is; no change required. This resolves the deferred minors "dead anull
branch" and "untested missing-file/same-path 100% tempo paths" — the latter branches are
unreachable from production code, so their test gap carries no risk.

### 3. MINOR — `remaining == 2.0` special case is string cosmetics, not logic

```python
if abs(remaining - 2.0) < 1e-9:
    filters.append("atempo=2.0")
else:
    filters.append(f"atempo={remaining:.10g}")
```

This deviates from the plan and exists only so 200% and 400% emit `atempo=2.0` rather than
`atempo=2` (`:.10g` drops the trailing zero). `atempo=2` is equally valid ffmpeg, so the branch
buys nothing functionally — it satisfies an exact-string test assertion. Not a bug and not worth
churn now, but the tests are over-specified on formatting: they pin the literal filter string
rather than the resulting factor. A follow-up could assert on the parsed product instead.

### 4. MINOR — Pass 2 output frame rate is unconstrained

The tempo command applies `setpts` with no `fps=`/`-r`, so a 30 fps Pass 1 file becomes ~48 fps
at 160%, 60 fps at 200%, and 150 fps at 500%. A 150 fps vertical 1080p file is unusual for
social upload targets and inflates encode time and file size.

This mirrors pre-existing behavior — `render_video`'s in-render `setpts` path has the same
property for Edge reddit jobs at high speeds — and the spec asked for "the same profile used for
finals today", so the implementation is consistent with the codebase. Worth a follow-up that
normalizes both paths with `fps=30` (as `build_reddit_background` already does), not a blocker
here.

### 5. MINOR — no `-shortest` on the tempo command

`render_video` uses `-shortest`; the tempo command does not. `setpts` and `atempo` produce
lengths that can differ by a few milliseconds, so the output takes the longer stream. The drift
is inaudible and invisible. Adding `-shortest` would make Pass 2 match Pass 1's convention.

### 6. MINOR — a failed Pass 2 can leave a truncated MP4 visible in the Library

`ffmpeg -y` writes directly to `outputs/{name}.mp4`, so a mid-encode failure can leave a partial
file there. `list_outputs` (`web/library.py:172-178`) enumerates `outputs_dir` by glob rather
than by job record, so the partial file appears in the Library even though the job is `"error"`
and `record.output_name` was never set.

This is pre-existing — a failed Pass 1 render had exactly the same effect, since Pass 1 also
wrote straight to `outputs/`. The change adds a second failure window rather than a new class of
bug. A future cleanup would encode to a temp file and `os.replace` into `outputs/`. The spec's
"do not mark done with an unsped or partial final" requirement is satisfied: the job never
reaches `"done"`.

### 7. NOTE — the Video speed control now means two different things

Worth recording because it will generate support questions:

- **Edge:** `video_speed` applies `setpts` to the gameplay footage only. Narration and captions
  stay at 1×, and `-shortest` clamps output to narration length. The slider means "how fast the
  background plays".
- **Gemini (new):** `video_speed` retimes the entire finished file — footage, narration, and
  burned captions — so output length becomes `narration / speed`. The slider means "how fast the
  whole video plays".

Same control, same label, no UI hint about the difference. The spec approved this consciously
("Speeding the finished file keeps burned karaoke, title-card overlays, gameplay, and voice
locked together"), so it is not a defect in this change. Flagging it as product debt for a
follow-up label or tooltip.

### 8. NOTE — reddit clip planning gets easier, not harder, at Pass 1

I checked this because forcing Pass 1 to 100% could plausibly have changed footage requirements.
`plan_reddit_sentence_clips` computes `source_needed = sent_dur * (video_speed / 100.0)`
(`reddit_clips.py:104`), so 100% needs *less* source footage than 500%, and the planner loops a
short file rather than failing. No regression risk for small video libraries.

### 9. NOTE — Pass 2 doubles wall-clock time with no progress signal

Pass 2 is a full second re-encode at `preset medium / crf 18`, roughly doubling render time for
Gemini jobs at ≠100% and adding one transcode generation of quality loss. The job sits on
`"rendering"` for the whole time. The spec makes a Pass 2 progress string an explicit non-goal,
so this is accepted, but users will perceive long Gemini renders as stalled.

## Triage of deferred minors from the task reviews

| Deferred item | Verdict | Reasoning |
|---|---|---|
| Untested missing-file / same-path 100% tempo paths | **Stay deferred** | Unreachable from `run_job`; defensive-only. See Finding 2. |
| Dead `anull` branch in tempo helper | **Stay deferred** | Confirmed unreachable, harmless, reasonable contract for a public helper. See Finding 2. |
| Gemini picture mode + tempo untested | **Must fix** | The test gap hid a real behavior bug. See Finding 1 — add the guard and the test together. |
| Reddit test omits `render_1x` cleanup assert | **Stay deferred** | Cleanup is one shared code path already asserted in `test_run_job_gemini_tempos_when_video_speed_not_100`; a second assert on the same lines adds no coverage. |
| No Pass 2 failure test | **Stay deferred** | `test_tempo_finished_video_ffmpeg_failure_raises` covers the raise, and propagation uses `run_job`'s generic `except Exception` that every other pipeline step already relies on. Cheap to add later; not load-bearing. |

## Strengths

- **Spec fidelity.** Every product decision in the spec table maps to a verifiable line of code,
  including the easy-to-miss ones: status is untouched between passes, `record.video_speed` keeps
  the user's configured value, and Pass 2 reuses `render_video`'s exact encoder flags rather than
  inventing a profile.
- **Edge is genuinely protected.** `test_run_job_edge_still_passes_configured_video_speed` asserts
  both halves of the invariant — the configured speed reaches the render *and* `tempo_finished_video`
  raises if it is ever called. That is the right shape for a regression test on a provider fork.
- **The atempo chain is correct across the whole reachable range**, including the awkward 500%
  case that needs three stages, and it is tested at both range ends plus the chained case.
- **Small, well-placed seam.** Three derived locals (`render_video_speed`, `needs_tempo`,
  `pass1_path`) computed once, with the picture and video branches converging on `pass1_path`.
  No duplicated Pass 2 logic and no new status machinery.
- **Validation is consistent end to end.** `tempo_finished_video` re-validates with the same
  `mode` that `create()` used, so a bad speed can never surface after a completed Pass 1.
- **Cleanup is failure-tolerant** — `unlink(missing_ok=True)` inside `try/except OSError` means a
  locked temp file on Windows cannot flip a successful render into an error.
- **Tests are honest.** The mocks capture kwargs and assert on real filesystem effects (final
  bytes are `b"mp4-sped"`, `render_1x.mp4` is gone) rather than just on call counts.

## Required before merge

1. Resolve Finding 1: either exclude `mode == "picture"` from `needs_tempo`, or expose/reset the
   Video speed control for Picture mode (the latter is a UI change and needs a spec amendment).
2. Add the accompanying Gemini + picture job test.

Findings 2–9 need no action for this merge.
