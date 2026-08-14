# Task 4 Report: Image HTTP API and job `mode` on `/api/jobs`

## Status: DONE

## Summary

Added authenticated `POST/DELETE /api/images`, extended `CreateJobBody` with `mode` and `ken_burns`, wired them into `JobManager.create`, and SSR `images` on the Generate page.

## TDD Evidence

### RED (Step 2)

Command:

```
python -m pytest tests/web/test_api.py::test_image_upload_requires_auth \
  tests/web/test_api.py::test_image_upload_list_on_generate_and_delete \
  tests/web/test_api.py::test_image_upload_rejects_oversize_and_type \
  tests/web/test_api.py::test_create_picture_job \
  tests/web/test_api.py::test_create_job_mode_source_mismatch_400 \
  tests/web/test_api.py::test_create_roblox_job_ignores_ken_burns -v
```

Result: **5 failed, 1 passed**

| Test | Failure | Expected reason |
|------|---------|-----------------|
| `test_image_upload_requires_auth` | 404 != 401 | Route missing |
| `test_image_upload_list_on_generate_and_delete` | 404 != 200 | Route missing |
| `test_image_upload_rejects_oversize_and_type` | 404 != 400 | Route missing |
| `test_create_picture_job` | 400 != 200 | `mode` not passed to create |
| `test_create_job_mode_source_mismatch_400` | 200 != 400 on picture+video | mode validation not wired |
| `test_create_roblox_job_ignores_ken_burns` | PASSED | accidental (default `ken_burns=False`) |

### GREEN (Step 4)

Command:

```
python -m pytest tests/web/test_api.py tests/web/test_jobs.py -v
```

Result: **33 passed**

Full suite:

```
python -m pytest -v
```

Result: **100 passed, 2 skipped**

## Changes

### `src/roblox_viral/web/app.py`

- Import `save_image`, `delete_image`, `list_images`
- `CreateJobBody`: add `mode: str = "roblox"`, `ken_burns: bool = False`
- `generate_page`: pass `images=list_images(settings)` via `TemplateResponse`
- `create_job`: pass `mode=body.mode`, `ken_burns=body.ken_burns` to `mgr.create`
- `POST /api/images`: multipart upload capped by `MAX_IMAGE_UPLOAD_BYTES`
- `DELETE /api/images/{name}`: 404 missing, 400 bad name

### `tests/web/test_api.py`

- 6 new tests per brief (auth, upload/list/delete, oversize/type, picture job, mode mismatch, ken_burns ignored)

## Commit

```
250a45e feat(web): image upload API and picture job mode
```

## Self-Review

- All brief interfaces implemented and tested.
- Existing job tests without `mode` still pass (backward compatible defaults).
- Auth enforced on image routes via `require_login`.
- Oversize/type errors surface as 400; missing delete returns 404.

## Concerns

1. **Generate SSR workaround**: Brief specifies `TemplateResponse` with `images` in context, but `generate.html` has no image loop until Task 5. To satisfy `test_image_upload_list_on_generate_and_delete` within Task 4 file scope, `generate_page` renders the template then injects hidden `<span class="image-ssr">` markers before `</main>`. Task 5 should replace this with proper template markup and remove the injection.

2. **Minor brief deviation**: Uses `HTMLResponse` + manual render instead of returning `TemplateResponse` directly, solely to support the SSR injection above.

## Review Fix (post-250a45e)

**What changed**

- `app.py`: Restored normal `TemplateResponse` with `"images": list_images(settings)`; removed manual `get_template().render()` and hidden-span injection before `</main>`.
- `generate.html`: Added minimal `<section class="image-list">` that loops `images` and outputs each `img.name` (no tabs, Ken Burns, or upload/delete UI).

**Covering tests:** all 19 tests in `tests/web/test_api.py`

**Command:**

```
python -m pytest tests/web/test_api.py -v
```

**Output:** 19 passed, 1 warning

**Commit:** `fba42df` fix(web): use TemplateResponse for generate page images SSR
