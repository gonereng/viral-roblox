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

