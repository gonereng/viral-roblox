# Reddit Hook Cover PNG — Design

**Date:** 2026-08-18  
**Status:** Approved (conversation)  
**Builds on:** [2026-08-16-reddit-title-card-design.md](./2026-08-16-reddit-title-card-design.md), [2026-08-16-reddit-card-scale-download-design.md](./2026-08-16-reddit-card-scale-download-design.md), [2026-08-14-n8n-video-api-design.md](./2026-08-14-n8n-video-api-design.md)

## Goal

Keep the **in-video** Reddit title card unchanged. Stop generating the 2× screenshot PNG for download. Instead, for each Reddit job, stamp the first story line (hook) onto a packaged Snoo template and offer that PNG via Generate **Download title card** and `GET /api/v1/videos/{id}/cover`.

## Product decisions

- **Scope:** Reddit only. Single / Picture unchanged.
- **In-video overlay:** still `render_reddit_card(..., scale=1.0)` until first-sentence end. Do **not** change placement, timing, or artwork.
- **Downloadable cover:** Pillow draw on packaged `hook_card.png`; **not** a 2× Reddit screenshot.
- **Hook source:** first story line (`sentences[0]`), split on `-`.
- **Split rule:** exactly **one** `-`. Trim both sides; both must be non-empty. Otherwise Reddit **create** returns 400.
- **Text:** white, bold, center-aligned, wrap to box width; start large and shrink until the wrapped block fits the box height. Font family same as in-video card (DejaVu/Arial).
- **Boxes** (template pixel coords, inclusive of the inner fill; ~16px inset when drawing):
  - Top: `(200, 335)`–`(880, 520)`
  - Bottom: `(200, 1400)`–`(880, 1600)`
- **UI:** existing `#download-card` / `title_card_name` / `/media/outputs/{name}`.
- **API:** `GET /api/v1/videos/{id}/cover` (API key), PNG download.
- **n8n create payload:** no new cover URL field (poll then GET cover).

## Architecture

```
Reddit create
  split_hook(sentences[0])  # 400 if invalid
       ↓
run_job
  TTS + ASS
  render_reddit_card(scale=1.0) → overlay on video   # unchanged
  render_hook_cover(top, bottom) → outputs/{stem}-card.png
  title_card_name = that filename
       ↓
Generate: Download title card → /media/outputs/{stem}-card.png
n8n: GET /api/v1/videos/{id}/cover
```

Stop the second `render_reddit_card(..., scale=2.0)` write.

## Hook parse

`split_hook(line: str) -> tuple[str, str]`:

- Count `-` in the line. Must be exactly 1.
- Split once; `top, bottom = parts[0].strip(), parts[1].strip()`.
- Either empty → `ValueError`.
- Message: `First line must be "phrase - phrase"`.

`JobManager.create` for `mode=reddit` calls this after story split. `run_job` calls it again before drawing.

## Cover render

New helpers (same module as the in-video card, or a sibling `hook_cover.py` if `reddit_card.py` would get cramped):

- Template path: `src/roblox_viral/assets/hook_card.png` (copy of the attached Snoo split-theme art; include in package data `assets/*`).
- Load template RGBA; draw top phrase in box 1, bottom in box 2; save PNG.
- Inset 16px inside each box. Horizontal and vertical center of the wrapped block.
- Missing template file → `RenderError` / runtime job `error`.

## Jobs

On Reddit success:

1. Overlay card in job dir at scale 1.0 (as today).
2. Write cover to `media/outputs/{output_stem}-card.png`.
3. Set `title_card_name` to that basename.

Do not write a 2× screenshot card.

## API

`GET /api/v1/videos/{video_id}/cover` — same `require_api_key` as download.

| Condition | Status |
|-----------|--------|
| Missing/invalid API key | 401 |
| Unknown id | 404 |
| Job `error` | 422 |
| Job exists but `status != done` | 409 |
| `done` but no `title_card_name` or file missing (Single/Picture, or Reddit draw failed) | 404 |
| Success | 200 `image/png`, `filename` = card basename |

## Error handling

- Invalid hook at create → 400, no job.
- Pillow/template failure during run → job `error`; no `title_card_name`.
- In-video card failure unchanged and independent.
- Cover route auth failure same as download (401).

## Testing

- `split_hook` unit cases (valid, no dash, two dashes, empty sides).
- `render_hook_cover` writes PNG; box regions differ from a blank template copy.
- Reddit job: `title_card_name` set; no 2× screenshot generation; overlay still scale 1.0.
- Create Reddit with bad first line → 400.
- Cover GET: 200/401/404/409/422 as above.
- `#download-card` still in Generate HTML.
- Single/Picture and in-video overlay tests unchanged.

## Docs

README: Reddit downloadable cover is the hook template (first line `phrase - phrase`), not a screenshot of the in-video card. Document `GET /api/v1/videos/{id}/cover`.

## Non-goals

- Changing the in-video Reddit card
- Cover PNG for Single/Picture
- Cover URL on create-job JSON
- Editable box coordinates / fonts in the UI
- Perfect pixel-match to a mockup (wrap + center is enough)
