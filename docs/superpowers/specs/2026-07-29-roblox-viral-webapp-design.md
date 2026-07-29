# Roblox Viral Web App — Design

**Date:** 2026-07-29  
**Status:** Approved (conversation)  
**Builds on:** [2026-07-27-roblox-viral-storytime-design.md](./2026-07-27-roblox-viral-storytime-design.md)

## Goal

Convert the existing CLI storytime generator into a password-protected Python web app. Single operator today; Docker-ready for later publish. Core UX: pick a preuploaded source video, paste a story, choose an English Edge TTS voice, generate with visible job progress, then play/download the result.

## Product decisions

- Solo user with simple password login (session cookie); `APP_PASSWORD` from env
- Background job + progress polling (not a blocking spinner-only page)
- Source videos managed in the web UI (upload / list / delete), stored on disk
- Voice dropdown: all English Edge TTS voices; default `en-US-EmmaNeural`
- Reuse existing pipeline: one sentence per line, one-word captions, mute + loop + 9:16 ffmpeg
- One render at a time
- Out of v1: multi-user accounts, Redis/Celery, cloud storage, TikTok upload, voice preview button, parallel jobs

## Architecture

```
Browser
  → Login (session)
  → Generate / Library pages
  → Job API (create + poll status)
  → In-process background worker
  → Existing voice / captions / render modules
  → media/sources, media/outputs, media/jobs
```

FastAPI web layer wraps the current `roblox_viral` pipeline. No rewrite of TTS/caption/ffmpeg logic.

## Pages

| Page | Access | Contents |
|------|--------|----------|
| Login | Public | Password form |
| Generate (home) | Auth | Source dropdown, story textarea, voice dropdown, Generate, progress, player + download, recent outputs |
| Library | Auth | Upload, list, delete source videos |
| Logout | Auth | Clear session |

### Generate progress states

`queued` → `synthesizing` → `captioning` → `rendering` → `done` | `error`

Client polls roughly once per second until terminal state.

### Story input

Same rules as CLI: one sentence per line in the textarea.

## Jobs

- Create job returns an id immediately; worker runs asynchronously
- Status persisted under `media/jobs/{id}/` (JSON sidecar + artifacts) so refresh can recover a finished job
- In-memory registry for active jobs; reject or queue if a render is already running (v1: single-flight — return busy error if one is in progress)
- On success: output MP4 under `media/outputs/`; UI can stream/play and download

## Auth

- Login page + signed session cookie
- `APP_PASSWORD` required to start in Docker/production
- `APP_SECRET` for cookie signing; in local dev may auto-generate ephemeral secret with a warning if unset
- Logout clears session
- All generate/library/job/media routes require auth

## Storage layout

```
media/
  sources/     # uploaded gameplay clips
  outputs/     # finished vertical MP4s
  jobs/{id}/   # status.json, temp narration/ASS, etc.
```

Optional `MEDIA_ROOT` env overrides the root path.

## Project layout

```
src/roblox_viral/           # existing CLI pipeline (kept)
src/roblox_viral/web/       # FastAPI app, templates, static
Dockerfile
docker-compose.yml
```

CLI entrypoint remains for local scripting.

## Docker

- Image includes Python deps + ffmpeg
- Compose publishes port 8000, sets `APP_PASSWORD` / `APP_SECRET`, mounts `./media:/app/media`
- Operator drops or uploads clips into the sources library after start

## Env

| Variable | Purpose |
|----------|---------|
| `APP_PASSWORD` | Login password |
| `APP_SECRET` | Session cookie signing key |
| `MEDIA_ROOT` | Optional media root (default `media/`) |

## Success criteria

- Log in with password; unauthenticated users cannot generate or access media
- Upload a source video; it appears in the Generate dropdown
- Submit story + voice; progress advances through states; finished video plays and downloads
- English voice list loads from Edge TTS; Emma is default
- `docker compose up` runs the app with ffmpeg available and a persistent media volume
