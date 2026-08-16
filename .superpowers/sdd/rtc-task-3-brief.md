### Task 3: `render_video` title-card overlay

**Files:**
- Modify: `src/roblox_viral/render.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- Consumes: PNG path + until seconds
- Produces: kwargs `title_card_path: Path | str | None = None`, `title_card_until_s: float | None = None`

Behavior:
- If `title_card_path` set, require file exists; require `title_card_until_s is not None` and `> 0`
- Add as extra `-i` after audio (Reddit never combines with greenscreen; if both provided, greenscreen first then title on top is OK, but jobs never pass both)
- For the common Reddit path (`overlay is None`, title set):

Build filter_complex:
1. scale/crop/(setpts) on `[0:v]` → `[base]`
2. `[base]ass=...[cap]`
3. `[cap][N:v]overlay=(W-w)/2:(H/2-h):enable='lte(t,{T:.3f})'[outv]` where N is title input index

Without title card, keep existing no-overlay `-vf` path and existing greenscreen path unchanged.

- [ ] **Step 1: Failing test**

```python
def test_render_video_title_card_overlay_enable(tmp_path, monkeypatch):
    # fake_run capture cmd
    card = _touch(tmp_path / "card.png")
    render_video(
        video_path=...,
        audio_path=...,
        ass_path=...,
        output_path=...,
        title_card_path=card,
        title_card_until_s=1.25,
        overlay_path=None,
    )
    # assert filter contains overlay=(W-w)/2:(H/2-h):enable='lte(t,1.250)'
    # assert str(card) in cmd as -i
```

Also assert existing greenscreen test still passes without title kwargs.

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat: overlay timed Reddit title card in render_video`

---

