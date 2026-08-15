# Library Tabs, Raw Videos & Video Speed — Design

**Date:** 2026-08-15  
**Status:** Approved (conversation)  
**Builds on:** [2026-07-29-roblox-viral-webapp-design.md](./2026-07-29-roblox-viral-webapp-design.md), [2026-08-11-voice-pitch-speed-design.md](./2026-08-11-voice-pitch-speed-design.md), [2026-08-14-picture-generation-design.md](./2026-08-14-picture-generation-design.md), [2026-08-14-n8n-video-api-design.md](./2026-08-14-n8n-video-api-design.md), [2026-08-14-n8n-media-upload-design.md](./2026-08-14-n8n-media-upload-design.md)  
**Supersedes (partially):** image upload location in picture design (moves to Library); YouTube import ([2026-08-04-youtube-library-import-design.md](./2026-08-04-youtube-library-import-design.md)) is **removed**; voice design’s “no setpts on gameplay” is amended by a separate **video_speed** control (voice pitch/speed remain independent).

## Goal

1. Add a **video speed** slider on Generate (Roblox only) so gameplay playback rate can change independently of TTS voice speed.
2. Restructure **Library** into three tabs: 1‑minute slice uploads, as‑is video uploads, and as‑is image uploads.
3. Remove **YouTube** download/import from the product.
4. Align the **n8n API** with `video_speed` and raw-library `source_name` resolution.

Source gameplay audio is already discarded at mux (`-map 1:a:0`); no further mute work.

## Product decisions

### Video speed

- **Independent** of voice pitch/speed.
- **UI:** Range 50–200%, step 1, default **100%** (unchanged footage). Label shows current percent (same pattern as voice speed).
- **Scope:** Roblox mode only — **hide** the slider in Picture mode. Ken Burns pacing unchanged.
- **Render:** ffmpeg `setpts` on the gameplay video stream. Loop to TTS duration still applies. TTS remains the only audio track.
- **Overlay:** Greenscreen overlay stays ~3.5s wall-clock at the start; **not** scaled by `video_speed`.
- **Persistence:** Job record field; form default 100 on refresh (same as other sliders).

### Library tabs

| Tab | Behavior | Directory |
|-----|----------|-----------|
| **1‑minute clips** | Existing: upload ≥60s, slice into `stem-N.mp4`, discard original | `media/sources/` |
| **Videos** | Upload as-is; validate extension/size only; no slice; no minimum duration | `media/videos/` |
| **Images** | Upload/delete as-is (moved from Generate Picture tab) | `media/images/` |

- Each tab lists and deletes only its own assets.
- Create `media/videos/` via `ensure_dirs` / `Settings.videos_dir`.
- Existing `sources/` and `images/` content keeps working.

### Generate (minimal change; full page revamp later)

- **Roblox:** One source dropdown listing both slices and raw videos, with labels, e.g. `clip-1.mp4 (1m)` and `full.mp4 (video)`.
- **Picture:** Image dropdown only; **remove** upload/delete from Generate.
- Video speed slider under voice controls when Roblox is active.

### YouTube

- Remove UI, `POST /api/library/youtube`, `JobManager.create_youtube` / `run_youtube_job`, and related docs/scripts references as needed.
- Cookies / yt-dlp paths used only for YouTube may be cleaned up if unused elsewhere.

### n8n API

- Optional form field `video_speed` (50–200, default 100); empty → default; invalid → 400.
- `type=roblox` + `source_name`: resolve `media/sources/` first, then `media/videos/`; missing → 400.
- `type=leni`: still `media/images/` only.
- Ephemeral `media` upload unchanged (as-is, no slice).
- Voice `pitch` / `speed` unchanged.

## Architecture

```
Library page
  Tab 1m  → save_upload → slice → media/sources/
  Tab Videos → save_raw_video → media/videos/
  Tab Images → save_image → media/images/
  (YouTube removed)

Generate
  Roblox: pick labeled source (sources ∪ videos) + voice pitch/speed + video_speed
  Picture: pick image only + voice pitch/speed (+ Ken Burns)
       ↓
  POST /api/jobs { mode, source_name, story, voice, pitch, speed, video_speed?, ken_burns? }
       ↓
  JobManager.create(..., video_speed=100)
  resolve source: roblox → sources then videos; picture → images
       ↓
  TTS → ASS
       ↓
  render_video(..., video_speed=...)  # setpts when ≠ 100; overlay wall-clock
  render_still(...)                   # ignores video_speed
```

### Mapping helper

In `voice.py` or a small shared module (prefer next to existing speed helpers):

- `validate_video_speed(percent: int) -> int` — require int in 50…200; raise `ValueError` otherwise.
- Render maps percent `S` to setpts factor `100/S` (e.g. 200% → `setpts=0.5*PTS`, 50% → `setpts=2*PTS`). At 100%, skip setpts (current filter graph).

### Job / API (UI)

- `JobRecord.video_speed: int = 100`
- `CreateJobBody.video_speed` optional; default 100
- Out of range → HTTP 400
- `run_job` passes `video_speed` into `render_video` only for roblox mode

### Library helpers

- `list_videos`, `save_video` (as-is), `delete_video`, `resolve_video` under `videos_dir`
- Shared listing helper for Generate: combine `list_sources` + `list_videos` with a `kind` (`slice` | `video`) for labels
- Roblox job resolve: try sources, then videos (same name must not collide across folders in practice; if both exist, **sources wins**)

### Frontend

- `library.html` / `library.js`: three tabs; drop YouTube form
- `generate.html` / `app.js`: labeled source options; video speed slider; strip Picture upload UI
- Routes: image upload/delete remain available to Library (reuse existing `/api/images` or Library-prefixed aliases — prefer keep `/api/images` and call from Library JS)

## Storage

```
media/
  sources/   # 1-minute slices
  videos/    # raw uploads (new)
  images/    # stills (managed from Library)
  outputs/
  jobs/{id}/
```

## Testing

- Library: raw video save does not call slice; list/delete under `videos/`; image flows from Library; YouTube endpoint absent or 404; related unit tests updated/removed
- `validate_video_speed` / setpts factor: bounds and 100% passthrough
- Jobs API: accepts `video_speed`; out of range → 400; persisted on record
- Render: when `video_speed != 100`, filter graph includes expected setpts; overlay duration unchanged
- n8n: optional `video_speed`; `source_name` finds file in `videos/` when not in `sources/`
- Picture create ignores or omits `video_speed` (default 100 on record is fine)

## Non-goals

- Full Generate page redesign (labeled dropdown is temporary)
- Coupling voice speed and video speed
- Video speed affecting Picture / Ken Burns
- Volume control
- CLI flags for video speed or raw library
- Migrating existing files between `sources/` and `videos/`
- Changing the ≥60s rule for the 1‑minute slice tab
