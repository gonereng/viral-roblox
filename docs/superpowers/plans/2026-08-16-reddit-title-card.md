# Reddit Title Card Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On Reddit renders, generate a Pillow Reddit-style title card (first story line), overlay it above karaoke until that sentence ends, and disable the greenscreen subscribe clip for Reddit only.

**Architecture:** `first_sentence_end_s` from caption partitioning; `render_reddit_card` writes PNG; `render_video` gains optional `title_card_path` / `title_card_until_s` and composites after ASS; Reddit `run_job` wires card + `overlay_path=None`.

**Tech Stack:** Python 3.10+, Pillow, ffmpeg, FastAPI jobs (existing), pytest

## Global Constraints

- Reddit mode only; Single keeps greenscreen; Picture unchanged
- Title = `sentences[0]`; timing = last word `end_ms` of first sentence / 1000
- Placement: `overlay=(W-w)/2:(H/2-h):enable='lte(t,T)'` (bottom on midline)
- Captions stay on; card above ASS
- Fixed username + packaged avatar; Pillow dependency
- Spec: `docs/superpowers/specs/2026-08-16-reddit-title-card-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | Add `Pillow` |
| `src/roblox_viral/reddit_card.py` | Card PNG + `first_sentence_end_s` |
| `src/roblox_viral/assets/reddit_avatar.png` | Packaged avatar |
| `src/roblox_viral/render.py` | Title-card overlay kwargs |
| `src/roblox_viral/web/jobs.py` | Reddit wiring |
| `tests/test_reddit_card.py` | Timing + PNG tests |
| `tests/test_render.py` | ffmpeg filter assertions |
| `tests/web/test_jobs.py` | Reddit passes title card / no greenscreen |
| `README.md` | Brief mention |

---

### Task 1: Pillow dependency + avatar asset

**Files:**
- Modify: `pyproject.toml`
- Create: `src/roblox_viral/assets/reddit_avatar.png` (small circular-ready PNG; can be a simple generated placeholder if no artist asset — e.g. write a tiny PNG via a one-off script or ship a minimal Snoo-like circle)

**Interfaces:**
- Produces: `Pillow` in project dependencies; avatar path resolvable as `Path(__file__).parent / "assets" / "reddit_avatar.png"`
- `package-data` already includes `assets/*`

- [ ] **Step 1: Add dependency**

```toml
  "Pillow>=10.0.0",
```

- [ ] **Step 2: Create avatar PNG** under `src/roblox_viral/assets/reddit_avatar.png` (at least 128×128 RGBA). Acceptable: solid circle with simple face marks matching dark Reddit look.

- [ ] **Step 3: `pip install -e ".[dev]" -q` and verify import**

```bash
python -c "from PIL import Image; print(Image.__version__)"
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/roblox_viral/assets/reddit_avatar.png
git commit -m "chore: add Pillow and reddit avatar asset"
```

---

### Task 2: `first_sentence_end_s` + `render_reddit_card`

**Files:**
- Create: `src/roblox_viral/reddit_card.py`
- Create: `tests/test_reddit_card.py`

**Interfaces:**
- Produces:

```python
DEFAULT_REDDIT_USERNAME = "Resident_Vehicle2780"
CARD_WIDTH = 972  # ~90% of 1080
CARD_BG = (26, 26, 27, 255)  # #1A1A1B

def first_sentence_end_s(
    sentences: list[str],
    words: list[WordTiming],
    *,
    fallback_s: float = 2.0,
) -> float:
    """Return end time (seconds) of first sentence; fallback if no words."""

def render_reddit_card(
    title: str,
    output_path: Path | str,
    *,
    username: str = DEFAULT_REDDIT_USERNAME,
    avatar_path: Path | str | None = None,
) -> Path:
    """Write RGBA PNG; return path. Width CARD_WIDTH; height from content."""
```

`first_sentence_end_s` implementation:

```python
groups = partition_words_by_sentences(sentences, words)
if not groups or not groups[0]:
    return fallback_s
return groups[0][-1].end_ms / 1000.0
```

Card layout (Pillow):
- Load avatar (default packaged); resize to ~40px circle (mask)
- Header row: avatar | username (white) | "3d" (gray) | kebab menu right-aligned
- Title: bold white, wrap to card inner width, line spacing
- Padding ~24px; dark fill rectangle

- [ ] **Step 1: Failing tests**

```python
from roblox_viral.voice import WordTiming
from roblox_viral.reddit_card import first_sentence_end_s, render_reddit_card


def test_first_sentence_end_s():
    sentences = ["Hello world.", "Second line."]
    words = [
        WordTiming("Hello", 0, 200),
        WordTiming("world.", 200, 500),
        WordTiming("Second", 500, 800),
        WordTiming("line.", 800, 1000),
    ]
    assert abs(first_sentence_end_s(sentences, words) - 0.5) < 1e-6


def test_first_sentence_end_s_fallback_empty_words():
    assert first_sentence_end_s(["Hi."], []) == 2.0


def test_render_reddit_card_writes_png(tmp_path):
    out = tmp_path / "card.png"
    path = render_reddit_card("Company copied my code after refusing to pay.", out)
    assert path.is_file()
    from PIL import Image
    im = Image.open(path)
    assert im.size[0] == 972
    assert im.size[1] > 80
    assert im.mode in ("RGBA", "RGB")
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_reddit_card.py -v`

- [ ] **Step 3: Implement `reddit_card.py`**

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit** `feat: generate Reddit title card PNG with Pillow`

---

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

### Task 4: Wire Reddit `run_job`

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`

**Interfaces:**
- After TTS + ASS, when `mode == "reddit"`:
  - `T = first_sentence_end_s(sentences, words)`
  - `card_path = job_dir / "reddit_card.png"`; `render_reddit_card(sentences[0], card_path)`
  - After `build_reddit_background`, call `render_video(..., overlay_path=None, title_card_path=card_path, title_card_until_s=T, video_speed=...)`
- For `single` (and ephemeral non-picture): keep `overlay_path=settings.overlay_video_path`, no title card

- [ ] **Step 1: Failing tests**

```python
def test_run_reddit_passes_title_card_and_no_greenscreen(...):
    # monkeypatch TTS, write_ass, plan, build_reddit_background, render_video, render_reddit_card
    # assert render_video kwargs: overlay_path is None
    # title_card_path ends with reddit_card.png, title_card_until_s > 0


def test_run_single_still_uses_greenscreen(...):
    # assert overlay_path equals settings.overlay_video_path
    # title_card_path not passed / None
```

Update existing `test_run_reddit_builds_background_and_renders` expectations.

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat(web): attach Reddit title card and disable subscribe overlay`

---

### Task 5: README + full suite

**Files:**
- Modify: `README.md` — one short note under Generate/Reddit: title card with first line until sentence ends; no subscribe overlay yet

- [ ] **Step 1: Update README**

- [ ] **Step 2: `pytest -q` — all PASS**

- [ ] **Step 3: Commit** `docs: mention Reddit title card overlay`

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Pillow + avatar | 1 |
| Card PNG + first-sentence timing | 2 |
| ffmpeg title overlay | 3 |
| Reddit job wiring; no greenscreen | 4 |
| Docs | 5 |

## Consistency

- Overlay expression: `overlay=(W-w)/2:(H/2-h):enable='lte(t,{T:.3f})'`
- Card width 972; username fixed constant
- Reddit: `overlay_path=None` always when title card used
