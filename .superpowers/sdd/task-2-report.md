# Task 2 Report: Multipart create endpoint

## What was implemented

- **`POST /api/v1/videos`** now accepts multipart form fields (`voice`, `story`, `type`, `source_name`) plus optional `media` file upload.
- **Library-backed validation**: video/image filename checks and size limits via `validate_video_filename`, `validate_image_filename`, `MAX_UPLOAD_BYTES`, `MAX_IMAGE_UPLOAD_BYTES`.
- **Ephemeral uploads**: media files stored as `jobs/{id}/input.<ext>` with `ephemeral=True`; library `source_name` path unchanged.
- **Mutual exclusion**: 400 if both `media` and `source_name` provided, or neither.
- **Removed** unused `CreateVideoBody` Pydantic model.

## What was tested and results

| Scope | Command | Result |
|-------|---------|--------|
| Focused (task) | `pytest tests/web/test_api_v1.py -v` | 13 passed |
| Full suite | `pytest tests/web/test_api_v1.py tests/web/test_jobs.py -q` | 29 passed |

## TDD Evidence

### RED

```text
pytest tests/web/test_api_v1.py -v
```

```
10 failed, 3 passed
422 Unprocessable Entity (JSON body expected, form data sent)
```

### GREEN

```text
pytest tests/web/test_api_v1.py tests/web/test_jobs.py -q
```

```
29 passed in 1.61s
```

## Commit

```
feat(web): accept multipart media on n8n video create
```

Files: `src/roblox_viral/web/api_v1.py`, `tests/web/test_api_v1.py`

## Concerns

- Upload reads entire file into memory before size check; acceptable per plan but could use `_read_upload_capped` for streaming in a follow-up.
- No dedicated test for oversize upload rejection on this endpoint (covered indirectly via library tests).
