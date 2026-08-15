# Library Tabs, Raw Videos & Video Speed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Roblox-only gameplay `video_speed` (50–200%, default 100), restructure Library into three tabs (1‑minute slices / raw videos / images), remove YouTube import, and align the n8n API.

**Architecture:** Validate `video_speed` in `voice.py`; apply ffmpeg `setpts` inside `render_video` when ≠100. Store raw uploads in `media/videos/` with list/save/delete/resolve helpers; resolve Roblox sources as sources-first then videos. Strip YouTube modules/routes/deps. Library page tabs call existing slice upload plus new video routes and `/api/images`.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, vanilla JS, ffmpeg, pytest

## Global Constraints

- `video_speed`: 50…200, step 1, default **100**; independent of TTS pitch/speed
- Roblox only — **hide** slider in Picture mode; Ken Burns unchanged
- setpts factor `100/S` (200% → `setpts=100/200*PTS`); at 100% omit setpts
- Overlay remains wall-clock `OVERLAY_DURATION_S` (3.5s), not scaled by `video_speed`
- Source audio already discarded via `-map 1:a:0` — no mute work
- Raw videos: `media/videos/`; slices: `media/sources/`; images: `media/images/`
- Name collision across folders: **sources wins**
- YouTube fully removed (UI, API, jobs, `youtube.py`, yt-dlp, cookies settings/docs)
- Spec: `docs/superpowers/specs/2026-08-15-library-tabs-video-speed-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/voice.py` | `DEFAULT_VIDEO_SPEED`, `validate_video_speed` |
| `src/roblox_viral/render.py` | `video_speed` kwarg + setpts in filter graph |
| `tests/test_voice.py` | video_speed validation tests |
| `tests/test_render.py` | setpts present/absent in cmd |
| `src/roblox_viral/web/config.py` | `videos_dir`; drop youtube cookies |
| `src/roblox_viral/web/library.py` | raw video CRUD; `list_roblox_sources`; `resolve_roblox_media` |
| `tests/web/test_library.py` | save/list/delete/resolve raw + combined list |
| `src/roblox_viral/web/jobs.py` | `video_speed` on record; resolve roblox media; drop YouTube |
| `src/roblox_viral/web/app.py` | CreateJobBody; library routes; drop YouTube; Generate context |
| `src/roblox_viral/web/api_v1.py` | optional `video_speed`; roblox resolve |
| `src/roblox_viral/web/templates/library.html` | three tabs; no YouTube |
| `src/roblox_viral/web/static/library.js` | tab UI + image upload via `/api/images` |
| `src/roblox_viral/web/templates/generate.html` | labeled sources; video speed; no image upload |
| `src/roblox_viral/web/static/app.js` | POST `video_speed`; hide slider; drop image upload JS |
| `src/roblox_viral/web/youtube.py` | **Delete** |
| `tests/web/test_youtube*.py` | **Delete** or replace with 404 smoke |
| `pyproject.toml` | remove `yt-dlp` |
| `README.md` | Library tabs, video_speed, drop YouTube |

---

### Task 1: `validate_video_speed` + `render_video` setpts

**Files:**
- Modify: `src/roblox_viral/voice.py`
- Modify: `src/roblox_viral/render.py`
- Modify: `tests/test_voice.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- Produces:
  - `DEFAULT_VIDEO_SPEED = 100`
  - `VIDEO_SPEED_MIN, VIDEO_SPEED_MAX = 50, 200`
  - `validate_video_speed(percent: int) -> int` — raise `ValueError` if not int or out of range; return `percent`
  - `render_video(..., video_speed: int = 100)` — call `validate_video_speed`; if ≠100 insert `setpts=100/{S}*PTS` after crop, before `ass` (both `-vf` and overlay `filter_complex` base chain)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_voice.py`:

```python
from roblox_viral.voice import (
    DEFAULT_VIDEO_SPEED,
    VIDEO_SPEED_MAX,
    VIDEO_SPEED_MIN,
    validate_video_speed,
)


def test_validate_video_speed_ok():
    assert DEFAULT_VIDEO_SPEED == 100
    assert validate_video_speed(100) == 100
    assert validate_video_speed(50) == 50
    assert validate_video_speed(200) == 200


def test_validate_video_speed_rejects():
    import pytest

    with pytest.raises(ValueError):
        validate_video_speed(49)
    with pytest.raises(ValueError):
        validate_video_speed(201)
    with pytest.raises(ValueError):
        validate_video_speed(True)  # type: ignore[arg-type]
```

Append to `tests/test_render.py`:

```python
def test_render_video_default_speed_omits_setpts(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
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
    render_video(
        video_path=video, audio_path=audio, ass_path=ass, output_path=out
    )
    vf = seen["cmd"][seen["cmd"].index("-vf") + 1]
    assert "setpts" not in vf


def test_render_video_speed_200_inserts_setpts(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
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
    render_video(
        video_path=video,
        audio_path=audio,
        ass_path=ass,
        output_path=out,
        video_speed=200,
    )
    vf = seen["cmd"][seen["cmd"].index("-vf") + 1]
    assert "setpts=100/200*PTS" in vf


def test_render_video_overlay_includes_setpts_on_base(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    overlay = _touch(tmp_path / "overlay.mp4")
    out = tmp_path / "out.mp4"
    seen = {}

    monkeypatch.setattr("roblox_viral.render.probe_duration_seconds", lambda _p: 5.0)
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"mp4")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)
    render_video(
        video_path=video,
        audio_path=audio,
        ass_path=ass,
        output_path=out,
        overlay_path=overlay,
        video_speed=150,
    )
    fc = seen["cmd"][seen["cmd"].index("-filter_complex") + 1]
    assert "setpts=100/150*PTS" in fc
    assert "lte(t,3.5)" in fc
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_voice.py::test_validate_video_speed_ok tests/test_render.py::test_render_video_speed_200_inserts_setpts -v`

Expected: FAIL (import / missing kwarg)

- [ ] **Step 3: Implement helpers + render**

In `voice.py` add:

```python
DEFAULT_VIDEO_SPEED = 100
VIDEO_SPEED_MIN, VIDEO_SPEED_MAX = 50, 200


def validate_video_speed(percent: int) -> int:
    if not isinstance(percent, int) or isinstance(percent, bool):
        raise ValueError("video_speed must be an int")
    if percent < VIDEO_SPEED_MIN or percent > VIDEO_SPEED_MAX:
        raise ValueError(
            f"video_speed must be between {VIDEO_SPEED_MIN} and {VIDEO_SPEED_MAX}"
        )
    return percent
```

In `render.py`, import `validate_video_speed`. Add:

```python
def _playback_setpts(video_speed: int) -> str | None:
    validate_video_speed(video_speed)
    if video_speed == 100:
        return None
    return f"setpts=100/{video_speed}*PTS"
```

Add `video_speed: int = 100` to `render_video`. Build chain:

```python
setpts = _playback_setpts(video_speed)
parts = [
    f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase",
    f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}",
]
if setpts:
    parts.append(setpts)
parts.append(f"ass='{ass_escaped}'")
vf = ",".join(parts)
```

Overlay `filter_complex` base leg:

```python
base_parts = [
    f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase",
    f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}",
]
if setpts:
    base_parts.append(setpts)
base = ",".join(base_parts)
fc = (
    f"[0:v]{base}[base];"
    f"[base]ass='{ass_escaped}'[cap];"
    # existing chromakey + overlay with enable='lte(t,{OVERLAY_DURATION_S})'
)
```

Keep overlay input `-t {OVERLAY_DURATION_S}` unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_voice.py tests/test_render.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/voice.py src/roblox_viral/render.py tests/test_voice.py tests/test_render.py
git commit -m "feat: apply optional setpts for gameplay video_speed"
```

---

### Task 2: `videos_dir` + raw video library helpers

**Files:**
- Modify: `src/roblox_viral/web/config.py`
- Modify: `src/roblox_viral/web/library.py`
- Modify: `tests/web/test_library.py`

**Interfaces:**
- Produces:
  - `Settings.videos_dir` → `media_root / "videos"`
  - `ensure_media_dirs` also creates `videos_dir`
  - `@dataclass(frozen=True) class RobloxSource: name: str; kind: str; path: Path; size_bytes: int` (`kind` in `{"slice","video"}`)
  - `list_videos(settings) -> list[SourceVideo]`
  - `resolve_video(settings, name: str) -> Path`
  - `save_video(settings, filename: str, data: bytes) -> SourceVideo` — as-is, no slice; size ≤ `MAX_UPLOAD_BYTES`; exclusive create like images
  - `delete_video(settings, name: str) -> None`
  - `resolve_roblox_media(settings, name: str) -> Path` — try `resolve_source`, on `FileNotFoundError` try `resolve_video`
  - `list_roblox_sources(settings) -> list[RobloxSource]` — all slices sorted then all videos sorted

- [ ] **Step 1: Write failing tests**

```python
def test_save_video_stores_as_is_no_slice(tmp_path, monkeypatch):
    from roblox_viral.web.config import Settings
    from roblox_viral.web import library as lib

    media = tmp_path / "media"
    s = Settings(
        media_root=media,
        app_password="x",
        app_secret="dev-secret-key-at-least-32-chars!!",
        require_password=False,
        youtube_cookies="",
    )
    s.ensure_media_dirs()
    called = {"slice": False}

    def boom(*a, **k):
        called["slice"] = True
        raise AssertionError("slice must not run")

    monkeypatch.setattr(lib, "slice_into_minute_parts", boom)
    item = lib.save_video(s, "full.mp4", b"rawbytes")
    assert item.name == "full.mp4"
    assert (s.videos_dir / "full.mp4").read_bytes() == b"rawbytes"
    assert called["slice"] is False
    assert lib.list_videos(s)[0].name == "full.mp4"


def test_resolve_roblox_media_sources_win(tmp_path):
    from roblox_viral.web.config import Settings
    from roblox_viral.web import library as lib

    media = tmp_path / "media"
    s = Settings(
        media_root=media,
        app_password="x",
        app_secret="dev-secret-key-at-least-32-chars!!",
        require_password=False,
        youtube_cookies="",
    )
    s.ensure_media_dirs()
    (s.sources_dir / "same.mp4").write_bytes(b"slice")
    (s.videos_dir / "same.mp4").write_bytes(b"raw")
    path = lib.resolve_roblox_media(s, "same.mp4")
    assert path == (s.sources_dir / "same.mp4").resolve()


def test_resolve_roblox_media_falls_back_to_videos(tmp_path):
    from roblox_viral.web.config import Settings
    from roblox_viral.web import library as lib

    media = tmp_path / "media"
    s = Settings(
        media_root=media,
        app_password="x",
        app_secret="dev-secret-key-at-least-32-chars!!",
        require_password=False,
        youtube_cookies="",
    )
    s.ensure_media_dirs()
    (s.videos_dir / "only.mp4").write_bytes(b"raw")
    path = lib.resolve_roblox_media(s, "only.mp4")
    assert path == (s.videos_dir / "only.mp4").resolve()


def test_list_roblox_sources_labels_kinds(tmp_path):
    from roblox_viral.web.config import Settings
    from roblox_viral.web import library as lib

    media = tmp_path / "media"
    s = Settings(
        media_root=media,
        app_password="x",
        app_secret="dev-secret-key-at-least-32-chars!!",
        require_password=False,
        youtube_cookies="",
    )
    s.ensure_media_dirs()
    (s.sources_dir / "a-1.mp4").write_bytes(b"1")
    (s.videos_dir / "b.mp4").write_bytes(b"2")
    items = lib.list_roblox_sources(s)
    kinds = {i.name: i.kind for i in items}
    assert kinds["a-1.mp4"] == "slice"
    assert kinds["b.mp4"] == "video"
```

After Task 5 removes `youtube_cookies`, drop that kwarg from Settings construction in these tests.

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/web/test_library.py -k "save_video or resolve_roblox or list_roblox" -v`

- [ ] **Step 3: Implement**

`config.py`:

```python
@property
def videos_dir(self) -> Path:
    return self.media_root / "videos"

def ensure_media_dirs(self) -> None:
    for d in (
        self.sources_dir,
        self.videos_dir,
        self.images_dir,
        self.outputs_dir,
        self.jobs_dir,
    ):
        d.mkdir(parents=True, exist_ok=True)
```

`library.py`:

```python
@dataclass(frozen=True)
class RobloxSource:
    name: str
    kind: str  # "slice" | "video"
    path: Path
    size_bytes: int


def _commit_video_upload(videos_dir: Path, safe: str, data: bytes) -> Path:
    stem = Path(safe).stem
    suffix = Path(safe).suffix.lower()
    dest = videos_dir / safe
    while True:
        try:
            with open(dest, "xb") as fh:
                fh.write(data)
        except FileExistsError:
            dest = videos_dir / f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
            continue
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
        return dest


def list_videos(settings: Settings) -> list[SourceVideo]:
    items: list[SourceVideo] = []
    if not settings.videos_dir.is_dir():
        return items
    for path in sorted(settings.videos_dir.iterdir()):
        if path.is_file() and _SAFE_NAME.match(path.name) and not path.name.startswith("."):
            items.append(SourceVideo(path.name, path, path.stat().st_size))
    return items


def resolve_video(settings: Settings, name: str) -> Path:
    safe = _safe_name(name)
    path = (settings.videos_dir / safe).resolve()
    if not path.is_relative_to(settings.videos_dir.resolve()):
        raise ValueError("Invalid path")
    if not path.is_file():
        raise FileNotFoundError(safe)
    return path


def save_video(settings: Settings, filename: str, data: bytes) -> SourceVideo:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"Upload exceeds maximum size of {MAX_UPLOAD_BYTES} bytes"
        )
    safe = _safe_name(filename)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    dest = _commit_video_upload(settings.videos_dir, safe, data)
    return SourceVideo(dest.name, dest, dest.stat().st_size)


def delete_video(settings: Settings, name: str) -> None:
    resolve_video(settings, name).unlink()


def resolve_roblox_media(settings: Settings, name: str) -> Path:
    try:
        return resolve_source(settings, name)
    except FileNotFoundError:
        return resolve_video(settings, name)


def list_roblox_sources(settings: Settings) -> list[RobloxSource]:
    out: list[RobloxSource] = []
    for s in list_sources(settings):
        out.append(RobloxSource(s.name, "slice", s.path, s.size_bytes))
    for v in list_videos(settings):
        out.append(RobloxSource(v.name, "video", v.path, v.size_bytes))
    return out
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/web/test_library.py -k "save_video or resolve_roblox or list_roblox" -v`

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/config.py src/roblox_viral/web/library.py tests/web/test_library.py
git commit -m "feat(web): add media/videos library helpers for raw uploads"
```

---

### Task 3: JobManager `video_speed` + roblox resolve

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`
- Modify: `src/roblox_viral/web/app.py` (`CreateJobBody` + `/api/jobs`)
- Modify: `tests/web/test_api.py`

**Interfaces:**
- Consumes: `validate_video_speed`, `resolve_roblox_media`, `render_video(..., video_speed=)`
- Produces:
  - `JobRecord.video_speed: int = DEFAULT_VIDEO_SPEED`
  - `create(..., video_speed: int = DEFAULT_VIDEO_SPEED)` — validate; non-ephemeral roblox uses `resolve_roblox_media`
  - `run_job` resolves via `resolve_roblox_media` (non-ephemeral roblox); passes `video_speed=record.video_speed` to `render_video`
  - Persist/load `video_speed` in `status.json`
  - `CreateJobBody.video_speed: int | None = None` → default 100; validate → 400

- [ ] **Step 1: Write failing tests**

In `tests/web/test_jobs.py` / `test_api.py` (follow existing helpers):

```python
def test_create_job_persists_video_speed(tmp_path, monkeypatch):
    # Settings + file in videos_dir only
    # mgr.create(..., video_speed=150)
    # assert record.video_speed == 150


def test_create_job_rejects_bad_video_speed(tmp_path, monkeypatch):
    # create(..., video_speed=999) raises ValueError


def test_run_job_passes_video_speed_to_render(tmp_path, monkeypatch):
    # monkeypatch EdgeTTSProvider, write_ass, render_video; capture kwargs
    # assert seen["video_speed"] == 175


def test_api_jobs_accepts_video_speed(tmp_path, monkeypatch):
    # POST /api/jobs with video_speed: 120 → 200; GET shows 120


def test_api_jobs_rejects_video_speed(tmp_path, monkeypatch):
    # video_speed: 10 → 400
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/web/test_jobs.py tests/web/test_api.py -k video_speed -v`

- [ ] **Step 3: Implement**

`jobs.py` — import `DEFAULT_VIDEO_SPEED`, `validate_video_speed`, `resolve_roblox_media`. Add field on `JobRecord`. In `create`:

```python
validate_video_speed(video_speed)
...
elif mode == "picture":
    resolve_image(settings, source_name)
else:
    resolve_roblox_media(settings, source_name)
    ken_burns = False
```

Persist `video_speed` on record and in disk load:

```python
video_speed=int(data["video_speed"]) if "video_speed" in data else DEFAULT_VIDEO_SPEED,
```

`run_job` roblox non-ephemeral: `resolve_roblox_media`; `render_video(..., video_speed=record.video_speed)`.

`app.py` CreateJobBody + handler:

```python
video_speed: int | None = None
...
video_speed = DEFAULT_VIDEO_SPEED if body.video_speed is None else body.video_speed
validate_video_speed(video_speed)  # in same try as pitch/speed
mgr.create(..., video_speed=video_speed, ...)
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/web/test_jobs.py tests/web/test_api.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/jobs.py src/roblox_viral/web/app.py tests/web/test_jobs.py tests/web/test_api.py
git commit -m "feat(web): persist and apply job video_speed for Roblox renders"
```

---

### Task 4: Generate UI — labeled sources, video speed slider, drop image upload

**Files:**
- Modify: `src/roblox_viral/web/app.py` (generate page → `list_roblox_sources`)
- Modify: `src/roblox_viral/web/templates/generate.html`
- Modify: `src/roblox_viral/web/static/app.js`

**Interfaces:**
- Consumes: `list_roblox_sources`
- Produces: options labeled `(1m)` / `(video)`; `#video_speed` slider hidden in Picture; POST includes `video_speed`; no image upload/delete on Generate

- [ ] **Step 1: Update `generate.html`**

```html
{% for s in sources %}
<option value="{{ s.name }}">{{ s.name }} {% if s.kind == "slice" %}(1m){% else %}(video){% endif %}</option>
{% endfor %}
```

Picture: select + Ken Burns only; empty text `No images — upload in Library`.

After voice speed:

```html
<label class="slider-field" id="video-speed-field">
  Video speed <span id="video-speed-value">100%</span>
  <input id="video_speed" name="video_speed" type="range" min="50" max="200" step="1" value="100" />
</label>
```

- [ ] **Step 2: Update `app.js`**

- Label sync for `#video_speed` / `#video-speed-value`
- Mode tab: hide `#video-speed-field` in Picture; show in Roblox
- Job POST: `video_speed: Number(...)`
- Remove image upload/delete fetch handlers

- [ ] **Step 3: Update `generate_page`**

```python
sources = list_roblox_sources(settings)
```

- [ ] **Step 4: Commit**

```bash
git add src/roblox_viral/web/templates/generate.html src/roblox_viral/web/static/app.js src/roblox_viral/web/app.py
git commit -m "feat(web): Generate video_speed slider and labeled roblox sources"
```

---

### Task 5: Remove YouTube

**Files:**
- Delete: `src/roblox_viral/web/youtube.py`
- Delete: `tests/web/test_youtube.py`, `tests/web/test_youtube_api.py`, `tests/web/test_youtube_jobs.py`
- Create: `tests/web/test_youtube_removed.py`
- Modify: `src/roblox_viral/web/jobs.py` — remove `create_youtube`, `run_youtube_job`, youtube imports
- Modify: `src/roblox_viral/web/app.py` — remove `POST /api/library/youtube`
- Modify: `src/roblox_viral/web/config.py` — remove `youtube_cookies` / `youtube_cookies_path` / env
- Modify: `tests/web/test_config.py` — remove youtube cookies tests
- Modify: `pyproject.toml` — remove `yt-dlp`
- Modify: `README.md` — remove YouTube/cookies/`YOUTUBE_COOKIES` (finish polish in Task 8)

**Interfaces:**
- Produces: `POST /api/library/youtube` → 404; no `yt_dlp` imports

- [ ] **Step 1: Write smoke test**

```python
def test_youtube_endpoint_gone(tmp_path, monkeypatch):
    # logged-in client (same pattern as other library API tests)
    r = c.post(
        "/api/library/youtube",
        json={"url": "https://youtu.be/x", "name": "a"},
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run — expect FAIL while route exists (not 404)**

- [ ] **Step 3: Delete YouTube code paths**

- Remove jobs/app/config pieces listed above
- Delete `youtube.py` and old youtube tests
- Remove `yt-dlp` from `pyproject.toml`
- Prefer drop unused JobStatus values `downloading` / `slicing` if nothing sets them
- Keep optional `JobRecord` fields `url`/`stem`/`created_slices` for old status.json reads, or remove if tests do not need them — either is fine if load still tolerant

- [ ] **Step 4: Run**

Run: `pytest tests/web -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u src/roblox_viral/web tests/web pyproject.toml README.md
git add tests/web/test_youtube_removed.py
git commit -m "feat(web): remove YouTube library import and yt-dlp"
```

---

### Task 6: Library page three tabs

**Files:**
- Modify: `src/roblox_viral/web/templates/library.html`
- Modify: `src/roblox_viral/web/static/library.js`
- Modify: `src/roblox_viral/web/app.py`
- Modify: `tests/web/` (library upload/route tests)

**Interfaces:**
- Produces:
  - `POST /library/upload` — slices (unchanged); template `tab="slices"`
  - `POST /library/delete` — delete slice
  - `POST /library/videos/upload` — `save_video`
  - `POST /library/videos/delete` — `delete_video`
  - Images via `POST /api/images` + `DELETE /api/images/{name}` from `library.js`
  - Tabs: **1-minute clips** | **Videos** | **Images**
  - `_library_ctx(settings, *, error=None, message=None, tab="slices")` → `sources`, `videos`, `images`, `error`, `message`, `tab`

- [ ] **Step 1: Write failing route tests**

```python
def test_library_raw_video_upload(tmp_path, monkeypatch):
    # logged-in client
    r = c.post(
        "/library/videos/upload",
        files={"file": ("clip.mp4", b"data", "video/mp4")},
    )
    assert r.status_code == 200
    assert (settings.videos_dir / "clip.mp4").is_file()


def test_library_page_has_tabs_not_youtube(tmp_path, monkeypatch):
    r = c.get("/library")
    assert r.status_code == 200
    body = r.text
    assert "YouTube" not in body
    assert "Videos" in body
    assert "Images" in body
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement routes + template + JS**

Template: three tab buttons + three panels (slices form `/library/upload`; videos form `/library/videos/upload`; images file input + JS to `/api/images`). Server-render lists with delete forms/buttons. After POST, re-render with correct `tab` so the active panel stays open.

`library.js`: tab switching; image upload `FormData` → `POST /api/images` → reload; image delete → `DELETE /api/images/{name}` → reload.

Every `TemplateResponse` for library must include `videos`, `images`, `tab`.

- [ ] **Step 4: Run**

Run: `pytest tests/web -k library -v`

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/templates/library.html src/roblox_viral/web/static/library.js src/roblox_viral/web/app.py tests/web
git commit -m "feat(web): Library tabs for slices, raw videos, and images"
```

---

### Task 7: n8n API `video_speed` + raw `source_name`

**Files:**
- Modify: `src/roblox_viral/web/api_v1.py`
- Modify: `tests/web/test_api_v1.py`
- Modify: `README.md`
- Modify: `scripts/test-n8n-api.ps1` (optional `-F "video_speed=100"`)

**Interfaces:**
- Produces: form `video_speed: str = Form("")`; default `DEFAULT_VIDEO_SPEED`; invalid → 400
- Roblox `source_name` works for `videos/` via Task 3 `resolve_roblox_media`

- [ ] **Step 1: Write failing tests**

```python
def test_create_accepts_video_speed(tmp_path, monkeypatch):
    # clip in sources; video_speed="160"; GET → 160


def test_create_resolves_raw_library_video(tmp_path, monkeypatch):
    # only videos_dir/raw.mp4; source_name=raw.mp4 → 200


def test_create_invalid_video_speed_400(tmp_path, monkeypatch):
    # video_speed="9" → 400
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
video_speed: str = Form(""),
...
video_speed_i = _optional_int(video_speed, DEFAULT_VIDEO_SPEED, "video_speed")
validate_video_speed(video_speed_i)
...
mgr.create(..., video_speed=video_speed_i, ...)
```

- [ ] **Step 4: Run**

Run: `pytest tests/web/test_api_v1.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/api_v1.py tests/web/test_api_v1.py README.md scripts/test-n8n-api.ps1
git commit -m "feat(api): optional video_speed and raw library source_name for n8n"
```

---

### Task 8: README polish + full regression

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Finish README**

Document Library tabs, Generate video speed, n8n `video_speed`, no YouTube/yt-dlp/cookies.

- [ ] **Step 2: Full suite**

Run: `pytest -q`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document library tabs and video_speed"
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| video_speed 50–200 default 100 | 1, 3, 4 |
| Independent of voice | 3, 4 |
| Hide in Picture | 4 |
| setpts / 100% passthrough | 1 |
| Overlay wall-clock | 1 |
| Library three tabs | 6 |
| `media/videos/` | 2 |
| Images from Library only | 4, 6 |
| Labeled Generate dropdown | 4 |
| Remove YouTube | 5 |
| n8n video_speed + raw resolve | 7 |
| README | 5, 7, 8 |

## Consistency check

- Names: `validate_video_speed`, `DEFAULT_VIDEO_SPEED`, `resolve_roblox_media`, `list_roblox_sources`, `save_video`
- setpts string: `setpts=100/{S}*PTS`
- No TBD/TODO placeholders in steps
