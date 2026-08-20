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

