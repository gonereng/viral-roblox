# Generate Modes: Single, Picture, Reddit — Design

**Date:** 2026-08-15  
**Status:** Approved (conversation)  
**Builds on:** [2026-08-15-library-tabs-video-speed-design.md](./2026-08-15-library-tabs-video-speed-design.md), [2026-08-14-picture-generation-design.md](./2026-08-14-picture-generation-design.md), [2026-08-06-greenscreen-overlay-design.md](./2026-08-06-greenscreen-overlay-design.md), [2026-08-14-n8n-video-api-design.md](./2026-08-14-n8n-video-api-design.md)  
**Breaking:** Internal/UI mode `roblox` → `single`; n8n `type=roblox` rejected in favor of `type=single`. New `mode`/`type` `reddit`.

## Goal

Restructure Generate into three tabs:

1. **Single background video** — one 1‑minute Library slice, looped to TTS (former Roblox flow).
2. **Picture** — unchanged.
3. **Reddit** — auto-pick a random sequence of short Library videos (`media/videos/`), concatenated/trimmed to match spoken length; same voice/pitch/voice-speed/video-speed controls as Single.

Also: apply greenscreen overlay to **Single and Reddit**, at **2×** previous size, fitted inside the frame (not cropped off).

## Product decisions

### Tabs & sources

| UI tab | `mode` | Background source | Overlay | Video speed |
|--------|--------|-------------------|---------|-------------|
| Single background video | `single` | Dropdown: `media/sources/` only | Yes | Yes (50–200, default 100) |
| Picture | `picture` | Images + Ken Burns (unchanged) | No | Hidden |
| Reddit | `reddit` | No picker; auto pool from `media/videos/` | Yes | Yes |

- Shared: story, voice, pitch, voice speed; Generate story.
- Default tab: Single. Refresh resets to Single (no URL persistence).
- Disable Generate when the active mode has no usable media (no slices / no images / empty videos pool).

### Reddit clip assembly

- After TTS, target duration = narration length.
- Shuffle the videos pool; consume whole clips without reuse until the pool is exhausted, then reshuffle and continue.
- When the next whole clip would overshoot remaining time, **trim** that clip to the remainder.
- Build a temporary concat under `jobs/{id}/`, then run the normal vertical render (crop, ASS, `video_speed` setpts, TTS mux, overlay).
- Empty `media/videos/` → clear error at create or run (prefer create-time when listing is empty).

### Single background

- Same as former Roblox: `-stream_loop` one chosen slice to TTS duration.
- Resolve **sources only** (do not fall back to `media/videos/`).
- Dropdown labels no longer mix `(1m)` and `(video)` — slices only (optional `(1m)` label or plain name).

### Overlay (Single + Reddit)

- Duration: first **3.5s** wall-clock, centered (unchanged timing).
- Size: **2×** previous height target → scale overlay to **fit inside** 1080×1920 with aspect ratio preserved (`force_original_aspect_ratio=decrease` / equivalent), so nothing is clipped off the frame edges.
- Previous height was `OUTPUT_HEIGHT // 2`; new target box is full frame (max height 1920, max width 1080).
- Picture: still no overlay.

### Voice / speed

- Reddit copies Single: voice select, pitch, voice speed, video speed.
- Picture: pitch + voice speed only (video speed hidden), unchanged.

## Architecture

```
Generate
  single  → pick sources/ clip → TTS → render_video(slice, overlay, video_speed)
  picture → pick image → TTS → render_still(ken_burns)
  reddit  → TTS → plan_clips(videos/) → concat+trim temp → render_video(temp, overlay, video_speed)
```

### Clip planner (pure helper)

e.g. in `library.py` or `render.py`:

```text
plan_reddit_clips(paths: list[Path], target_seconds: float, *, rng) -> list[ClipSegment]
# ClipSegment: path, start_s=0, duration_s
# shuffle without replacement; reshuffle when empty; last segment trimmed
```

### Concat step

ffmpeg concat demuxer (or filter) writing `jobs/{id}/reddit_bg.mp4` (or similar), then existing `render_video(video_path=...)`.

### Job / API

- `JobRecord.mode`: `"single" | "picture" | "reddit"`
- Load compat: `mode == "roblox"` → treat as `"single"`
- `create`: for `reddit`, no `source_name` required; validate `list_videos` non-empty. For `single`, `resolve_source` only. For `picture`, `resolve_image`.
- `CreateJobBody.mode` defaults to `"single"`
- `run_job`: branch on mode; reddit builds concat then `render_video` with overlay

### Frontend

- Three tabs; rename Roblox → Single background video; add Reddit block (status text: uses Library Videos pool).
- `app.js`: `currentMode` ∈ `single|picture|reddit`; POST accordingly; hide video speed on picture; enable/disable Generate per tab inventory.
- `generate.html`: sources from `list_sources` only (not `list_roblox_sources`).

### n8n

| `type` | Behavior |
|--------|----------|
| `single` | Former `roblox` create (slice `source_name` or ephemeral `media`) |
| `reddit` | No background `source_name`/`media`; uses `media/videos/` |
| `leni` | Unchanged |
| `roblox` | **400** — detail tells client to use `single` |

Optional form fields pitch/speed/`video_speed` apply to `single` and `reddit` as today.

## Testing

- Planner unit tests: order/trim/reshuffle/empty
- Overlay filter uses fit-in-frame scale (assert in mocked ffmpeg cmd)
- Jobs: `single` resolves sources only; `reddit` requires videos; `roblox` mode string hydrates as single
- UI/API: accept `mode=single|reddit|picture`
- n8n: `type=single`, `type=reddit`, reject `type=roblox`
- Picture regression: no overlay, no video_speed required

## Non-goals

- User-selected Reddit pool / multi-select on Generate
- Video speed for Picture / Ken Burns
- CLI flags for reddit/single
- Auto-migrating external n8n workflows beyond the 400 message
- Changing Library tab structure
