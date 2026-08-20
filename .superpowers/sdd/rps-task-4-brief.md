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
