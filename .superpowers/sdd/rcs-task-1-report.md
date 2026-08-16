# Task 1 Report: Scale Reddit card layout ~2×

**Branch:** `feat/reddit-card-scale-download`  
**Date:** 2026-08-16  
**Status:** DONE

## Summary

Scaled Reddit title-card Pillow layout ~2×: module constants, font sizes (38/36/68), and hard-coded header/menu offsets. Added `test_reddit_card_layout_constants_are_scaled` and tightened height assertion in `test_render_reddit_card_writes_png`.

## Changes

| File | Action |
|------|--------|
| `src/roblox_viral/reddit_card.py` | Doubled `_PADDING`, `_AVATAR_SIZE`, `_HEADER_HEIGHT`, `_TITLE_GAP`, `_BOTTOM_PADDING`, `_TITLE_SPACING`; fonts 38/36/68; header gaps 24/18/20; menu dots 2× |
| `tests/test_reddit_card.py` | Added layout constants test; PNG height threshold `> 160` |

## TDD

1. **RED:** `pytest tests/test_reddit_card.py -v` — 2 failed (`_AVATAR_SIZE` 40≠80, height 142≯160)
2. **GREEN:** same — 4 passed
3. **Full suite:** `pytest -v` — 169 passed

## Commit

- `f62a1e9` — `feat: scale Reddit title card layout ~2x`

## Self-review

- All brief constants match exactly; function signature unchanged.
- Colors, username default, and avatar path logic untouched.
- Menu dot geometry and header offsets scaled consistently (~2×).
- No unrelated files committed; dirty tree (jobs.py, sdd docs) left unstaged.
- Downstream tasks may need overlay/ffmpeg scaling if card pixel size affects video compositing.
