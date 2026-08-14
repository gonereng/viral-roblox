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

