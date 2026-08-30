# Task 2 Review: Jobs dual render + `output_name_b`

**Base:** `3e5b9c6549877c8d64f4990dfff3ea7818433bfd`  
**HEAD:** `f5400ee855dedea54fba1551cff54305fb1f441f`  
**Reviewer verification:** `pytest tests/web/test_jobs.py -q` → 44 passed; `pytest -q` → 259 passed

---

## Spec Verdict: **PASS**

| Requirement | Status |
|-------------|--------|
| `JobRecord.output_name_b: str \| None = None` | ✅ |
| Hydrate `output_name_b` in `_load` / persist via `asdict` | ✅ |
| Reddit `create`: `split_reddit_story` → validate hook on Part A only | ✅ |
| Non-reddit `create`: unchanged (`split_sentences` on full story) | ✅ |
| Full story stored in `_stories` | ✅ |
| `run_job`: reddit splits; else `part_a=story`, `part_b=None` | ✅ |
| `_render_story_part` with `work_suffix` + `include_title_card` | ✅ |
| Part A: sequential synthesize → caption → card → render | ✅ |
| Part B: second render, `{stem}-b.mp4`, `work_suffix="_b"`, no card | ✅ |
| No BREAK / empty after BREAK → single output, `output_name_b=None` | ✅ |
| Single still gets X card (`include_title_card` + `mode=="single"`) | ✅ |
| Picture unchanged (no card branch; single render) | ✅ |
| Four new tests from brief | ✅ |
| Commit `feat(jobs): Reddit BREAK dual render on one job` | ✅ |
| Scope: `jobs.py` + `test_jobs.py` only | ✅ |

### Constraint checklist

- **Reddit BREAK dual sequential render:** `run_job` calls `_render_story_part` twice when `part_b is not None`; each pass runs full synthesize → caption → render pipeline. Confirmed by `test_run_job_reddit_break_writes_two_outputs` (`len(seen["renders"]) == 2`).
- **`output_name_b`:** Set to `f"{Path(output_name).stem}-b.mp4"`; cleared to `None` when no Part B. Asserted in break / no-break tests.
- **Part B no card:** Part B call uses `include_title_card=False`; second render gets `title_card_path=None`. Asserted in break test.
- **Single / Picture unchanged:** Refactor preserves mode branches inside helper; `test_run_single_passes_x_card_and_no_greenscreen` still passes (x_card path, no reddit card). Picture tests unchanged in full suite.
- **Hook on Part A only:** `create` validates `split_hook(sentences[0])` on Part A after `split_reddit_story`; Part B line without dash allowed (`test_create_reddit_validates_hook_on_part_a_only`); bad Part A hook rejected even with BREAK (`test_create_reddit_rejects_bad_hook_even_with_break`).

### Critical / Important flags

| Flag | Trigger | Result |
|------|---------|--------|
| **Critical** | Single X-card regressed | **Not triggered** — x_card test passes |
| **Critical** | Picture mode regressed | **Not triggered** — 259/259 suite green |
| **Critical** | Part B still gets a card | **Not triggered** — second render `title_card_path is None` |

---

## Quality Verdict: **PASS**

### Strengths

- Clean extraction: `_render_story_part` centralizes the existing pipeline without changing mode-specific behavior for single/picture.
- `include_title_card` flag cleanly separates Part A (reddit card / single x_card) from Part B (no card) without mode hacks.
- Work-file suffixing (`narration_b.mp3`, `captions_b.ass`, `reddit_bg_b.mp4`, `render_1x_b.mp4`) prevents Part A/B collisions in the same job dir.
- Shared `_reddit_break_mocks` helper mirrors existing reddit test patterns; new tests are focused and readable.
- `title_card_download_name` correctly uses `output_path.stem` (fixes scoping after refactor; equivalent to prior `{stem}-card.png` behavior).

### Minor nits (non-blocking)

1. **No disk-hydration test for `output_name_b`** — field is loaded in `_load` and persisted via `asdict`, but unlike `title_card_name` there is no round-trip test after job completion.
2. **No dual-part Gemini tempo test** — Part B would run tempo independently when `video_speed != 100`; report notes this; existing single-part gemini reddit test still passes.
3. **Status oscillation on dual render** — job status flips synthesizing → captioning → rendering twice (brief explicitly allows this).

None affect correctness or readiness for Task 3 (API/UI download for Part B).

---

## Summary

| Dimension | Verdict |
|-----------|---------|
| **Spec compliance** | **PASS** |
| **Code quality** | **PASS** |

Task 2 meets all brief constraints. No Critical or Important regressions on Single X-card, Picture, or Part B card behavior. Proceed to Task 3.
