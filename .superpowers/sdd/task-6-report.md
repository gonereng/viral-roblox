# Task 6 Report: Library routes + Generate page + Job API

## Status

**DONE**

## Commits

- `feat(web): library, generate UI, and job API` (`4b1f511`, after BASE `7135133`)

Files:
- `src/roblox_viral/web/app.py` (modified)
- `src/roblox_viral/web/auth.py` (modified — unused `RedirectResponse` import removed)
- `src/roblox_viral/web/templates/base.html` (nav + static CSS)
- `src/roblox_viral/web/templates/login.html` (minimal header)
- `src/roblox_viral/web/templates/generate.html` (created)
- `src/roblox_viral/web/templates/library.html` (created)
- `src/roblox_viral/web/static/app.js` (created — 1s poll)
- `src/roblox_viral/web/static/app.css` (created)
- `tests/web/test_api.py` (created)
- `tests/web/test_auth_routes.py` (mock voices for offline GET /)

## What was implemented

- Single `JobManager` on `app.state.job_manager`
- `GET /` — generate form with sources + English voices (Emma default); voice fetch failure falls back to Emma
- Library: `GET /library`, `POST /library/upload`, `POST /library/delete`
- `POST /api/jobs` → create + `BackgroundTasks.add_task(mgr.run_job, ...)`; `BusyError` → **409**
- `GET /api/jobs/{id}` → job JSON (`asdict`); 404 if missing
- `GET /media/outputs/{name}` — auth-required `FileResponse` with path-safe basename check
- Package-relative `TEMPLATES_DIR` / `STATIC_DIR` via `Path(__file__).parent`; static mounted at `/static`
- Logout already present (`GET|POST /logout`)

## Tests

Command: `pytest tests/web -v`

Result: **17 passed**

Notable API cases:
- create + poll (mocked `run_job`; TestClient runs background before return → GET `done`)
- busy → 409
- library upload/list/delete
- media auth + serve
- generate page sources + Emma selected

## Concerns

- Templates/static still not declared as setuptools `package-data`; works with editable/`pythonpath=src`, may be missing from a wheel install.
- `GET /` calls live `list_english_voices()` unless mocked; production depends on Edge TTS network; failure path shows Emma only.
- Generate page has no “recent outputs” list from the design table (not in Task 6 brief interfaces).

## Follow-up: Recent outputs (design gap)

**Status:** DONE

**Commit:** `feat(web): show recent outputs on generate page`

- Added `list_outputs()` in `library.py` — newest MP4s from `settings.outputs_dir`, cap 10
- `GET /` passes `recent_outputs` to `generate.html`
- Template section lists name, size, and `/media/outputs/{name}` play/download link
- Existing generate form, progress, and result UI unchanged

**Tests:** `pytest tests/web -v` — **19 passed** (+2: `test_generate_page_lists_recent_outputs`, `test_list_outputs_newest_first`)

**Concern resolved:** Generate page now matches design spec “recent outputs” row.
