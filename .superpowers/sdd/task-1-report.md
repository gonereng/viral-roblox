# Task 1 Report: `split_hook` + `render_hook_cover` + template asset

## Status: DONE

## Summary

Implemented Reddit hook cover stamping: `split_hook` parses `"phrase - phrase"` lines, `render_hook_cover` draws top/bottom text into fixed boxes on a template PNG, and the packaged Gemini Snoo asset was copied to `src/roblox_viral/assets/hook_card.png`.

## Files Created

| File | Purpose |
|------|---------|
| `src/roblox_viral/assets/hook_card.png` | Packaged cover template (104,942 bytes, PNG) |
| `src/roblox_viral/hook_cover.py` | `split_hook`, `render_hook_cover`, box constants |
| `tests/test_hook_cover.py` | Unit tests for parsing and rendering |

## TDD Evidence

### RED (Step 3)

```
python -m pytest tests/test_hook_cover.py -v
```

```
ERROR collecting tests/test_hook_cover.py
ModuleNotFoundError: No module named 'roblox_viral.hook_cover'
```

Expected failure: module not yet implemented.

### GREEN (Step 5)

```
python -m pytest tests/test_hook_cover.py -v
```

```
9 passed in 0.70s
```

All tests:
- `test_split_hook_valid` — trims and splits on single `-`
- `test_split_hook_rejects_bad_lines` (6 cases) — raises `ValueError` with `"phrase - phrase"`
- `test_render_hook_cover_paints_both_boxes` — text changes pixels in `BOX_TOP` and `BOX_BOTTOM`
- `test_render_hook_cover_missing_template_raises` — `FileNotFoundError` with "template"

### Full Suite (pre-commit)

```
python -m pytest -v
```

```
180 passed, 2 skipped in 9.88s
```

## Self-Review

- **Interfaces match brief verbatim:** `HOOK_ERROR`, `BOX_TOP`, `BOX_BOTTOM`, `BOX_INSET`, `split_hook`, `default_template_path`, `render_hook_cover`.
- **Dependencies:** Reuses `roblox_viral.reddit_card._font` and `_wrap_text` as specified.
- **Missing template:** Raises `FileNotFoundError(f"Cover template not found: {template}")` — message contains "template".
- **Asset:** Copied from Cursor workspace Gemini PNG; confirmed exists at `src/roblox_viral/assets/hook_card.png`.
- **Package data:** `pyproject.toml` already lists `assets/*` under `roblox_viral` package-data.
- **Minor note:** Test helper uses deprecated `Image.getdata()` (Pillow 14 warning only; from brief test code, not a regression).

## Commit

```
c042136 feat: stamp Reddit hook phrases onto cover template
```

Files committed: `hook_card.png`, `hook_cover.py`, `test_hook_cover.py` only (excluded `docs/` and `.superpowers/sdd/`).

## Review Fix: `_draw_box` min-font fallback

### What changed

In `_draw_box`, the fallback when no font size fits the box now initializes `lines` from `_wrap_text(text, _MIN_FONT font, inner_w)` instead of `[text]`. Spacing and line height also derive from the min-font metrics. Long hooks that overflow at every tried size still render as a wrapped min-font block (may clip vertically, but never collapse to one unwrapped line).

Added `test_render_hook_cover_wraps_long_text_at_min_font`: renders a 30-word hook, asserts min-font wrapping produces multiple lines, and checks painted white pixels span more than one text row in `BOX_TOP`.

### Commit

```
6ae9ca8 fix: wrap long hook text at min font fallback
```

### Tests

```
python -m pytest tests/test_hook_cover.py -v
```

```
10 passed in 0.57s
```

Covering test: `test_render_hook_cover_wraps_long_text_at_min_font`

## Re-Review Fix: shrink-to-fit and clip overflow

### What changed

`_draw_box` now shrinks font size from 56px down to 8px until the wrapped block fits `inner_h`, using per-line `textbbox` heights. If still too tall at 8px, excess wrapped lines are dropped from the bottom. Each line is drawn only when its bounding box fits fully inside the inset rectangle (no single unwrapped line fallback).

Replaced `test_render_hook_cover_wraps_long_text_at_min_font` with `test_render_hook_cover_long_text_stays_inside_inset`: 50-word hooks in both boxes must paint text inside the inset and leave margin strips at background color.

### Commit

```
1eec75f fix: shrink and clip hook text to box height
```

### Tests

```
python -m pytest tests/test_hook_cover.py -v
```

```
10 passed in 1.38s
```

Covering test: `test_render_hook_cover_long_text_stays_inside_inset`

## Re-Review Fix: scale-to-fit (no line dropping)

### What changed

Removed `_trim_lines_to_height` and per-line clipping. `_draw_box` now picks the largest font (56px→8px) whose wrapped block fits the inset; if none fit at 8px, the full wrapped phrase is rasterized onto a transparent layer and scaled down with LANCZOS to fit `inner_w × inner_h`, then pasted centered. All wrapped lines remain visible.

Updated `test_render_hook_cover_long_text_stays_inside_inset` to assert text stays inside inset margins and spans >20px vertically (multi-line block, not a single clipped line).

### Commit

```
ff4b037 fix: scale long hook text to fit without dropping lines
```

### Tests

```
python -m pytest tests/test_hook_cover.py -v
```

```
10 passed in 1.57s
```

Covering test: `test_render_hook_cover_long_text_stays_inside_inset`

## Re-Review Fix: font top offset in `_render_text_block`

### What changed

`_render_text_block` now draws each line at `y - bbox[1]` so glyphs with a positive font top offset are not clipped on the temporary layer. Layer height includes `top_pad = max(bbox[1])` before the alpha tight-crop.

### Commit

```
1c0aafa fix: account for font top offset in text block raster
```

### Tests

```
python -m pytest tests/test_hook_cover.py -v
```

```
10 passed in 1.48s
```
