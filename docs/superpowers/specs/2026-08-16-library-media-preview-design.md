# Library Media Preview — Design

**Date:** 2026-08-16  
**Status:** Approved (conversation)  
**Builds on:** [2026-08-15-library-tabs-video-speed-design.md](./2026-08-15-library-tabs-video-speed-design.md)

## Goal

Let users **preview** Library assets inline on all three tabs (1-minute clips, Videos, Images) without leaving the page or downloading files manually.

## Product decisions

- **Scope:** All Library tabs — `media/sources/`, `media/videos/`, `media/images/`.
- **Interaction:** Inline in each list row (under name/size), not a modal.
- **Video playback:** Native `<video controls playsinline preload="none">` — nothing buffered until play.
- **Images:** Inline `<img loading="lazy">` with the same compact max-height as videos.
- **Auth:** Same session login gate as `/media/outputs/{name}`.
- **No** poster/thumbnail generation, no “pause other players” logic, no Generate-page preview.

## Architecture

Add three login-gated GET routes beside the existing outputs route:

| Route | Resolve helper | Response |
|-------|----------------|----------|
| `GET /media/sources/{name}` | `resolve_source` | video `FileResponse` |
| `GET /media/videos/{name}` | `resolve_video` | video `FileResponse` |
| `GET /media/images/{name}` | `resolve_image` | image `FileResponse` |

Shared rules (match `/media/outputs/{name}`):

- Filename is basename-only (`Path(name).name == name`); otherwise 400.
- Resolved path must stay under the corresponding media directory; otherwise 400.
- Missing file → 404.
- Unauthenticated → same as other `require_login` routes.

Optional: a small internal helper to build `FileResponse` (media type by suffix) so the four media routes share boilerplate. Not required if three thin routes stay clear.

Video `media_type`: prefer `video/mp4` for `.mp4`; other extensions may use a simple suffix map or a generic video type. Image types: `image/jpeg`, `image/png`, `image/webp` by suffix.

Do **not** mount `StaticFiles` on media dirs (auth and path checks would be weaker).

## UI

`library.html` list items keep name, size, and delete. Add a preview block:

- Clips: `<video … src="/media/sources/{{ source.name }}">`
- Videos: `<video … src="/media/videos/{{ video.name }}">`
- Images: `<img … src="/media/images/{{ image.name }}" alt="{{ image.name }}">`

CSS (e.g. `.source-preview`): max-height ~240px, full width when wrapped, `object-fit: contain`. Preserve existing flex row + delete alignment.

No new JS for playback; `library.js` remains image upload/delete only.

## Error handling

| Condition | Response |
|-----------|----------|
| Bad / path-escape name | 400 |
| File not found | 404 |
| Not logged in | Existing auth behavior |

## Testing

- Each new media route: 200 with a real file under the correct dir; 404 when missing; 400 for `../`-style names.
- Unauthenticated access rejected (consistent with `/media/outputs`).
- Optional: library HTML includes `preload="none"` and the three `/media/…` URL prefixes for listed items.

## Out of scope

- ffmpeg poster frames / thumbnail cache
- Explicit HTTP Range tuning beyond Starlette/`FileResponse` defaults
- Preview in Generate source dropdown
- Changes to upload, slice, or delete flows

## Success criteria

- On Library, every listed clip, video, and image can be previewed inline after login.
- Video rows do not start downloading until the user hits play.
- Path traversal and cross-directory reads are rejected.
