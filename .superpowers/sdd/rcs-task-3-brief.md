### Task 3: Generate UI — Download title card link

**Files:**
- Modify: `src/roblox_viral/web/templates/generate.html`
- Modify: `src/roblox_viral/web/static/app.js`
- Modify: `tests/web/test_api.py` (or add generate-page smoke if a pattern exists)
- Modify: `README.md`

**Interfaces:**
- Consumes: job JSON `title_card_name` from Task 2
- Produces: `#download-card` visible only when that field is set

- [ ] **Step 1: Failing smoke** — if Generate page is already fetched in tests, add:

```python
def test_generate_page_has_hidden_title_card_download(tmp_path, monkeypatch):
    async def fake_voices():
        return [VoiceInfo("en-US-EmmaNeural", "en-US", "Female")]

    monkeypatch.setattr("roblox_viral.web.app.list_english_voices", fake_voices)
    c = _client(tmp_path, monkeypatch)
    _login(c)
    r = c.get("/")
    assert r.status_code == 200
    assert 'id="download-card"' in r.text
    assert "Download title card" in r.text
```

Place near other generate-page tests in `tests/web/test_api.py`. Use same `_seed` / voices pattern as `test_generate_page_lists_recent_outputs`.

- [ ] **Step 2: Run RED**

Run: `pytest tests/web/test_api.py::test_generate_page_has_hidden_title_card_download -v`

Expected: FAIL (missing `download-card`)

- [ ] **Step 3: Template**

In `generate.html` result section:

```html
  <section class="result" id="result" hidden>
    <video id="player" controls playsinline></video>
    <p>
      <a id="download" href="#" download>Download MP4</a>
      <a id="download-card" href="#" download hidden>Download title card</a>
    </p>
  </section>
```

- [ ] **Step 4: JS**

```javascript
  const downloadCard = document.getElementById("download-card");

  function showResult(outputName, titleCardName) {
    const url = `/media/outputs/${encodeURIComponent(outputName)}`;
    resultEl.hidden = false;
    player.src = url;
    download.href = url;
    download.download = outputName;
    if (downloadCard) {
      if (titleCardName) {
        const cardUrl = `/media/outputs/${encodeURIComponent(titleCardName)}`;
        downloadCard.hidden = false;
        downloadCard.href = cardUrl;
        downloadCard.download = titleCardName;
      } else {
        downloadCard.hidden = true;
        downloadCard.removeAttribute("href");
        downloadCard.removeAttribute("download");
      }
    }
    prependRecentOutput(outputName);
  }
```

Update poll `done` branch:

```javascript
      if (job.output_name) {
        showResult(job.output_name, job.title_card_name || null);
      }
```

- [ ] **Step 5: README** — one bullet under Generate/Reddit: title card is ~2× and downloadable from the result panel.

- [ ] **Step 6: GREEN + suite**

Run:

```bash
pytest tests/web/test_api.py::test_generate_page_has_hidden_title_card_download -v
pytest -q
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/roblox_viral/web/templates/generate.html src/roblox_viral/web/static/app.js tests/web/test_api.py README.md
git commit -m "feat(web): add Download title card link for Reddit jobs"
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| 2× fonts/avatar/padding; width 972 | 1 |
| Copy to `outputs/{stem}-card.png` | 2 |
| `title_card_name` on job + hydrate | 2 |
| `/media/outputs` image MIME | 2 |
| Generate `#download-card` Reddit-only via JSON | 3 |
| No Recent-list card links | (constraint) |
| Overlay geometry unchanged | (no render.py change) |
