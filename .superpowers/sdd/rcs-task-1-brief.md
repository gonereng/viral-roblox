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

