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

