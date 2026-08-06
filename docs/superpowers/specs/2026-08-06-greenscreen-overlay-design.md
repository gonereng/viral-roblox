# Greenscreen Overlay on Generated Videos — Design

**Date:** 2026-08-06  
**Status:** Approved (conversation)  
**Builds on:** [2026-07-29-roblox-viral-webapp-design.md](./2026-07-29-roblox-viral-webapp-design.md)

## Goal

During each generated storytime render, optionally composite the first 3.5 seconds of a greenscreen clip (chromakey removed) centered over the gameplay/captions, muted, at roughly half frame height.

## Product decisions

- Timing: overlay appears at the **start** of the output (`t = 0` … `3.5s`)
- Duration: **3.5 seconds** of the overlay source (trim with ffmpeg `-t` / filter trim)
- Size: scale overlay so height ≈ **half of output height** (`1920 // 2` = 960px), keep aspect ratio; center horizontally and vertically
- Audio: overlay is **muted**; TTS remains the only audio track
- Layering: **overlay above burned ASS captions** (covers captions where they overlap)
- Presence: if overlay file is **missing**, render behaves exactly as today (no error)
- Failure: if overlay file is present but ffmpeg chromakey/overlay fails → `RenderError` with stderr snippet
- UI: **none** — file drop-in only
- Out of scope: per-job toggle, multiple overlays, end/mid timing UI, mixing overlay audio, pre-baking alpha assets

## Architecture

```
JobManager / CLI
  → Settings.overlay_video_path (None if file absent)
  → render_video(..., overlay_path=...)
       if overlay_path:
         filter_complex:
           [0:v] scale+crop → [base]
           [base] ass → [captioned]
           [2:t=3.5] chromakey + scale → [ov]
           [captioned][ov] overlay=center:enable='lte(t,3.5)' → [outv]
         map [outv] + TTS audio
       else:
         existing -vf scale+crop+ass
```

### Asset location

- Default path: `MEDIA_ROOT/overlay.mp4` (typically `media/overlay.mp4`)
- Optional env: `OVERLAY_VIDEO` — absolute or relative path; used when that file exists
- Starting content: user’s root `download.mp4` copied/moved to `media/overlay.mp4` during setup (media stays gitignored)
- Docker: existing `./media` volume is enough; optional compose passthrough of `OVERLAY_VIDEO` not required if default path is used

### Config

Extend `Settings`:

- `overlay_video: str` from `OVERLAY_VIDEO` (default `""`)
- Property `overlay_video_path: Path | None` — resolve env path if set and file exists; else `media_root / "overlay.mp4"` if that file exists; else `None`

### Render API

`render_video` gains optional `overlay_path: Path | None = None`.

When set:

1. Third ffmpeg input: overlay file (no stream loop)
2. Limit overlay input to 3.5s (e.g. `-t 3.5` before that `-i`, or `trim=duration=3.5` in the filter)
3. Chromakey: color near `0x00FE00` (clip corners sample ~`(0,254,0)`); moderate `similarity` / `blend` tuned so green is removed without eating the subject
4. Scale: `scale=-2:960` (or `OUTPUT_HEIGHT // 2`)
5. Format with alpha as needed for overlay (`format=yuva420p` after chromakey is typical)
6. `overlay=(W-w)/2:(H-h)/2:enable='lte(t,3.5)'` onto the captioned base
7. Do **not** map overlay audio

Constants live next to `OUTPUT_WIDTH` / `OUTPUT_HEIGHT` in `render.py` (duration, target height, chromakey params).

### Call sites

- Web job runner: pass `settings.overlay_video_path` into `render_video`
- CLI: resolve the same settings path (or pass through if already constructing Settings) so CLI and web match

## Testing

- Config: missing file → `None`; default `media/overlay.mp4` present → path; `OVERLAY_VIDEO` present → that path
- Render command construction (monkeypatch ffmpeg): with overlay → `filter_complex` / third input / chromakey / overlay enable; without → no third video input for overlay
- Optional light integration (skip without ffmpeg): tiny synthetic greenscreen + short gameplay + silent audio + minimal ASS → output file exists and duration ≈ audio duration

## Docs

README: one short note — place greenscreen MP4 at `media/overlay.mp4` (or set `OVERLAY_VIDEO`) to enable the intro overlay.

## Non-goals

- Library UI to upload/replace the overlay
- Adjustable duration/size/position in the Generate form
- Preprocessing pipeline to bake transparent ProRes/WebM
