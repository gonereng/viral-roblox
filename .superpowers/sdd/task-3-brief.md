### Task 3: Cover API + README + n8n reddit stories

**Files:**
- Modify: `src/roblox_viral/web/api_v1.py`
- Modify: `tests/web/test_api_v1.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `JobRecord.title_card_name`, `settings.outputs_dir`
- Produces: `GET /api/v1/videos/{video_id}/cover` with the same auth and status mapping as `/download`, but `media_type="image/png"`

- [ ] **Step 1: Write failing tests**

In `tests/web/test_api_v1.py`, change reddit create stories `"Hi.\n"` to `"Hi - there.\n"` in `test_create_reddit_with_story_voice_type`, `test_create_reddit_rejects_media`, `test_create_reddit_rejects_source_name`.

Append:

```python
def test_cover_requires_api_key(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/v1/videos/" + "a" * 32 + "/cover")
    assert r.status_code == 401


def test_cover_done_returns_png(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        rec.status = "done"
        rec.output_name = f"{job_id}.mp4"
        rec.title_card_name = f"{job_id}-card.png"
        settings.outputs_dir.mkdir(parents=True, exist_ok=True)
        (settings.outputs_dir / rec.output_name).write_bytes(b"mp4")
        (settings.outputs_dir / rec.title_card_name).write_bytes(b"png-bytes")
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    job_id = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Top - Bottom.\n",
            "type": "reddit",
        },
    ).json()["id"]
    r = c.get(f"/api/v1/videos/{job_id}/cover", headers=_headers())
    assert r.status_code == 200
    assert r.content == b"png-bytes"
    assert "image/png" in r.headers.get("content-type", "")


def test_cover_not_ready_409(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")
    monkeypatch.setattr(JobManager, "run_job", lambda *a, **k: None)
    mgr: JobManager = c.app.state.job_manager
    rec = mgr.create(
        settings, "", "Top - Bottom.\n", "en-US-EmmaNeural", mode="reddit"
    )
    with mgr._lock:
        mgr._active_id = None
    r = c.get(f"/api/v1/videos/{rec.id}/cover", headers=_headers())
    assert r.status_code == 409


def test_cover_error_422(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")
    mgr: JobManager = c.app.state.job_manager
    rec = mgr.create(
        settings, "", "Top - Bottom.\n", "en-US-EmmaNeural", mode="reddit"
    )
    rec.status = "error"
    rec.error = "boom"
    with mgr._lock:
        mgr._active_id = None
    r = c.get(f"/api/v1/videos/{rec.id}/cover", headers=_headers())
    assert r.status_code == 422


def test_cover_single_done_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        rec.status = "done"
        rec.output_name = f"{job_id}.mp4"
        (settings.outputs_dir / rec.output_name).write_bytes(b"mp4")
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    job_id = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
            "source_name": "clip.mp4",
        },
    ).json()["id"]
    r = c.get(f"/api/v1/videos/{job_id}/cover", headers=_headers())
    assert r.status_code == 404


def test_cover_unknown_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get(
        "/api/v1/videos/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/cover",
        headers=_headers(),
    )
    assert r.status_code == 404
```

Also add (web session API already returns 400 via `create`):

```python
def test_create_reddit_rejects_story_without_hook_dash(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "reddit",
        },
    )
    assert r.status_code == 400
    assert "phrase - phrase" in r.json()["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/web/test_api_v1.py -k "cover or reddit" -v`

Expected: cover routes 404; `"Hi.\n"` reddit creates fail 400 until stories are updated (update stories in Step 1 first so only missing `/cover` fails).

- [ ] **Step 3: Implement the route**

In `src/roblox_viral/web/api_v1.py`, after `download_video`:

```python
@router.get("/videos/{video_id}/cover")
def download_cover(
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
    if record.status != "done":
        raise HTTPException(status_code=409, detail="Video not ready")
    name = record.title_card_name
    if not name:
        raise HTTPException(status_code=404, detail="Cover not found")
    safe = Path(name).name
    if safe != name:
        raise HTTPException(status_code=400, detail="Invalid cover name")
    path = (settings.outputs_dir / safe).resolve()
    if not path.is_relative_to(settings.outputs_dir.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="Cover file missing")
    return FileResponse(path, media_type="image/png", filename=safe)
```

In `README.md`:

- Replace the Reddit paragraph that mentions the ~2× screenshot with:

```markdown
**Reddit** shows a title card with the first story line, centered until that sentence finishes in the narration. The in-video card is unchanged. After generate, **Download title card** is a cover PNG: the packaged Snoo template with the first story line split on a single `-` (`phrase - phrase`) drawn in the two boxes. n8n: `GET /api/v1/videos/{id}/cover`.
```

- After the download bullet in n8n API, add: then download the cover with `GET /api/v1/videos/{id}/cover` (Reddit only; 404 for other types).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/web/test_api_v1.py tests/web/test_jobs.py tests/test_hook_cover.py tests/test_reddit_card.py -v`

Expected: PASS. Then full suite: `python -m pytest -q`

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/api_v1.py tests/web/test_api_v1.py README.md
git commit -m "feat(web): n8n cover download endpoint for Reddit hook PNG"
```

---

## Self-review

**Spec coverage:** split_hook (T1), boxes/text/template (T1), no 2× screenshot (T2), title_card_name (T2), overlay 1× (T2), create 400 (T2/T3), GET cover codes (T3), README (T3), UI `#download-card` unchanged (no task — already exists). Generate HTML needs no change.

**Placeholders:** none.

**Types:** `split_hook(line: str) -> tuple[str, str]`; `render_hook_cover(top, bottom, output_path, *, template_path=None) -> Path`; cover route uses `title_card_name`.
