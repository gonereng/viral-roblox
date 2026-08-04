# YouTube Library Import — Design

**Date:** 2026-08-04  
**Status:** Approved (conversation)  
**Builds on:** [2026-07-29-roblox-viral-webapp-design.md](./2026-07-29-roblox-viral-webapp-design.md)

## Goal

On the Library page, paste a YouTube URL and a rename stem; the app downloads the video in the background, splits it into 1-minute slices (same rules as file upload), and lists them as sources. Progress is polled like Generate.

## Product decisions

- Approach: `yt-dlp` Python package + shared single-flight job manager with render jobs
- UI: background job with progress (not a blocking form wait)
- Concurrency: only one heavy job at a time — either a **render** or a **YouTube import** (not both, not two imports). Busy → HTTP 409
- Quality: best MP4 up to **1080p**
- Rename: required stem input; output files `{stem}-1.mp4`, `{stem}-2.mp4`, … (leftover under 1 minute discarded)
- Keep existing file upload unchanged
- Auth: same session login as Library
- Out of scope: playlists/channels, non-YouTube sites, quality picker UI, parallel imports

## Architecture

```
Browser (Library)
  → POST /api/library/youtube { url, name }
  → Shared JobManager (single-flight with render)
  → downloading (yt-dlp → jobs/{id}/download.mp4)
  → slicing (reuse slice_into_minute_parts)
  → sources/{stem}-N.mp4
  → GET /api/jobs/{id} poll until done|error
```

### Dependencies

- Add `yt-dlp` to project dependencies
- ffmpeg already in Docker image (mux/remux as needed by yt-dlp)

### Format

Prefer MP4 ≤1080p, e.g.:

`bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b[height<=1080]`

### Rename / stem validation

- Required non-empty stem after strip
- Safe characters aligned with library naming (`A-Za-z0-9._ -`); no path separators, no extension in the input
- Final slice names must satisfy existing `_SAFE_NAME` / `slice_part_name` rules

## Job model

Extend or generalize the existing job system so import and render share one `_active_id` lock.

### Import statuses

`queued` → `downloading` → `slicing` → `done` | `error`

### Render statuses (unchanged)

`queued` → `synthesizing` → `captioning` → `rendering` → `done` | `error`

### Persistence

Status under `media/jobs/{id}/status.json` (same pattern as render). Temp download under that job dir; delete after successful slice (and on failure cleanup best-effort).

Import job record fields (conceptual): `id`, `status`, `error`, `kind` (`youtube` | `render`), `url` (import), `name` (stem), `created_slices` (optional list on success), plus existing render fields where applicable — or separate record types with a common poll shape.

Poll response for import should include at least: `id`, `status`, `error`, and on success enough info to refresh the UI (e.g. `created_slices` or a message).

## UI

### Library page

- Existing upload form unchanged
- New form: YouTube URL, rename (stem), “Import from YouTube”
- Progress: status text + error (aria-live), poll ~1s
- On `done`: show success and refresh source list (reload page or re-fetch list)
- On `409` / busy: show clear “a job is already in progress” message

### Generate page

- Existing 409 handling remains; busy message may mention import or render generically (“A job is already in progress”)

## API

| Route | Behavior |
|-------|----------|
| `POST /api/library/youtube` | Auth required. JSON `{ "url": "...", "name": "stem" }`. Creates import job. Returns `{ "id", "status" }`. 400 invalid; 409 busy |
| `GET /api/jobs/{job_id}` | Auth required. Returns job record for render **or** import |

## Error handling

| Case | Behavior |
|------|----------|
| Not logged in | 401 |
| Empty/invalid URL or name | 400 |
| Busy (render or import active) | 409 |
| yt-dlp failure | job `error` with short message |
| Video &lt; 1 minute | job `error` (same rule as upload) |
| Slice/ffmpeg failure | job `error` |

## Testing

Mock yt-dlp (no real network in CI).

- Import API requires auth
- Invalid URL/name → 400
- Busy when another job active → 409
- Success: mocked downloaded file → slices named with given stem
- Job error path persists and returns error message

## Implementation sketch

- `pyproject.toml` / Docker: add `yt-dlp`
- `library.py` (or `youtube.py`): validate URL/stem; `download_youtube(url, dest) -> Path`
- `jobs.py`: shared busy lock; `create_youtube_import` + `run_youtube_job`
- `app.py`: `POST /api/library/youtube`; ensure `GET /api/jobs/{id}` works for imports
- `library.html` + small JS for poll/refresh
- Tests under `tests/web/`
