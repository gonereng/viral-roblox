# Reddit Per-Sentence Clips Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reddit backgrounds use one new library video per sentence (trimmed to sentence TTS length, loop short files), with mode-specific video speed limits (Reddit 100–500%, Single 50–200%).

**Architecture:** Add `sentence_durations_s` + `plan_reddit_sentence_clips` in `reddit_clips.py`; Reddit `run_job` partitions words by sentence and plans per sentence with `video_speed`. Extend `validate_video_speed(percent, mode=...)` and clamp Generate slider bounds in JS on tab switch.

**Tech Stack:** Python 3.10+, ffmpeg concat (existing), FastAPI jobs, pytest

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-20-reddit-per-sentence-clips-design.md`
- One **bag pop** per sentence; loop **same path** within sentence if file too short
- Trim from **start 0:00** only
- Source per sentence: `sentence_duration × (video_speed / 100)`
- Reddit `video_speed`: **100–500**, default 100
- Single `video_speed`: **50–200**, default 100
- Picture: slider hidden; record default 100
- Title card / overlay unchanged

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/reddit_clips.py` | `sentence_durations_s`, `plan_reddit_sentence_clips` |
| `tests/test_reddit_clips.py` | Planner + duration helper tests |
| `src/roblox_viral/voice.py` | Mode-aware `validate_video_speed` |
| `tests/test_voice.py` | Range tests per mode |
| `src/roblox_viral/web/jobs.py` | Reddit wiring |
| `tests/web/test_jobs.py` | Reddit run uses sentence planner |
| `src/roblox_viral/web/app.py` | Pass `mode` to validation |
| `src/roblox_viral/web/api_v1.py` | Pass `type`→mode to validation |
| `tests/web/test_api.py`, `tests/web/test_api_v1.py` | 400/200 for new bounds |
| `src/roblox_viral/web/templates/generate.html` | Initial slider attrs (Single default) |
| `src/roblox_viral/web/static/app.js` | Mode-dependent min/max clamp |
| `README.md` | Reddit per-sentence + speed ranges |

---

### Task 1: `sentence_durations_s` + `plan_reddit_sentence_clips`

**Files:**
- Modify: `src/roblox_viral/reddit_clips.py`
- Modify: `tests/test_reddit_clips.py`

**Interfaces:**
- Produces:

```python
def sentence_durations_s(
    sentences: list[str], words: list[WordTiming]
) -> list[float]:
    """Wall-clock seconds per sentence from word timings."""

def plan_reddit_sentence_clips(
    paths: list[Path],
    sentence_durations_s: list[float],
    *,
    video_speed: int = 100,
    durations: dict[Path, float] | None = None,
    rng: random.Random | None = None,
) -> list[ClipSegment]:
```

Keep existing `plan_reddit_clips` (total-target) for its tests unless you migrate tests — Reddit production will stop calling it.

- [ ] **Step 1: Write failing tests** in `tests/test_reddit_clips.py`:

```python
from roblox_viral.reddit_clips import (
    plan_reddit_clips,
    plan_reddit_sentence_clips,
    sentence_durations_s,
)
from roblox_viral.voice import WordTiming


def test_sentence_durations_s_from_word_groups():
    sentences = ["Hello world.", "Second line."]
    words = [
        WordTiming("Hello", 0, 200),
        WordTiming("world.", 200, 500),
        WordTiming("Second", 500, 800),
        WordTiming("line.", 800, 1000),
    ]
    durs = sentence_durations_s(sentences, words)
    assert len(durs) == 2
    assert abs(durs[0] - 0.5) < 1e-6
    assert abs(durs[1] - 0.5) < 1e-6


def test_plan_one_video_per_sentence():
    paths = [Path("a.mp4"), Path("b.mp4"), Path("c.mp4")]
    durs_map = {p: 30.0 for p in paths}
    rng = random.Random(0)
    segs = plan_reddit_sentence_clips(
        paths,
        [2.0, 3.0, 1.5],
        video_speed=100,
        durations=durs_map,
        rng=rng,
    )
    # 3 sentences -> 3 picks -> 3 segments (each file long enough)
    assert len(segs) == 3
    assert segs[0].path != segs[1].path != segs[2].path
    assert abs(segs[0].duration_s - 2.0) < 1e-6
    assert abs(segs[1].duration_s - 3.0) < 1e-6
    assert abs(segs[2].duration_s - 1.5) < 1e-6


def test_plan_loops_short_file_within_sentence():
    p = Path("short.mp4")
    segs = plan_reddit_sentence_clips(
        [p],
        [5.0],
        video_speed=100,
        durations={p: 2.0},
        rng=random.Random(1),
    )
    assert len(segs) == 3  # 2+2+1
    assert all(s.path == p and s.start_s == 0.0 for s in segs)
    assert abs(sum(s.duration_s for s in segs) - 5.0) < 1e-6


def test_plan_video_speed_doubles_source():
    p = Path("a.mp4")
    segs = plan_reddit_sentence_clips(
        [p],
        [2.0],
        video_speed=200,
        durations={p: 10.0},
        rng=random.Random(2),
    )
    assert abs(sum(s.duration_s for s in segs) - 4.0) < 1e-6


def test_plan_reshuffles_when_more_sentences_than_pool():
    paths = [Path("a.mp4"), Path("b.mp4")]
    durs_map = {p: 10.0 for p in paths}
    rng = random.Random(3)
    segs = plan_reddit_sentence_clips(
        paths,
        [1.0, 1.0, 1.0],
        durations=durs_map,
        rng=rng,
    )
    assert len(segs) == 3
    assert len({s.path for s in segs}) >= 2  # used both before repeat
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_reddit_clips.py::test_sentence_durations_s_from_word_groups tests/test_reddit_clips.py::test_plan_one_video_per_sentence -v`

Expected: FAIL (import / not defined)

- [ ] **Step 3: Implement in `reddit_clips.py`**

Add imports:

```python
from roblox_viral.captions import partition_words_by_sentences
from roblox_viral.voice import WordTiming
```

```python
def sentence_durations_s(
    sentences: list[str], words: list[WordTiming]
) -> list[float]:
    groups = partition_words_by_sentences(sentences, words)
    if len(groups) != len(sentences):
        raise ValueError("sentence count mismatch")
    out: list[float] = []
    for group in groups:
        if not group:
            raise ValueError("sentence has no words")
        duration = (group[-1].end_ms - group[0].start_ms) / 1000.0
        if duration <= 0:
            raise ValueError("sentence duration must be positive")
        out.append(duration)
    return out


def plan_reddit_sentence_clips(
    paths: list[Path],
    sentence_durations_s: list[float],
    *,
    video_speed: int = 100,
    durations: dict[Path, float] | None = None,
    rng: random.Random | None = None,
) -> list[ClipSegment]:
    if not paths or not sentence_durations_s:
        raise ValueError("paths and sentence_durations_s must be non-empty")
    if video_speed <= 0:
        raise ValueError("video_speed must be positive")

    rng = rng or random.Random()
    out: list[ClipSegment] = []
    bag: list[Path] = []

    for sent_dur in sentence_durations_s:
        if sent_dur <= 0:
            raise ValueError("sentence duration must be positive")
        source_needed = sent_dur * (video_speed / 100.0)
        if not bag:
            bag = list(paths)
            rng.shuffle(bag)
        path = bag.pop()
        file_duration = _duration_for(path, durations)
        if file_duration <= 0:
            raise ValueError(f"duration must be positive for {path}")

        remaining = source_needed
        while remaining > _EPSILON:
            use = min(file_duration, remaining)
            out.append(ClipSegment(path=path, start_s=0.0, duration_s=use))
            remaining -= use

    return out
```

- [ ] **Step 4: Run GREEN**

Run: `pytest tests/test_reddit_clips.py -v`

Expected: all PASS (including legacy `plan_reddit_clips` tests)

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/reddit_clips.py tests/test_reddit_clips.py
git commit -m "feat: plan Reddit background clips per sentence"
```

---

### Task 2: Mode-aware `validate_video_speed`

**Files:**
- Modify: `src/roblox_viral/voice.py`
- Modify: `tests/test_voice.py`
- Modify: `src/roblox_viral/web/jobs.py` (create validation only)
- Modify: `src/roblox_viral/web/app.py`
- Modify: `src/roblox_viral/web/api_v1.py`

**Interfaces:**
- Produces:

```python
SINGLE_VIDEO_SPEED_MIN, SINGLE_VIDEO_SPEED_MAX = 50, 200
REDDIT_VIDEO_SPEED_MIN, REDDIT_VIDEO_SPEED_MAX = 100, 500

def validate_video_speed(percent: int, *, mode: str = "single") -> int:
```

- `mode` normalized: `reddit` → Reddit range; `single`, `picture`, default → Single range (picture accepts but caller ignores).

- [ ] **Step 1: Failing tests** in `tests/test_voice.py`:

```python
def test_validate_video_speed_reddit_allows_500():
    assert validate_video_speed(500, mode="reddit") == 500


def test_validate_video_speed_reddit_rejects_99():
    with pytest.raises(ValueError):
        validate_video_speed(99, mode="reddit")


def test_validate_video_speed_single_still_50_200():
    assert validate_video_speed(50, mode="single") == 50
    with pytest.raises(ValueError):
        validate_video_speed(49, mode="single")
    with pytest.raises(ValueError):
        validate_video_speed(500, mode="single")
```

Update existing `test_validate_video_speed_ok` to pass `mode="single"` if signature adds `mode` kwarg.

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_voice.py -k video_speed -v`

Expected: FAIL on 500 for reddit

- [ ] **Step 3: Implement `voice.py`**

Replace global min/max usage in `validate_video_speed` with mode branch:

```python
SINGLE_VIDEO_SPEED_MIN, SINGLE_VIDEO_SPEED_MAX = 50, 200
REDDIT_VIDEO_SPEED_MIN, REDDIT_VIDEO_SPEED_MAX = 100, 500

# Keep VIDEO_SPEED_MIN/MAX as aliases to SINGLE_* for backward compat if referenced elsewhere
VIDEO_SPEED_MIN, VIDEO_SPEED_MAX = SINGLE_VIDEO_SPEED_MIN, SINGLE_VIDEO_SPEED_MAX


def validate_video_speed(percent: int, *, mode: str = "single") -> int:
    if not isinstance(percent, int) or isinstance(percent, bool):
        raise ValueError("video_speed must be an int")
    m = (mode or "single").strip().lower()
    if m == "reddit":
        lo, hi = REDDIT_VIDEO_SPEED_MIN, REDDIT_VIDEO_SPEED_MAX
    else:
        lo, hi = SINGLE_VIDEO_SPEED_MIN, SINGLE_VIDEO_SPEED_MAX
    if percent < lo or percent > hi:
        raise ValueError(f"video_speed must be between {lo} and {hi}")
    return percent
```

In `jobs.py` `create`:

```python
validate_video_speed(video_speed, mode=mode)
```

In `app.py` job create (after resolving mode):

```python
validate_video_speed(video_speed, mode=mode)
```

In `api_v1.py` (after `mode = _mode_from_type(type)`):

```python
validate_video_speed(video_speed_i, mode=mode)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_voice.py -k video_speed tests/web/test_api.py::test_api_jobs_rejects_video_speed tests/web/test_api_v1.py::test_create_invalid_video_speed_400 -v`

Update API tests if they use `video_speed: 10` for single — still 400. Add `test_create_accepts_reddit_video_speed_500` in `test_api_v1.py`:

```python
def test_create_accepts_reddit_video_speed_500(tmp_path, monkeypatch):
    # videos in pool, type=reddit, video_speed=500 → 200
```

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/voice.py tests/test_voice.py src/roblox_viral/web/jobs.py src/roblox_viral/web/app.py src/roblox_viral/web/api_v1.py tests/web/test_api_v1.py tests/web/test_api.py tests/web/test_jobs.py
git commit -m "feat: mode-specific video_speed validation (Reddit 100-500)"
```

---

### Task 3: Wire Reddit `run_job` to sentence planner

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`

**Interfaces:**
- Consumes: `sentence_durations_s`, `plan_reddit_sentence_clips` from Task 1

- [ ] **Step 1: Update failing job test**

Replace `test_run_reddit_scales_plan_target_by_video_speed` with sentence-based assertion:

```python
def test_run_reddit_plans_by_sentence_durations(tmp_path, monkeypatch):
    # ... fakes like existing reddit run tests ...
    seen = {}

    def fake_plan(paths, sentence_durations_s, *, video_speed, durations):
        seen["plan"] = (paths, sentence_durations_s, video_speed, durations)
        return ["planned-segment"]

    monkeypatch.setattr(
        jobs_module, "plan_reddit_sentence_clips", fake_plan, raising=False
    )
    # fake synthesize returns words spanning 2 sentences with known timings
    # ...
    job = mgr.create(..., mode="reddit", video_speed=200)
    mgr.run_job(s, job.id)
    _, sent_durs, speed, _ = seen["plan"]
    assert len(sent_durs) == 2  # match story lines
    assert speed == 200
```

Remove or update any test still patching `plan_reddit_clips` for Reddit success path to patch `plan_reddit_sentence_clips` instead.

- [ ] **Step 2: Run RED**

Run: `pytest tests/web/test_jobs.py::test_run_reddit_plans_by_sentence_durations -v`

Expected: FAIL

- [ ] **Step 3: Implement `jobs.py` reddit block**

Imports:

```python
from roblox_viral.reddit_clips import (
    plan_reddit_clips,
    plan_reddit_sentence_clips,
    sentence_durations_s,
)
```

Replace reddit planning block:

```python
                sent_durations = sentence_durations_s(sentences, words)
                segments = plan_reddit_sentence_clips(
                    videos,
                    sent_durations,
                    video_speed=record.video_speed,
                    durations=durations,
                )
```

Remove `narration_duration` / `plan_target` / `plan_reddit_clips` from Reddit branch.

- [ ] **Step 4: Run GREEN**

Run: `pytest tests/web/test_jobs.py -k reddit -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/jobs.py tests/web/test_jobs.py
git commit -m "feat(web): Reddit background one clip per sentence"
```

---

### Task 4: Generate slider bounds + README

**Files:**
- Modify: `src/roblox_viral/web/templates/generate.html`
- Modify: `src/roblox_viral/web/static/app.js`
- Modify: `tests/web/test_api.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: Reddit 100–500, Single 50–200 constants (mirror in JS as literals matching spec)

- [ ] **Step 1: Failing smoke test** in `tests/web/test_api.py`:

```python
def test_generate_page_video_speed_bounds(tmp_path, monkeypatch):
    async def fake_voices():
        return [VoiceInfo("en-US-EmmaNeural", "en-US", "Female")]
    monkeypatch.setattr("roblox_viral.web.app.list_english_voices", fake_voices)
    c = _client(tmp_path, monkeypatch)
    _login(c)
    r = c.get("/")
    assert 'id="video_speed"' in r.text
    assert 'min="50"' in r.text
    assert 'max="200"' in r.text
    assert "data-single-min" in r.text or "VIDEO_SPEED_BOUNDS" in r.text
```

Prefer data attributes on `#video_speed` or `#generate-form` for JS:

```html
<input id="video_speed" ... min="50" max="200" value="100"
       data-single-min="50" data-single-max="200"
       data-reddit-min="100" data-reddit-max="500" />
```

Optional test: assert those data attributes exist.

- [ ] **Step 2: Implement `app.js` in `setMode`**

```javascript
  const VIDEO_BOUNDS = {
    single: { min: 50, max: 200 },
    reddit: { min: 100, max: 500 },
  };

  function clampVideoSpeedForMode(mode) {
    if (!videoSpeedInput || mode === "picture") return;
    const b = VIDEO_BOUNDS[mode === "reddit" ? "reddit" : "single"];
    videoSpeedInput.min = String(b.min);
    videoSpeedInput.max = String(b.max);
    const v = Number(videoSpeedInput.value);
    if (v < b.min) videoSpeedInput.value = String(b.min);
    if (v > b.max) videoSpeedInput.value = String(b.max);
    syncVoiceSliders();
  }
```

Call `clampVideoSpeedForMode(mode)` at end of `setMode(mode)`.

- [ ] **Step 3: README**

Under Reddit / Generate / n8n sections:
- Reddit backgrounds: **one library video per sentence**
- Reddit `video_speed` **100–500%**; Single **50–200%**

- [ ] **Step 4: Run suite**

Run: `pytest -q`

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/templates/generate.html src/roblox_viral/web/static/app.js tests/web/test_api.py README.md
git commit -m "feat(web): mode-specific video speed slider bounds"
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Per-sentence planner + loop short file | 1 |
| Bag pop per sentence, reshuffle | 1 |
| source = sentence × speed/100 | 1 |
| Reddit validate 100–500 | 2 |
| Single validate 50–200 | 2 |
| jobs wiring | 3 |
| Slider bounds Reddit/Single | 4 |
| README | 4 |
