# Single Mode X Hook Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On Single (Roblox) renders, generate a Pillow dark X-style post card with the first story sentence, overlay it until that sentence ends, and disable the greenscreen subscribe clip for Single.

**Architecture:** Reuse `first_sentence_end_s` and existing `render_video` `title_card_path` / `title_card_until_s` overlay. New `x_card.py` draws the post; Single `run_job` writes `x_card.png` and passes `overlay_path=None`. No downloadable PNG / API cover in v1.

**Tech Stack:** Python 3.10+, Pillow (already in project), ffmpeg (existing), pytest

## Global Constraints

- Single mode only; Reddit keeps Reddit card; Picture unchanged
- Body = `sentences[0]`; timing = `first_sentence_end_s` (fallback ~2s)
- Placement: existing title-card overlay `(W-w)/2:(H/2-h)` until `T`
- Display name `jacques.guddebuer`, handle `@jacques.guddebuer`, packaged `x_avatar.png`
- Random high engagement each render (injectable RNG for tests)
- Greenscreen off for Single when X card is used (`overlay_path=None`)
- No downloadable card / no `/cover` endpoint in v1
- Spec: `docs/superpowers/specs/2026-08-22-single-x-hook-card-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/assets/x_avatar.png` | Packaged Roblox avatar (from user attachment) |
| `src/roblox_viral/x_card.py` | Engagement format/random + `render_x_card` |
| `src/roblox_viral/web/jobs.py` | Single: X card + no greenscreen |
| `tests/test_x_card.py` | PNG + engagement unit tests |
| `tests/web/test_jobs.py` | Replace greenscreen Single assertion with X-card wiring |
| `README.md` | One short Single/X-card note |

---

### Task 1: Avatar asset + `render_x_card`

**Files:**
- Create: `src/roblox_viral/assets/x_avatar.png`
- Create: `src/roblox_viral/x_card.py`
- Create: `tests/test_x_card.py`

**Interfaces:**
- Consumes: Pillow; avatar at `Path(__file__).parent / "assets" / "x_avatar.png"`
- Produces:

```python
DEFAULT_X_DISPLAY_NAME = "jacques.guddebuer"
DEFAULT_X_HANDLE = "@jacques.guddebuer"
CARD_WIDTH = 972  # ~90% of 1080

def format_engagement_count(n: int) -> str: ...
def random_engagement(*, rng: random.Random | None = None) -> dict[str, int]:
    # keys: replies, reposts, likes, views
    # ranges: replies 1_000–20_000, reposts 5_000–80_000,
    #         likes 20_000–500_000, views 100_000–2_000_000

def render_x_card(
    body: str,
    output_path: Path | str,
    *,
    display_name: str = DEFAULT_X_DISPLAY_NAME,
    handle: str = DEFAULT_X_HANDLE,
    avatar_path: Path | str | None = None,
    engagement: dict[str, int] | None = None,
    rng: random.Random | None = None,
) -> Path: ...
```

- [ ] **Step 1: Copy avatar into package assets**

Source (Cursor workspace attachment):

`C:\Users\Roland\.cursor\projects\c-Users-Roland-Projects-roblox-viral\assets\c__Users_Roland_AppData_Roaming_Cursor_User_workspaceStorage_465b1e8b915dfdf46dd0d078f4a9c47b_images_7667655322601407510_avatar.png-200cf8ff-e7f0-4efa-a5e5-52f26a53433b.png`

```powershell
Copy-Item -Force `
  "C:\Users\Roland\.cursor\projects\c-Users-Roland-Projects-roblox-viral\assets\c__Users_Roland_AppData_Roaming_Cursor_User_workspaceStorage_465b1e8b915dfdf46dd0d078f4a9c47b_images_7667655322601407510_avatar.png-200cf8ff-e7f0-4efa-a5e5-52f26a53433b.png" `
  "src\roblox_viral\assets\x_avatar.png"
```

Verify file exists and opens:

```bash
python -c "from pathlib import Path; from PIL import Image; p=Path('src/roblox_viral/assets/x_avatar.png'); print(p.exists(), Image.open(p).size)"
```

Expected: `True` and a positive `(w, h)`.

- [ ] **Step 2: Write failing tests** in `tests/test_x_card.py`

```python
from pathlib import Path
import random

from roblox_viral.x_card import (
    DEFAULT_X_DISPLAY_NAME,
    DEFAULT_X_HANDLE,
    format_engagement_count,
    random_engagement,
    render_x_card,
)


def test_format_engagement_count():
    assert format_engagement_count(37) == "37"
    assert format_engagement_count(866) == "866"
    assert format_engagement_count(3200) == "3.2K"
    assert format_engagement_count(95000) == "95K"
    assert format_engagement_count(1_100_000) == "1.1M"


def test_random_engagement_ranges():
    rng = random.Random(0)
    for _ in range(20):
        e = random_engagement(rng=rng)
        assert 1_000 <= e["replies"] <= 20_000
        assert 5_000 <= e["reposts"] <= 80_000
        assert 20_000 <= e["likes"] <= 500_000
        assert 100_000 <= e["views"] <= 2_000_000


def test_render_x_card_writes_png(tmp_path):
    out = tmp_path / "x_card.png"
    path = render_x_card(
        "Hook line that should appear on the card.",
        out,
        engagement={
            "replies": 1200,
            "reposts": 8600,
            "likes": 32000,
            "views": 950000,
        },
    )
    assert path == out
    assert out.is_file()
    assert out.stat().st_size > 1000
    from PIL import Image

    with Image.open(out) as im:
        assert im.size[0] >= 800
        assert im.size[1] > 100
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_x_card.py -v
```

Expected: FAIL (module / symbols missing).

- [ ] **Step 4: Implement `src/roblox_viral/x_card.py`**

Minimal behavior:

- `format_engagement_count`: `<1000` as int string; thousands as one-decimal `K` when needed (strip trailing `.0`); millions as `M` similarly (`3200` → `3.2K`, `95000` → `95K`, `1100000` → `1.1M`).
- `random_engagement`: use `rng or random.Random()`; `randint` in the documented inclusive ranges.
- `render_x_card`: dark card (`~#000000` / near-black), circular avatar via mask (same approach as `reddit_card._load_avatar`), bold white display name + blue check circle/✓, gray `handle · 22h`, kebab dots, wrapped white body (copy wrap helpers into this module), optional blue “Show more” if more than ~6 lines, footer row with simple icon placeholders (Unicode or small drawn shapes) + formatted counts. Width `CARD_WIDTH = 972`. Save opaque RGBA PNG. Raise clear error if avatar missing.

Do **not** add a download `scale=` path in v1.

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_x_card.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/roblox_viral/assets/x_avatar.png src/roblox_viral/x_card.py tests/test_x_card.py
git commit -m "feat: render Single-mode X-style hook card PNG"
```

---

### Task 2: Wire Single `run_job` (X card, no greenscreen)

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`
- Modify: `README.md` (short note under Generate / Single)

**Interfaces:**
- Consumes: `first_sentence_end_s` from `roblox_viral.reddit_card`; `render_x_card` from `roblox_viral.x_card`
- Produces: for `mode == "single"`, `title_card_path` = `jobs/{id}/x_card.png`, `title_card_until_s = first_sentence_end_s(...)`, `overlay_path=None`
- Does **not** set `title_card_name` / does not copy download PNG for Single

- [ ] **Step 1: Replace failing/outdated Single greenscreen test**

In `tests/web/test_jobs.py`, replace `test_run_single_still_uses_greenscreen` with:

```python
def test_run_single_passes_x_card_and_no_greenscreen(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    seen = {}

    def fake_synthesize(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [
            WordTiming("One", 0, 200),
            WordTiming("line", 200, 500),
        ]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_x_card(body, output_path, **kwargs):
        Path(output_path).write_bytes(b"png")
        return Path(output_path)

    def fake_render_video(**kwargs):
        seen["render"] = kwargs
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    def boom_reddit(*args, **kwargs):
        raise AssertionError("render_reddit_card should not run for single jobs")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)
    monkeypatch.setattr("roblox_viral.web.jobs.render_x_card", fake_render_x_card)
    monkeypatch.setattr(
        "roblox_viral.web.jobs.render_reddit_card", boom_reddit, raising=False
    )

    job = mgr.create(s, "clip.mp4", "One line only here.\n", "en-US-EmmaNeural")
    mgr.run_job(s, job.id)

    assert seen["render"]["overlay_path"] is None
    assert str(seen["render"]["title_card_path"]).endswith("x_card.png")
    assert seen["render"]["title_card_until_s"] == 0.5
    assert mgr.get(job.id, s).status == "done"
    assert mgr.get(job.id, s).title_card_name is None
```

Keep existing Reddit title-card tests unchanged (they must still pass).

- [ ] **Step 2: Run the new test to verify it fails**

```bash
pytest tests/web/test_jobs.py::test_run_single_passes_x_card_and_no_greenscreen -v
```

Expected: FAIL (still greenscreen / no `x_card`, or `render_x_card` not imported).

- [ ] **Step 3: Wire `jobs.py`**

Imports:

```python
from roblox_viral.x_card import render_x_card
```

(`first_sentence_end_s` / `render_reddit_card` already imported.)

After captioning, extend the title-card block:

```python
title_card_path: Path | None = None
title_card_until_s: float | None = None
title_card_download_name: str | None = None
if record.mode == "reddit":
    title_card_until_s = first_sentence_end_s(sentences, words)
    title_card_path = job_dir / "reddit_card.png"
    render_reddit_card(sentences[0], title_card_path, scale=1.0)
    title_card_download_name = f"{Path(output_name).stem}-card.png"
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    render_reddit_card(
        sentences[0],
        settings.outputs_dir / title_card_download_name,
        scale=2.0,
    )
elif record.mode == "single":
    title_card_until_s = first_sentence_end_s(sentences, words)
    title_card_path = job_dir / "x_card.png"
    render_x_card(sentences[0], title_card_path)
```

Change greenscreen selection:

```python
overlay_path = (
    None
    if record.mode in ("reddit", "single")
    else settings.overlay_video_path
)
```

Do not set `record.title_card_name` for Single.

- [ ] **Step 4: Run job tests**

```bash
pytest tests/web/test_jobs.py -v
```

Expected: PASS (including Reddit regressions and new Single X-card test).

- [ ] **Step 5: README**

Under Generate / Single (or equivalent), add one bullet:

- Single videos show an X-style hook card with the first story line until that sentence ends; the greenscreen subscribe overlay is not used on Single while this card is active.

- [ ] **Step 6: Full relevant suite**

```bash
pytest tests/test_x_card.py tests/web/test_jobs.py tests/test_render.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/roblox_viral/web/jobs.py tests/web/test_jobs.py README.md
git commit -m "feat(web): overlay X hook card on Single videos"
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Pillow X card module | 1 |
| Packaged `x_avatar.png` | 1 |
| Display name / handle / verified / engagement | 1 |
| First sentence body + timing via `first_sentence_end_s` | 2 |
| Single `title_card_*` + `overlay_path=None` | 2 |
| Reddit / Picture unchanged | 2 (regression tests) |
| No download / no `/cover` | 1–2 (explicit non-action) |
| README note | 2 |

## Self-review notes

- No placeholders left in steps.
- `test_run_single_still_uses_greenscreen` is intentionally replaced — Spec requires greenscreen off for Single with X card.
- Engagement ranges and formatter examples match the design table.
- Avatar copy path is the Cursor attachment saved with this brainstorm session.
