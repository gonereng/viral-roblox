# n8n Video API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add API-key–authenticated `/api/v1/videos` create, status, and download endpoints for n8n, reusing `JobManager` (`leni` → picture mode).

**Architecture:** `Settings.api_key` + `require_api_key` dependency; thin FastAPI routes that map `type` to `mode`, start background `run_job`, return job JSON / `FileResponse`. UI session auth unchanged.

**Tech Stack:** Python 3.10+, FastAPI, pytest, existing JobManager

## Global Constraints

- Routes: `POST /api/v1/videos`, `GET /api/v1/videos/{id}`, `GET /api/v1/videos/{id}/download`
- Auth: `X-API-Key` vs env `API_KEY`; missing/wrong → **401**; unset `API_KEY` → **503**
- Create body: `voice`, `story`, `type` (`roblox`|`leni`), `source_name` (required)
- `leni` → `mode="picture"`; `roblox` → `mode="roblox"`; pitch/speed defaults 15/130; `ken_burns=false`
- Create returns `{ "id" }` immediately; busy → **409**
- Download: **200** MP4 if done; **409** if still running; **404** unknown; **422** if error
- Spec: `docs/superpowers/specs/2026-08-14-n8n-video-api-design.md`
- Out of scope: webhooks, multi-keys, exposing pitch/speed/ken_burns on v1, cookie auth for these routes

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/web/config.py` | `api_key` from `API_KEY` |
| `src/roblox_viral/web/auth.py` | `require_api_key` |
| `src/roblox_viral/web/api_v1.py` | Router: create / status / download |
| `src/roblox_viral/web/app.py` | `include_router` |
| `docker-compose.yml` | Pass `API_KEY` |
| `README.md` | n8n usage |
| `tests/web/test_config.py` | api_key from env |
| `tests/web/test_api_v1.py` | Auth + create/status/download |

---

### Task 1: `API_KEY` settings + `require_api_key`

**Files:**
- Modify: `src/roblox_viral/web/config.py`
- Modify: `src/roblox_viral/web/auth.py`
- Modify: `tests/web/test_config.py`
- Create: `tests/web/test_api_v1.py` (auth-only tests first; more in Task 2–3)

**Interfaces:**
- Produces:
  - `Settings.api_key: str = ""` from `os.environ.get("API_KEY", "")`
  - `async def require_api_key(request: Request) -> None` — if `not settings.api_key.strip()` → HTTP 503 detail `"API key not configured"`; else compare `request.headers.get("X-API-Key")` or `""` to `settings.api_key` with `secrets.compare_digest` (catch `ValueError` → treat as mismatch); mismatch → 401 `"Invalid API key"`

- [ ] **Step 1: Write failing config + auth tests**

Append to `tests/web/test_config.py`:

```python
def test_api_key_from_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("API_KEY", "n8n-secret")
    settings = Settings.from_env()
    assert settings.api_key == "n8n-secret"
```

In `tests/web/test_api_v1.py`:

```python
from fastapi.testclient import TestClient

from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings
from roblox_viral.web.voices import clear_cache


def _v1_client(tmp_path, monkeypatch, api_key: str | None = "test-key"):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    if api_key is None:
        monkeypatch.delenv("API_KEY", raising=False)
    else:
        monkeypatch.setenv("API_KEY", api_key)
    clear_cache()
    return TestClient(create_app(Settings.from_env()))


def test_v1_requires_api_key_header(tmp_path, monkeypatch):
    c = _v1_client(tmp_path, monkeypatch)
    r = c.post(
        "/api/v1/videos",
        json={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "roblox",
            "source_name": "clip.mp4",
        },
    )
    assert r.status_code == 401


def test_v1_wrong_api_key(tmp_path, monkeypatch):
    c = _v1_client(tmp_path, monkeypatch)
    r = c.post(
        "/api/v1/videos",
        headers={"X-API-Key": "nope"},
        json={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "roblox",
            "source_name": "clip.mp4",
        },
    )
    assert r.status_code == 401


def test_v1_api_key_unset_returns_503(tmp_path, monkeypatch):
    c = _v1_client(tmp_path, monkeypatch, api_key=None)
    r = c.get("/api/v1/videos/deadbeef", headers={"X-API-Key": "x"})
    # Route may 404 if not registered yet in Task 1 — for Task 1 only assert
    # require_api_key via a minimal mounted probe OR implement stub routes in Task 1.
    # Prefer: implement require_api_key + register empty router with GET /api/v1/videos/_probe
    # Simpler: Task 1 only unit-tests require_api_key with a tiny FastAPI app in the test file.
```

**Preferred Task 1 auth unit test** (no full routes yet):

```python
# tests/web/test_api_key_auth.py
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from roblox_viral.web.auth import require_api_key
from roblox_viral.web.config import Settings


def _app(settings: Settings) -> TestClient:
    app = FastAPI()
    app.state.settings = settings

    @app.get("/probe")
    async def probe(_: None = Depends(require_api_key)):
        return {"ok": True}

    return TestClient(app)


def test_require_api_key_503_when_unset(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "x")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("API_KEY", raising=False)
    s = Settings.from_env()
    c = _app(s)
    r = c.get("/probe", headers={"X-API-Key": "anything"})
    assert r.status_code == 503


def test_require_api_key_401_and_200(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "x")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("API_KEY", "good")
    s = Settings.from_env()
    c = _app(s)
    assert c.get("/probe").status_code == 401
    assert c.get("/probe", headers={"X-API-Key": "bad"}).status_code == 401
    assert c.get("/probe", headers={"X-API-Key": "good"}).status_code == 200
```

Use **`tests/web/test_api_key_auth.py`** for Task 1 (not incomplete `test_api_v1` stubs). Create `test_api_v1.py` in Task 2.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/web/test_config.py::test_api_key_from_env tests/web/test_api_key_auth.py -v`

Expected: FAIL (missing `api_key` / `require_api_key`)

- [ ] **Step 3: Implement**

In `config.py` `Settings` dataclass add `api_key: str = ""`. In `from_env`:

```python
api_key = os.environ.get("API_KEY", "")
# pass api_key=api_key into cls(...)
```

In `auth.py`:

```python
import secrets
from fastapi import Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_503_SERVICE_UNAVAILABLE


async def require_api_key(request: Request) -> None:
    settings = request.app.state.settings
    expected = (settings.api_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key not configured",
        )
    provided = request.headers.get("X-API-Key") or ""
    try:
        ok = secrets.compare_digest(provided, expected)
    except ValueError:
        ok = False
    if not ok:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/web/test_config.py::test_api_key_from_env tests/web/test_api_key_auth.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/config.py src/roblox_viral/web/auth.py tests/web/test_config.py tests/web/test_api_key_auth.py
git commit -m "feat(web): add API_KEY settings and require_api_key"
```

---

### Task 2: Create + status routes

**Files:**
- Create: `src/roblox_viral/web/api_v1.py`
- Modify: `src/roblox_viral/web/app.py` (include router)
- Create: `tests/web/test_api_v1.py`

**Interfaces:**
- Consumes: `require_api_key`, `JobManager.create` / `get` / `run_job`, `BusyError`, `DEFAULT_VOICE`, `DEFAULT_PITCH`, `DEFAULT_SPEED`
- Produces:
  - `APIRouter(prefix="/api/v1", tags=["v1"])`
  - `CreateVideoBody`: `voice: str`, `story: str`, `type: str`, `source_name: str`
  - `POST /videos` → `{ "id": job_id }`
  - `GET /videos/{id}` → `asdict(record)` (or subset: id, status, error, output_name, mode, source_name)

Type map helper in `api_v1.py`:

```python
def _mode_from_type(video_type: str) -> str:
    t = (video_type or "").strip().lower()
    if t == "roblox":
        return "roblox"
    if t == "leni":
        return "picture"
    raise ValueError("type must be 'roblox' or 'leni'")
```

- [ ] **Step 1: Write failing integration tests**

```python
# tests/web/test_api_v1.py
from fastapi.testclient import TestClient

from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings
from roblox_viral.web.jobs import JobManager
from roblox_viral.web.voices import clear_cache

API_KEY = "test-key"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("API_KEY", API_KEY)
    clear_cache()
    return TestClient(create_app(Settings.from_env()))


def _headers():
    return {"X-API-Key": API_KEY}


def test_create_roblox_video_returns_id(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        rec.status = "done"
        rec.output_name = f"{job_id}.mp4"
        out = settings.outputs_dir / rec.output_name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"mp4")
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        json={
            "voice": "en-US-EmmaNeural",
            "story": "Hello world.\n",
            "type": "roblox",
            "source_name": "clip.mp4",
        },
    )
    assert r.status_code == 200
    job_id = r.json()["id"]
    assert job_id
    st = c.get(f"/api/v1/videos/{job_id}", headers=_headers())
    assert st.status_code == 200
    assert st.json()["status"] == "done"
    assert st.json()["mode"] == "roblox"


def test_create_leni_maps_to_picture(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    (settings.images_dir / "still.jpg").write_bytes(b"img")

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        rec.status = "done"
        rec.output_name = f"{job_id}.mp4"
        (settings.outputs_dir / rec.output_name).write_bytes(b"mp4")
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        json={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "leni",
            "source_name": "still.jpg",
        },
    )
    assert r.status_code == 200
    st = c.get(f"/api/v1/videos/{r.json()['id']}", headers=_headers())
    assert st.json()["mode"] == "picture"


def test_create_bad_type_400(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        json={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "other",
            "source_name": "clip.mp4",
        },
    )
    assert r.status_code == 400


def test_create_busy_409(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")
    mgr: JobManager = c.app.state.job_manager
    mgr._active_id = "busy"
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        json={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "roblox",
            "source_name": "clip.mp4",
        },
    )
    assert r.status_code == 409
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/web/test_api_v1.py -v`

- [ ] **Step 3: Implement `api_v1.py` + mount**

```python
# src/roblox_viral/web/api_v1.py
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel

from roblox_viral.voice import DEFAULT_PITCH, DEFAULT_SPEED
from roblox_viral.web.auth import require_api_key
from roblox_viral.web.jobs import BusyError, JobManager
from roblox_viral.web.voices import DEFAULT_VOICE

router = APIRouter(prefix="/api/v1", tags=["v1"])


class CreateVideoBody(BaseModel):
    voice: str = ""
    story: str = ""
    type: str = ""
    source_name: str = ""


def _mode_from_type(video_type: str) -> str:
    t = (video_type or "").strip().lower()
    if t == "roblox":
        return "roblox"
    if t == "leni":
        return "picture"
    raise ValueError("type must be 'roblox' or 'leni'")


@router.post("/videos")
async def create_video(
    request: Request,
    background_tasks: BackgroundTasks,
    body: CreateVideoBody,
    _: None = Depends(require_api_key),
) -> dict:
    settings = request.app.state.settings
    mgr: JobManager = request.app.state.job_manager
    try:
        mode = _mode_from_type(body.type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    voice = (body.voice or "").strip() or DEFAULT_VOICE
    try:
        record = mgr.create(
            settings,
            body.source_name,
            body.story,
            voice,
            pitch=DEFAULT_PITCH,
            speed=DEFAULT_SPEED,
            mode=mode,
            ken_burns=False,
        )
    except BusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(mgr.run_job, settings, record.id)
    return {"id": record.id}


@router.get("/videos/{video_id}")
def get_video(
    video_id: str,
    request: Request,
    _: None = Depends(require_api_key),
) -> dict:
    settings = request.app.state.settings
    mgr: JobManager = request.app.state.job_manager
    record = mgr.get(video_id, settings)
    if record is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return asdict(record)
```

In `create_app`, after building `app`:

```python
from roblox_viral.web.api_v1 import router as api_v1_router
app.include_router(api_v1_router)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/web/test_api_v1.py tests/web/test_api_key_auth.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/api_v1.py src/roblox_viral/web/app.py tests/web/test_api_v1.py
git commit -m "feat(web): n8n create and status video API"
```

---

### Task 3: Download + compose + README

**Files:**
- Modify: `src/roblox_viral/web/api_v1.py`
- Modify: `tests/web/test_api_v1.py`
- Modify: `docker-compose.yml`
- Modify: `README.md`

**Interfaces:**
- Produces: `GET /api/v1/videos/{id}/download` → `FileResponse`

- [ ] **Step 1: Write download tests**

```python
def test_download_done_returns_mp4(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        rec.status = "done"
        rec.output_name = f"{job_id}.mp4"
        (settings.outputs_dir / rec.output_name).write_bytes(b"fake-mp4-bytes")
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    job_id = c.post(
        "/api/v1/videos",
        headers=_headers(),
        json={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "roblox",
            "source_name": "clip.mp4",
        },
    ).json()["id"]
    r = c.get(f"/api/v1/videos/{job_id}/download", headers=_headers())
    assert r.status_code == 200
    assert r.content == b"fake-mp4-bytes"
    assert "video/mp4" in r.headers.get("content-type", "")


def test_download_not_ready_409(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")

    def fake_run(self, settings, job_id):
        # leave queued/active without finishing
        pass

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    # Manually create without completing:
    mgr: JobManager = c.app.state.job_manager
    rec = mgr.create(
        settings, "clip.mp4", "Hi.\n", "en-US-EmmaNeural", mode="roblox"
    )
    # clear active so we don't care; status still queued
    with mgr._lock:
        mgr._active_id = None
    r = c.get(f"/api/v1/videos/{rec.id}/download", headers=_headers())
    assert r.status_code == 409


def test_download_error_422(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")
    mgr: JobManager = c.app.state.job_manager
    rec = mgr.create(
        settings, "clip.mp4", "Hi.\n", "en-US-EmmaNeural", mode="roblox"
    )
    rec.status = "error"
    rec.error = "boom"
    with mgr._lock:
        mgr._active_id = None
    r = c.get(f"/api/v1/videos/{rec.id}/download", headers=_headers())
    assert r.status_code == 422


def test_download_unknown_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/v1/videos/0" * 16 + "/download", headers=_headers())
    # use a valid-looking 32-hex id that does not exist
    r = c.get(
        "/api/v1/videos/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/download",
        headers=_headers(),
    )
    assert r.status_code == 404
```

Fix the botched first assert line in `test_download_unknown_404` — only the 32-hex path.

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/web/test_api_v1.py -k download -v`

- [ ] **Step 3: Implement download**

```python
from pathlib import Path
from fastapi.responses import FileResponse

@router.get("/videos/{video_id}/download")
def download_video(
    video_id: str,
    request: Request,
    _: None = Depends(require_api_key),
) -> FileResponse:
    settings = request.app.state.settings
    mgr: JobManager = request.app.state.job_manager
    record = mgr.get(video_id, settings)
    if record is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if record.status == "error":
        raise HTTPException(
            status_code=422, detail=record.error or "Render failed"
        )
    if record.status != "done" or not record.output_name:
        raise HTTPException(status_code=409, detail="Video not ready")
    safe = Path(record.output_name).name
    if safe != record.output_name:
        raise HTTPException(status_code=400, detail="Invalid output name")
    path = (settings.outputs_dir / safe).resolve()
    if not path.is_relative_to(settings.outputs_dir.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="Output file missing")
    return FileResponse(path, media_type="video/mp4", filename=safe)
```

- [ ] **Step 4: docker-compose + README**

`docker-compose.yml` environment:

```yaml
      API_KEY: ${API_KEY:-}
```

README — add under Optional env vars:

| `API_KEY` | Shared secret for `/api/v1/videos*` (`X-API-Key`). Required for n8n integration. |

And a short **n8n API** subsection:

```markdown
### n8n API

Set `API_KEY` in `.env`. Then:

1. `POST /api/v1/videos` with header `X-API-Key` and JSON
   `{ "voice", "story", "type": "roblox"|"leni", "source_name" }` → `{ "id" }`
2. Poll `GET /api/v1/videos/{id}` until `status` is `done` or `error`
3. `GET /api/v1/videos/{id}/download` → MP4 (`409` while rendering)
```

- [ ] **Step 5: Full related suite + commit**

Run: `pytest tests/web/test_api_v1.py tests/web/test_api_key_auth.py tests/web/test_config.py -q`

```bash
git add src/roblox_viral/web/api_v1.py tests/web/test_api_v1.py docker-compose.yml README.md
git commit -m "feat(web): n8n video download endpoint and docs"
```

---

## Self-review (plan vs spec)

| Spec | Task |
|------|------|
| API_KEY + X-API-Key + 401/503 | Task 1 |
| POST create + type map + busy 409 | Task 2 |
| GET status | Task 2 |
| GET download 200/409/404/422 | Task 3 |
| compose + README | Task 3 |
| Defaults pitch/speed/ken_burns | Task 2 |
| No webhooks / multi-key | Honored |

No TBD placeholders. Types consistent: `CreateVideoBody`, `require_api_key`, job `id` as video id.
