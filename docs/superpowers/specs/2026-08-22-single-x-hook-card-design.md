# Single Mode X Hook Card Overlay — Design

**Date:** 2026-08-22  
**Status:** Approved (conversation)  
**Builds on:** [2026-08-16-reddit-title-card-design.md](./2026-08-16-reddit-title-card-design.md), [2026-08-06-greenscreen-overlay-design.md](./2026-08-06-greenscreen-overlay-design.md)

## Goal

On **Single** (Roblox) videos only, show a generated dark-mode **X / Twitter-style post card** with the **first story sentence** as the body. The card sits in the upper half of the frame (same placement as the Reddit title card), stays until that sentence finishes in the narration, then disappears. Karaoke captions remain visible underneath. Do **not** show the greenscreen/subscribe overlay on Single while this card is used.

This is an **in-video hook overlay**, not a separate TikTok cover/thumbnail pipeline and not a downloadable PNG in v1.

## Product decisions

| Decision | Choice |
|----------|--------|
| Scope | Single mode only (UI + n8n `type=single` via same job path) |
| Card creation | **Pillow** — approximate X dark post UI (not pixel-perfect) |
| Body text | `sentences[0]` (first non-empty story line) |
| Display name | Fixed `jacques.guddebuer` + blue verified check |
| Handle | Fixed `@jacques.guddebuer` |
| Timestamp | Fixed fake (e.g. `22h`) |
| Avatar | Packaged circular crop of the user-provided Roblox avatar (`src/roblox_viral/assets/x_avatar.png`) |
| Engagement | Random **high** counts per render: replies ~1k–20k, reposts ~5k–80k, likes ~20k–500k, views ~100k–2M; format as `1.2K` / `95K` / `1.1M` |
| Footer icons | Simple reply / repost / like / views / bookmark / share glyphs |
| “Show more” | Blue truncated affordance when body is clipped to max lines |
| Placement | Horizontally centered; **bottom of card on y = OUTPUT_HEIGHT/2** (same as Reddit) |
| Timing | Visible from `t=0` until first-sentence end (`first_sentence_end_s`) |
| Captions | **Both** — ASS karaoke continues; card composites **above** captions |
| Greenscreen | **Off** for Single when X card is used (`overlay_path=None`) |
| Download / API cover | **Out of scope** for v1 |

## Architecture

```
run_job (mode=single)
  sentences = split_sentences(story)
  words = EdgeTTS...synthesize(...)
  T = first_sentence_end_s(sentences, words)
  render_x_card(sentences[0], jobs/{id}/x_card.png)
  render_video(
    ...,
    overlay_path=None,
    title_card_path=x_card.png,
    title_card_until_s=T,
  )
```

Reuse existing `render_video` kwargs `title_card_path` / `title_card_until_s` and the same ffmpeg overlay expression as Reddit. No new render filter path required.

### First-sentence end time

Reuse `first_sentence_end_s` from `reddit_card.py` (or a shared helper if extracted):

- `partition_words_by_sentences(sentences, words)[0][-1].end_ms / 1000.0`
- Fallback ~2.0s if the first sentence has no word timings

### Card image (`render_x_card`)

- New module: `src/roblox_viral/x_card.py`
- Packaged avatar: copy the provided Roblox avatar into `src/roblox_viral/assets/x_avatar.png` (ensure `package-data` includes `assets/*` as today)
- Layout (dark mode, inspired by the attached X template):
  - Black / near-black card background
  - Circular avatar, bold white display name, blue verified mark, gray handle + `·` + timestamp, kebab menu
  - Wrapped white body text (first sentence)
  - Engagement row with icons + formatted random counts
- Width ≈ **80–90% of frame** (align with Reddit card width conventions); height grows with wrapped text
- Output: opaque RGBA PNG
- Random engagement: seeded optionally for tests; production uses non-deterministic high ranges above

### Jobs

- `mode == "single"`: generate X card, pass `title_card_*`, set `overlay_path=None`
- `mode == "reddit"`: unchanged (Reddit card + no greenscreen)
- `mode == "picture"`: unchanged (no X card; existing still / Ken Burns path)

Ephemeral Single jobs from n8n (`type=single` with uploaded `media`) follow the same Single path.

## Error handling

| Case | Behavior |
|------|----------|
| Empty story | Existing job failure before card |
| Missing `x_avatar.png` | Clear error when rendering the card |
| First sentence has no timings | `first_sentence_end_s` fallback (~2s) |
| Card render failure | Job `error` status with message |

## Testing

- Unit: `render_x_card` writes PNG; includes display name / handle; engagement formatter covers K/M
- Unit: random engagement stays within documented ranges (or inject RNG for determinism)
- Jobs: Single `run_job` passes `title_card_path` ending in `x_card.png`, positive `title_card_until_s`, and `overlay_path=None`
- Regression: Reddit still uses `reddit_card.png`; Picture does not pass title-card kwargs
- Render: existing title-card overlay tests remain valid (no filter change expected)

## Non-goals / out of scope (v1)

- Downloadable PNG, Generate “Download title card”, Recent outputs card link for Single
- `GET /api/v1/videos/{id}/cover` or other TikTok cover/thumbnail generation
- Picture / `leni` / Reddit using the X card
- Keeping greenscreen alongside the X card
- Editable username, avatar upload, or theme from UI
- Pixel-perfect X branding / official icon SVGs
- Separate TikTok cover image distinct from this in-video overlay
