# Reddit Hook Cover PNG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop writing the 2× Reddit screenshot PNG; stamp the first story line (`phrase - phrase`) onto the packaged Snoo template and serve it via Generate download and `GET /api/v1/videos/{id}/cover`, without changing the in-video 1× overlay.

**Architecture:** New `hook_cover.py` (`split_hook`, `render_hook_cover`). Reddit `create` validates the hook. `run_job` still draws `render_reddit_card(scale=1.0)` for ffmpeg; cover PNG is the template + two text boxes. n8n cover route mirrors `/download` status codes.

**Tech Stack:** Python 3.10+, Pillow, FastAPI, pytest

## Global Constraints

- In-video Reddit card: `render_reddit_card(..., scale=1.0)` unchanged (timing, placement, art)
- Cover boxes: top `(200, 335)–(880, 520)`; bottom `(200, 1400)–(880, 1600)`; 16px inset
- Text: white, bold, center-aligned, wrap; shrink font until wrapped block fits box height
- Hook: first story line; **exactly one** `-`; both sides non-empty after trim; error `First line must be "phrase - phrase"`
- Cover file: `media/outputs/{stem}-card.png`; `JobRecord.title_card_name` that basename
- API: `GET /api/v1/videos/{id}/cover` — 401 / 404 / 409 / 422 / 200 `image/png` as spec
- Single/Picture: no hook check, no cover
- Spec: `docs/superpowers/specs/2026-08-18-reddit-hook-cover-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/assets/hook_card.png` | Packaged Snoo template |
| `src/roblox_viral/hook_cover.py` | `split_hook`, `render_hook_cover` |
| `tests/test_hook_cover.py` | Parse + draw tests |
| `src/roblox_viral/web/jobs.py` | Validate hook; write cover instead of 2× card |
| `tests/web/test_jobs.py` | Reddit create/run expectations |
| `src/roblox_viral/web/api_v1.py` | `/videos/{id}/cover` |
| `tests/web/test_api_v1.py` | Cover HTTP + reddit stories with a dash |
| `README.md` | Hook format + cover URL |

---

### Task 1: `split_hook` + `render_hook_cover` + template asset

**Files:**
- Create: `src/roblox_viral/assets/hook_card.png`
- Create: `src/roblox_viral/hook_cover.py`
- Create: `tests/test_hook_cover.py`

**Interfaces:**
- Consumes: `roblox_viral.reddit_card._font`, `roblox_viral.reddit_card._wrap_text`
- Produces:
  - `HOOK_ERROR = 'First line must be "phrase - phrase"'`
  - `BOX_TOP = (200, 335, 880, 520)`  # x1, y1, x2, y2
  - `BOX_BOTTOM = (200, 1400, 880, 1600)`
  - `BOX_INSET = 16`
  - `split_hook(line: str) -> tuple[str, str]` — raise `ValueError(HOOK_ERROR)` if not exactly one `-` with two non-empty trimmed sides
  - `default_template_path() -> Path` — `Path(__file__).resolve().parent / "assets" / "hook_card.png"`
  - `render_hook_cover(top: str, bottom: str, output_path: Path \| str, *, template_path: Path \| str \| None = None) -> Path`
  - Missing template → `FileNotFoundError` or `RuntimeError` with "template" in the message

- [ ] **Step 1: Copy the template asset**

Copy the attached Snoo art to `src/roblox_viral/assets/hook_card.png`. Source (Cursor workspace image):

`C:\Users\Roland\.cursor\projects\d-WorkSpace-viral-roblox\assets\c__Users_Roland_AppData_Roaming_Cursor_User_workspaceStorage_b0012328d70214772596edede1362835_images_Gemini_Generated_Image_7ovay57ovay57ova-8c137f28-13df-49f0-909f-4bbbb065b0c7.png`

PowerShell:

```powershell
Copy-Item -Force "C:\Users\Roland\.cursor\projects\d-WorkSpace-viral-roblox\assets\c__Users_Roland_AppData_Roaming_Cursor_User_workspaceStorage_b0012328d70214772596edede1362835_images_Gemini_Generated_Image_7ovay57ovay57ova-8c137f28-13df-49f0-909f-4bbbb065b0c7.png" "src/roblox_viral/assets/hook_card.png"
```

If that path is missing, search the repo/`assets` folder for the Gemini PNG and copy it. Confirm `src/roblox_viral/assets/hook_card.png` exists and is a PNG.

- [ ] **Step 2: Write failing tests**

Create `tests/test_hook_cover.py`:

```python
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from roblox_viral.hook_cover import (
    BOX_BOTTOM,
    BOX_TOP,
    HOOK_ERROR,
    render_hook_cover,
    split_hook,
)


def test_split_hook_valid():
    assert split_hook("I found a door - Then it slammed") == (
        "I found a door",
        "Then it slammed",
    )
    assert split_hook("  A  -  B  ") == ("A", "B")


@pytest.mark.parametrize(
    "line",
    [
        "No dash here",
        "too - many - dashes",
        " - only bottom",
        "only top - ",
        "-",
        "",
    ],
)
def test_split_hook_rejects_bad_lines(line):
    with pytest.raises(ValueError, match="phrase - phrase"):
        split_hook(line)


def _blank_template(path: Path) -> Path:
    img = Image.new("RGBA", (1080, 1920), (10, 10, 10, 255))
    draw = ImageDraw.Draw(img)
    for box in (BOX_TOP, BOX_BOTTOM):
        draw.rectangle(box, fill=(40, 40, 40, 255))
    img.save(path)
    return path


def _box_pixels(image: Image.Image, box: tuple[int, int, int, int]) -> list:
    x1, y1, x2, y2 = box
    crop = image.crop((x1, y1, x2, y2))
    return list(crop.getdata())


def test_render_hook_cover_paints_both_boxes(tmp_path):
    template = _blank_template(tmp_path / "tpl.png")
    out = tmp_path / "cover.png"
    render_hook_cover("Hello world", "Second phrase", out, template_path=template)
    assert out.is_file()
    with Image.open(template) as blank, Image.open(out) as painted:
        assert painted.size == (1080, 1920)
        assert _box_pixels(painted, BOX_TOP) != _box_pixels(blank, BOX_TOP)
        assert _box_pixels(painted, BOX_BOTTOM) != _box_pixels(blank, BOX_BOTTOM)


def test_render_hook_cover_missing_template_raises(tmp_path):
    with pytest.raises((FileNotFoundError, RuntimeError), match="[Tt]emplate"):
        render_hook_cover(
            "A",
            "B",
            tmp_path / "out.png",
            template_path=tmp_path / "missing.png",
        )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_hook_cover.py -v`

Expected: FAIL (`ModuleNotFoundError` / `hook_cover` not defined).

- [ ] **Step 4: Implement `hook_cover.py`**

Create `src/roblox_viral/hook_cover.py`:

```python
"""Stamp hook phrases onto the packaged Reddit cover template."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from roblox_viral.reddit_card import _font, _wrap_text

HOOK_ERROR = 'First line must be "phrase - phrase"'
BOX_TOP = (200, 335, 880, 520)
BOX_BOTTOM = (200, 1400, 880, 1600)
BOX_INSET = 16
_MAX_FONT = 56
_MIN_FONT = 16


def default_template_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "hook_card.png"


def split_hook(line: str) -> tuple[str, str]:
    text = line or ""
    if text.count("-") != 1:
        raise ValueError(HOOK_ERROR)
    left, right = text.split("-", 1)
    top, bottom = left.strip(), right.strip()
    if not top or not bottom:
        raise ValueError(HOOK_ERROR)
    return top, bottom


def _draw_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
) -> None:
    x1, y1, x2, y2 = box
    inner_w = (x2 - x1) - 2 * BOX_INSET
    inner_h = (y2 - y1) - 2 * BOX_INSET
    font = _font(_MIN_FONT, bold=True)
    lines = [text]
    spacing = 4
    line_h = _MIN_FONT
    for size in range(_MAX_FONT, _MIN_FONT - 1, -2):
        candidate = _font(size, bold=True)
        wrapped = _wrap_text(text, candidate, inner_w)
        bbox = candidate.getbbox("Ag")
        lh = bbox[3] - bbox[1]
        sp = max(4, size // 8)
        block_h = len(wrapped) * lh + max(0, len(wrapped) - 1) * sp
        if block_h <= inner_h:
            font = candidate
            lines = wrapped
            spacing = sp
            line_h = lh
            break
    block_h = len(lines) * line_h + max(0, len(lines) - 1) * spacing
    y = y1 + BOX_INSET + max(0, (inner_h - block_h) / 2)
    for line in lines:
        w = draw.textlength(line, font=font)
        x = x1 + BOX_INSET + max(0, (inner_w - w) / 2)
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h + spacing


def render_hook_cover(
    top: str,
    bottom: str,
    output_path: Path | str,
    *,
    template_path: Path | str | None = None,
) -> Path:
    template = Path(template_path) if template_path is not None else default_template_path()
    if not template.is_file():
        raise FileNotFoundError(f"Cover template not found: {template}")
    with Image.open(template) as src:
        image = src.convert("RGBA")
    draw = ImageDraw.Draw(image)
    _draw_box(draw, top, BOX_TOP)
    _draw_box(draw, bottom, BOX_BOTTOM)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="PNG")
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_hook_cover.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/roblox_viral/assets/hook_card.png src/roblox_viral/hook_cover.py tests/test_hook_cover.py
git commit -m "feat: stamp Reddit hook phrases onto cover template"
```

---

### Task 2: Reddit jobs use hook cover instead of 2× screenshot

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`

**Interfaces:**
- Consumes: `split_hook`, `render_hook_cover` from Task 1
- Produces: Reddit `create` calls `split_hook(sentences[0])`; `run_job` writes cover via `render_hook_cover` to `outputs/{stem}-card.png`; overlay still `render_reddit_card(..., scale=1.0)` only (no second call at scale 2.0)

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_jobs.py`:

```python
def test_create_reddit_rejects_hook_without_dash(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.videos_dir / "one.mp4").write_bytes(b"vid")
    mgr = JobManager()
    with pytest.raises(ValueError, match="phrase - phrase"):
        mgr.create(s, "", "Hello world.\nSecond.\n", "en-US-EmmaNeural", mode="reddit")
```

In `test_run_reddit_passes_title_card_and_no_greenscreen`:

- Change `story` to `"First sentence here - Second hook.\nSecond line.\n"`
- After fakes, add:

```python
    def fake_render_hook_cover(top, bottom, output_path, *, template_path=None):
        seen.setdefault("covers", []).append((top, bottom, Path(output_path)))
        Path(output_path).write_bytes(b"hook-png")

    monkeypatch.setattr(
        jobs_module, "render_hook_cover", fake_render_hook_cover, raising=False
    )
```

- Change assertions: `seen["cards"]` has **length 1**, scale `1.0`, title `"First sentence here - Second hook."`
- Assert `seen["covers"][0][0] == "First sentence here"`
- Assert `seen["covers"][0][1] == "Second hook."`
- Assert `str(seen["covers"][0][2]).endswith("-card.png")`
- Remove `assert seen["cards"][1][2] == 2.0`

In `test_run_reddit_copies_title_card_to_outputs`:

- Story: `"One line only here - Bottom phrase.\n"`
- Replace reliance on `fake_render_reddit_card` writing the **outputs** file. Keep overlay fake; add:

```python
    def fake_render_hook_cover(top, bottom, output_path, *, template_path=None):
        Path(output_path).write_bytes(b"hook-png")

    monkeypatch.setattr(
        jobs_module, "render_hook_cover", fake_render_hook_cover, raising=False
    )
```

- Assert `card_path.read_bytes() == b"hook-png"` (not `b"png-card"`)

Update **every** `mgr.create(..., mode="reddit")` story in this file so the first line has exactly one `-` (existing tests will 400 otherwise), e.g. `"Hello - world.\n"`, `"One line only - here.\n"`. Search `mode="reddit"` and fix each story.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/web/test_jobs.py -k reddit -v`

Expected: new reject test FAIL (create succeeds) and/or 2× card assertions still expecting two `render_reddit_card` calls.

- [ ] **Step 3: Wire jobs**

In `src/roblox_viral/web/jobs.py`:

1. Import:

```python
from roblox_viral.hook_cover import render_hook_cover, split_hook
```

2. In `create`, after `if not sentences: raise ValueError("Story is empty")`:

```python
        if mode == "reddit":
            split_hook(sentences[0])
```

3. Replace the block that calls `render_reddit_card` twice. Keep 1× overlay; write cover with `render_hook_cover`:

```python
            if record.mode == "reddit":
                title_card_until_s = first_sentence_end_s(sentences, words)
                title_card_path = job_dir / "reddit_card.png"
                render_reddit_card(sentences[0], title_card_path, scale=1.0)
                top, bottom = split_hook(sentences[0])
                title_card_download_name = f"{Path(output_name).stem}-card.png"
                settings.outputs_dir.mkdir(parents=True, exist_ok=True)
                render_hook_cover(
                    top,
                    bottom,
                    settings.outputs_dir / title_card_download_name,
                )
```

Do not call `render_reddit_card(..., scale=2.0)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/web/test_jobs.py tests/test_hook_cover.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/jobs.py tests/web/test_jobs.py
git commit -m "feat(web): Reddit jobs write hook cover instead of 2x screenshot"
```

---

### Task 3: Cover API + README + n8n reddit stories

**Files:**
- Modify: `src/roblox_viral/web/api_v1.py`
- Modify: `tests/web/test_api_v1.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `JobRecord.title_card_name`, `settings.outputs_dir`
- Produces: `GET /api/v1/videos/{video_id}/cover` with the same auth and status mapping as `/download`, but `media_type="image/png"`

- [ ] **Step 1: Write failing tests**

In `tests/web/test_api_v1.py`, change reddit create stories `"Hi.\n"` to `"Hi - there.\n"` in `test_create_reddit_with_story_voice_type`, `test_create_reddit_rejects_media`, `test_create_reddit_rejects_source_name`.

Append:

```python
def test_cover_requires_api_key(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/v1/videos/" + "a" * 32 + "/cover")
    assert r.status_code == 401


def test_cover_done_returns_png(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        rec.status = "done"
        rec.output_name = f"{job_id}.mp4"
        rec.title_card_name = f"{job_id}-card.png"
        settings.outputs_dir.mkdir(parents=True, exist_ok=True)
        (settings.outputs_dir / rec.output_name).write_bytes(b"mp4")
        (settings.outputs_dir / rec.title_card_name).write_bytes(b"png-bytes")
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    job_id = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Top - Bottom.\n",
            "type": "reddit",
        },
    ).json()["id"]
    r = c.get(f"/api/v1/videos/{job_id}/cover", headers=_headers())
    assert r.status_code == 200
    assert r.content == b"png-bytes"
    assert "image/png" in r.headers.get("content-type", "")


def test_cover_not_ready_409(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")
    monkeypatch.setattr(JobManager, "run_job", lambda *a, **k: None)
    mgr: JobManager = c.app.state.job_manager
    rec = mgr.create(
        settings, "", "Top - Bottom.\n", "en-US-EmmaNeural", mode="reddit"
    )
    with mgr._lock:
        mgr._active_id = None
    r = c.get(f"/api/v1/videos/{rec.id}/cover", headers=_headers())
    assert r.status_code == 409


def test_cover_error_422(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")
    mgr: JobManager = c.app.state.job_manager
    rec = mgr.create(
        settings, "", "Top - Bottom.\n", "en-US-EmmaNeural", mode="reddit"
    )
    rec.status = "error"
    rec.error = "boom"
    with mgr._lock:
        mgr._active_id = None
    r = c.get(f"/api/v1/videos/{rec.id}/cover", headers=_headers())
    assert r.status_code == 422


def test_cover_single_done_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        rec.status = "done"
        rec.output_name = f"{job_id}.mp4"
        (settings.outputs_dir / rec.output_name).write_bytes(b"mp4")
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    job_id = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
            "source_name": "clip.mp4",
        },
    ).json()["id"]
    r = c.get(f"/api/v1/videos/{job_id}/cover", headers=_headers())
    assert r.status_code == 404


def test_cover_unknown_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get(
        "/api/v1/videos/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/cover",
        headers=_headers(),
    )
    assert r.status_code == 404
```

Also add (web session API already returns 400 via `create`):

```python
def test_create_reddit_rejects_story_without_hook_dash(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "reddit",
        },
    )
    assert r.status_code == 400
    assert "phrase - phrase" in r.json()["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/web/test_api_v1.py -k "cover or reddit" -v`

Expected: cover routes 404; `"Hi.\n"` reddit creates fail 400 until stories are updated (update stories in Step 1 first so only missing `/cover` fails).

- [ ] **Step 3: Implement the route**

In `src/roblox_viral/web/api_v1.py`, after `download_video`:

```python
@router.get("/videos/{video_id}/cover")
def download_cover(
    video_id: str,
    request: Request,
    _: None = Depends(require_api_key),
) -> FileResponse:
    settings = request.app.state.settings
    mgr: JobManager = request.app.state.job_manager
    record = mgr.get(video_id, settings)
    if record is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if record.status == "error":
        raise HTTPException(
            status_code=422, detail=record.error or "Render failed"
        )
    if record.status != "done":
        raise HTTPException(status_code=409, detail="Video not ready")
    name = record.title_card_name
    if not name:
        raise HTTPException(status_code=404, detail="Cover not found")
    safe = Path(name).name
    if safe != name:
        raise HTTPException(status_code=400, detail="Invalid cover name")
    path = (settings.outputs_dir / safe).resolve()
    if not path.is_relative_to(settings.outputs_dir.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="Cover file missing")
    return FileResponse(path, media_type="image/png", filename=safe)
```

In `README.md`:

- Replace the Reddit paragraph that mentions the ~2× screenshot with:

```markdown
**Reddit** shows a title card with the first story line, centered until that sentence finishes in the narration. The in-video card is unchanged. After generate, **Download title card** is a cover PNG: the packaged Snoo template with the first story line split on a single `-` (`phrase - phrase`) drawn in the two boxes. n8n: `GET /api/v1/videos/{id}/cover`.
```

- After the download bullet in n8n API, add: then download the cover with `GET /api/v1/videos/{id}/cover` (Reddit only; 404 for other types).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/web/test_api_v1.py tests/web/test_jobs.py tests/test_hook_cover.py tests/test_reddit_card.py -v`

Expected: PASS. Then full suite: `python -m pytest -q`

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/api_v1.py tests/web/test_api_v1.py README.md
git commit -m "feat(web): n8n cover download endpoint for Reddit hook PNG"
```

---

## Self-review

**Spec coverage:** split_hook (T1), boxes/text/template (T1), no 2× screenshot (T2), title_card_name (T2), overlay 1× (T2), create 400 (T2/T3), GET cover codes (T3), README (T3), UI `#download-card` unchanged (no task — already exists). Generate HTML needs no change.

**Placeholders:** none.

**Types:** `split_hook(line: str) -> tuple[str, str]`; `render_hook_cover(top, bottom, output_path, *, template_path=None) -> Path`; cover route uses `title_card_name`.
