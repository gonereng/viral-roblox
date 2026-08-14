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

