# n8n Multipart Media Upload — Design

**Date:** 2026-08-14  
**Status:** Approved (conversation)  
**Builds on:** [2026-08-14-n8n-video-api-design.md](./2026-08-14-n8n-video-api-design.md)

## Goal

Let n8n supply the gameplay video or still image on create via multipart upload, while still allowing Library `source_name`. Uploaded roblox videos are used as-is for that job (no 1-minute Library slicing).

## Product decisions

- `POST /api/v1/videos` accepts **multipart/form-data** only (breaking change from JSON body).
- Fields: `voice`, `story`, `type` (`roblox`|`leni`), plus exactly one of:
  - `media` — uploaded file
  - `source_name` — existing Library clip/image name
- Neither or both → **400**
- **roblox + media:** save job-local video; render uses it as-is (loop/crop to narration); do **not** slice into Library parts
- **leni + media:** save job-local image; picture pipeline (`mode=picture`); no overlay
- Size/type limits: reuse `MAX_UPLOAD_BYTES` / video name rules for roblox; `MAX_IMAGE_UPLOAD_BYTES` / image rules for leni
- Wrong media kind for `type` → **400**
- Status + download + API key auth unchanged
- Out of scope: URL/base64 media, keeping JSON create, multi-file uploads, Ken Burns / pitch / speed on this form

## Architecture

```
POST /api/v1/videos (multipart)
  → require_api_key
  → validate type + XOR(media, source_name)
  → if source_name: JobManager.create(...) as today
  → if media:
       allocate job id / create job dir early OR create then write input
       write jobs/{id}/input.<ext>
       JobManager.create/run with ephemeral input path
```

### Job-local input

Preferred mechanism:

1. Create job record (needs a resolvable source for validation today) — extend create so that when `ephemeral_input` is provided:
   - Skip Library `resolve_source` / `resolve_image`
   - Store `source_name` as something like `input.mp4` / `input.jpg` for display
   - Persist flag or convention: `run_job` looks for `jobs/{id}/input.*` first and uses that path for `render_video` / `render_still`

Concrete convention:

- Uploaded file always stored as `settings.jobs_dir / job_id / ("input" + safe_suffix)`
- Allowed suffixes: roblox `.mp4`/`.mov`/`.webm`/`.mkv` (align with existing video rules); leni `.jpg`/`.jpeg`/`.png`/`.webp`
- `JobRecord` gains optional `ephemeral: bool = False` (or detect `input.*` in job dir at run time — prefer explicit `ephemeral: bool` for clarity)

Order of operations for upload path:

1. Validate type + file content-type/extension + size (read capped)
2. `mgr.create(..., ephemeral=True, source_name=f"input{suffix}")` — create must not require Library file when `ephemeral=True`
3. Write bytes to `job_dir / source_name`
4. `background_tasks.add_task(mgr.run_job, ...)`

For Library path: unchanged (`ephemeral=False`).

### `run_job` resolution

```
if record.ephemeral:
    path = jobs_dir/id / record.source_name  # must exist
else:
    path = resolve_source|resolve_image(settings, record.source_name)
```

## Testing

- Multipart roblox upload → id; fake run sees job-local input
- Multipart leni upload → mode picture
- `source_name` without file still works
- Both / neither → 400
- Image uploaded with type=roblox → 400
- Oversize → 400
- Auth still required

## Docs

README n8n section: form-data fields; PowerShell `multipart/form-data` example with `-Form`.

## Non-goals

- Dual JSON+multipart create
- Persisting uploads into Library `sources/` / `images/`
- Slicing uploaded roblox videos into minute parts
