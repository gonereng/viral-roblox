### Task 3: Picture-mode jobs

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`

**Interfaces:**
- Consumes: `resolve_image`, `render_still` from Tasks 1–2
- Produces:
  - `JobRecord.mode: str = "roblox"`
  - `JobRecord.ken_burns: bool = False`
  - `JobManager.create(..., mode: str = "roblox", ken_burns: bool = False)`
  - Invalid mode → `ValueError`
  - `mode=="picture"` → `resolve_image`; `mode=="roblox"` → `resolve_source` and force `ken_burns=False`
  - `run_job`: picture → `render_still(image_path=..., ken_burns=record.ken_burns)` with no overlay; roblox → existing `render_video` + overlay
  - Hydrate `mode` / `ken_burns` from `status.json` (defaults if missing)

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_jobs.py`:

```python
def test_create_picture_job_resolves_image(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.images_dir / "still.jpg").write_bytes(b"img")
    mgr = JobManager()
    job = mgr.create(
        s,
        "still.jpg",
        "Hello world.\n",
        "en-US-EmmaNeural",
        mode="picture",
        ken_burns=True,
    )
    assert job.mode == "picture"
    assert job.ken_burns is True
    assert job.kind == "render"
    assert job.source_name == "still.jpg"


def test_create_picture_rejects_video_name(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    with pytest.raises((ValueError, FileNotFoundError)):
        mgr.create(
            s, "clip.mp4", "Hello world.\n", "en-US-EmmaNeural", mode="picture"
        )


def test_create_roblox_ignores_ken_burns(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    job = mgr.create(
        s,
        "clip.mp4",
        "Hello world.\n",
        "en-US-EmmaNeural",
        ken_burns=True,
    )
    assert job.mode == "roblox"
    assert job.ken_burns is False


def test_create_rejects_unknown_mode(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    with pytest.raises(ValueError, match="mode"):
        mgr.create(
            s, "clip.mp4", "Hello world.\n", "en-US-EmmaNeural", mode="gif"
        )


def test_picture_job_blocks_second_of_either_mode(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.images_dir / "still.jpg").write_bytes(b"img")
    mgr = JobManager()
    mgr.create(
        s, "still.jpg", "Hello world.\n", "en-US-EmmaNeural", mode="picture"
    )
    with pytest.raises(BusyError):
        mgr.create(s, "clip.mp4", "Other.\n", "en-US-EmmaNeural")


def test_run_picture_job_calls_render_still(tmp_path, monkeypatch):
    from pathlib import Path

    s = _settings(tmp_path, monkeypatch)
    (s.images_dir / "still.jpg").write_bytes(b"img")
    mgr = JobManager()
    seen = {}

    def fake_synthesize(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [WordTiming("One", 0, 100)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_still(**kwargs):
        seen.update(kwargs)
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    def boom_video(**kwargs):
        raise AssertionError("render_video should not run for picture jobs")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_still", fake_render_still)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", boom_video)

    job = mgr.create(
        s,
        "still.jpg",
        "One line only here.\n",
        "en-US-EmmaNeural",
        mode="picture",
        ken_burns=True,
    )
    mgr.run_job(s, job.id)
    done = mgr.get(job.id, s)
    assert done.status == "done"
    assert done.output_name.endswith(".mp4")
    assert "still" in done.output_name
    assert seen["ken_burns"] is True
    assert "overlay_path" not in seen
    assert Path(seen["image_path"]).name == "still.jpg"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/web/test_jobs.py -v`

Expected: new tests FAIL (`create()` unexpected kwargs / no `mode`).

- [ ] **Step 3: Implement job fields and branching**

In `src/roblox_viral/web/jobs.py`:

1. Import `render_still` next to `render_video`.
2. Import `resolve_image` next to `resolve_source`.
3. Add fields on `JobRecord` after `speed`:

```python
    mode: str = "roblox"  # "roblox" | "picture"
    ken_burns: bool = False
```

4. Change `create` signature and validation (before the lock):

```python
    def create(
        self,
        settings: Settings,
        source_name: str,
        story: str,
        voice: str,
        pitch: int = DEFAULT_PITCH,
        speed: int = DEFAULT_SPEED,
        mode: str = "roblox",
        ken_burns: bool = False,
    ) -> JobRecord:
        format_edge_pitch(pitch)
        format_edge_rate(speed)
        if mode not in ("roblox", "picture"):
            raise ValueError(f"Invalid mode: {mode!r}")
        if mode == "picture":
            resolve_image(settings, source_name)
        else:
            resolve_source(settings, source_name)
            ken_burns = False
        sentences = split_sentences(story)
        if not sentences:
            raise ValueError("Story is empty")
```

5. Pass `mode=mode` and `ken_burns=ken_burns` into the `JobRecord(...)` constructor (keep `kind="render"`).

6. In `get()` hydration, after `speed=...`:

```python
                mode=str(data.get("mode") or "roblox"),
                ken_burns=bool(data.get("ken_burns", False)),
```

7. In `run_job`, replace the `video_path = resolve_source(...)` + `render_video(...)` block with:

```python
            job_dir = settings.jobs_dir / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            narration_path = job_dir / "narration.mp3"
            ass_path = job_dir / "captions.ass"
            output_name = make_output_name(record.source_name)
            output_path = settings.outputs_dir / output_name

            self._set_status(settings, record, "synthesizing")
            words = EdgeTTSProvider(
                record.voice,
                rate=format_edge_rate(record.speed),
                pitch=format_edge_pitch(record.pitch),
            ).synthesize(join_for_tts(sentences), narration_path)

            self._set_status(settings, record, "captioning")
            write_ass(words, ass_path, sentences=sentences)

            self._set_status(settings, record, "rendering")
            if record.mode == "picture":
                image_path = resolve_image(settings, record.source_name)
                render_still(
                    image_path=image_path,
                    audio_path=narration_path,
                    ass_path=ass_path,
                    output_path=output_path,
                    ken_burns=record.ken_burns,
                    work_dir=job_dir,
                )
            else:
                video_path = resolve_source(settings, record.source_name)
                render_video(
                    video_path=video_path,
                    audio_path=narration_path,
                    ass_path=ass_path,
                    output_path=output_path,
                    work_dir=job_dir,
                    overlay_path=settings.overlay_video_path,
                )
```

Keep the existing `record.output_name = output_name` / status `done` / except / finally.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/web/test_jobs.py -v`

Expected: PASS (existing roblox tests included).

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/jobs.py tests/web/test_jobs.py
git commit -m "feat(web): picture-mode jobs with optional Ken Burns"
```

---

