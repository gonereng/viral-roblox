### Task 3: Generate page sliders

**Files:**
- Modify: `src/roblox_viral/web/templates/generate.html`
- Modify: `src/roblox_viral/web/static/app.js`
- Modify: `src/roblox_viral/web/static/app.css`

**Interfaces:**
- Consumes: API `pitch` / `speed` ints
- Produces: form controls with ids `pitch`, `speed`, labels `pitch-value`, `speed-value`

- [ ] **Step 1: Add HTML sliders after voice select**

In `generate.html`, after the Voice `</label>` and before the Generate button:

```html
    <label class="slider-field">
      Pitch <span id="pitch-value">+15%</span>
      <input id="pitch" name="pitch" type="range" min="-50" max="50" step="1" value="15" />
    </label>

    <label class="slider-field">
      Speed <span id="speed-value">130%</span>
      <input id="speed" name="speed" type="range" min="50" max="200" step="1" value="130" />
    </label>
```

- [ ] **Step 2: Wire JS labels + payload**

In `app.js`, near the top of the generate form setup (after getting `form`):

```javascript
  const pitchInput = document.getElementById("pitch");
  const speedInput = document.getElementById("speed");
  const pitchValue = document.getElementById("pitch-value");
  const speedValue = document.getElementById("speed-value");

  function formatPitchLabel(n) {
    const v = Number(n);
    return (v > 0 ? "+" : "") + v + "%";
  }
  function formatSpeedLabel(n) {
    return Number(n) + "%";
  }
  function syncVoiceSliders() {
    if (pitchValue) pitchValue.textContent = formatPitchLabel(pitchInput.value);
    if (speedValue) speedValue.textContent = formatSpeedLabel(speedInput.value);
  }
  if (pitchInput && speedInput) {
    pitchInput.addEventListener("input", syncVoiceSliders);
    speedInput.addEventListener("input", syncVoiceSliders);
    syncVoiceSliders();
  }
```

Update payload:

```javascript
    const payload = {
      source_name: document.getElementById("source_name").value,
      story: document.getElementById("story").value,
      voice: document.getElementById("voice").value,
      pitch: Number(document.getElementById("pitch").value),
      speed: Number(document.getElementById("speed").value),
    };
```

- [ ] **Step 3: Minimal CSS**

In `app.css`, add:

```css
.slider-field input[type="range"] {
  width: 100%;
  display: block;
  margin-top: 0.35rem;
}
.slider-field span {
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 4: Smoke-check related tests still pass**

Run: `pytest tests/web/test_api.py tests/web/test_jobs.py tests/test_voice.py -q`

Expected: PASS

Manual: rebuild Docker if used; open Generate; confirm defaults +15% / 130%; generate still works.

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/templates/generate.html src/roblox_viral/web/static/app.js src/roblox_viral/web/static/app.css
git commit -m "feat(web): pitch and speed sliders on Generate"
```

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Sliders + defaults + labels | Task 3 |
| Edge Hz / rate mapping | Task 1 |
| Jobs/API fields + validation | Task 2 |
| Captions follow TTS timings | Implicit (no caption changes) |
| Video not sped up | Implicit (no render changes) |
| CLI unchanged | Honored |
| Tests helpers/provider/API/job | Tasks 1–2 |

No placeholders. Types: `pitch: int`, `speed: int`, Edge strings via formatters.
