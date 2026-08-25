# Gemini Video Speed Post-Render Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For Gemini TTS jobs only, render at 1× then optionally tempo the finished MP4 to the configured `video_speed`.

**Architecture:** Pass 1 always uses effective `video_speed=100` for clip planning and `render_*`. If configured speed ≠ 100, Pass 2 runs `tempo_finished_video` (`setpts` + chained `atempo`) from `job_dir/render_1x.mp4` to the final outputs path. Edge jobs unchanged.

**Tech Stack:** Python, ffmpeg (`libx264`/`aac`), existing FastAPI job runner, pytest

## Global Constraints

- Gemini only (`tts_provider == "gemini"`)
- Control: existing `video_speed` (Single 50–200, Reddit 100–500)
- Pass 1 forced to 100%; skip Pass 2 when configured `video_speed == 100`
- Pitch-preserving `atempo` (not `asetrate`)
- Stay on job status `"rendering"` through both passes
- No Generate UI changes
- Spec: `docs/superpowers/specs/2026-08-25-gemini-video-speed-post-render-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/render.py` | `atempo` chain builder + `tempo_finished_video` ffmpeg helper |
| `src/roblox_viral/web/jobs.py` | Gemini: Pass 1 at 100%, optional Pass 2; Edge unchanged |
| `tests/test_render.py` | Unit tests for chain + tempo helper (mocked ffmpeg) |
| `tests/web/test_jobs.py` | Gemini vs Edge `video_speed` wiring tests |

---

### Task 1: `tempo_finished_video` helper

**Files:**
- Modify: `src/roblox_viral/render.py`
- Test: `tests/test_render.py`

**Produces:**
```python
def build_atempo_filters(speed_percent: int) -> list[str]:
    """Return atempo=... filter names for factor speed_percent/100 (each in [0.5, 2.0])."""

def tempo_finished_video(
    *,
    input_path: Path | str,
    output_path: Path | str,
    video_speed: int,
    mode: str = "single",
) -> Path:
    """Re-encode finished MP4 faster/slower; raise RenderError on ffmpeg failure."""
```

- [ ] **Step 1: Write failing tests for `build_atempo_filters`**

Add to `tests/test_render.py`:

```python
from roblox_viral.render import build_atempo_filters, tempo_finished_video


def test_build_atempo_filters_100_empty():
    assert build_atempo_filters(100) == []


def test_build_atempo_filters_200_single():
    assert build_atempo_filters(200) == ["atempo=2.0"]


def test_build_atempo_filters_50_single():
    assert build_atempo_filters(50) == ["atempo=0.5"]


def test_build_atempo_filters_500_chained():
    # 5.0 = 2.0 * 2.0 * 1.25
    assert build_atempo_filters(500) == ["atempo=2.0", "atempo=2.0", "atempo=1.25"]


def test_build_atempo_filters_150():
    assert build_atempo_filters(150) == ["atempo=1.5"]
```

- [ ] **Step 2: Run tests — expect fail (import/name missing)**

```bash
pytest tests/test_render.py::test_build_atempo_filters_100_empty tests/test_render.py::test_build_atempo_filters_500_chained -v
```

Expected: FAIL importing `build_atempo_filters`

- [ ] **Step 3: Implement `build_atempo_filters`**

In `src/roblox_viral/render.py` (near `_playback_setpts`):

```python
def build_atempo_filters(speed_percent: int) -> list[str]:
    """Split playback factor into ffmpeg atempo values in [0.5, 2.0]."""
    if not isinstance(speed_percent, int) or isinstance(speed_percent, bool):
        raise ValueError("video_speed must be an int")
    if speed_percent <= 0:
        raise ValueError("video_speed must be positive")
    factor = speed_percent / 100.0
    if abs(factor - 1.0) < 1e-9:
        return []
    filters: list[str] = []
    remaining = factor
    while remaining > 2.0 + 1e-9:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5 - 1e-9:
        filters.append("atempo=0.5")
        remaining /= 0.5
    # remaining now in [0.5, 2.0]
    if abs(remaining - 1.0) > 1e-9:
        filters.append(f"atempo={remaining:.10g}")
    return filters
```

Note: for 500%, after two `/2` steps remaining is 1.25 → `["atempo=2.0","atempo=2.0","atempo=1.25"]`. Format with `:.10g` so 1.5 stays `1.5` and 1.25 stays `1.25`.

- [ ] **Step 4: Run atempo filter tests — expect PASS**

```bash
pytest tests/test_render.py::test_build_atempo_filters_100_empty tests/test_render.py::test_build_atempo_filters_200_single tests/test_render.py::test_build_atempo_filters_50_single tests/test_render.py::test_build_atempo_filters_500_chained tests/test_render.py::test_build_atempo_filters_150 -v
```

Expected: PASS

- [ ] **Step 5: Write failing tests for `tempo_finished_video`**

```python
def test_tempo_finished_video_100_copies_without_ffmpeg(tmp_path, monkeypatch):
    src = _touch(tmp_path / "in.mp4", b"one-x")
    out = tmp_path / "out.mp4"

    def boom(*a, **k):
        raise AssertionError("ffmpeg must not run at 100%")

    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", boom)
    monkeypatch.setattr("roblox_viral.render.subprocess.run", boom)

    result = tempo_finished_video(
        input_path=src, output_path=out, video_speed=100, mode="single"
    )
    assert result == out
    assert out.read_bytes() == b"one-x"


def test_tempo_finished_video_200_uses_setpts_and_atempo(tmp_path, monkeypatch):
    src = _touch(tmp_path / "in.mp4", b"one-x")
    out = tmp_path / "out.mp4"
    seen = {}

    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"sped")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)

    tempo_finished_video(
        input_path=src, output_path=out, video_speed=200, mode="single"
    )
    cmd = seen["cmd"]
    assert cmd[0] == "ffmpeg"
    assert "-filter_complex" in cmd
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "setpts=100/200*PTS" in fc
    assert "atempo=2.0" in fc
    assert "-c:v" in cmd and "libx264" in cmd
    assert "-c:a" in cmd and "aac" in cmd
    assert str(out) == cmd[-1]
    assert out.read_bytes() == b"sped"


def test_tempo_finished_video_reddit_500(tmp_path, monkeypatch):
    src = _touch(tmp_path / "in.mp4", b"x")
    out = tmp_path / "out.mp4"
    seen = {}
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        seen["cmd"] = cmd
        out.write_bytes(b"ok")

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)
    tempo_finished_video(
        input_path=src, output_path=out, video_speed=500, mode="reddit"
    )
    fc = seen["cmd"][seen["cmd"].index("-filter_complex") + 1]
    assert "setpts=100/500*PTS" in fc
    assert fc.count("atempo=") == 3


def test_tempo_finished_video_rejects_bad_speed(tmp_path):
    src = _touch(tmp_path / "in.mp4", b"x")
    with pytest.raises(ValueError, match="video_speed"):
        tempo_finished_video(
            input_path=src,
            output_path=tmp_path / "out.mp4",
            video_speed=10,
            mode="single",
        )


def test_tempo_finished_video_ffmpeg_failure_raises(tmp_path, monkeypatch):
    src = _touch(tmp_path / "in.mp4", b"x")
    out = tmp_path / "out.mp4"
    monkeypatch.setattr("roblox_viral.render.require_ffmpeg", lambda: "ffmpeg")

    def fake_run(cmd, check=False, capture_output=True, text=True):
        class R:
            returncode = 1
            stderr = "boom"

        return R()

    monkeypatch.setattr("roblox_viral.render.subprocess.run", fake_run)
    with pytest.raises(RenderError, match="tempo"):
        tempo_finished_video(
            input_path=src, output_path=out, video_speed=150, mode="single"
        )
```

- [ ] **Step 6: Run tempo tests — expect fail**

```bash
pytest tests/test_render.py::test_tempo_finished_video_100_copies_without_ffmpeg tests/test_render.py::test_tempo_finished_video_200_uses_setpts_and_atempo -v
```

Expected: FAIL importing `tempo_finished_video`

- [ ] **Step 7: Implement `tempo_finished_video`**

```python
def tempo_finished_video(
    *,
    input_path: Path | str,
    output_path: Path | str,
    video_speed: int,
    mode: str = "single",
) -> Path:
    """Speed up/slow down a finished vertical MP4 (video + audio, pitch preserved)."""
    validate_video_speed(video_speed, mode=mode)
    src = Path(input_path)
    out = Path(output_path)
    if not src.is_file():
        raise RenderError(f"Video not found: {src}")

    if video_speed == 100:
        if src.resolve() != out.resolve():
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, out)
        return out

    ffmpeg = require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    setpts = f"setpts=100/{video_speed}*PTS"
    atempo = build_atempo_filters(video_speed)
    audio_chain = ",".join(atempo) if atempo else "anull"
    filter_complex = f"[0:v]{setpts}[v];[0:a]{audio_chain}[a]"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-map",
        "[a]",
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
        "-movflags",
        "+faststart",
        str(out),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RenderError(
            "ffmpeg tempo finished video failed:\n"
            + (result.stderr or result.stdout or "")
        )
    return out
```

Ensure `shutil` is already imported in `render.py` (it is via `require_ffmpeg`).

- [ ] **Step 8: Run all new render tests — expect PASS**

```bash
pytest tests/test_render.py -k "atempo or tempo_finished" -v
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/roblox_viral/render.py tests/test_render.py
git commit -m "feat(render): tempo finished MP4 for Gemini video_speed"
```

---

### Task 2: Wire Gemini Pass 1 / Pass 2 in `jobs.py`

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Test: `tests/web/test_jobs.py`

**Consumes:** `tempo_finished_video` from Task 1  
**Produces:** Gemini jobs force Pass 1 at 100%; Pass 2 when `record.video_speed != 100`

- [ ] **Step 1: Write failing job tests**

Add to `tests/web/test_jobs.py` (follow existing `_settings` / monkeypatch patterns; set `GEMINI_API_KEY` for Gemini creates):

```python
def test_run_job_gemini_forces_render_video_speed_100(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    seen = {}

    def fake_gemini_synth(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [WordTiming("One", 0, 100)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_video(**kwargs):
        seen["render"] = kwargs
        Path(kwargs["output_path"]).write_bytes(b"mp4-1x")

    def boom_tempo(**kwargs):
        raise AssertionError("tempo must not run at video_speed 100")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.GeminiTTSProvider.synthesize", fake_gemini_synth
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)
    monkeypatch.setattr("roblox_viral.web.jobs.tempo_finished_video", boom_tempo)

    job = mgr.create(
        s,
        "clip.mp4",
        "One line only here.\n",
        "Kore",
        tts_provider="gemini",
        video_speed=100,
    )
    mgr.run_job(s, job.id)
    assert seen["render"]["video_speed"] == 100
    assert mgr.get(job.id, s).status == "done"
    # Pass 1 wrote directly to final output (no render_1x left behind as final)
    assert (s.outputs_dir / mgr.get(job.id, s).output_name).is_file()


def test_run_job_gemini_tempos_when_video_speed_not_100(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    seen = {}

    def fake_gemini_synth(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [WordTiming("One", 0, 100)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_video(**kwargs):
        seen["render"] = dict(kwargs)
        Path(kwargs["output_path"]).write_bytes(b"mp4-1x")

    def fake_tempo(**kwargs):
        seen["tempo"] = dict(kwargs)
        Path(kwargs["output_path"]).write_bytes(b"mp4-sped")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.GeminiTTSProvider.synthesize", fake_gemini_synth
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)
    monkeypatch.setattr("roblox_viral.web.jobs.tempo_finished_video", fake_tempo)

    job = mgr.create(
        s,
        "clip.mp4",
        "One line only here.\n",
        "Kore",
        tts_provider="gemini",
        video_speed=160,
    )
    mgr.run_job(s, job.id)
    assert seen["render"]["video_speed"] == 100
    render_out = Path(seen["render"]["output_path"])
    assert render_out.name == "render_1x.mp4"
    assert seen["tempo"]["video_speed"] == 160
    assert seen["tempo"]["mode"] == "single"
    assert Path(seen["tempo"]["input_path"]) == render_out
    final = s.outputs_dir / mgr.get(job.id, s).output_name
    assert Path(seen["tempo"]["output_path"]) == final
    assert final.read_bytes() == b"mp4-sped"
    assert not render_out.is_file()  # deleted after success
    assert mgr.get(job.id, s).status == "done"


def test_run_job_edge_still_passes_configured_video_speed(tmp_path, monkeypatch):
    """Regression: Edge must not force 100 or call tempo_finished_video."""
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    seen = {}

    def fake_synthesize(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [WordTiming("One", 0, 100)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_video(**kwargs):
        seen["render"] = kwargs
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    def boom_tempo(**kwargs):
        raise AssertionError("tempo must not run for edge")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)
    monkeypatch.setattr("roblox_viral.web.jobs.tempo_finished_video", boom_tempo)

    job = mgr.create(
        s,
        "clip.mp4",
        "One line only here.\n",
        "en-US-EmmaNeural",
        video_speed=175,
    )
    mgr.run_job(s, job.id)
    assert seen["render"]["video_speed"] == 175
    assert mgr.get(job.id, s).status == "done"


def test_run_job_gemini_reddit_plans_at_100_then_tempos(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    s = _settings(tmp_path, monkeypatch)
    # Ensure library has at least one video for reddit mode (reuse helpers from existing reddit tests)
    videos_dir = s.videos_dir
    videos_dir.mkdir(parents=True, exist_ok=True)
    (videos_dir / "a.mp4").write_bytes(b"vid")

    mgr = JobManager()
    seen = {}

    def fake_gemini_synth(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [WordTiming("One", 0, 500), WordTiming("line", 500, 1000)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_plan(paths, sentence_durations_s, *, video_speed, durations):
        seen["plan_speed"] = video_speed
        from roblox_viral.reddit_clips import ClipSegment

        return [
            ClipSegment(path=paths[0], start_s=0.0, duration_s=1.0)
            for _ in sentence_durations_s
        ]

    def fake_build(segments, output_path, *, work_dir=None):
        Path(output_path).write_bytes(b"bg")

    def fake_render_video(**kwargs):
        seen["render"] = dict(kwargs)
        Path(kwargs["output_path"]).write_bytes(b"mp4-1x")

    def fake_card(*a, **k):
        if a and hasattr(a[-1], "write_bytes"):
            Path(a[-1]).write_bytes(b"png")
        elif "output_path" in k:
            Path(k["output_path"]).write_bytes(b"png")

    def fake_tempo(**kwargs):
        seen["tempo"] = dict(kwargs)
        Path(kwargs["output_path"]).write_bytes(b"sped")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.GeminiTTSProvider.synthesize", fake_gemini_synth
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.plan_reddit_sentence_clips", fake_plan)
    monkeypatch.setattr("roblox_viral.web.jobs.build_reddit_background", fake_build)
    monkeypatch.setattr("roblox_viral.web.jobs.render_reddit_card", fake_card)
    monkeypatch.setattr("roblox_viral.web.jobs.render_hook_cover", fake_card)
    monkeypatch.setattr("roblox_viral.web.jobs.probe_duration_seconds", lambda p: 10.0)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)
    monkeypatch.setattr("roblox_viral.web.jobs.tempo_finished_video", fake_tempo)

    job = mgr.create(
        s,
        "",
        "One line only here.\n",
        "Kore",
        mode="reddit",
        tts_provider="gemini",
        video_speed=200,
    )
    mgr.run_job(s, job.id)
    assert seen["plan_speed"] == 100
    assert seen["render"]["video_speed"] == 100
    assert seen["tempo"]["video_speed"] == 200
    assert seen["tempo"]["mode"] == "reddit"
    assert mgr.get(job.id, s).status == "done"
```

If existing reddit job tests use a different `_settings` / source_name convention, mirror that file’s working reddit test (`test_run_job_reddit_*`) for create args and card mocks — keep assertions on `plan_speed == 100`, render 100, tempo 200.

- [ ] **Step 2: Run new job tests — expect fail**

```bash
pytest tests/web/test_jobs.py::test_run_job_gemini_tempos_when_video_speed_not_100 tests/web/test_jobs.py::test_run_job_gemini_forces_render_video_speed_100 -v
```

Expected: FAIL (no `tempo_finished_video` import / Pass 1 still uses 160)

- [ ] **Step 3: Implement jobs wiring**

In `src/roblox_viral/web/jobs.py`:

1. Import:

```python
from roblox_viral.render import (
    # existing imports...
    tempo_finished_video,
)
```

(If `render_video` / `render_still` / `build_reddit_background` are already imported from `roblox_viral.render`, add `tempo_finished_video` to that import.)

2. Before media planning / render, compute:

```python
render_video_speed = (
    100 if record.tts_provider == "gemini" else record.video_speed
)
```

3. Use `render_video_speed` (not `record.video_speed`) in:
   - `plan_reddit_sentence_clips(..., video_speed=render_video_speed, ...)`
   - `render_video(..., video_speed=render_video_speed, ...)`
   - (picture `render_still` has no video_speed — unchanged)

4. Choose Pass 1 output path:

```python
needs_tempo = (
    record.tts_provider == "gemini" and record.video_speed != 100
)
pass1_path = (
    job_dir / "render_1x.mp4" if needs_tempo else output_path
)
```

Pass `pass1_path` as `output_path=` to `render_video` / `render_still`.

5. After successful Pass 1:

```python
if needs_tempo:
    tempo_finished_video(
        input_path=pass1_path,
        output_path=output_path,
        video_speed=record.video_speed,
        mode=record.mode,
    )
    try:
        pass1_path.unlink(missing_ok=True)
    except OSError:
        pass
```

Keep `record.output_name = output_name` pointing at the final (sped) file. Do not change status between passes.

- [ ] **Step 4: Run job tests — expect PASS**

```bash
pytest tests/web/test_jobs.py::test_run_job_gemini_forces_render_video_speed_100 tests/web/test_jobs.py::test_run_job_gemini_tempos_when_video_speed_not_100 tests/web/test_jobs.py::test_run_job_edge_still_passes_configured_video_speed tests/web/test_jobs.py::test_run_job_gemini_reddit_plans_at_100_then_tempos tests/web/test_jobs.py::test_run_job_passes_video_speed_to_render -v
```

Expected: PASS

- [ ] **Step 5: Full regression**

```bash
pytest -q
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/roblox_viral/web/jobs.py tests/web/test_jobs.py
git commit -m "feat(jobs): Gemini video_speed via post-render tempo"
```

---

## Spec coverage

| Spec requirement | Task |
|------------------|------|
| Gemini-only post tempo | 2 |
| Pass 1 forced `video_speed=100` | 2 |
| Skip Pass 2 at 100% | 1 (copy/no-op) + 2 (no call) |
| `setpts` + chained `atempo` | 1 |
| Reddit ≤500% | 1 + 2 reddit test |
| Edge unchanged | 2 regression test |
| No new job status / no UI | — (non-goals) |
| Delete `render_1x` on success | 2 |

## Self-review

- No TBD/placeholder steps
- `tempo_finished_video` / `build_atempo_filters` names consistent across tasks
- Picture mode: Pass 1 still → Pass 2 tempo when Gemini + ≠100 (covered by same `needs_tempo` + `pass1_path` on `render_still`)
