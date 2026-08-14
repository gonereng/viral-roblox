# n8n Video API — Design

**Date:** 2026-08-14  
**Status:** Approved (conversation)  
**Builds on:** [2026-07-29-roblox-viral-webapp-design.md](./2026-07-29-roblox-viral-webapp-design.md), [2026-08-14-picture-generation-design.md](./2026-08-14-picture-generation-design.md)

## Goal

Expose a small API-key–authenticated HTTP API for n8n: create a render job from voice + story + type + media name, poll status by ID, and download the finished MP4. Reuse the existing `JobManager` pipeline (no duplicate render path).

## Product decisions

- **Type:** `roblox` | `leni`. `leni` is an alias for internal picture mode (`mode=picture`).
- **Create body (required):** `voice`, `story`, `type`, `source_name` (Library video name for roblox; image name for leni).
- **Create response:** `{ "id": "<job_id>" }` immediately; job runs in background (same as UI Generate).
- **Flow for n8n:** create → poll status (or retry download) → download MP4 when `done`.
- **Auth:** `X-API-Key` header compared to env `API_KEY` (constant-time). Web UI session login unchanged and not used on these routes.
- **Defaults:** pitch `15`, speed `130`, `ken_burns=false` (not exposed on this API in v1).
- **Busy:** single-flight lock unchanged → create returns **409** if a job is already running.
- **Out of scope:** webhooks, multiple API keys, pitch/speed/ken_burns on this API, sync/blocking create, cookie auth for n8n.

## API surface

| Method | Path | Auth | Success |
|--------|------|------|---------|
| `POST` | `/api/v1/videos` | `X-API-Key` | `200` `{ "id": "..." }` |
| `GET` | `/api/v1/videos/{id}` | same | `200` `{ id, status, error?, output_name?, ... }` (job poll shape) |
| `GET` | `/api/v1/videos/{id}/download` | same | `200` MP4 file download |

### Error codes

- **401** — missing/wrong API key  
- **503** — `API_KEY` not configured (v1 routes refuse to run open)  
- **400** — invalid body / unknown type / bad or missing `source_name` for the type  
- **409** — create while busy; **or** download while job still running  
- **404** — unknown job id  
- **422** — download when job `status=error` (include error detail)

### Create mapping

```
type=roblox  → JobManager.create(..., mode="roblox", source_name=..., ken_burns=False)
type=leni    → JobManager.create(..., mode="picture", source_name=..., ken_burns=False)
```

Voice/story/pitch/speed as existing create (defaults for pitch/speed).

## Architecture

```
n8n HTTP Request
  → require_api_key (X-API-Key vs Settings.api_key)
  → POST /api/v1/videos
       → validate type + resolve_source|resolve_image
       → mgr.create(...) + BackgroundTasks.add_task(mgr.run_job)
       → { id }
  → GET /api/v1/videos/{id}
       → mgr.get → JSON status
  → GET /api/v1/videos/{id}/download
       → if done: FileResponse(outputs/{output_name})
       → else 409 / 404 / 422 as above
```

### Config

- `Settings.api_key: str` from `API_KEY` (default `""`)
- docker-compose: `API_KEY: ${API_KEY:-}`
- README: document key + example n8n sequence

### Code layout

Prefer a small module (e.g. `web/api_v1.py` or routes registered from `app.py`) with:

- `require_api_key` dependency  
- Pydantic body for create  
- Three route handlers  

No changes to ffmpeg/render beyond calling existing job APIs.

## Testing

- API key: 401 / 503 / happy path with header  
- Create roblox + leni (mocked `run_job` or fast fake render as existing tests)  
- Bad type / wrong media kind → 400  
- Busy → 409  
- Status returns fields  
- Download: not ready 409; done returns file bytes; error 422; missing 404  

## Non-goals

- Public unauthenticated access  
- Replacing `/api/jobs` for the browser UI  
- n8n workflow JSON checked into the repo (README examples only)
