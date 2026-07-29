# Roblox Viral Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a password-protected FastAPI web UI that uploads source videos, accepts a story + English Edge voice, runs the existing render pipeline as a background job with progress, and plays/downloads the finished MP4 — Docker-ready.

**Architecture:** Keep `story` / `voice` / `captions` / `render` as the engine. Add `src/roblox_viral/web/` with session auth, disk-backed media library, single-flight job runner, Jinja templates + small JS poller. Persist job status under `media/jobs/{id}/status.json`.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, python-multipart, itsdangerous (or Starlette SessionMiddleware), uvicorn, edge-tts, ffmpeg (existing), pytest + httpx

## Global Constraints

- Reuse existing pipeline APIs; do not rewrite TTS/caption/ffmpeg logic
- Story: one sentence per line; captions: one word at a time
- Default voice: `en-US-EmmaNeural`
- Voice dropdown: all English Edge TTS voices (`Locale` starts with `en`)
- Auth: session cookie; `APP_PASSWORD` required in Docker; `APP_SECRET` for signing
- Single-flight jobs: if a job is active, new create returns HTTP 409
- Progress states exactly: `queued` → `synthesizing` → `captioning` → `rendering` → `done` | `error`
- Media layout: `media/sources/`, `media/outputs/`, `media/jobs/`
- CLI entrypoint `roblox-viral` remains working
- Out of v1: Redis/Celery, multi-user accounts, cloud storage, voice preview, parallel renders

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/web/config.py` | Env + `MEDIA_ROOT`, ensure dirs |
| `src/roblox_viral/web/auth.py` | Password check, session dependency |
| `src/roblox_viral/web/library.py` | List/upload/delete source videos |
| `src/roblox_viral/web/voices.py` | List English Edge voices (cached) |
| `src/roblox_viral/web/jobs.py` | Job model, disk status, single-flight worker |
| `src/roblox_viral/web/app.py` | FastAPI routes + templates wiring |
| `src/roblox_viral/web/templates/*.html` | login, generate, library, base |
| `src/roblox_viral/web/static/app.js` | Job progress polling |
| `src/roblox_viral/web/static/app.css` | Minimal usable styling |
| `Dockerfile`, `docker-compose.yml` | Runtime with ffmpeg + volume |
| `tests/web/*.py` | Auth, library, jobs, routes |

---

### Task 1: Config + media paths

**Files:**
- Create: `src/roblox_viral/web/__init__.py`
- Create: `src/roblox_viral/web/config.py`
- Create: `tests/web/test_config.py`
- Modify: `pyproject.toml` (add web deps)
- Modify: `.gitignore` (ensure `media/` ignored except maybe `.gitkeep`)

**Interfaces:**
- Produces: `Settings` dataclass; `get_settings() -> Settings`; `Settings.ensure_media_dirs() -> None`; properties `sources_dir`, `outputs_dir`, `jobs_dir`

- [ ] **Step 1: Add dependencies to `pyproject.toml`**

```toml
dependencies = [
  "edge-tts>=6.1.9",
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "jinja2>=3.1.0",
  "python-multipart>=0.0.9",
  "itsdangerous>=2.2.0",
  "httpx>=0.27.0",
]

[project.scripts]
roblox-viral = "roblox_viral.cli:main"
roblox-viral-web = "roblox_viral.web.app:main"
```

Also add to `requirements.txt` the same packages.

- [ ] **Step 2: Write failing test**

```python
# tests/web/test_config.py
from pathlib import Path
from roblox_viral.web.config import Settings

def test_ensure_media_dirs(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    settings = Settings.from_env()
    settings.ensure_media_dirs()
    assert settings.sources_dir.is_dir()
    assert settings.outputs_dir.is_dir()
    assert settings.jobs_dir.is_dir()
```

- [ ] **Step 3: Run test — expect fail**

Run: `pytest tests/web/test_config.py -v`  
Expected: FAIL (module not found)

- [ ] **Step 4: Implement `config.py`**

```python
from __future__ import annotations

import os
import secrets
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    media_root: Path
    app_password: str
    app_secret: str
    require_password: bool = True

    @property
    def sources_dir(self) -> Path:
        return self.media_root / "sources"

    @property
    def outputs_dir(self) -> Path:
        return self.media_root / "outputs"

    @property
    def jobs_dir(self) -> Path:
        return self.media_root / "jobs"

    def ensure_media_dirs(self) -> None:
        for d in (self.sources_dir, self.outputs_dir, self.jobs_dir):
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> Settings:
        media = Path(os.environ.get("MEDIA_ROOT", "media")).resolve()
        password = os.environ.get("APP_PASSWORD", "")
        secret = os.environ.get("APP_SECRET", "")
        require = os.environ.get("APP_REQUIRE_PASSWORD", "1") not in ("0", "false", "False")
        if require and not password:
            raise RuntimeError("APP_PASSWORD is required")
        if not secret:
            secret = secrets.token_hex(32)
            warnings.warn("APP_SECRET unset; using ephemeral secret (sessions reset on restart)", stacklevel=2)
        return cls(media_root=media, app_password=password, app_secret=secret, require_password=require)


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
```

- [ ] **Step 5: Run test — expect pass**

Run: `pytest tests/web/test_config.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml requirements.txt src/roblox_viral/web tests/web .gitignore
git commit -m "feat(web): add settings and media path helpers"
```

---

### Task 2: Source video library

**Files:**
- Create: `src/roblox_viral/web/library.py`
- Create: `tests/web/test_library.py`

**Interfaces:**
- Consumes: `Settings.sources_dir`
- Produces: `list_sources(settings) -> list[SourceVideo]`; `save_upload(settings, filename: str, data: bytes) -> SourceVideo`; `delete_source(settings, name: str) -> None`; `resolve_source(settings, name: str) -> Path`
- `SourceVideo`: `name: str`, `path: Path`, `size_bytes: int`

- [ ] **Step 1: Write failing tests**

```python
# tests/web/test_library.py
import pytest
from roblox_viral.web.config import Settings
from roblox_viral.web import library

def _settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "x")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    s = Settings.from_env()
    s.ensure_media_dirs()
    return s

def test_save_list_delete_source(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    vid = library.save_upload(s, "clip.mp4", b"fake-bytes")
    assert vid.name == "clip.mp4"
    assert library.list_sources(s)[0].name == "clip.mp4"
    assert library.resolve_source(s, "clip.mp4").is_file()
    library.delete_source(s, "clip.mp4")
    assert library.list_sources(s) == []

def test_rejects_path_traversal(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        library.resolve_source(s, "../evil.mp4")
```

- [ ] **Step 2: Run tests — expect fail**

Run: `pytest tests/web/test_library.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement `library.py`**

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from roblox_viral.web.config import Settings

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._ -]+\.(mp4|mov|webm|mkv)$", re.I)


@dataclass(frozen=True)
class SourceVideo:
    name: str
    path: Path
    size_bytes: int


def _safe_name(name: str) -> str:
    base = Path(name).name
    if not _SAFE_NAME.match(base):
        raise ValueError(f"Invalid video filename: {name!r}")
    return base


def list_sources(settings: Settings) -> list[SourceVideo]:
    items: list[SourceVideo] = []
    for path in sorted(settings.sources_dir.iterdir()):
        if path.is_file() and _SAFE_NAME.match(path.name):
            items.append(SourceVideo(path.name, path, path.stat().st_size))
    return items


def resolve_source(settings: Settings, name: str) -> Path:
    safe = _safe_name(name)
    path = (settings.sources_dir / safe).resolve()
    if not str(path).startswith(str(settings.sources_dir.resolve())):
        raise ValueError("Invalid path")
    if not path.is_file():
        raise FileNotFoundError(safe)
    return path


def save_upload(settings: Settings, filename: str, data: bytes) -> SourceVideo:
    safe = _safe_name(filename)
    path = settings.sources_dir / safe
    path.write_bytes(data)
    return SourceVideo(safe, path, path.stat().st_size)


def delete_source(settings: Settings, name: str) -> None:
    resolve_source(settings, name).unlink()
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/web/test_library.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/library.py tests/web/test_library.py
git commit -m "feat(web): source video library helpers"
```

---

### Task 3: English voice list

**Files:**
- Create: `src/roblox_viral/web/voices.py`
- Create: `tests/web/test_voices.py`

**Interfaces:**
- Produces: `async def list_english_voices() -> list[VoiceInfo]`; `VoiceInfo(short_name: str, locale: str, gender: str)`; default constant `DEFAULT_VOICE = "en-US-EmmaNeural"`
- Cache voices in-process for 1 hour

- [ ] **Step 1: Write failing test (mocked edge_tts)**

```python
# tests/web/test_voices.py
import pytest
from roblox_viral.web import voices

@pytest.mark.asyncio
async def test_list_english_voices_filters(monkeypatch):
    async def fake_list():
        return [
            {"ShortName": "en-US-EmmaNeural", "Locale": "en-US", "Gender": "Female"},
            {"ShortName": "de-DE-ConradNeural", "Locale": "de-DE", "Gender": "Male"},
            {"ShortName": "en-GB-RyanNeural", "Locale": "en-GB", "Gender": "Male"},
        ]
    monkeypatch.setattr(voices, "_fetch_voices", fake_list)
    voices.clear_cache()
    result = await voices.list_english_voices()
    names = [v.short_name for v in result]
    assert names == ["en-GB-RyanNeural", "en-US-EmmaNeural"]
    assert voices.DEFAULT_VOICE == "en-US-EmmaNeural"
```

- [ ] **Step 2: Implement `voices.py`** with `_fetch_voices` calling `edge_tts.list_voices()`, filter `Locale.startswith("en")`, sort by ShortName, TTL cache via module globals + timestamp.

- [ ] **Step 3: Add pytest-asyncio if needed**

```toml
# pyproject.toml optional dep or main test dep
# pip install pytest-asyncio
```

Add `pytest-asyncio` to dev/test install and `asyncio_mode = auto` under `[tool.pytest.ini_options]`.

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/web/test_voices.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/voices.py tests/web/test_voices.py pyproject.toml
git commit -m "feat(web): list English Edge TTS voices"
```

---

### Task 4: Job store + single-flight pipeline worker

**Files:**
- Create: `src/roblox_viral/web/jobs.py`
- Create: `tests/web/test_jobs.py`

**Interfaces:**
- Produces:
  - `JobStatus` literal: `queued|synthesizing|captioning|rendering|done|error`
  - `JobRecord` dataclass: `id`, `status`, `error`, `source_name`, `voice`, `output_name`, `created_at`
  - `JobManager.create(settings, source_name, story, voice) -> JobRecord` raises `BusyError` if active job exists
  - `JobManager.get(job_id) -> JobRecord | None`
  - `JobManager.run_job(settings, job_id)` — sync function invoked in a thread/background task; updates status through stages; calls:
    - `EdgeTTSProvider(voice).synthesize(join_for_tts(sentences), narration_path)`
    - `write_ass(words, ass_path, sentences=sentences)`
    - `render_video(video_path=..., audio_path=..., ass_path=..., output_path=outputs/{job_id}.mp4, work_dir=jobs/{id})`
  - Persist `status.json` after every status change under `settings.jobs_dir / job_id /`

- [ ] **Step 1: Write failing unit tests with mocked pipeline**

```python
# tests/web/test_jobs.py
import pytest
from roblox_viral.web.config import Settings
from roblox_viral.web.jobs import BusyError, JobManager

def _settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "x")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    s = Settings.from_env()
    s.ensure_media_dirs()
    (s.sources_dir / "clip.mp4").write_bytes(b"abc")
    return s

def test_single_flight_rejects_second_job(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    j1 = mgr.create(s, "clip.mp4", "Hello world.\n", "en-US-EmmaNeural")
    assert j1.status == "queued"
    with pytest.raises(BusyError):
        mgr.create(s, "clip.mp4", "Other.\n", "en-US-EmmaNeural")

def test_run_job_updates_statuses(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    # monkeypatch EdgeTTSProvider.synthesize, write_ass, render_video to no-ops that write a fake output
    ...
    job = mgr.create(s, "clip.mp4", "One line only here.\n", "en-US-EmmaNeural")
    mgr.run_job(s, job.id)
    done = mgr.get(job.id)
    assert done.status == "done"
    assert done.output_name.endswith(".mp4")
    assert (s.jobs_dir / job.id / "status.json").is_file()
```

Fill in mocks so `synthesize` returns one `WordTiming`, `write_ass` writes a file, `render_video` writes empty mp4 to `output_path`.

- [ ] **Step 2: Implement `jobs.py`** — thread-safe lock for single-flight; clear lock in `finally` when job finishes (done/error).

Status transition order inside `run_job`:
1. set `synthesizing`
2. TTS
3. set `captioning`
4. ASS
5. set `rendering`
6. ffmpeg
7. set `done` + `output_name`

On exception: set `error` + message, re-raise or swallow for worker.

Story parsing: `sentences = split_sentences(story)` from `roblox_viral.story`; if empty raise.

- [ ] **Step 3: Run tests — expect pass**

Run: `pytest tests/web/test_jobs.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/roblox_viral/web/jobs.py tests/web/test_jobs.py
git commit -m "feat(web): single-flight render job manager"
```

---

### Task 5: Auth helpers + FastAPI app shell

**Files:**
- Create: `src/roblox_viral/web/auth.py`
- Create: `src/roblox_viral/web/app.py` (minimal: health + login routes)
- Create: `src/roblox_viral/web/templates/base.html`
- Create: `src/roblox_viral/web/templates/login.html`
- Create: `tests/web/test_auth_routes.py`

**Interfaces:**
- Produces: `create_app(settings: Settings | None = None) -> FastAPI`
- Session key `authenticated: bool` via `SessionMiddleware(secret_key=settings.app_secret)`
- Dependency `require_login(request) -> None` redirects to `/login` for HTML or 401 for API (`Accept: application/json` or path starts with `/api/`)

- [ ] **Step 1: Write failing route tests**

```python
# tests/web/test_auth_routes.py
from fastapi.testclient import TestClient
from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings

def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    app = create_app(Settings.from_env())
    return TestClient(app)

def test_generate_requires_login(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "/login" in r.headers["location"]

def test_login_success(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.post("/login", data={"password": "s3cret"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert c.get("/").status_code == 200
```

- [ ] **Step 2: Implement auth + minimal app** with Jinja2Templates pointing at `web/templates`.

`main()` for uvicorn:

```python
def main() -> None:
    import uvicorn
    uvicorn.run("roblox_viral.web.app:app", host="0.0.0.0", port=8000, reload=False)

app = create_app()  # module-level for uvicorn string import — lazy-safe: create_app() reads env at import; document that tests call create_app(settings)
```

Prefer:

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.ensure_media_dirs()
    app = FastAPI()
    app.state.settings = settings
    ...
    return app
```

And for CLI: `app = create_app()` only inside `main()` or use factory with uvicorn `factory=True`.

Use: `uvicorn.run(create_app, factory=True, ...)`.

- [ ] **Step 3: Run tests — expect pass**

Run: `pytest tests/web/test_auth_routes.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/roblox_viral/web/auth.py src/roblox_viral/web/app.py src/roblox_viral/web/templates tests/web/test_auth_routes.py
git commit -m "feat(web): session login and app factory"
```

---

### Task 6: Library routes + Generate page + Job API

**Files:**
- Modify: `src/roblox_viral/web/app.py`
- Create: `src/roblox_viral/web/templates/generate.html`
- Create: `src/roblox_viral/web/templates/library.html`
- Create: `src/roblox_viral/web/static/app.js`
- Create: `src/roblox_viral/web/static/app.css`
- Create: `tests/web/test_api.py`

**Interfaces:**
- `GET /` — generate form (sources + voices)
- `GET /library` — upload UI
- `POST /library/upload` — multipart file
- `POST /library/delete` — form `name`
- `POST /api/jobs` — JSON `{source_name, story, voice}` → `{id, status}` or 409
- `GET /api/jobs/{id}` — job JSON
- `GET /media/outputs/{name}` — file response (auth required)
- Background: `fastapi.BackgroundTasks` or `asyncio.to_thread(mgr.run_job, ...)`

- [ ] **Step 1: Write API tests**

```python
def test_create_job_and_poll(tmp_path, monkeypatch):
    # mock JobManager.run_job to mark done immediately OR monkeypatch pipeline
    ...
    r = c.post("/api/jobs", json={"source_name": "clip.mp4", "story": "Hi there.\n", "voice": "en-US-EmmaNeural"})
    assert r.status_code == 200
    job_id = r.json()["id"]
    # after background runs in TestClient, status done
```

Note: `TestClient` runs background tasks before returning by default in Starlette — assert final status via GET.

- [ ] **Step 2: Implement templates + JS poller**

`app.js` outline:
- On Generate click → POST `/api/jobs` → poll `/api/jobs/{id}` every 1000ms → update `#status` → on `done` set `<video src="/media/outputs/...">` and download link; on `error` show message.

- [ ] **Step 3: Wire routes in `app.py`** including logout `POST /logout`.

- [ ] **Step 4: Run full web tests**

Run: `pytest tests/web -v`  
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web tests/web
git commit -m "feat(web): library, generate UI, and job API"
```

---

### Task 7: Docker + README

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `media/sources/.gitkeep`
- Create: `media/outputs/.gitkeep`
- Create: `media/jobs/.gitkeep`
- Modify: `README.md`
- Modify: `.gitignore` — ignore `media/**/*` but keep `.gitkeep`

**Dockerfile sketch:**

```dockerfile
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV MEDIA_ROOT=/app/media
EXPOSE 8000
CMD ["uvicorn", "roblox_viral.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml sketch:**

```yaml
services:
  web:
    build: .
    ports: ["8000:8000"]
    environment:
      APP_PASSWORD: ${APP_PASSWORD:?set APP_PASSWORD}
      APP_SECRET: ${APP_SECRET:?set APP_SECRET}
      MEDIA_ROOT: /app/media
    volumes:
      - ./media:/app/media
```

- [ ] **Step 1: Add Docker files + README section** for local web run:

```bash
set APP_PASSWORD=...
set APP_SECRET=...
pip install -e .
roblox-viral-web
# or: uvicorn roblox_viral.web.app:create_app --factory --reload
```

- [ ] **Step 2: Manual smoke (local)**

1. Set env vars; start server  
2. Login → Library upload `examples/sample.mp4` if present (or generate one with ffmpeg)  
3. Generate with `examples/story.txt` content and Emma  
4. Confirm progress states and playback  

- [ ] **Step 3: Commit**

```bash
git add Dockerfile docker-compose.yml README.md media .gitignore
git commit -m "feat(web): Docker packaging and docs"
```

---

### Task 8: End-to-end verification

- [ ] **Step 1: Run full unit suite**

Run: `pytest -q`  
Expected: all existing + web tests PASS

- [ ] **Step 2: Optional real render smoke** (ffmpeg + network for Edge TTS) via the web UI or a small script calling `JobManager` without mocks

- [ ] **Step 3: Confirm CLI still works**

Run: `roblox-viral --help`  
Expected: help text

---

## Spec coverage check

| Spec item | Task |
|-----------|------|
| Session password login | 5 |
| Generate: source + story + voice | 6 |
| All English voices, Emma default | 3, 6 |
| Job progress states + polling | 4, 6 |
| Library upload/list/delete | 2, 6 |
| Single-flight busy | 4, 6 |
| Disk media layout | 1, 2, 4 |
| Docker + ffmpeg + volume | 7 |
| Keep CLI | 7–8 (unchanged cli) |
| Reuse pipeline | 4 |

## Placeholder / consistency self-review

- Status strings match spec exactly
- `BusyError` → HTTP 409 in Task 6
- `create_app` factory used by Docker and tests
- No Celery/Redis introduced
