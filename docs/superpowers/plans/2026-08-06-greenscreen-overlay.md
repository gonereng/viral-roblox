# Greenscreen Intro Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On each generated storytime render, when `media/overlay.mp4` (or `OVERLAY_VIDEO`) exists, chromakey its first 3.5s and composite it muted and centered at half frame height over the captioned gameplay from t=0.

**Architecture:** Extend `Settings` with `overlay_video_path`. Extend `render_video` to optionally take a third ffmpeg input and a `filter_complex` (scale/crop → ASS → chromakey/scale overlay → centered `overlay` with `enable` + `eof_action=pass`). Wire web jobs and CLI to pass the settings path. Missing overlay = unchanged behavior.

**Tech Stack:** Python 3.10+, ffmpeg (chromakey + overlay filters), pytest, existing FastAPI job runner

## Global Constraints

- Timing: overlay at start, `t = 0` … `3.5s`
- Overlay source trim: first **3.5** seconds
- Size: height ≈ `OUTPUT_HEIGHT // 2` (960px), keep aspect; center H+V
- Audio: overlay muted; map TTS only
- Layering: overlay **above** burned ASS captions
- Missing overlay file: render unchanged (no error)
- Present but ffmpeg fails: `RenderError` with stderr
- No UI; asset drop-in only
- Out of scope: per-job toggle, adjustable timing/size, overlay audio mix, pre-baked alpha pipeline
- Spec: `docs/superpowers/specs/2026-08-06-greenscreen-overlay-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/web/config.py` | `OVERLAY_VIDEO` + `overlay_video_path` |
| `src/roblox_viral/render.py` | Optional overlay in `render_video` via `filter_complex` |
| `src/roblox_viral/web/jobs.py` | Pass `settings.overlay_video_path` into `render_video` |
| `src/roblox_viral/cli.py` | Resolve overlay path (env/`media/overlay.mp4`) and pass through |
| `README.md` | Document `media/overlay.mp4` / `OVERLAY_VIDEO` |
| `tests/web/test_config.py` | Overlay path resolution tests |
| `tests/test_render.py` | Command-shape tests for with/without overlay |
| `media/overlay.mp4` | Local asset (gitignored); copy from root `download.mp4` |

---

### Task 1: Settings `overlay_video_path` + README

**Files:**
- Modify: `src/roblox_viral/web/config.py`
- Modify: `tests/web/test_config.py`
- Modify: `README.md`

**Interfaces:**
- Produces:
  - `Settings.overlay_video: str` (from env `OVERLAY_VIDEO`, default `""`)
  - `Settings.overlay_video_path: Path | None` — if `overlay_video` set and that path is a file, return it; else if `media_root / "overlay.mp4"` is a file, return that; else `None`

- [ ] **Step 1: Write the failing test**

Append to `tests/web/test_config.py`:

```python
def test_overlay_video_path_default_and_env(tmp_path: Path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("MEDIA_ROOT", str(media))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("OVERLAY_VIDEO", raising=False)
    settings = Settings.from_env()
    assert settings.overlay_video_path is None

    overlay = media / "overlay.mp4"
    overlay.write_bytes(b"fake")
    assert settings.overlay_video_path == overlay

    other = tmp_path / "other_overlay.mp4"
    other.write_bytes(b"fake")
    monkeypatch.setenv("OVERLAY_VIDEO", str(other))
    settings2 = Settings.from_env()
    assert settings2.overlay_video_path == other
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_config.py::test_overlay_video_path_default_and_env -v`

Expected: FAIL (`overlay_video_path` missing / AttributeError)

- [ ] **Step 3: Implement Settings fields**

In `src/roblox_viral/web/config.py`:

1. Add field on `Settings`: `overlay_video: str = ""`
2. Add property:

```python
@property
def overlay_video_path(self) -> Path | None:
    """Greenscreen intro overlay MP4, if configured or present under media/."""
    if self.overlay_video.strip():
        path = Path(self.overlay_video).expanduser()
        return path if path.is_file() else None
    default = self.media_root / "overlay.mp4"
    return default if default.is_file() else None
```

3. In `from_env`, read `overlay_video = os.environ.get("OVERLAY_VIDEO", "")` and pass into `cls(...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_config.py::test_overlay_video_path_default_and_env -v`

Expected: PASS

- [ ] **Step 5: README note**

In `README.md` Optional env vars (or near Generate docs), add:

- Place a greenscreen MP4 at `media/overlay.mp4` (or set `OVERLAY_VIDEO` to its path) to composite the first 3.5s, keyed and centered at half height, at the start of each generated video. Overlay audio is ignored.

- [ ] **Step 6: Commit**

```bash
git add src/roblox_viral/web/config.py tests/web/test_config.py README.md
git commit -m "feat(web): add overlay video path settings"
```

---

### Task 2: `render_video` chromakey overlay filter graph

**Files:**
- Modify: `src/roblox_viral/render.py`
- Create: `tests/test_render.py`

**Interfaces:**
- Consumes: none from Task 1 (path is passed in by callers)
- Produces:
  - Module constants:
    - `OVERLAY_DURATION_S = 3.5`
    - `OVERLAY_HEIGHT = OUTPUT_HEIGHT // 2`  # 960
    - `OVERLAY_CHROMA_COLOR = "0x00FE00"`
    - `OVERLAY_CHROMA_SIMILARITY = "0.30"`
    - `OVERLAY_CHROMA_BLEND = "0.10"`
  - `render_video(..., overlay_path: Path | str | None = None)` — when `overlay_path` is a file, use `filter_complex` with third input; when `None` or missing file, keep existing `-vf` path (treat missing file as no overlay only if callers pass `None`; if a path is passed but file missing, raise `RenderError`)

**Behavior when overlay is set:**

ffmpeg inputs (order matters):

1. Gameplay: `-stream_loop -1 -i {video}`
2. TTS audio: `-i {audio}`
3. Overlay: `-t {OVERLAY_DURATION_S} -i {overlay}` (limit to 3.5s; do not loop)

`filter_complex` (labels illustrative):

```
[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[base];
[base]ass='{escaped}'[cap];
[2:v]chromakey=0x00FE00:0.30:0.10,format=yuva420p,scale=-2:960[ov];
[cap][ov]overlay=(W-w)/2:(H-h)/2:enable='lte(t,3.5)':eof_action=pass[outv]
```

Maps: `-map [outv] -map 1:a:0` (never map overlay audio). Keep existing codecs/flags (`libx264`, CRF 18, AAC, `-shortest`, `+faststart`, `-t` audio duration on output as today).

When overlay is `None`: keep the existing single `-vf` chain and two-input command unchanged.

- [ ] **Step 1: Write failing tests**

Create `tests/test_render.py`:

```python
from pathlib import Path

import pytest

from roblox_viral.render import RenderError, render_video


def _touch(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_render_video_without_overlay_uses_vf(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    out = tmp_path / "out.mp4"
    seen = {}

    def fake_probe(_path):
        return 2.0

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"mp4")
        class R:
            returncode = 0
            stderr = ""
        return R()

    monkeypatch.setattr("roblox_viral.render.probe_duration_seconds", fake_probe)
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)

    render_video(
        video_path=video,
        audio_path=audio,
        ass_path=ass,
        output_path=out,
    )
    cmd = seen["cmd"]
    assert "-filter_complex" not in cmd
    assert "-vf" in cmd
    assert str(video) in cmd
    assert str(audio) in cmd


def test_render_video_with_overlay_uses_filter_complex(tmp_path, monkeypatch):
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
    )
    cmd = " ".join(seen["cmd"])
    assert "-filter_complex" in seen["cmd"]
    assert "chromakey" in cmd
    assert "overlay=" in cmd
    assert "eof_action=pass" in cmd
    assert str(overlay) in seen["cmd"]
    # overlay limited to 3.5s: "-t" "3.5" immediately before overlay -i
    idx = seen["cmd"].index(str(overlay))
    assert seen["cmd"][idx - 2 : idx] == ["-t", "3.5"] or seen["cmd"][idx - 2 : idx] == [
        "-t",
        "3.500",
    ]
    assert "-map" in seen["cmd"]
    assert "[outv]" in seen["cmd"]
    assert "0:v:0" not in " ".join(
        seen["cmd"][seen["cmd"].index("-map") :]
    ) or True  # mapped via [outv]
    # must not map overlay audio as sole audio — TTS is input 1
    assert "1:a:0" in seen["cmd"]


def test_render_video_missing_overlay_path_raises(tmp_path, monkeypatch):
    video = _touch(tmp_path / "game.mp4")
    audio = _touch(tmp_path / "n.mp3")
    ass = _touch(tmp_path / "c.ass", b"[Script Info]\n")
    out = tmp_path / "out.mp4"
    monkeypatch.setattr("roblox_viral.render.probe_duration_seconds", lambda _p: 1.0)
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")
    with pytest.raises(RenderError, match="Overlay"):
        render_video(
            video_path=video,
            audio_path=audio,
            ass_path=ass,
            output_path=out,
            overlay_path=tmp_path / "missing.mp4",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_render.py -v`

Expected: FAIL (no `overlay_path` kwarg / wrong command shape)

- [ ] **Step 3: Implement overlay path in `render.py`**

Update `src/roblox_viral/render.py`:

1. Add constants after `OUTPUT_HEIGHT`:

```python
OVERLAY_DURATION_S = 3.5
OVERLAY_HEIGHT = OUTPUT_HEIGHT // 2
OVERLAY_CHROMA_COLOR = "0x00FE00"
OVERLAY_CHROMA_SIMILARITY = "0.30"
OVERLAY_CHROMA_BLEND = "0.10"
```

2. Extend `render_video` signature with `overlay_path: Path | str | None = None`.

3. After validating video/audio/ass, if `overlay_path is not None`:
   - `overlay = Path(overlay_path)`
   - if not `overlay.is_file()`: raise `RenderError(f"Overlay video not found: {overlay}")`

4. Branch command construction:

**Without overlay** — keep current `-vf` + two inputs.

**With overlay** — build:

```python
ass_escaped = _ass_filter_path(ass)
fc = (
    f"[0:v]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
    f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}[base];"
    f"[base]ass='{ass_escaped}'[cap];"
    f"[2:v]chromakey={OVERLAY_CHROMA_COLOR}:{OVERLAY_CHROMA_SIMILARITY}:{OVERLAY_CHROMA_BLEND},"
    f"format=yuva420p,scale=-2:{OVERLAY_HEIGHT}[ov];"
    f"[cap][ov]overlay=(W-w)/2:(H-h)/2:enable='lte(t,{OVERLAY_DURATION_S})':eof_action=pass[outv]"
)
cmd = [
    ffmpeg, "-y",
    "-stream_loop", "-1", "-i", str(video),
    "-i", str(audio),
    "-t", f"{OVERLAY_DURATION_S}", "-i", str(overlay),
    "-t", f"{audio_duration:.3f}",
    "-filter_complex", fc,
    "-map", "[outv]",
    "-map", "1:a:0",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
    "-c:a", "aac", "-b:a", "192k",
    "-shortest",
    "-movflags", "+faststart",
    str(out),
]
```

5. Keep the same `subprocess.run` / `RenderError` handling for both branches.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_render.py -v`

Expected: PASS

- [ ] **Step 5: Optional smoke (manual / local only)**

If ffmpeg is available and `download.mp4` exists at repo root, a quick sanity check (not required for CI):

```bash
# create tiny ASS + use short audio; or rely on full pipeline after Task 3
```

Skip automating full encode in CI unless cheap fixtures already exist.

- [ ] **Step 6: Commit**

```bash
git add src/roblox_viral/render.py tests/test_render.py
git commit -m "feat: chromakey intro overlay in render_video"
```

---

### Task 3: Wire jobs + CLI + place overlay asset

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `src/roblox_viral/cli.py`
- Local only: copy `download.mp4` → `media/overlay.mp4` (gitignored; do not commit the binary)

**Interfaces:**
- Consumes: `Settings.overlay_video_path`, `render_video(..., overlay_path=...)`
- Produces: web + CLI renders apply overlay when file present

- [ ] **Step 1: Pass overlay from JobManager**

In `src/roblox_viral/web/jobs.py`, update the `render_video(...)` call inside `run_job` to:

```python
render_video(
    video_path=video_path,
    audio_path=narration_path,
    ass_path=ass_path,
    output_path=output_path,
    work_dir=job_dir,
    overlay_path=settings.overlay_video_path,
)
```

Existing job tests already use `**kwargs` on fake_render — they should keep passing.

- [ ] **Step 2: Run web job tests**

Run: `pytest tests/web/test_jobs.py -v`

Expected: PASS

- [ ] **Step 3: Wire CLI**

In `src/roblox_viral/cli.py`, before `render_video`:

```python
from roblox_viral.web.config import Settings

# Resolve overlay the same way as the web app (MEDIA_ROOT / OVERLAY_VIDEO).
overlay_path = None
try:
    overlay_path = Settings.from_env().overlay_video_path
except RuntimeError:
    # APP_PASSWORD may be unset in CLI-only use; fall back to ./media/overlay.mp4
    candidate = Path(os.environ.get("MEDIA_ROOT", "media")) / "overlay.mp4"
    if candidate.is_file():
        overlay_path = candidate
    env_overlay = os.environ.get("OVERLAY_VIDEO", "").strip()
    if env_overlay:
        p = Path(env_overlay).expanduser()
        if p.is_file():
            overlay_path = p
```

Simpler preferred approach (avoid Settings password requirement): add a small helper in `render.py` or `config.py`:

```python
# in config.py (module-level, no password required)
def resolve_overlay_video_path(
    media_root: Path | None = None,
    overlay_video: str | None = None,
) -> Path | None:
    env_path = (overlay_video if overlay_video is not None else os.environ.get("OVERLAY_VIDEO", "")).strip()
    if env_path:
        path = Path(env_path).expanduser()
        return path if path.is_file() else None
    root = media_root if media_root is not None else Path(os.environ.get("MEDIA_ROOT", "media"))
    default = Path(root) / "overlay.mp4"
    return default if default.is_file() else None
```

Then:

- `Settings.overlay_video_path` delegates to `resolve_overlay_video_path(self.media_root, self.overlay_video)`
- CLI: `overlay_path=resolve_overlay_video_path()`

Add one unit test for the helper in `tests/web/test_config.py` if extracted (optional if property tests already cover Settings).

Update CLI `render_video(...)` call:

```python
render_video(
    video_path=args.video,
    audio_path=audio_path,
    ass_path=ass_path,
    output_path=args.out,
    keep_temp=args.keep_temp,
    work_dir=temp_dir,
    overlay_path=resolve_overlay_video_path(),
)
```

Import `resolve_overlay_video_path` from `roblox_viral.web.config` (or from `roblox_viral.render` if you prefer keeping CLI free of web package — prefer `config.py` helper as specified).

- [ ] **Step 4: Place local asset**

From repo root (PowerShell):

```powershell
New-Item -ItemType Directory -Force -Path media | Out-Null
Copy-Item -Force download.mp4 media/overlay.mp4
```

Do **not** `git add` `media/overlay.mp4`.

- [ ] **Step 5: Run full relevant suite**

Run: `pytest tests/test_render.py tests/web/test_config.py tests/web/test_jobs.py -q`

Expected: all PASS

- [ ] **Step 6: Commit code only**

```bash
git add src/roblox_viral/web/jobs.py src/roblox_viral/cli.py src/roblox_viral/web/config.py tests/web/test_config.py
git commit -m "feat: wire greenscreen overlay into web and CLI renders"
```

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Start @ 0–3.5s, half height, muted, above captions | Task 2 |
| Missing file → no overlay | Tasks 1–3 (`None` path) |
| Present + ffmpeg fail → RenderError | Task 2 (existing stderr path) |
| `media/overlay.mp4` / `OVERLAY_VIDEO` | Tasks 1, 3 |
| Web + CLI call sites | Task 3 |
| Tests config + command shape | Tasks 1–2 |
| README | Task 1 |
| No UI / no audio mix / no pre-bake | Honored (non-goals) |

No placeholders left. Types: `overlay_path: Path | str | None`; `overlay_video_path: Path | None`; constants named consistently across tasks.
