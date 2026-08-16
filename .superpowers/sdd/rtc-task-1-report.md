# Task 1 Report: Pillow dependency + avatar asset

**Branch:** `feat/reddit-title-card`  
**Date:** 2026-08-16  
**Status:** DONE

## Summary

Added `Pillow>=10.0.0` to `pyproject.toml` and created `src/roblox_viral/assets/reddit_avatar.png` (128×128 RGBA Snoo-like placeholder). Asset is included via existing `package-data` glob `assets/*`.

## Changes

| File | Action |
|------|--------|
| `pyproject.toml` | Added `Pillow>=10.0.0` dependency |
| `src/roblox_viral/assets/reddit_avatar.png` | Created 128×128 RGBA avatar (orange circle, white face, antenna) |

## Verification

```text
pip install -e ".[dev]" -q
python -c "from PIL import Image; print(Image.__version__)"
# 11.0.0

python -c "from PIL import Image; from pathlib import Path; p=Path('src/roblox_viral/assets/reddit_avatar.png'); im=Image.open(p); print(im.size, im.mode)"
# (128, 128) RGBA
```

## Commit

- `1930d8f` — `chore: add Pillow and reddit avatar asset`

## Notes

- Avatar is a programmatic placeholder suitable for title-card compositing; replace with branded asset later if desired.
- Resolvable at runtime as `Path(__file__).parent / "assets" / "reddit_avatar.png"` from package modules under `roblox_viral`.
