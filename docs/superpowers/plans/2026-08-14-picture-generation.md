# Picture Storytime Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Generate-page Picture mode that turns a still image plus the existing TTS/caption pipeline into a 1080×1920 storytime MP4, with an optional slow center zoom-in and no greenscreen overlay.

**Architecture:** Images live in `media/images/` with library helpers and `/api/images` upload/delete. Jobs gain `mode` (`roblox`|`picture`) and `ken_burns`. Shared TTS + ASS; Roblox still calls `render_video` (overlay allowed); Picture calls new `render_still` (`-loop 1`, optional `zoompan`). Generate page tabs swap only the source block.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, vanilla JS, ffmpeg, pytest

## Global Constraints

- Picture formats: `.jpg`, `.jpeg`, `.png`, `.webp`; upload cap **20 MB** (`MAX_IMAGE_UPLOAD_BYTES = 20_000_000`)
- Cover-crop to **1080×1920**; Ken Burns off by default; on = zoom **1.0 → 1.20** centered over full TTS duration at **30 fps**
- Picture jobs **never** pass overlay; Roblox overlay behavior unchanged
- `kind="render"` for both Generate modes; `mode` distinguishes them
- Omitted `mode` defaults to `"roblox"` (existing clients keep working)
- Roblox `ken_burns` is ignored (store `False`)
- CLI unchanged (no `--image`)
- Library page stays video-only
- Spec: `docs/superpowers/specs/2026-08-14-picture-generation-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/web/config.py` | `images_dir`; create it in `ensure_media_dirs` |
| `src/roblox_viral/web/library.py` | `SourceImage`, list/save/delete/resolve image helpers |
| `src/roblox_viral/render.py` | `render_still` (static + Ken Burns) |
| `src/roblox_viral/web/jobs.py` | `mode`, `ken_burns` on create/run/hydrate |
| `src/roblox_viral/web/app.py` | `/api/images`, job body `mode`/`ken_burns`, Generate `images` |
| `src/roblox_viral/web/templates/generate.html` | Roblox \| Picture tabs + image controls |
| `src/roblox_viral/web/static/app.js` | Tab switch, image upload/delete, job payload |
| `src/roblox_viral/web/static/app.css` | Tab + picture-source layout |
| `tests/web/test_config.py` | `images_dir` created |
| `tests/web/test_library.py` | Image helper tests |
| `tests/test_render.py` | `render_still` ffmpeg command tests |
| `tests/web/test_jobs.py` | Picture create/run + busy lock |
| `tests/web/test_api.py` | Image HTTP + job mode HTTP + Generate HTML |
| `README.md` | Picture tab usage |

---

### Task 1: Image library helpers

**Files:**
- Modify: `src/roblox_viral/web/config.py`
- Modify: `src/roblox_viral/web/library.py`
- Modify: `tests/web/test_config.py`
- Modify: `tests/web/test_library.py`

**Interfaces:**
- Consumes: `Settings.media_root`
- Produces:
  - `Settings.images_dir` → `self.media_root / "images"`
  - `MAX_IMAGE_UPLOAD_BYTES = 20_000_000`
  - `SourceImage(name: str, path: Path, size_bytes: int)`
  - `list_images(settings: Settings) -> list[SourceImage]`
  - `resolve_image(settings: Settings, name: str) -> Path`
  - `save_image(settings: Settings, filename: str, data: bytes) -> SourceImage`
  - `delete_image(settings: Settings, name: str) -> None`
  - Collision: if dest exists, `{stem}-{uuid.uuid4().hex[:8]}{suffix}`
  - Temp write then rename; unlink temp on failure

- [ ] **Step 1: Write failing tests**

Add to `tests/web/test_config.py` inside `test_ensure_media_dirs`:

```python
    assert settings.images_dir.is_dir()
```

Append to `tests/web/test_library.py`:

```python
def test_save_list_delete_image(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    saved = library.save_image(s, "photo.jpg", b"jpeg-bytes")
    assert saved.name == "photo.jpg"
    assert saved.path == s.images_dir / "photo.jpg"
    assert saved.path.read_bytes() == b"jpeg-bytes"
    listed = library.list_images(s)
    assert [i.name for i in listed] == ["photo.jpg"]
    assert library.resolve_image(s, "photo.jpg") == saved.path
    library.delete_image(s, "photo.jpg")
    assert library.list_images(s) == []


def test_save_image_unique_on_collision(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    first = library.save_image(s, "photo.jpg", b"a")
    second = library.save_image(s, "photo.jpg", b"b")
    assert first.name == "photo.jpg"
    assert second.name != "photo.jpg"
    assert second.name.startswith("photo-")
    assert second.name.endswith(".jpg")
    assert {first.name, second.name} == {i.name for i in library.list_images(s)}


def test_save_image_rejects_oversize_and_unsafe(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    monkeypatch.setattr(library, "MAX_IMAGE_UPLOAD_BYTES", 10)
    with pytest.raises(ValueError, match="maximum size"):
        library.save_image(s, "photo.jpg", b"x" * 11)
    assert list(s.images_dir.iterdir()) == []
    with pytest.raises(ValueError):
        library.save_image(s, "evil.exe", b"xx")
    with pytest.raises(ValueError):
        library.resolve_image(s, "../evil.jpg")
    with pytest.raises(ValueError):
        library.resolve_image(s, "clip.mp4")


def test_images_not_listed_as_video_sources(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    library.save_image(s, "still.png", b"png")
    (s.sources_dir / "clip.mp4").write_bytes(b"vid")
    assert [x.name for x in library.list_sources(s)] == ["clip.mp4"]
    assert [x.name for x in library.list_images(s)] == ["still.png"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/web/test_config.py::test_ensure_media_dirs tests/web/test_library.py -v`

Expected: `images_dir` assertion fails and image helper tests fail with `ImportError` / `AttributeError`.

- [ ] **Step 3: Implement helpers**

In `src/roblox_viral/web/config.py`, add property and include it in `ensure_media_dirs`:

```python
    @property
    def images_dir(self) -> Path:
        return self.media_root / "images"

    def ensure_media_dirs(self) -> None:
        for d in (self.sources_dir, self.images_dir, self.outputs_dir, self.jobs_dir):
            d.mkdir(parents=True, exist_ok=True)
```

In `src/roblox_viral/web/library.py`, add next to the video helpers:

```python
_SAFE_IMAGE_NAME = re.compile(r"^[A-Za-z0-9._ -]+\.(jpg|jpeg|png|webp)$", re.I)
MAX_IMAGE_UPLOAD_BYTES = 20_000_000


@dataclass(frozen=True)
class SourceImage:
    name: str
    path: Path
    size_bytes: int


def _safe_image_name(name: str) -> str:
    base = Path(name).name
    if base != name or not _SAFE_IMAGE_NAME.match(base):
        raise ValueError(f"Invalid image filename: {name!r}")
    return base


def list_images(settings: Settings) -> list[SourceImage]:
    items: list[SourceImage] = []
    if not settings.images_dir.is_dir():
        return items
    for path in sorted(settings.images_dir.iterdir()):
        if path.is_file() and _SAFE_IMAGE_NAME.match(path.name) and not path.name.startswith("."):
            items.append(SourceImage(path.name, path, path.stat().st_size))
    return items


def resolve_image(settings: Settings, name: str) -> Path:
    safe = _safe_image_name(name)
    path = (settings.images_dir / safe).resolve()
    if not path.is_relative_to(settings.images_dir.resolve()):
        raise ValueError("Invalid path")
    if not path.is_file():
        raise FileNotFoundError(safe)
    return path


def save_image(settings: Settings, filename: str, data: bytes) -> SourceImage:
    if len(data) > MAX_IMAGE_UPLOAD_BYTES:
        raise ValueError(
            f"Upload exceeds maximum size of {MAX_IMAGE_UPLOAD_BYTES} bytes"
        )
    safe = _safe_image_name(filename)
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.images_dir / safe
    if dest.exists():
        dest = settings.images_dir / f"{Path(safe).stem}-{uuid.uuid4().hex[:8]}{Path(safe).suffix.lower()}"
    temp = settings.images_dir / f".upload-{uuid.uuid4().hex}{Path(safe).suffix.lower()}"
    try:
        temp.write_bytes(data)
        temp.replace(dest)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return SourceImage(dest.name, dest, dest.stat().st_size)


def delete_image(settings: Settings, name: str) -> None:
    resolve_image(settings, name).unlink()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/web/test_config.py::test_ensure_media_dirs tests/web/test_library.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/config.py src/roblox_viral/web/library.py tests/web/test_config.py tests/web/test_library.py
git commit -m "feat(web): image library helpers under media/images"
```

---

### Task 2: `render_still`

**Files:**
- Modify: `src/roblox_viral/render.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- Consumes: `OUTPUT_WIDTH`, `OUTPUT_HEIGHT`, `probe_duration_seconds`, `_ass_filter_path`, `require_ffmpeg`
- Produces:
  - `KEN_BURNS_ZOOM = 1.20`
  - `KEN_BURNS_FPS = 30`
  - `render_still(*, image_path, audio_path, ass_path, output_path, ken_burns: bool = False, work_dir=None) -> Path`
  - No overlay argument
  - Static vf: `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,ass='...'`
  - Ken Burns: cover-scale to `1296x2304` (`1080*1.20` × `1920*1.20`), `zoompan` 1.0→1.20 over `max(1, round(duration * 30))` frames, `s=1080x1920`, then `ass`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_render.py`:

```python
from roblox_viral.render import render_still


def test_render_still_static_loops_image_no_overlay(tmp_path, monkeypatch):
    image = _touch(tmp_path / "still.jpg")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    out = tmp_path / "out.mp4"
    seen = {}

    monkeypatch.setattr("roblox_viral.render.probe_duration_seconds", lambda _p: 2.5)
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"mp4")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)

    render_still(
        image_path=image,
        audio_path=audio,
        ass_path=ass,
        output_path=out,
        ken_burns=False,
    )
    cmd = seen["cmd"]
    assert cmd.count("-i") == 2
    assert "-loop" in cmd
    assert cmd[cmd.index("-loop") + 1] == "1"
    assert "-framerate" in cmd
    assert str(image) in cmd
    assert str(audio) in cmd
    assert "-vf" in cmd
    vf = cmd[cmd.index("-vf") + 1]
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in vf
    assert "crop=1080:1920" in vf
    assert "zoompan" not in vf
    assert "-filter_complex" not in cmd
    assert "chromakey" not in " ".join(cmd)
    assert "0:v:0" in cmd
    assert "1:a:0" in cmd
    assert "-t" in cmd


def test_render_still_ken_burns_uses_zoompan(tmp_path, monkeypatch):
    image = _touch(tmp_path / "still.png")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    out = tmp_path / "out.mp4"
    seen = {}

    monkeypatch.setattr("roblox_viral.render.probe_duration_seconds", lambda _p: 2.0)
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"mp4")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)

    render_still(
        image_path=image,
        audio_path=audio,
        ass_path=ass,
        output_path=out,
        ken_burns=True,
    )
    cmd = seen["cmd"]
    vf = cmd[cmd.index("-vf") + 1]
    assert "zoompan" in vf
    assert "1.20" in vf or "1.2" in vf
    assert "s=1080x1920" in vf
    assert "fps=30" in vf
    assert "crop=1296:2304" in vf
    assert cmd.count("-i") == 2


def test_render_still_missing_image_raises(tmp_path, monkeypatch):
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    monkeypatch.setattr("roblox_viral.render.probe_duration_seconds", lambda _p: 1.0)
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")
    with pytest.raises(RenderError, match="Image"):
        render_still(
            image_path=tmp_path / "missing.jpg",
            audio_path=audio,
            ass_path=ass,
            output_path=tmp_path / "out.mp4",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_render.py -v`

Expected: existing overlay tests PASS; new tests FAIL (`render_still` not defined).

- [ ] **Step 3: Implement `render_still`**

Add constants and function in `src/roblox_viral/render.py` after the overlay constants:

```python
KEN_BURNS_ZOOM = 1.20
KEN_BURNS_FPS = 30
```

Add after `render_video`:

```python
def render_still(
    *,
    image_path: Path | str,
    audio_path: Path | str,
    ass_path: Path | str,
    output_path: Path | str,
    ken_burns: bool = False,
    work_dir: Path | str | None = None,
) -> Path:
    """Hold (or Ken-Burns zoom) an image for TTS duration; burn ASS; mux TTS. No overlay."""
    ffmpeg = require_ffmpeg()
    image = Path(image_path)
    audio = Path(audio_path)
    ass = Path(ass_path)
    out = Path(output_path)

    if not image.is_file():
        raise RenderError(f"Image not found: {image}")
    if not audio.is_file():
        raise RenderError(f"Audio not found: {audio}")
    if not ass.is_file():
        raise RenderError(f"Captions not found: {ass}")

    out.parent.mkdir(parents=True, exist_ok=True)
    if work_dir is not None:
        Path(work_dir).mkdir(parents=True, exist_ok=True)

    audio_duration = probe_duration_seconds(audio)
    ass_escaped = _ass_filter_path(ass)

    if ken_burns:
        cover_w = int(OUTPUT_WIDTH * KEN_BURNS_ZOOM)
        cover_h = int(OUTPUT_HEIGHT * KEN_BURNS_ZOOM)
        frames = max(1, round(audio_duration * KEN_BURNS_FPS))
        zoom_delta = KEN_BURNS_ZOOM - 1.0
        vf = (
            f"scale={cover_w}:{cover_h}:force_original_aspect_ratio=increase,"
            f"crop={cover_w}:{cover_h},"
            f"zoompan=z='min(1+{zoom_delta}*on/{frames},{KEN_BURNS_ZOOM})':"
            f"d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:fps={KEN_BURNS_FPS},"
            f"ass='{ass_escaped}'"
        )
    else:
        vf = (
            f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},"
            f"ass='{ass_escaped}'"
        )

    cmd = [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-framerate",
        str(KEN_BURNS_FPS),
        "-i",
        str(image),
        "-i",
        str(audio),
        "-t",
        f"{audio_duration:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(out),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RenderError(
            "ffmpeg render failed:\n"
            + (result.stderr[-2000:] if result.stderr else "no stderr")
        )
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_render.py -v`

Expected: PASS (including existing overlay tests).

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/render.py tests/test_render.py
git commit -m "feat: render still images to vertical storytime video"
```

---

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

### Task 4: Image HTTP API and job `mode` on `/api/jobs`

**Files:**
- Modify: `src/roblox_viral/web/app.py`
- Modify: `tests/web/test_api.py`

**Interfaces:**
- Consumes: `save_image`, `delete_image`, `list_images`, `MAX_IMAGE_UPLOAD_BYTES`, `JobManager.create(..., mode=, ken_burns=)`
- Produces:
  - `POST /api/images` multipart `file` → `{ "name": str }` (auth); cap with `MAX_IMAGE_UPLOAD_BYTES`
  - `DELETE /api/images/{name}` → `{ "ok": true }`; missing → 404; bad name → 400
  - `CreateJobBody.mode: str = "roblox"`, `ken_burns: bool = False`
  - Generate page context includes `images=list_images(settings)`

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_api.py`:

```python
def test_image_upload_requires_auth(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post(
        "/api/images",
        files={"file": ("photo.jpg", b"xx", "image/jpeg")},
    )
    assert r.status_code == 401


def test_image_upload_list_on_generate_and_delete(tmp_path, monkeypatch):
    async def fake_voices():
        return [VoiceInfo("en-US-EmmaNeural", "en-US", "Female")]

    monkeypatch.setattr("roblox_viral.web.app.list_english_voices", fake_voices)
    c = _client(tmp_path, monkeypatch)
    _login(c)
    upload = c.post(
        "/api/images",
        files={"file": ("photo.jpg", b"jpeg-bytes", "image/jpeg")},
    )
    assert upload.status_code == 200
    assert upload.json()["name"] == "photo.jpg"

    page = c.get("/")
    assert page.status_code == 200
    assert "photo.jpg" in page.text

    deleted = c.delete("/api/images/photo.jpg")
    assert deleted.status_code == 200
    assert "photo.jpg" not in c.get("/").text


def test_image_upload_rejects_oversize_and_type(tmp_path, monkeypatch):
    from roblox_viral.web import library

    monkeypatch.setattr(library, "MAX_IMAGE_UPLOAD_BYTES", 100)
    c = _client(tmp_path, monkeypatch)
    _login(c)
    oversize = c.post(
        "/api/images",
        files={"file": ("photo.jpg", b"x" * 150, "image/jpeg")},
    )
    assert oversize.status_code == 400
    bad = c.post(
        "/api/images",
        files={"file": ("clip.mp4", b"xx", "video/mp4")},
    )
    assert bad.status_code == 400
    missing = c.delete("/api/images/nope.jpg")
    assert missing.status_code == 404


def test_create_picture_job(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    settings = c.app.state.settings
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    (settings.images_dir / "still.jpg").write_bytes(b"img")

    def fake_run_job(self: JobManager, settings: Settings, job_id: str) -> None:
        record = self.get(job_id)
        assert record is not None
        record.output_name = f"{job_id}.mp4"
        out = settings.outputs_dir / record.output_name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake-mp4")
        record.status = "done"
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run_job)

    r = c.post(
        "/api/jobs",
        json={
            "mode": "picture",
            "source_name": "still.jpg",
            "story": "Hi there.\n",
            "voice": "en-US-EmmaNeural",
            "ken_burns": True,
        },
    )
    assert r.status_code == 200
    polled = c.get(f"/api/jobs/{r.json()['id']}")
    assert polled.json()["mode"] == "picture"
    assert polled.json()["ken_burns"] is True


def test_create_job_mode_source_mismatch_400(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    _seed_source(c)
    settings = c.app.state.settings
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    (settings.images_dir / "still.jpg").write_bytes(b"img")

    roblox_with_image = c.post(
        "/api/jobs",
        json={
            "mode": "roblox",
            "source_name": "still.jpg",
            "story": "Hi.\n",
            "voice": "en-US-EmmaNeural",
        },
    )
    assert roblox_with_image.status_code == 400

    picture_with_video = c.post(
        "/api/jobs",
        json={
            "mode": "picture",
            "source_name": "clip.mp4",
            "story": "Hi.\n",
            "voice": "en-US-EmmaNeural",
        },
    )
    assert picture_with_video.status_code == 400

    unknown = c.post(
        "/api/jobs",
        json={
            "mode": "gif",
            "source_name": "clip.mp4",
            "story": "Hi.\n",
            "voice": "en-US-EmmaNeural",
        },
    )
    assert unknown.status_code == 400


def test_create_roblox_job_ignores_ken_burns(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    _seed_source(c)

    def fake_run_job(self: JobManager, settings: Settings, job_id: str) -> None:
        record = self.get(job_id)
        assert record is not None
        record.status = "done"
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run_job)
    r = c.post(
        "/api/jobs",
        json={
            "source_name": "clip.mp4",
            "story": "Hi.\n",
            "voice": "en-US-EmmaNeural",
            "ken_burns": True,
        },
    )
    assert r.status_code == 200
    data = c.get(f"/api/jobs/{r.json()['id']}").json()
    assert data["mode"] == "roblox"
    assert data["ken_burns"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/web/test_api.py -v`

Expected: new tests FAIL (404 on `/api/images`, jobs ignore `mode`).

- [ ] **Step 3: Wire routes and job body**

In `src/roblox_viral/web/app.py`:

1. Expand the library import:

```python
from roblox_viral.web.library import (
    delete_image,
    delete_source,
    list_images,
    list_outputs,
    list_sources,
    save_image,
    save_upload,
)
```

2. Extend `CreateJobBody`:

```python
class CreateJobBody(BaseModel):
    source_name: str = ""
    story: str = ""
    voice: str | None = None
    pitch: int | None = None
    speed: int | None = None
    mode: str = "roblox"
    ken_burns: bool = False
```

3. In `generate_page` context, add `"images": list_images(settings)`.

4. Pass mode/ken_burns into `mgr.create`:

```python
            record = mgr.create(
                settings,
                source_name,
                story,
                voice,
                pitch=pitch,
                speed=speed,
                mode=body.mode,
                ken_burns=body.ken_burns,
            )
```

5. Add routes (near other `/api/` routes, auth required):

```python
    @app.post("/api/images")
    async def upload_image(
        request: Request,
        file: UploadFile = File(...),
        _: None = Depends(require_login),
    ) -> dict:
        settings = request.app.state.settings
        filename = file.filename or ""
        try:
            data = await _read_upload_capped(
                file, library_mod.MAX_IMAGE_UPLOAD_BYTES
            )
            saved = save_image(settings, filename, data)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"name": saved.name}

    @app.delete("/api/images/{name}")
    def remove_image(
        name: str,
        request: Request,
        _: None = Depends(require_login),
    ) -> dict:
        settings = request.app.state.settings
        try:
            delete_image(settings, name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/web/test_api.py tests/web/test_jobs.py -v`

Expected: PASS. Existing create-job tests still work with omitted `mode`.

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/app.py tests/web/test_api.py
git commit -m "feat(web): image upload API and picture job mode"
```

---

### Task 5: Generate UI tabs + README

**Files:**
- Modify: `src/roblox_viral/web/templates/generate.html`
- Modify: `src/roblox_viral/web/static/app.js`
- Modify: `src/roblox_viral/web/static/app.css`
- Modify: `README.md`
- Modify: `tests/web/test_api.py`

**Interfaces:**
- Consumes: `images` template var; `POST /api/images`; `DELETE /api/images/{name}`; job `mode` / `ken_burns`
- Produces: Roblox tab default; Picture tab with `#image_name`, `#image-file`, `#image-upload-btn`, `#image-delete-btn`, `#ken_burns`; JS posts the active mode

- [ ] **Step 1: Write failing HTML tests**

Append to `tests/web/test_api.py`:

```python
def test_generate_page_has_picture_tab_controls(tmp_path, monkeypatch):
    async def fake_voices():
        return [VoiceInfo("en-US-EmmaNeural", "en-US", "Female")]

    monkeypatch.setattr("roblox_viral.web.app.list_english_voices", fake_voices)
    c = _client(tmp_path, monkeypatch)
    _login(c)
    settings = c.app.state.settings
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    (settings.images_dir / "still.jpg").write_bytes(b"img")
    r = c.get("/")
    assert r.status_code == 200
    assert 'id="tab-roblox"' in r.text
    assert 'id="tab-picture"' in r.text
    assert 'id="image_name"' in r.text
    assert "still.jpg" in r.text
    assert 'id="ken_burns"' in r.text
    assert 'id="image-file"' in r.text
    assert 'id="image-delete-btn"' in r.text
    # Ken Burns lives in the picture block, not the roblox source block
    roblox_idx = r.text.index('id="roblox-source-block"')
    picture_idx = r.text.index('id="picture-source-block"')
    ken_idx = r.text.index('id="ken_burns"')
    assert picture_idx < ken_idx
    assert "ken_burns" not in r.text[roblox_idx:picture_idx]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_api.py::test_generate_page_has_picture_tab_controls -v`

Expected: FAIL (ids missing).

- [ ] **Step 3: Implement UI, JS, CSS, README**

Replace the lede + source `<label>` in `src/roblox_viral/web/templates/generate.html` with:

```html
  <h1>Generate</h1>
  <p class="lede">Pick a Roblox clip or a still image, paste a story (one sentence per line), choose a voice.</p>

  <form id="generate-form" class="generate-form">
    <div class="mode-tabs" role="tablist">
      <button type="button" role="tab" id="tab-roblox" data-mode="roblox" aria-selected="true">Roblox</button>
      <button type="button" role="tab" id="tab-picture" data-mode="picture" aria-selected="false">Picture</button>
    </div>

    <div id="roblox-source-block">
      <label>
        Source video
        <select id="source_name" name="source_name">
          {% if not sources %}
          <option value="" disabled selected>No sources — upload in Library</option>
          {% else %}
          {% for s in sources %}
          <option value="{{ s.name }}">{{ s.name }}</option>
          {% endfor %}
          {% endif %}
        </select>
      </label>
    </div>

    <div id="picture-source-block" hidden>
      <label>
        Source image
        <select id="image_name" name="image_name">
          {% if not images %}
          <option value="" disabled selected>No images — upload below</option>
          {% else %}
          {% for img in images %}
          <option value="{{ img.name }}">{{ img.name }}</option>
          {% endfor %}
          {% endif %}
        </select>
      </label>
      <div class="image-actions">
        <label>
          Upload image
          <input id="image-file" type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp">
        </label>
        <button id="image-upload-btn" type="button">Upload</button>
        <button id="image-delete-btn" type="button"{% if not images %} disabled{% endif %}>Delete</button>
      </div>
      <p id="image-error" class="error" hidden></p>
      <label class="checkbox-field">
        <input id="ken_burns" name="ken_burns" type="checkbox">
        Ken Burns (slow zoom-in)
      </label>
    </div>
```

Keep story / voice / pitch / speed / generate button as they are. Change the generate button to:

```html
    <button id="generate-btn" type="submit"{% if not sources %} disabled{% endif %}>Generate</button>
```

(Roblox is the default tab, so disable when there are no videos — JS will recompute on tab switch.)

In `src/roblox_viral/web/static/app.css` add:

```css
.mode-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.mode-tabs button {
  background: transparent;
  color: var(--muted);
  border: 1px solid var(--line);
}

.mode-tabs button[aria-selected="true"] {
  background: var(--accent);
  color: var(--accent-ink);
  border-color: var(--accent);
}

.image-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 0.75rem;
  margin: 0 0 1rem;
}

.checkbox-field {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
```

In `src/roblox_viral/web/static/app.js`, after the voice slider setup and before `const form = ...` is fine; add tab + image helpers, and change the job payload. Insert this block after `syncVoiceSliders()` setup:

```javascript
  const tabRoblox = document.getElementById("tab-roblox");
  const tabPicture = document.getElementById("tab-picture");
  const robloxBlock = document.getElementById("roblox-source-block");
  const pictureBlock = document.getElementById("picture-source-block");
  const sourceSelect = document.getElementById("source_name");
  const imageSelect = document.getElementById("image_name");
  const imageFile = document.getElementById("image-file");
  const imageUploadBtn = document.getElementById("image-upload-btn");
  const imageDeleteBtn = document.getElementById("image-delete-btn");
  const imageErr = document.getElementById("image-error");
  const kenBurnsEl = document.getElementById("ken_burns");
  let currentMode = "roblox";

  function showImageError(message) {
    if (!imageErr) return;
    imageErr.hidden = false;
    imageErr.textContent = message;
  }
  function clearImageError() {
    if (!imageErr) return;
    imageErr.hidden = true;
    imageErr.textContent = "";
  }
  function imageSelectHasValue() {
    return Boolean(imageSelect && imageSelect.value);
  }
  function syncGenerateEnabled() {
    if (!generateBtn) return;
    if (currentMode === "picture") {
      generateBtn.disabled = !imageSelectHasValue();
    } else {
      generateBtn.disabled = !(sourceSelect && sourceSelect.value);
    }
  }
  function setMode(mode) {
    currentMode = mode;
    const isPicture = mode === "picture";
    if (robloxBlock) robloxBlock.hidden = isPicture;
    if (pictureBlock) pictureBlock.hidden = !isPicture;
    if (tabRoblox) tabRoblox.setAttribute("aria-selected", isPicture ? "false" : "true");
    if (tabPicture) tabPicture.setAttribute("aria-selected", isPicture ? "true" : "false");
    syncGenerateEnabled();
  }
  if (tabRoblox) tabRoblox.addEventListener("click", () => setMode("roblox"));
  if (tabPicture) tabPicture.addEventListener("click", () => setMode("picture"));

  if (imageUploadBtn && imageFile && imageSelect) {
    imageUploadBtn.addEventListener("click", async () => {
      clearImageError();
      const file = imageFile.files && imageFile.files[0];
      if (!file) {
        showImageError("Choose an image file first");
        return;
      }
      const data = new FormData();
      data.append("file", file, file.name);
      imageUploadBtn.disabled = true;
      try {
        const res = await fetch("/api/images", {
          method: "POST",
          headers: { Accept: "application/json" },
          body: data,
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          showImageError(body.detail || `Upload failed (${res.status})`);
          return;
        }
        const empty = imageSelect.querySelector("option[disabled]");
        if (empty) empty.remove();
        const opt = document.createElement("option");
        opt.value = body.name;
        opt.textContent = body.name;
        imageSelect.append(opt);
        imageSelect.value = body.name;
        if (imageDeleteBtn) imageDeleteBtn.disabled = false;
        imageFile.value = "";
        syncGenerateEnabled();
      } catch (err) {
        showImageError(err.message || String(err));
      } finally {
        imageUploadBtn.disabled = false;
      }
    });
  }

  if (imageDeleteBtn && imageSelect) {
    imageDeleteBtn.addEventListener("click", async () => {
      clearImageError();
      const name = imageSelect.value;
      if (!name) return;
      imageDeleteBtn.disabled = true;
      try {
        const res = await fetch("/api/images/" + encodeURIComponent(name), {
          method: "DELETE",
          headers: { Accept: "application/json" },
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          showImageError(body.detail || `Delete failed (${res.status})`);
          imageDeleteBtn.disabled = false;
          return;
        }
        const opt = imageSelect.querySelector('option[value="' + CSS.escape(name) + '"]');
        if (opt) opt.remove();
        if (!imageSelect.options.length) {
          const placeholder = document.createElement("option");
          placeholder.value = "";
          placeholder.disabled = true;
          placeholder.selected = true;
          placeholder.textContent = "No images — upload below";
          imageSelect.append(placeholder);
          imageDeleteBtn.disabled = true;
        } else {
          imageSelect.selectedIndex = 0;
          imageDeleteBtn.disabled = false;
        }
        syncGenerateEnabled();
      } catch (err) {
        showImageError(err.message || String(err));
        imageDeleteBtn.disabled = false;
      }
    });
  }
```

Move `const generateBtn = document.getElementById("generate-btn");` **above** this tab block (it is currently declared later). Cut it from its later position so it exists before `syncGenerateEnabled`.

Replace the job `payload` object with:

```javascript
    const payload = {
      mode: currentMode,
      source_name:
        currentMode === "picture"
          ? document.getElementById("image_name").value
          : document.getElementById("source_name").value,
      story: document.getElementById("story").value,
      voice: document.getElementById("voice").value,
      pitch: Number(document.getElementById("pitch").value),
      speed: Number(document.getElementById("speed").value),
      ken_burns:
        currentMode === "picture" &&
        Boolean(document.getElementById("ken_burns") && document.getElementById("ken_burns").checked),
    };
```

In `README.md` web-app intro paragraph, after the Library sentence, add:

```markdown
On **Generate**, switch **Roblox** (gameplay clip from Library) or **Picture** (upload a still on that tab: jpg/png/webp). Picture videos use the same story, voice, pitch, and speed; optional **Ken Burns** slowly zooms in. The greenscreen overlay applies to Roblox videos only.
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/web/test_api.py tests/web/test_jobs.py tests/test_render.py tests/web/test_library.py tests/web/test_config.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/templates/generate.html src/roblox_viral/web/static/app.js src/roblox_viral/web/static/app.css tests/web/test_api.py README.md
git commit -m "feat(web): Roblox and Picture tabs on Generate"
```

---

## Self-review

**Spec coverage:** Image dir + helpers (T1), `render_still` static/Ken Burns/no overlay (T2), job mode + busy lock + run branch (T3), `/api/images` + job HTTP mode mismatch (T4), Generate tabs/upload/delete/Ken Burns + README (T5). CLI, overlay-on-picture, Library mixing, letterbox: explicitly out of scope.

**Placeholders:** none.

**Types:** `mode: str` (`"roblox"`|`"picture"`), `ken_burns: bool`, `SourceImage`, `render_still(..., ken_burns: bool = False)`, `MAX_IMAGE_UPLOAD_BYTES = 20_000_000` used by helpers and `_read_upload_capped`.
