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

