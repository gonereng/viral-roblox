# Reddit Title Card Overlay — Design

**Date:** 2026-08-16  
**Status:** Approved (conversation)  
**Builds on:** [2026-08-15-generate-single-reddit-design.md](./2026-08-15-generate-single-reddit-design.md), [2026-08-06-greenscreen-overlay-design.md](./2026-08-06-greenscreen-overlay-design.md)

## Goal

On **Reddit** videos only, show a generated Reddit-style post card with the **first story sentence** as the title. The card sits in the upper half of the frame (bottom edge on the horizontal midline), stays until that sentence finishes in the narration, then disappears. Karaoke captions remain visible underneath. Do **not** show the greenscreen/subscribe overlay on Reddit for now.

## Product decisions

| Decision | Choice |
|----------|--------|
| Scope | Reddit mode only (UI + n8n `type=reddit` via same job path) |
| Card creation | **Pillow** — draw dark card; fixed username + packaged avatar + “3d” + ⋮ + wrapped title |
| Title text | `sentences[0]` (first non-empty story line) |
| Header chrome | Fixed fake (v1); not random |
| Placement | Horizontally centered; **bottom of card on y = OUTPUT_HEIGHT/2** (960 in 1080×1920) |
| Timing | Visible from `t=0` until first-sentence end (last word `end_ms` of that sentence) |
| Captions | **Both** — ASS karaoke continues; title card composites **above** captions |
| Greenscreen | **Off** for Reddit (`overlay_path=None`); Single unchanged |
| Username | Fixed string styled like the reference screenshot (e.g. a plausible Reddit username) |

## Architecture

```
run_job (mode=reddit)
  sentences = split_sentences(story)
  words = EdgeTTS...synthesize(...)
  T = first_sentence_end_s(sentences, words)   # ms→seconds
  render_reddit_card(sentences[0], jobs/{id}/reddit_card.png)
  build_reddit_background(...) → reddit_bg.mp4
  render_video(
    video_path=reddit_bg,
    ...,
    overlay_path=None,
    title_card_path=reddit_card.png,
    title_card_until_s=T,
  )
```

### First-sentence end time

Use existing caption partitioning:

- `partition_words_by_sentences(sentences, words)[0][-1].end_ms / 1000.0`
- If the first sentence has no words (edge case), fall back to a short default (e.g. 2.0s) or skip the card — prefer skip/error only if story empty (already guarded).

### Card image (`render_reddit_card`)

- New module e.g. `src/roblox_viral/reddit_card.py`
- Dependency: add **Pillow** to `pyproject.toml`
- Packaged asset: small circular avatar (derived from reference / Snoo-style PNG under `src/roblox_viral/assets/`)
- Layout: dark charcoal background (`~#1A1A1B`), white bold title, muted gray “3d”, white username, kebab menu
- Width ≈ **90% of frame** (~972px); height grows with wrapped title; padding consistent with reference
- Output: RGBA PNG with opaque card (no need for rounded corners in v1 unless easy)

### ffmpeg overlay in `render_video`

New optional kwargs:

- `title_card_path: Path | None = None`
- `title_card_until_s: float | None = None`

When set:

- Input the PNG as an extra `-i`
- After ASS on the base (and **without** greenscreen when Reddit), overlay:

```text
overlay=(W-w)/2:(H/2-h):enable='lte(t,{T})'
```

(`H/2-h` places the bottom of the card on the midline.)

Filter order when both captions and title card:

1. Scale/crop/(setpts) gameplay  
2. ASS captions  
3. Title card overlay (on top)

Greenscreen path: unchanged for Single; Reddit never passes `overlay_path`.

### Jobs

- Only `mode == "reddit"` generates the card and passes title-card kwargs.
- `single` / `picture` unchanged.

## Testing

- Unit: `first_sentence_end_s` from mocked word timings  
- Unit: `render_reddit_card` writes PNG; dimensions sensible; title present (optional pixel smoke)  
- Render: mocked ffmpeg cmd includes title overlay enable + midline expression; Reddit jobs pass `overlay_path=None`  
- Regression: Single still receives greenscreen overlay  

## Non-goals

- Random usernames / multiple avatars  
- Re-enabling subscribe overlay on Reddit  
- Title card on Single or Picture  
- Hiding karaoke while the card is visible  
- Editable card theme / fonts from UI  
- Perfect pixel-match to the reference screenshot (close visual match is enough)
