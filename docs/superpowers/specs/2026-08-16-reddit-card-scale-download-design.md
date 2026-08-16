# Reddit Title Card 2× + Download — Design

**Date:** 2026-08-16  
**Status:** Approved (conversation)  
**Builds on:** [2026-08-16-reddit-title-card-design.md](./2026-08-16-reddit-title-card-design.md)

## Goal

1. Scale the Reddit title card so **title and header (avatar, username, meta)** are roughly **2×** larger while staying proportional.
2. After a Reddit generate, offer a **Download title card** link next to **Download MP4** on the Generate result panel (Reddit only).

## Product decisions

### Card sizing

| Constant | Previous | New (~2×) |
|----------|----------|-----------|
| Title font | 34 | 68 |
| Username font | 19 | 38 |
| Meta (“3d”) | 18 | 36 |
| Avatar | 40 | 80 |
| Padding, header height, title gap/spacing, related offsets | as today | ~2× |

- **`CARD_WIDTH` stays 972** (~90% of 1080) so the card still fits the frame; larger type wraps more.
- ffmpeg overlay placement unchanged: centered horizontally, bottom on vertical midline, shown until first sentence ends.
- Greenscreen remains off for Reddit.

### Download

- Generate result panel only (not Recent outputs; not Generate dropdowns).
- Link label: **Download title card**; shown only when the finished job has a title card.
- Single / Picture: no card, link stays hidden.
- Serve the PNG via existing authenticated `/media/outputs/{name}` with correct image MIME.

## Architecture

### Render

Update `reddit_card.py` layout constants and font sizes to the table above. Keep wrapping, colors, username, and avatar asset behavior.

### Persist

On Reddit `run_job` success:

1. Generate card under the job dir (as today) for the video overlay.
2. Also write/copy to `media/outputs/{output_stem}-card.png` where `{output_stem}` matches the MP4 basename without `.mp4`.
3. Set `JobRecord.title_card_name` to that PNG filename; persist in `status.json`.

Non-Reddit jobs: `title_card_name` remains `null` / omitted.

### Serve

Extend `GET /media/outputs/{name}` to use `media_type_for_name` (or equivalent) so `.png` → `image/png` and `.mp4` → `video/mp4`. Keep basename + directory containment checks and `require_login`.

`list_outputs` already returns **`.mp4` only** — card PNGs do not appear in Recent outputs.

### API / UI

- Job status JSON includes `title_card_name` (string or null).
- `generate.html`: add `#download-card` next to `#download`; default `hidden`.
- `app.js` `showResult` / poll `done`: if `title_card_name` set, unhide and point `#download-card` at `/media/outputs/{name}` with `download` attribute; otherwise hide/clear.

## Error handling

- Missing card file on disk when name is set: media route 404 (same as missing MP4).
- Invalid output names: 400 as today.
- Unauthenticated: same login gate as other `/media/outputs` requests.

## Testing

- Card generation uses ~2× sizes (assert constants and/or taller card for a fixed short title vs prior baseline).
- Reddit job sets `title_card_name` and creates the PNG under `outputs/`.
- Job GET exposes `title_card_name` for Reddit done jobs; null/absent for other modes.
- Authenticated GET of the card PNG returns 200 and `image/png`.
- Optional: Generate HTML includes `#download-card` (hidden by default).

## Out of scope

- Title-card links in Recent outputs
- n8n API download field for the card
- Changing overlay geometry or first-sentence timing
- Re-adding greenscreen for Reddit

## Success criteria

- Reddit overlays show a proportionally larger title card (title + header).
- After a Reddit generate, users can download the title-card PNG from the result panel next to the MP4.
- Single/Picture flows unchanged aside from shared `/media/outputs` MIME handling.
