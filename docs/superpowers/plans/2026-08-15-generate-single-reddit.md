# Generate Single / Picture / Reddit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename Roblox → Single (sources-only), add Reddit mode (concat random `media/videos/` to TTS length), double overlay fitted in-frame on Single+Reddit, and align n8n (`single`/`reddit`/`leni`; reject `roblox`).

**Architecture:** Pure `plan_reddit_clips` + ffmpeg concat temp bg; reuse `render_video` for crop/ASS/setpts/overlay/TTS. Jobs/API/UI use `mode` ∈ `single|picture|reddit` with `roblox`→`single` hydrate compat.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, vanilla JS, ffmpeg, pytest

## Global Constraints

- Modes: `single` | `picture` | `reddit` (breaking rename from `roblox`)
- Single: dropdown `media/sources/` only; loop one clip; overlay yes; video_speed yes
- Reddit: no picker; auto pool `media/videos/`; shuffle without reuse then reshuffle; trim last; overlay yes; video_speed yes
- Picture: unchanged (no overlay, hide video_speed)
- Overlay: 3.5s wall-clock; **2×** size = fit inside 1080×1920 (aspect preserved, not cropped off)
- n8n: `type=single|reddit|leni`; `type=roblox` → 400 telling client to use `single`
- Empty videos pool → error for reddit create
- Spec: `docs/superpowers/specs/2026-08-15-generate-single-reddit-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/render.py` | Overlay fit-in-frame scale; `concat_reddit_background` |
| `src/roblox_viral/reddit_clips.py` (new) or `library.py` | `ClipSegment`, `plan_reddit_clips` |
| `tests/test_render.py` | Overlay scale assertion |
| `tests/test_reddit_clips.py` (new) | Planner unit tests |
| `src/roblox_viral/web/jobs.py` | Modes single/reddit; concat in run_job |
| `src/roblox_viral/web/app.py` | CreateJobBody; generate context |
| `src/roblox_viral/web/api_v1.py` | type mapping |
| `generate.html` / `app.js` | Three tabs |
| `README.md` | Document modes / n8n types |
| Tests: `test_jobs.py`, `test_api.py`, `test_api_v1.py` | Mode + n8n coverage |

---

### Task 1: Overlay 2× fit-in-frame

**Files:**
- Modify: `src/roblox_viral/render.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- Produces: Overlay scale uses fit-inside frame, not `scale=-2:OVERLAY_HEIGHT` with half height.
- Replace `OVERLAY_HEIGHT = OUTPUT_HEIGHT // 2` with fit expression, e.g. keep constants:

```python
# Max overlay box = full output frame (2× former half-height target)
OVERLAY_MAX_W = OUTPUT_WIDTH
OVERLAY_MAX_H = OUTPUT_HEIGHT
```

Filter fragment (after chromakey + yuva420p):

```text
scale=w='min(iw*{OVERLAY_MAX_W}/iw\,{OVERLAY_MAX_W})':h='min(ih*{OVERLAY_MAX_H}/ih\,{OVERLAY_MAX_H})':force_original_aspect_ratio=decrease
```

Simpler ffmpeg idiom that fits inside WxH:

```text
scale={OVERLAY_MAX_W}:{OVERLAY_MAX_H}:force_original_aspect_ratio=decrease
```

Use that after chromakey. Center overlay unchanged: `overlay=(W-w)/2:(H-h)/2:enable='lte(t,{OVERLAY_DURATION_S})'`.

- [ ] **Step 1: Write failing test**

In `tests/test_render.py`, extend overlay test (or add):

```python
def test_render_video_overlay_fits_full_frame(tmp_path, monkeypatch):
    # same fake_run setup as existing overlay test
    render_video(..., overlay_path=overlay)
    fc = seen["cmd"][seen["cmd"].index("-filter_complex") + 1]
    assert f"scale={1080}:{1920}:force_original_aspect_ratio=decrease" in fc
    assert "scale=-2:" not in fc  # old half-height pattern gone
    assert "lte(t,3.5)" in fc
```

Update any existing test that asserts `OVERLAY_HEIGHT` / `scale=-2:`.

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_render.py::test_render_video_overlay_fits_full_frame -v`

- [ ] **Step 3: Implement scale change in `render.py`**

- [ ] **Step 4: Run `pytest tests/test_render.py -v` — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: scale greenscreen overlay to fit full frame (2x)"
```

---

### Task 2: `plan_reddit_clips` planner

**Files:**
- Create: `src/roblox_viral/reddit_clips.py`
- Create: `tests/test_reddit_clips.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class ClipSegment:
    path: Path
    start_s: float  # always 0 for v1
    duration_s: float

def plan_reddit_clips(
    paths: list[Path],
    target_seconds: float,
    *,
    durations: dict[Path, float] | None = None,
    rng: random.Random | None = None,
) -> list[ClipSegment]:
    """
    Shuffle without replacement; reshuffle when exhausted; trim last segment.
    durations: optional map path→seconds (tests inject; production uses probe).
    Raise ValueError if paths empty or target_seconds <= 0.
    """
```

Production callers may pass `durations` from `probe_duration_seconds` per path. Planner itself should not call ffmpeg if `durations` provided.

Algorithm:
1. If not paths or target_seconds <= 0 → ValueError
2. remaining = target_seconds; out = []
3. bag = shuffled copy of paths; while remaining > 1e-6:
   - if bag empty: bag = shuffled copy of paths
   - take next path; d = durations[path]
   - if d <= 0: skip / error
   - use = min(d, remaining); append ClipSegment(path, 0, use); remaining -= use

- [ ] **Step 1: Failing tests**

```python
def test_plan_trims_last_clip():
    paths = [Path("a.mp4"), Path("b.mp4")]
    durs = {paths[0]: 10.0, paths[1]: 10.0}
    rng = random.Random(0)
    segs = plan_reddit_clips(paths, 15.0, durations=durs, rng=rng)
    assert abs(sum(s.duration_s for s in segs) - 15.0) < 1e-6
    assert segs[-1].duration_s < 10.0 or len(segs) == 2


def test_plan_reshuffles_when_exhausted():
    p = Path("only.mp4")
    segs = plan_reddit_clips([p], 25.0, durations={p: 10.0}, rng=random.Random(1))
    assert len(segs) == 3
    assert abs(sum(s.duration_s for s in segs) - 25.0) < 1e-6


def test_plan_empty_pool_errors():
    with pytest.raises(ValueError):
        plan_reddit_clips([], 10.0, durations={})
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `reddit_clips.py`**

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit** `feat: add reddit clip planner (shuffle, reshuffle, trim)`

---

### Task 3: Concat helper + wire into render pipeline helper

**Files:**
- Modify: `src/roblox_viral/render.py` — add `build_reddit_background(...)`
- Modify: `tests/test_render.py` or `tests/test_reddit_clips.py`

**Interfaces:**
- Consumes: `list[ClipSegment]`
- Produces:

```python
def build_reddit_background(
    segments: list[ClipSegment],
    output_path: Path,
    *,
    work_dir: Path | None = None,
) -> Path:
    """
    ffmpeg: for each segment, optionally trim (-t duration), then concat demuxer
    to output_path. Raise RenderError on failure.
    """
```

Implementation sketch:
- For each segment, if `duration_s` < full file duration (or always), write a trimmed temp with `-ss start -t duration -i path -c copy` (copy may fail on keyframes — prefer re-encode `-c:v libx264 -an` for reliability on shorts), collect paths.
- Write concat list file; `ffmpeg -f concat -safe 0 -i list.txt -c copy out` or re-encode.
- Prefer re-encode to one consistent stream for later `render_video` loop/crop.

Simpler approach acceptable for v1: filter_complex concat of N trimmed inputs in one ffmpeg invocation writing `output_path`.

- [ ] **Step 1: Test with monkeypatched subprocess** — assert ffmpeg invoked and output path returned when fake_run creates file

- [ ] **Step 2–4: TDD implement**

- [ ] **Step 5: Commit** `feat: build concat background from reddit clip segments`

---

### Task 4: JobManager `single` / `reddit`

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`

**Interfaces:**
- Consumes: `plan_reddit_clips`, `build_reddit_background`, `list_videos`, `probe_duration_seconds`, `resolve_source`
- Produces:
  - `normalize_mode(mode: str) -> str` — `roblox`→`single`; validate ∈ {single,picture,reddit}
  - `create(..., mode="single")`:
    - `single`: `resolve_source` (not `resolve_roblox_media`); require non-empty source_name
    - `picture`: unchanged
    - `reddit`: `source_name` may be `""`; require `list_videos(settings)` non-empty; store `source_name=""` or `"reddit"`
  - `run_job`:
    - `single` / ephemeral roblox-like: existing render_video + overlay
    - `reddit`: probe TTS duration after synth (or probe narration file); plan clips with durations; `build_reddit_background` → `job_dir/reddit_bg.mp4`; `render_video` that path + overlay + video_speed
  - Disk hydrate: `normalize_mode(data.get("mode") or "single")`

Update all tests that use `mode="roblox"` → `"single"`.

- [ ] **Step 1: Failing tests**

```python
def test_create_single_rejects_missing_source(...): ...
def test_create_reddit_requires_videos_pool(...): ...
def test_create_reddit_ok_with_videos(...): ...
def test_hydrate_roblox_mode_as_single(...): ...
def test_run_reddit_builds_background_and_renders(...):
    # monkeypatch plan, build_reddit_background, render_video, TTS
    # assert build called; render_video video_path == reddit_bg
```

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat(web): job modes single and reddit with concat background`

---

### Task 5: UI jobs API + Generate page context

**Files:**
- Modify: `src/roblox_viral/web/app.py`
- Modify: `tests/web/test_api.py`

**Interfaces:**
- `CreateJobBody.mode` default `"single"`
- Pass `list_sources` + `list_videos` (count or list) + `list_images` to template (not `list_roblox_sources`)
- Validate mode; 400 on bad mode

- [ ] **Step 1: Tests** — POST mode=single/reddit/picture; reject mode=roblox or accept only if you map (prefer reject on UI API for clarity, or map — **map roblox→single** on UI for soft compat; n8n still hard-rejects)

Plan choice: UI API **maps** `roblox`→`single`; n8n **rejects** `roblox`.

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat(web): API and generate context for single/reddit modes`

---

### Task 6: Generate frontend three tabs

**Files:**
- Modify: `src/roblox_viral/web/templates/generate.html`
- Modify: `src/roblox_viral/web/static/app.js`
- Modify: `tests/web/test_api.py` (HTML assertions)

**Interfaces:**
- Tabs: `#tab-single` label "Single background video"; `#tab-picture`; `#tab-reddit` "Reddit"
- Single block: `#source_name` from slices only
- Reddit block: short note “Uses random clips from Library → Videos”; no select
- `data-mode` / `currentMode`: `single|picture|reddit`
- Video speed visible for single+reddit; hidden for picture
- Generate disabled: single if no sources; picture if no images; reddit if no videos (pass `has_videos` boolean from template)
- POST `mode`, `source_name` (empty string for reddit)

- [ ] **Step 1: Update HTML/JS + page tests asserting tab ids and absence of Roblox label**

- [ ] **Step 2: Commit** `feat(web): Generate tabs for Single, Picture, and Reddit`

---

### Task 7: n8n API types

**Files:**
- Modify: `src/roblox_viral/web/api_v1.py`
- Modify: `tests/web/test_api_v1.py`
- Modify: `README.md` / `scripts/test-n8n-api.ps1`

**Interfaces:**

```python
def _mode_from_type(video_type: str) -> str:
    t = (video_type or "").strip().lower()
    if t == "single":
        return "single"
    if t == "reddit":
        return "reddit"
    if t == "leni":
        return "picture"
    if t == "roblox":
        raise ValueError("type 'roblox' is removed; use 'single'")
    raise ValueError("type must be 'single', 'reddit', or 'leni'")
```

For `reddit`:
- Do not require `source_name` or `media`
- Reject if both provided or if media provided (background not accepted)
- `mgr.create(..., source_name="", mode="reddit", ...)`

For `single`: same as former roblox (media XOR source_name).

- [ ] **Step 1: Tests** — single works; reddit with only story/voice/type; roblox → 400; leni ok

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat(api): n8n types single and reddit; reject roblox`

---

### Task 8: README + full regression

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document Generate tabs, overlay 2×, n8n types**

- [ ] **Step 2: `pytest -q` — all PASS**

- [ ] **Step 3: Commit** `docs: document Single/Reddit generate modes`

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Overlay 2× fit | 1 |
| plan_reddit_clips | 2 |
| concat temp bg | 3 |
| Job modes + run | 4 |
| API/context | 5 |
| Generate UI | 6 |
| n8n types | 7 |
| README | 8 |

## Consistency

- Mode strings: `single`, `picture`, `reddit` only in new code
- Overlay scale string: `scale=1080:1920:force_original_aspect_ratio=decrease`
- n8n rejects `roblox`; UI may map `roblox`→`single`
