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

