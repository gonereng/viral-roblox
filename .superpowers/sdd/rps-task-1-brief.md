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

