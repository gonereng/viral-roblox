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

