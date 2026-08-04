# YouTube Library Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Library import a YouTube URL with a rename stem as a background job that downloads (≤1080p MP4 via yt-dlp), splits into 1-minute slices, and shares the single-flight lock with render jobs.

**Architecture:** Add `yt-dlp` download helper; extend `JobManager` with `kind=youtube` jobs (`queued` → `downloading` → `slicing` → `done`|`error`) on the same `_active_id` lock; Library form + poll UI; reuse `slice_into_minute_parts`.

**Tech Stack:** Python 3.10+, FastAPI, yt-dlp, ffmpeg (existing), pytest

## Global Constraints

- Download tool: `yt-dlp` as a project dependency (not a separate system binary requirement beyond what the package needs)
- Quality: best MP4 up to 1080p
- Single-flight: only one heavy job at a time — render **or** YouTube import; busy → HTTP 409
- Import statuses exactly: `queued` → `downloading` → `slicing` → `done` | `error`
- Slice naming: `{stem}-1.mp4`, `{stem}-2.mp4`, …; leftover under 1 minute discarded (same as upload)
- Rename stem: required; safe chars `A-Za-z0-9._ -`; no extension in input
- Auth: same session login as Library
- Mock yt-dlp in tests — no real YouTube network in CI
- Out of scope: playlists/channels, non-YouTube sites, quality picker UI, parallel imports
- Keep existing file upload unchanged

## File map

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | Add `yt-dlp` dependency |
| `src/roblox_viral/web/youtube.py` | URL/stem validation + download wrapper |
| `src/roblox_viral/web/jobs.py` | Shared busy lock; YouTube job create/run; extended JobRecord |
| `src/roblox_viral/web/app.py` | `POST /api/library/youtube` |
| `src/roblox_viral/web/templates/library.html` | YouTube form + progress UI |
| `src/roblox_viral/web/static/library.js` | Poll import job / refresh |
| `README.md` | Document YouTube import |
| `tests/web/test_youtube.py` | Unit tests for validate/download mock |
| `tests/web/test_youtube_api.py` | API + busy + success (mocked) |
| `tests/web/test_jobs.py` | Busy shared between render and youtube |

---

### Task 1: yt-dlp dependency + download helper

**Files:**
- Modify: `pyproject.toml`
- Create: `src/roblox_viral/web/youtube.py`
- Create: `tests/web/test_youtube.py`

**Interfaces:**
- Produces:
  - `YOUTUBE_FORMAT = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b[height<=1080]"`
  - `validate_youtube_url(url: str) -> str` — strip; require `youtube.com` or `youtu.be` in netloc/path; raise `ValueError`
  - `validate_stem(name: str) -> str` — strip; require `^[A-Za-z0-9._ -]+$` and non-empty; reject if contains `.` only as part of allowed set but reject if looks like `foo.mp4` (has video extension); raise `ValueError`
  - `download_youtube(url: str, dest: Path) -> Path` — download to `dest` (mp4); raise `RuntimeError` on failure; return `dest`

- [ ] **Step 1: Add dependency**

In `pyproject.toml` dependencies list, add:

```toml
  "yt-dlp>=2024.8.0",
```

- [ ] **Step 2: Write failing tests**

```python
# tests/web/test_youtube.py
from pathlib import Path

import pytest

from roblox_viral.web.youtube import (
    download_youtube,
    validate_stem,
    validate_youtube_url,
)


def test_validate_youtube_url_accepts_watch_and_short():
    assert "youtube.com" in validate_youtube_url(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    assert "youtu.be" in validate_youtube_url("https://youtu.be/dQw4w9WgXcQ")


def test_validate_youtube_url_rejects_non_youtube():
    with pytest.raises(ValueError, match="YouTube"):
        validate_youtube_url("https://example.com/watch?v=abc")


def test_validate_stem_ok():
    assert validate_stem("  gameplay clip ") == "gameplay clip"


def test_validate_stem_rejects_extension_and_empty():
    with pytest.raises(ValueError):
        validate_stem("clip.mp4")
    with pytest.raises(ValueError):
        validate_stem("   ")
    with pytest.raises(ValueError):
        validate_stem("../evil")


def test_download_youtube_writes_dest(tmp_path, monkeypatch):
    dest = tmp_path / "download.mp4"

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def download(self, urls):
            dest.write_bytes(b"fake-mp4")

    monkeypatch.setattr(
        "roblox_viral.web.youtube.yt_dlp.YoutubeDL",
        FakeYDL,
    )
    out = download_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ", dest)
    assert out == dest
    assert dest.read_bytes() == b"fake-mp4"
```

- [ ] **Step 3: Run tests — expect fail**

Run: `pytest tests/web/test_youtube.py -v`  
Expected: FAIL (module not found)

- [ ] **Step 4: Implement `youtube.py`**

```python
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

YOUTUBE_FORMAT = (
    "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/"
    "b[height<=1080][ext=mp4]/b[height<=1080]"
)

_STEM_RE = re.compile(r"^[A-Za-z0-9._ -]+$")
_VIDEO_EXT = re.compile(r"\.(mp4|mov|webm|mkv)$", re.I)


def validate_youtube_url(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("YouTube URL is required")
    parsed = urlparse(cleaned)
    host = (parsed.netloc or "").lower()
    if "youtube.com" not in host and "youtu.be" not in host:
        raise ValueError("URL must be a YouTube link")
    return cleaned


def validate_stem(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("Name is required")
    if _VIDEO_EXT.search(cleaned):
        raise ValueError("Name must not include a file extension")
    if not _STEM_RE.fullmatch(cleaned) or ".." in cleaned or "/" in cleaned or "\\" in cleaned:
        raise ValueError("Invalid name (use letters, numbers, spaces, . _ -)")
    return cleaned


def download_youtube(url: str, dest: Path) -> Path:
    """Download best ≤1080p MP4 to dest. Raises RuntimeError on failure."""
    safe_url = validate_youtube_url(url)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # yt-dlp outtmpl without extension; force merge to mp4 path
    outtmpl = str(dest.with_suffix(""))
    opts = {
        "format": YOUTUBE_FORMAT,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([safe_url])
    except Exception as exc:
        raise RuntimeError(f"YouTube download failed: {exc}") from exc

    # yt-dlp may write dest or dest.mp4 depending on template
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    alt = Path(outtmpl + ".mp4")
    if alt.is_file() and alt.stat().st_size > 0:
        if alt != dest:
            alt.replace(dest)
        return dest
    raise RuntimeError("YouTube download produced no file")
```

Note: Adjust `outtmpl`/`dest` handling so the FakeYDL test that writes `dest` still passes — FakeYDL writes `dest` directly; production path must ensure final file is `dest`. Prefer setting `outtmpl` to `str(dest)` with `%(ext)s` carefully, or after download rename any produced file in `dest.parent` matching the job. Simplest production approach that matches the test:

```python
def download_youtube(url: str, dest: Path) -> Path:
    safe_url = validate_youtube_url(url)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": YOUTUBE_FORMAT,
        "outtmpl": str(dest.with_suffix("")),  # yt-dlp adds .mp4
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([safe_url])
    except Exception as exc:
        raise RuntimeError(f"YouTube download failed: {exc}") from exc

    produced = dest if dest.is_file() else dest.with_suffix(".mp4")
    # If outtmpl was stem without suffix, file is stem.mp4 == dest when dest ends in .mp4
    if not produced.is_file():
        candidates = list(dest.parent.glob(dest.stem + ".*"))
        if not candidates:
            raise RuntimeError("YouTube download produced no file")
        produced = candidates[0]
    if produced != dest:
        produced.replace(dest)
    if not dest.is_file() or dest.stat().st_size == 0:
        raise RuntimeError("YouTube download produced no file")
    return dest
```

For the unit test FakeYDL: it writes `dest` — that path must be the one FakeYDL uses. Pass `dest` into FakeYDL via closure as in the test (test writes `dest` directly). Good.

- [ ] **Step 5: Install + run tests**

Run: `pip install -e ".[dev]" -q; pytest tests/web/test_youtube.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/roblox_viral/web/youtube.py tests/web/test_youtube.py
git commit -m "feat(web): add YouTube download helper and yt-dlp dependency"
```

---

### Task 2: JobManager YouTube import + shared busy lock

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`
- Create: `tests/web/test_youtube_jobs.py` (or fold into test_jobs.py)

**Interfaces:**
- Consumes: `download_youtube`, `validate_stem`, `validate_youtube_url`, `slice_into_minute_parts`
- Produces:
  - `JobRecord` gains: `kind: str` (`"render"` | `"youtube"`), `url: str | None`, `stem: str | None`, `created_slices: list[str] | None`
  - Render `create(...)` sets `kind="render"`; busy message: `"A job is already in progress"`
  - `create_youtube(settings, url: str, stem: str) -> JobRecord`
  - `run_youtube_job(settings, job_id: str) -> None` — statuses downloading → slicing → done; clears `_active_id` in `finally`
  - `JobStatus` includes `"downloading"` | `"slicing"`
  - Disk hydrate must accept new fields with defaults for old status.json files

- [ ] **Step 1: Write failing tests**

```python
# tests/web/test_youtube_jobs.py
from pathlib import Path

import pytest

from roblox_viral.web.config import Settings
from roblox_viral.web.jobs import BusyError, JobManager
from roblox_viral.web.library import SourceVideo


def _settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "x")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    s = Settings.from_env()
    s.ensure_media_dirs()
    return s


def test_youtube_job_busy_blocks_render(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    # Pretend active youtube job
    mgr._active_id = "busy"
    (s.sources_dir / "clip.mp4").write_bytes(b"x")
    with pytest.raises(BusyError, match="already in progress"):
        mgr.create(s, "clip.mp4", "Hi.\n", "en-US-EmmaNeural")


def test_run_youtube_job_success(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()

    def fake_download(url: str, dest: Path) -> Path:
        dest.write_bytes(b"video")
        return dest

    def fake_slice(settings, uploaded_path, base_stem):
        name = f"{base_stem}-1.mp4"
        path = settings.sources_dir / name
        path.write_bytes(b"slice")
        return [SourceVideo(name, path, path.stat().st_size)]

    monkeypatch.setattr("roblox_viral.web.jobs.download_youtube", fake_download)
    monkeypatch.setattr(
        "roblox_viral.web.jobs.slice_into_minute_parts", fake_slice
    )

    record = mgr.create_youtube(
        s, "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "gameplay"
    )
    assert record.kind == "youtube"
    assert record.status == "queued"
    mgr.run_youtube_job(s, record.id)
    done = mgr.get(record.id, s)
    assert done is not None
    assert done.status == "done"
    assert done.created_slices == ["gameplay-1.mp4"]
    assert (s.sources_dir / "gameplay-1.mp4").is_file()
    assert mgr._active_id is None
```

Also update any existing BusyError message assertions in `tests/web/test_jobs.py` / `test_api.py` from `"A render job is already in progress"` to `"A job is already in progress"` if the plan changes the string.

- [ ] **Step 2: Run tests — expect fail**

Run: `pytest tests/web/test_youtube_jobs.py -v`  
Expected: FAIL (`create_youtube` missing)

- [ ] **Step 3: Extend `jobs.py`**

Update imports and types:

```python
from typing import Literal

from roblox_viral.web.library import (
    make_output_name,
    resolve_source,
    slice_into_minute_parts,
)
from roblox_viral.web.youtube import (
    download_youtube,
    validate_stem,
    validate_youtube_url,
)

JobStatus = Literal[
    "queued",
    "synthesizing",
    "captioning",
    "rendering",
    "downloading",
    "slicing",
    "done",
    "error",
]
```

Extend `JobRecord`:

```python
@dataclass
class JobRecord:
    id: str
    status: JobStatus
    error: str | None
    source_name: str
    voice: str
    output_name: str | None
    created_at: str
    kind: str = "render"  # "render" | "youtube"
    url: str | None = None
    stem: str | None = None
    created_slices: list[str] | None = None
```

In `create`, change BusyError message to `"A job is already in progress"` and set `kind="render"` on the record.

Update `get` hydrate to:

```python
record = JobRecord(
    id=str(data["id"]),
    status=data["status"],
    error=data.get("error"),
    source_name=str(data.get("source_name") or ""),
    voice=str(data.get("voice") or ""),
    output_name=data.get("output_name"),
    created_at=str(data["created_at"]),
    kind=str(data.get("kind") or "render"),
    url=data.get("url"),
    stem=data.get("stem"),
    created_slices=data.get("created_slices"),
)
```

Add methods:

```python
def create_youtube(self, settings: Settings, url: str, stem: str) -> JobRecord:
    safe_url = validate_youtube_url(url)
    safe_stem = validate_stem(stem)

    with self._lock:
        if self._active_id is not None:
            raise BusyError("A job is already in progress")
        job_id = uuid.uuid4().hex
        record = JobRecord(
            id=job_id,
            status="queued",
            error=None,
            source_name="",
            voice="",
            output_name=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            kind="youtube",
            url=safe_url,
            stem=safe_stem,
            created_slices=None,
        )
        self._jobs[job_id] = record
        self._active_id = job_id

    try:
        (settings.jobs_dir / job_id).mkdir(parents=True, exist_ok=True)
        self._persist(settings, record)
    except Exception:
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None
            self._jobs.pop(job_id, None)
        raise
    return record


def run_youtube_job(self, settings: Settings, job_id: str) -> None:
    record = self._jobs.get(job_id)
    if record is None:
        raise KeyError(f"Unknown job: {job_id}")
    job_dir = settings.jobs_dir / job_id
    download_path = job_dir / "download.mp4"
    try:
        self._set_status(settings, record, "downloading")
        download_youtube(record.url or "", download_path)

        self._set_status(settings, record, "slicing")
        slices = slice_into_minute_parts(
            settings, download_path, record.stem or "video"
        )
        record.created_slices = [s.name for s in slices]
        self._set_status(settings, record, "done")
    except Exception as exc:
        record.error = str(exc)
        self._set_status(settings, record, "error")
    finally:
        download_path.unlink(missing_ok=True)
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None
```

- [ ] **Step 4: Fix existing busy-message assertions**

Search and replace test expectations for `"A render job is already in progress"` → `"A job is already in progress"`.

- [ ] **Step 5: Run tests**

Run: `pytest tests/web/test_youtube_jobs.py tests/web/test_jobs.py tests/web/test_api.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/roblox_viral/web/jobs.py tests/web/test_youtube_jobs.py tests/web/test_jobs.py tests/web/test_api.py
git commit -m "feat(web): YouTube import jobs share single-flight lock"
```

---

### Task 3: API route + Library UI

**Files:**
- Modify: `src/roblox_viral/web/app.py`
- Modify: `src/roblox_viral/web/templates/library.html`
- Create: `src/roblox_viral/web/static/library.js`
- Modify: `src/roblox_viral/web/static/app.css` (minimal form spacing if needed)
- Modify: `src/roblox_viral/web/static/app.js` (optional: update Generate busy message text)
- Create: `tests/web/test_youtube_api.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `JobManager.create_youtube`, `run_youtube_job`
- Produces: `POST /api/library/youtube` → `{ "id", "status" }`

- [ ] **Step 1: Write failing API tests**

```python
# tests/web/test_youtube_api.py
from fastapi.testclient import TestClient

from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings
from roblox_viral.web.jobs import JobManager
from roblox_viral.web.library import SourceVideo
from pathlib import Path


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    return TestClient(create_app(Settings.from_env()))


def _login(c: TestClient) -> None:
    r = c.post("/login", data={"password": "s3cret"}, follow_redirects=False)
    assert r.status_code in (302, 303)


def test_youtube_import_requires_auth(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert (
        c.post(
            "/api/library/youtube",
            json={"url": "https://youtu.be/dQw4w9WgXcQ", "name": "clip"},
        ).status_code
        == 401
    )


def test_youtube_import_rejects_bad_name(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    r = c.post(
        "/api/library/youtube",
        json={"url": "https://youtu.be/dQw4w9WgXcQ", "name": "bad.mp4"},
    )
    assert r.status_code == 400


def test_youtube_import_success(tmp_path, monkeypatch):
    def fake_download(url: str, dest: Path) -> Path:
        dest.write_bytes(b"vid")
        return dest

    def fake_slice(settings, uploaded_path, base_stem):
        name = f"{base_stem}-1.mp4"
        path = settings.sources_dir / name
        path.write_bytes(b"slice")
        return [SourceVideo(name, path, 5)]

    monkeypatch.setattr("roblox_viral.web.jobs.download_youtube", fake_download)
    monkeypatch.setattr(
        "roblox_viral.web.jobs.slice_into_minute_parts", fake_slice
    )

    c = _client(tmp_path, monkeypatch)
    _login(c)
    r = c.post(
        "/api/library/youtube",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "name": "gameplay",
        },
    )
    assert r.status_code == 200
    job_id = r.json()["id"]
    # BackgroundTasks run in TestClient
    status = c.get(f"/api/jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "done"
    assert body["created_slices"] == ["gameplay-1.mp4"]
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/web/test_youtube_api.py -v`  
Expected: FAIL (404)

- [ ] **Step 3: Add route in `app.py`**

```python
class YoutubeImportBody(BaseModel):
    url: str = ""
    name: str = ""
```

```python
@app.post("/api/library/youtube")
async def youtube_import(
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_login),
) -> dict:
    settings = request.app.state.settings
    mgr: JobManager = request.app.state.job_manager
    try:
        raw = await request.body()
        body = YoutubeImportBody.model_validate_json(raw)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    try:
        record = mgr.create_youtube(settings, body.url, body.name)
    except BusyError as exc:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(mgr.run_youtube_job, settings, record.id)
    return {"id": record.id, "status": record.status}
```

Ensure `asdict(record)` on GET already returns new fields.

- [ ] **Step 4: Update `library.html`**

After the upload form, add:

```html
  <h2>Import from YouTube</h2>
  <form id="youtube-form" class="upload-form">
    <label>
      YouTube URL
      <input id="youtube_url" name="url" type="url" required placeholder="https://www.youtube.com/watch?v=...">
    </label>
    <label>
      Name (slice prefix)
      <input id="youtube_name" name="name" type="text" required placeholder="gameplay" pattern="[A-Za-z0-9._ \-]+" title="Letters, numbers, spaces, . _ -">
    </label>
    <button id="youtube-btn" type="submit">Import from YouTube</button>
  </form>

  <section class="progress" aria-live="polite">
    <p>Import status: <span id="yt-status">idle</span></p>
    <p id="yt-error" class="error" hidden></p>
    <p id="yt-message" class="ok" hidden></p>
  </section>
```

At bottom of page:

```html
{% block scripts %}
  <script src="/static/library.js" defer></script>
{% endblock %}
```

(If `library.html` already has no scripts block, add it.)

- [ ] **Step 5: Create `library.js`**

```javascript
(() => {
  const form = document.getElementById("youtube-form");
  if (!form) return;

  const statusEl = document.getElementById("yt-status");
  const errorEl = document.getElementById("yt-error");
  const messageEl = document.getElementById("yt-message");
  const btn = document.getElementById("youtube-btn");
  let pollTimer = null;

  function setStatus(t) {
    statusEl.textContent = t;
  }
  function showError(msg) {
    errorEl.hidden = false;
    errorEl.textContent = msg;
    messageEl.hidden = true;
  }
  function showMessage(msg) {
    messageEl.hidden = false;
    messageEl.textContent = msg;
    errorEl.hidden = true;
  }
  function clearFeedback() {
    errorEl.hidden = true;
    errorEl.textContent = "";
    messageEl.hidden = true;
    messageEl.textContent = "";
  }
  function stopPolling() {
    if (pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function pollJob(jobId) {
    const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`Status request failed (${res.status})`);
    const job = await res.json();
    setStatus(job.status);
    if (job.status === "done") {
      stopPolling();
      btn.disabled = false;
      const slices = (job.created_slices || []).join(", ");
      showMessage(slices ? `Created: ${slices}` : "Import complete.");
      window.setTimeout(() => window.location.reload(), 800);
      return;
    }
    if (job.status === "error") {
      stopPolling();
      btn.disabled = false;
      showError(job.error || "Import failed");
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearFeedback();
    stopPolling();
    btn.disabled = true;
    setStatus("starting");
    try {
      const res = await fetch("/api/library/youtube", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          url: document.getElementById("youtube_url").value,
          name: document.getElementById("youtube_name").value,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.status === 409) {
        btn.disabled = false;
        setStatus("busy");
        showError(body.detail || "A job is already in progress");
        return;
      }
      if (!res.ok) {
        btn.disabled = false;
        setStatus("error");
        showError(body.detail || `Import failed (${res.status})`);
        return;
      }
      setStatus(body.status || "queued");
      pollTimer = setInterval(() => {
        pollJob(body.id).catch((err) => {
          stopPolling();
          btn.disabled = false;
          showError(err.message || String(err));
        });
      }, 1000);
      await pollJob(body.id);
    } catch (err) {
      btn.disabled = false;
      setStatus("error");
      showError(err.message || String(err));
    }
  });
})();
```

- [ ] **Step 6: Update Generate busy copy (optional but recommended)**

In `app.js`, if the 409 message still says “render job”, change fallback to `"A job is already in progress"`.

- [ ] **Step 7: README**

In web app section, note: Library can import a YouTube URL (background job; best MP4 ≤1080p; splits into 1-minute slices). Requires `yt-dlp` (installed with the package).

- [ ] **Step 8: Run full web tests**

Run: `pytest tests/web -v`  
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/roblox_viral/web/app.py src/roblox_viral/web/templates/library.html src/roblox_viral/web/static/library.js src/roblox_viral/web/static/app.js README.md tests/web/test_youtube_api.py
git commit -m "feat(web): YouTube import UI and API on Library"
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| yt-dlp dependency | Task 1 |
| validate URL + stem / rename | Task 1 |
| ≤1080p MP4 format | Task 1 |
| Shared single-flight with render | Task 2 |
| Import statuses downloading/slicing | Task 2 |
| Reuse minute slice | Task 2 |
| Temp under jobs/{id}, cleanup | Task 2 |
| POST /api/library/youtube | Task 3 |
| Poll GET /api/jobs/{id} | Task 2–3 |
| Library form + progress UI | Task 3 |
| 400/409/auth | Task 3 |
| Mocked tests | Task 1–3 |
| README | Task 3 |
| Upload unchanged | Task 3 (no upload edits) |
