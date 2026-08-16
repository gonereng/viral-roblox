# Reddit Title Card 2× + Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scale the Reddit title card ~2× (title + header) and expose a Generate-page “Download title card” link for Reddit jobs only.

**Architecture:** Update `reddit_card.py` layout constants; on Reddit success copy the PNG to `media/outputs/{output_stem}-card.png`, persist `JobRecord.title_card_name`, serve via `/media/outputs` with correct MIME; wire `#download-card` in Generate UI from job JSON.

**Tech Stack:** Pillow, FastAPI/`FileResponse`, Jinja2, vanilla JS, pytest

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-16-reddit-card-scale-download-design.md`
- Fonts/avatar/padding ~2×; `CARD_WIDTH` stays **972**
- Title 68, username 38, meta 36, avatar 80
- Download link on Generate result panel only; Reddit only; hide for Single/Picture
- Card file name: `{Path(output_name).stem}-card.png` under `outputs/`
- Recent outputs stay `.mp4`-only (already true)
- Overlay geometry / timing unchanged; no greenscreen for Reddit

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/reddit_card.py` | 2× layout constants |
| `tests/test_reddit_card.py` | Assert new sizes / taller card |
| `src/roblox_viral/web/jobs.py` | `title_card_name`; copy PNG to outputs |
| `src/roblox_viral/web/app.py` | `/media/outputs` MIME via `media_type_for_name` |
| `tests/web/test_jobs.py` | Reddit sets `title_card_name` + writes outputs PNG |
| `tests/web/test_api.py` | Serve PNG; job JSON field |
| `src/roblox_viral/web/templates/generate.html` | `#download-card` |
| `src/roblox_viral/web/static/app.js` | Show/hide card download on done |
| `README.md` | One-line note (fold into UI task) |

---

### Task 1: Scale Reddit card layout ~2×

**Files:**
- Modify: `src/roblox_viral/reddit_card.py`
- Modify: `tests/test_reddit_card.py`

**Interfaces:**
- Consumes: existing `render_reddit_card(title, output_path, ...)`
- Produces: updated module constants (exact values below); same function signature

- [ ] **Step 1: Write failing assertions** in `tests/test_reddit_card.py`

Extend `test_render_reddit_card_writes_png` (or add `test_render_reddit_card_scaled_layout`):

```python
from roblox_viral import reddit_card as rc

def test_reddit_card_layout_constants_are_scaled():
    assert rc.CARD_WIDTH == 972
    assert rc._AVATAR_SIZE == 80
    assert rc._PADDING == 48
    assert rc._HEADER_HEIGHT == 80
    assert rc._TITLE_GAP == 36
    assert rc._BOTTOM_PADDING == 56
    assert rc._TITLE_SPACING == 16


def test_render_reddit_card_writes_png(tmp_path):
    out = tmp_path / "card.png"
    path = render_reddit_card("Company copied my code after refusing to pay.", out)
    assert path.is_file()
    with Image.open(path) as image:
        assert image.size[0] == 972
        assert image.size[1] > 160  # taller than old ~80+ header
        assert image.mode in ("RGBA", "RGB")
```

Also update font sizes inside `render_reddit_card` (tested indirectly via height; constants test covers spacing).

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/test_reddit_card.py -v`

Expected: FAIL on `_AVATAR_SIZE == 80` (still 40) and/or height `> 160`

- [ ] **Step 3: Update `reddit_card.py` constants and fonts**

```python
CARD_WIDTH = 972
CARD_BG = (26, 26, 27, 255)

_PADDING = 48
_AVATAR_SIZE = 80
_HEADER_HEIGHT = 80
_TITLE_GAP = 36
_BOTTOM_PADDING = 56
_TITLE_SPACING = 16
```

In `render_reddit_card`:

```python
username_font = _font(38, bold=True)
meta_font = _font(36)
title_font = _font(68, bold=True)
```

Scale related offsets that were hard-coded (e.g. `header_x` gap `12` → `24`, `header_y` `_PADDING + 9` → `_PADDING + 18`, meta x gap `10` → `20`, menu dot geometry roughly 2× if it looks tiny). Keep colors and username string.

- [ ] **Step 4: Run tests GREEN**

Run: `pytest tests/test_reddit_card.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/reddit_card.py tests/test_reddit_card.py
git commit -m "feat: scale Reddit title card layout ~2x"
```

---

### Task 2: Persist `title_card_name` + serve PNG from `/media/outputs`

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `src/roblox_viral/web/app.py`
- Modify: `tests/web/test_jobs.py`
- Modify: `tests/web/test_api.py`

**Interfaces:**
- Consumes: `render_reddit_card`, `make_output_name`, `media_type_for_name` (already in `library.py`)
- Produces:

```python
# JobRecord field
title_card_name: str | None = None

# On Reddit success, after output_name is known:
# title_card_name = f"{Path(output_name).stem}-card.png"
# shutil.copy2(job_dir / "reddit_card.png", settings.outputs_dir / title_card_name)
# OR render_reddit_card(..., outputs_path) then copy to job_dir — prefer:
#   render once to job_dir for overlay; copy bytes/file to outputs
```

`GET /api/jobs/{id}` already returns `asdict(record)` — new field appears automatically once on the dataclass + hydrate path.

- [ ] **Step 1: Write failing tests**

In `tests/web/test_jobs.py`, extend Reddit run test(s) (prefer updating `test_run_reddit_builds_background_and_renders` or add focused test):

```python
def test_run_reddit_copies_title_card_to_outputs(tmp_path, monkeypatch):
    # same fakes as existing reddit run test; ensure fake render_reddit_card writes PNG
    # after mgr.run_job:
    assert job.title_card_name is not None
    assert job.title_card_name.endswith("-card.png")
    card_path = s.outputs_dir / job.title_card_name
    assert card_path.is_file()
    # cold hydrate
    loaded = JobManager().get(job.id, s)
    assert loaded is not None
    assert loaded.title_card_name == job.title_card_name
```

Ensure `fake_render_reddit_card` (or the real one if already patched elsewhere) writes a file when the job path calls `render_reddit_card`. Existing title-card test already patches `render_reddit_card` — reuse that pattern and also assert copy to outputs happens in `run_job` (implementation copies after render).

In `tests/web/test_api.py`:

```python
def test_media_output_serves_png(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    settings = c.app.state.settings
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    (settings.outputs_dir / "story-card.png").write_bytes(b"png-bytes")
    r = c.get("/media/outputs/story-card.png")
    assert r.status_code == 200
    assert r.content == b"png-bytes"
    assert "image/png" in r.headers.get("content-type", "")
```

- [ ] **Step 2: Run RED**

Run:

```bash
pytest tests/web/test_jobs.py::test_run_reddit_copies_title_card_to_outputs \
       tests/web/test_api.py::test_media_output_serves_png -v
```

Expected: FAIL (`title_card_name` missing / Content-Type still video/mp4)

- [ ] **Step 3: Implement**

`JobRecord` — add `title_card_name: str | None = None`.

`create(...)` — leave default `None`.

`get` hydrate — add:

```python
title_card_name=data.get("title_card_name"),
```

In `run_job` Reddit block, after `render_reddit_card(...)` and once `output_name` is known (same place `record.output_name = output_name` is set is fine; do copy before or with that assignment):

```python
import shutil
# ...
card_out_name = f"{Path(output_name).stem}-card.png"
settings.outputs_dir.mkdir(parents=True, exist_ok=True)
shutil.copy2(title_card_path, settings.outputs_dir / card_out_name)
record.title_card_name = card_out_name
```

Only when `record.mode == "reddit"` and `title_card_path` was written. Non-Reddit: leave `None`.

`app.py` `media_output`:

```python
from roblox_viral.web.library import media_type_for_name  # if not already

return FileResponse(
    path,
    media_type=media_type_for_name(safe),
    filename=safe,
)
```

- [ ] **Step 4: Run GREEN**

Run same pytest command + `pytest tests/web/test_api.py::test_media_output_requires_auth_and_serves_file -v`

Expected: PASS (MP4 still works)

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/jobs.py src/roblox_viral/web/app.py tests/web/test_jobs.py tests/web/test_api.py
git commit -m "feat(web): persist and serve Reddit title card PNG downloads"
```

---

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
