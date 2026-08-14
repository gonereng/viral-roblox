# n8n Multipart Media Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change `POST /api/v1/videos` to multipart form-data so n8n can upload a video/image **or** pass Library `source_name`; uploaded roblox media is used as-is (no slicing).

**Architecture:** Add `JobRecord.ephemeral`; skip Library resolve when true; `run_job` reads `jobs/{id}/{source_name}`. API accepts Form fields + optional `UploadFile` `media` with XOR validation.

**Tech Stack:** FastAPI Form/File, existing library upload limits, pytest

## Global Constraints

- Multipart only on create (breaking vs JSON)
- Exactly one of `media` or `source_name`
- `leni` → picture; roblox upload → as-is, no Library slice
- Job-local file: `jobs/{id}/input.<ext>` (source_name stored as that filename)
- Size limits: `MAX_UPLOAD_BYTES` / `MAX_IMAGE_UPLOAD_BYTES`
- Spec: `docs/superpowers/specs/2026-08-14-n8n-media-upload-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/web/jobs.py` | `ephemeral` flag; create/run path resolution |
| `src/roblox_viral/web/api_v1.py` | Multipart create |
| `tests/web/test_jobs.py` | Ephemeral create/run |
| `tests/web/test_api_v1.py` | Multipart + XOR + migrate old JSON tests to form |
| `README.md` | Form-data examples |

---

### Task 1: JobManager ephemeral input

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`

**Interfaces:**
- Produces:
  - `JobRecord.ephemeral: bool = False`
  - `JobManager.create(..., ephemeral: bool = False)`
  - When `ephemeral=True`: do **not** call `resolve_source` / `resolve_image`; still validate `mode`; `source_name` must be a safe basename only (`Path(name).name == name` and match video or image regex based on mode)
  - Hydrate `ephemeral` from status.json (`bool(data.get("ephemeral", False))`)
  - `run_job`: if `record.ephemeral`: `media_path = (jobs_dir/job_id / record.source_name).resolve()`; require file under job_dir; else existing resolve_*

- [ ] **Step 1: Write failing tests**

```python
# append to tests/web/test_jobs.py
def test_create_ephemeral_skips_library(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    # no sources/images files
    job = mgr.create(
        s,
        "input.mp4",
        "One line only here.\n",
        "en-US-EmmaNeural",
        mode="roblox",
        ephemeral=True,
    )
    assert job.ephemeral is True
    assert job.source_name == "input.mp4"


def test_run_job_ephemeral_uses_job_dir_input(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    seen = {}

    def fake_synthesize(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [WordTiming("One", 0, 100)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_video(**kwargs):
        seen["video_path"] = Path(kwargs["video_path"])
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)

    job = mgr.create(
        s,
        "input.mp4",
        "One line only here.\n",
        "en-US-EmmaNeural",
        mode="roblox",
        ephemeral=True,
    )
    input_path = s.jobs_dir / job.id / "input.mp4"
    input_path.write_bytes(b"vid")
    mgr.run_job(s, job.id)
    assert mgr.get(job.id, s).status == "done"
    assert seen["video_path"] == input_path.resolve()
```

Adapt `_settings` / imports to match the file (`WordTiming`, `Path`).

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/web/test_jobs.py -k ephemeral -v`

- [ ] **Step 3: Implement**

In `JobRecord` add `ephemeral: bool = False`.

In `create`, add `ephemeral: bool = False` before building record:

```python
        if mode not in ("roblox", "picture"):
            raise ValueError(f"Invalid mode: {mode!r}")
        if ephemeral:
            safe = Path(source_name).name
            if safe != source_name or not safe:
                raise ValueError("Invalid source_name")
            if mode == "picture":
                from roblox_viral.web.library import _safe_image_name
                source_name = _safe_image_name(safe)
            else:
                from roblox_viral.web.library import _safe_name
                source_name = _safe_name(safe)
                ken_burns = False
        elif mode == "picture":
            resolve_image(settings, source_name)
        else:
            resolve_source(settings, source_name)
            ken_burns = False
```

Prefer exporting small public helpers instead of importing `_safe_*` if cleaner — e.g. add `validate_video_filename` / `validate_image_filename` in `library.py` that wrap `_safe_*`. Minimal approach: import `_safe_name` / `_safe_image_name` (already used pattern) OR call them via new public aliases:

```python
# library.py
def validate_video_filename(name: str) -> str:
    return _safe_name(name)

def validate_image_filename(name: str) -> str:
    return _safe_image_name(name)
```

Use those from jobs.

Pass `ephemeral=ephemeral` into `JobRecord(...)`.

In `get()` hydration add `ephemeral=bool(data.get("ephemeral", False))`.

In `run_job`:

```python
            job_dir = settings.jobs_dir / job_id
            ...
            if record.ephemeral:
                media_path = (job_dir / record.source_name).resolve()
                if not media_path.is_relative_to(job_dir.resolve()) or not media_path.is_file():
                    raise FileNotFoundError(record.source_name)
            elif record.mode == "picture":
                media_path = resolve_image(settings, record.source_name)
            else:
                media_path = resolve_source(settings, record.source_name)

            if record.mode == "picture":
                render_still(image_path=media_path, ...)
            else:
                render_video(video_path=media_path, ...)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/web/test_jobs.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/jobs.py src/roblox_viral/web/library.py tests/web/test_jobs.py
git commit -m "feat(web): ephemeral job-local media for renders"
```

---

### Task 2: Multipart create endpoint

**Files:**
- Modify: `src/roblox_viral/web/api_v1.py`
- Modify: `tests/web/test_api_v1.py`

**Interfaces:**
- Consumes: `JobManager.create(..., ephemeral=)`, upload byte helpers / limits from library
- Produces: multipart `POST /videos` with Form + File

- [ ] **Step 1: Rewrite/extend tests**

Change existing create tests from `json=` to `data=` form fields:

```python
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hello world.\n",
            "type": "roblox",
            "source_name": "clip.mp4",
        },
    )
```

Add:

```python
def test_create_with_media_upload_roblox(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        assert rec.ephemeral is True
        inp = settings.jobs_dir / job_id / rec.source_name
        assert inp.is_file()
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
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "roblox",
        },
        files={"media": ("clip.mp4", b"fake-video", "video/mp4")},
    )
    assert r.status_code == 200
    assert r.json()["id"]


def test_create_with_media_upload_leni(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        assert rec.mode == "picture"
        assert rec.ephemeral is True
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
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "leni",
        },
        files={"media": ("still.jpg", b"fake-img", "image/jpeg")},
    )
    assert r.status_code == 200
    st = c.get(f"/api/v1/videos/{r.json()['id']}", headers=_headers())
    assert st.json()["mode"] == "picture"


def test_create_rejects_both_media_and_source_name(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    (c.app.state.settings.sources_dir / "clip.mp4").write_bytes(b"vid")
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "roblox",
            "source_name": "clip.mp4",
        },
        files={"media": ("clip.mp4", b"x", "video/mp4")},
    )
    assert r.status_code == 400


def test_create_rejects_neither_media_nor_source(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "roblox",
        },
    )
    assert r.status_code == 400


def test_create_rejects_image_for_roblox(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "roblox",
        },
        files={"media": ("still.jpg", b"x", "image/jpeg")},
    )
    assert r.status_code == 400
```

- [ ] **Step 2: Run — expect FAIL** (JSON tests fail + new tests)

Run: `pytest tests/web/test_api_v1.py -v`

- [ ] **Step 3: Implement multipart handler**

Replace JSON body create with:

```python
from fastapi import File, Form, UploadFile
from roblox_viral.web import library as library_mod

@router.post("/videos")
async def create_video(
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_api_key),
    voice: str = Form(""),
    story: str = Form(""),
    type: str = Form(""),
    source_name: str = Form(""),
    media: UploadFile | None = File(None),
) -> dict:
    settings = request.app.state.settings
    mgr: JobManager = request.app.state.job_manager
    try:
        mode = _mode_from_type(type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    has_media = media is not None and bool(getattr(media, "filename", None))
    name = (source_name or "").strip()
    if has_media and name:
        raise HTTPException(
            status_code=400,
            detail="Provide either media file or source_name, not both",
        )
    if not has_media and not name:
        raise HTTPException(
            status_code=400,
            detail="Provide media file or source_name",
        )

    voice_s = (voice or "").strip() or DEFAULT_VOICE
    ephemeral = False
    input_bytes: bytes | None = None
    stored_name = name

    if has_media:
        assert media is not None
        raw_name = Path(media.filename or "upload.bin").name
        data = await media.read()
        try:
            if mode == "picture":
                if len(data) > library_mod.MAX_IMAGE_UPLOAD_BYTES:
                    raise ValueError(
                        f"Upload exceeds maximum size of "
                        f"{library_mod.MAX_IMAGE_UPLOAD_BYTES} bytes"
                    )
                stored_name = library_mod.validate_image_filename(raw_name)
            else:
                if len(data) > library_mod.MAX_UPLOAD_BYTES:
                    raise ValueError(
                        f"Upload exceeds maximum size of "
                        f"{library_mod.MAX_UPLOAD_BYTES} bytes"
                    )
                stored_name = library_mod.validate_video_filename(raw_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # Normalize to input.<ext>
        suffix = Path(stored_name).suffix.lower()
        stored_name = f"input{suffix}"
        ephemeral = True
        input_bytes = data

    try:
        record = mgr.create(
            settings,
            stored_name,
            story,
            voice_s,
            pitch=DEFAULT_PITCH,
            speed=DEFAULT_SPEED,
            mode=mode,
            ken_burns=False,
            ephemeral=ephemeral,
        )
    except BusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if input_bytes is not None:
        dest = settings.jobs_dir / record.id / record.source_name
        dest.write_bytes(input_bytes)

    background_tasks.add_task(mgr.run_job, settings, record.id)
    return {"id": record.id}
```

Remove unused `CreateVideoBody` if no longer needed.

Use capped read if preferred (reuse `_read_upload_capped` from app — either import/move helper to library or read-all then size-check as above). Size-check after read is OK for plan.

- [ ] **Step 4: Run tests**

Run: `pytest tests/web/test_api_v1.py tests/web/test_jobs.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/api_v1.py tests/web/test_api_v1.py
git commit -m "feat(web): accept multipart media on n8n video create"
```

---

### Task 3: README + PowerShell example

**Files:**
- Modify: `README.md`

**Interfaces:** docs only

- [ ] **Step 1: Update n8n API section**

Replace JSON create docs with form-data:

```markdown
### n8n API

Set `API_KEY` in `.env`. Header: `X-API-Key`.

**Create** — `POST /api/v1/videos` as `multipart/form-data`:

- `voice`, `story`, `type` (`roblox`|`leni`)
- either file field `media` **or** text field `source_name` (Library name)

Then poll `GET /api/v1/videos/{id}` and download `GET /api/v1/videos/{id}/download`.

PowerShell (upload):

```powershell
$headers = @{ "X-API-Key" = "your-key" }
$form = @{
  voice = "en-US-EmmaNeural"
  story = "Hello.`nWorld."
  type  = "roblox"
  media = Get-Item "C:\path\to\clip.mp4"
}
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/videos" -Headers $headers -Form $form
```

PowerShell (Library name):

```powershell
$form = @{
  voice = "en-US-EmmaNeural"
  story = "Hello.`nWorld."
  type  = "roblox"
  source_name = "gameplay-1.mp4"
}
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: n8n multipart upload examples"
```

---

## Self-review (plan vs spec)

| Spec | Task |
|------|------|
| Multipart + XOR media/source_name | Task 2 |
| Ephemeral job-local input, as-is roblox | Task 1–2 |
| leni image upload | Task 2 |
| Size limits | Task 2 |
| README examples | Task 3 |
| Status/download unchanged | Honored |

No placeholders. `ephemeral: bool` naming consistent across tasks.
