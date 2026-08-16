# Task 2 Report: Inline previews in Library UI + CSS + HTML smoke

## Status: DONE

## Summary

Embedded inline `<video preload="none">` previews for clips and Videos tabs, lazy `<img>` for Images tab, and `.source-preview` CSS (max-height 240px). TDD cycle completed; smoke and full suites green.

## TDD Evidence

### RED (Step 2)

```
pytest tests/web/test_library_routes.py::test_library_page_embeds_inline_previews -v
```

Result: **1 failed** — `assert 'preload="none"' in page.text` (previews not yet in template).

### GREEN (Step 5)

Same command → **1 passed** (1.24s)

Library suite: `pytest tests/web/test_library_routes.py -v` → **7 passed** (1.87s)

Full suite: `pytest -q` → **168 passed** (9.35s)

## Changes

### `src/roblox_viral/web/templates/library.html`

- Added `.source-preview` block after meta/delete row in each list item (slices, videos, images).
- Videos: `<video controls playsinline preload="none" src="/media/sources|videos/...">`.
- Images: `<img src="/media/images/..." alt="..." loading="lazy">`.

### `src/roblox_viral/web/static/app.css`

- Added `.source-preview` flex full-width wrap rule.
- Video/img: `max-height: 240px`, `object-fit: contain`, `background: var(--surface)` (no `--bg-elevated` in theme).

### `tests/web/test_library_routes.py`

- Added `test_library_page_embeds_inline_previews` verbatim from brief.

### `README.md`

- Added Library bullet: inline preview (video controls with no preload; lazy images).

## Commit

```
81b2941 feat(web): inline library video and image previews
```

Files committed (only task scope):

- `src/roblox_viral/web/templates/library.html`
- `src/roblox_viral/web/static/app.css`
- `tests/web/test_library_routes.py`
- `README.md`

## Self-Review

| Requirement | Met? | Notes |
|-------------|------|-------|
| Inline `<video preload="none">` on clips + Videos | Yes | Native controls, playsinline |
| Inline lazy `<img>` on Images | Yes | `loading="lazy"`, alt from name |
| CSS max-height ~240px | Yes | 240px in `.source-preview video, img` |
| No lightbox / no new playback JS | Yes | Template-only |
| Uses Task 1 media URLs | Yes | `/media/sources|videos|images/{name}` |
| Exact test code from brief | Yes | Copied verbatim |
| README bullet | Yes | Under Library section |
| Commit message from brief | Yes | Verbatim |

## Concerns

None. Previews sit on full-width row below name/meta/delete via existing `flex-wrap` on `.source-list li`. Hidden Images tab still renders preview markup in HTML (same as names); smoke test uses `?tab=images` for lazy img assertion.

## Verification Commands

```bash
pytest tests/web/test_library_routes.py::test_library_page_embeds_inline_previews -v
pytest tests/web/test_library_routes.py -v
pytest -q
```
