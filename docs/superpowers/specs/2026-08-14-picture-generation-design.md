# Picture Storytime Generation — Design

**Date:** 2026-08-14  
**Status:** Approved (conversation)  
**Builds on:** [2026-07-29-roblox-viral-webapp-design.md](./2026-07-29-roblox-viral-webapp-design.md), [2026-08-11-voice-pitch-speed-design.md](./2026-08-11-voice-pitch-speed-design.md), [2026-08-06-greenscreen-overlay-design.md](./2026-08-06-greenscreen-overlay-design.md)

## Goal

Add a second Generate mode that builds the same 1080×1920 storytime video from a **still image** instead of a Roblox gameplay clip. Narration, karaoke captions, voice, pitch, and speed stay identical. Picture jobs never apply the greenscreen overlay.

## Product decisions

- **UI:** Generate page tabs **Roblox** | **Picture**. Tabs only swap the source block. Story, Generate story, voice, pitch, speed, progress, player, and recent outputs stay shared.
- **Default tab:** Roblox. Refresh resets to Roblox (no URL/hash persistence).
- **Image library:** Lives on the Picture tab (upload, pick, delete). The Library page stays video-only (upload, YouTube, 1-minute slices).
- **Formats:** `.jpg`, `.jpeg`, `.png`, `.webp`
- **Upload cap:** 20 MB
- **Frame fill:** Always cover-crop to 1080×1920 (scale up, center crop). No letterboxing.
- **Ken Burns:** Picture-only switch. **Off** (default) = static hold. **On** = slow zoom-in from the center over the full narration (1.0 → 1.20). No random pan, no zoom-out, no speed slider.
- **Overlay:** Roblox jobs unchanged. Picture jobs never pass `overlay_path`.
- **CLI:** unchanged (no `--image`)
- **Jobs:** One render at a time, either mode. Recent outputs remain one shared list.

## Architecture

```
Browser Generate
  Roblox tab → pick media/sources clip
  Picture tab → upload/pick/delete media/images + Ken Burns switch
       ↓
  POST /api/jobs
    { mode, source_name, story, voice, pitch, speed, ken_burns? }
       ↓
  JobManager (existing single-flight lock)
       ↓
  story → Edge TTS (pitch/speed) → ASS captions
       ↓
  mode=roblox  → render_video(..., overlay_path=settings.overlay_video_path)
  mode=picture → render_still(..., ken_burns=...)   # no overlay
       ↓
  media/outputs/{stem}-{YYYY-MM-DD_HHMMSS}.mp4
```

## Storage

```
media/
  sources/     # gameplay clips (unchanged)
  images/      # stills for Picture mode (new)
  outputs/     # finished MP4s (shared)
  jobs/{id}/   # status + temp narration/ASS (unchanged)
```

`Settings.images_dir` → `media_root / "images"`. `ensure_dirs` creates it.

Safe image names: `^[A-Za-z0-9._ -]+\.(jpg|jpeg|png|webp)$` (case-insensitive). Resolve must stay under `images_dir`.

## Image library

Helpers in `library.py`: `list_images`, `save_image`, `delete_image`, `resolve_image`. Mirror the video helpers: unique names on upload, no leftover temp files on failure.

Auth-required routes (fetch from the Picture tab so the story textarea is not wiped):

| Method | Path | Behavior |
|--------|------|----------|
| POST | `/api/images` | Multipart `file`; save under `media/images/`; return `{ name }` |
| DELETE | `/api/images/{name}` | Delete that file; 404 if missing |

Generate page SSR includes `images` next to `sources`. Upload returns `{ name }`; JS appends that option to the Picture `<select>`. Delete removes that option from the select. No extra list-images GET in v1.

## Generate UI

- Tab control on Generate; only the active source block is visible.
- Roblox: existing source `<select>`. Generate disabled when `sources` is empty.
- Picture: image `<select>` (same pattern as Roblox source), file upload, a Delete button for the selected image, and a **Ken Burns** checkbox (default unchecked). Generate disabled when `images` is empty; upload remains enabled.
- Shared: story textarea, Generate story, voice, pitch, speed, Generate, status, player, recent outputs.

`app.js` posts `mode` (`"roblox"` | `"picture"`) and, when Picture, `ken_burns` boolean.

## Jobs / API

`GenerateJobBody` gains:

- `mode: Literal["roblox", "picture"]` — default `"roblox"` if omitted (backward compatible)
- `ken_burns: bool = False` — meaningful only for picture

`JobRecord` stores `mode` and `ken_burns`. Keep `kind="render"` for both Generate modes (`kind="youtube"` stays import-only).

`JobManager.create`:

1. Validate pitch/speed (existing).
2. Split story; empty → `ValueError`.
3. If `mode == "roblox"`: `resolve_source`; ignore `ken_burns`.
4. If `mode == "picture"`: `resolve_image`.
5. Same single-flight lock as today.

Worker after captions:

- Roblox: `render_video(video_path=..., overlay_path=settings.overlay_video_path)`
- Picture: `render_still(image_path=..., ken_burns=record.ken_burns)` — do not pass overlay

Output name: existing `make_output_name(source_name)` using the image or clip stem.

HTTP:

- Unknown mode, missing source for that mode, empty story, bad pitch/speed → 400
- Active job → 409 Busy
- `ken_burns` on a Roblox job → stored/ignored, not an error

## Render stills

New `render_still` in `render.py` (do not overload `render_video` with an image path). Same output size, x264/AAC, ASS burn, TTS as sole audio, duration = TTS length.

**Static (ken_burns=False):**

```
ffmpeg -y -loop 1 -framerate 30 -i IMAGE -i AUDIO -t AUDIO_DURATION
  -vf scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,ass=...
  -map 0:v:0 -map 1:a:0 ...
```

**Ken Burns (ken_burns=True):**

Cover-scale the image so a 1.20× center zoom never reveals edges, then `zoompan` from zoom 1.0 to 1.20 over `round(audio_duration * 30)` frames at 30 fps, output `s=1080x1920`, centered (`x`/`y` = `iw/2-(iw/zoom/2)` and `ih/2-(ih/zoom/2)`). Then burn ASS and mux TTS. No chromakey, no third input.

`render_video` is unchanged.

## Error handling

- Invalid/missing image name → 400 (create) or 404 (delete)
- Non-image or >20 MB upload → 400; no partial file left in `media/images/`
- Path traversal on image names → reject
- ffmpeg/TTS failure → job `error` with a short message (existing pattern)
- Missing overlay file cannot affect picture jobs

## Testing

- Image helpers: save/list/delete/resolve; reject unsafe names, traversal, oversize; images absent from video `list_sources` and vice versa
- Jobs API: picture + image name succeeds; roblox + image name or picture + video name → 400; `ken_burns` stored for picture, ignored for roblox; busy lock blocks a second job of either mode
- `render_still` with mocked ffmpeg: command has `-loop 1`, no overlay input, `zoompan` only when Ken Burns is on, ASS + TTS mapped
- Existing `render_video` overlay tests stay green
- Generate HTML includes both tabs, Picture upload/delete + Ken Burns control; Roblox tab does not show those controls

## Docs

README: Picture tab on Generate; upload stills there (not Library); Ken Burns optional zoom-in; overlay remains Roblox-only.

## Non-goals

- CLI `--image`
- Ken Burns speed/amount slider, zoom-out, random pan
- Overlay on picture jobs
- Mixing images into the Library page or YouTube import
- Letterboxing / fit-inside
- Persisting the active tab across refresh
- Image editing (crop UI, filters)
