### Task 2: Jobs + API pitch/speed

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `src/roblox_viral/web/app.py`
- Modify: `tests/web/test_jobs.py`
- Modify: `tests/web/test_api.py`

**Interfaces:**
- Consumes: `format_edge_pitch`, `format_edge_rate`, `DEFAULT_PITCH`, `DEFAULT_SPEED`, `EdgeTTSProvider(..., rate=, pitch=)`
- Produces:
  - `JobRecord.pitch: int = DEFAULT_PITCH`
  - `JobRecord.speed: int = DEFAULT_SPEED`
  - `JobManager.create(..., voice, pitch: int = DEFAULT_PITCH, speed: int = DEFAULT_SPEED)`
  - `CreateJobBody.pitch: int | None = None`, `speed: int | None = None`
  - API uses defaults when null; validates via formatters (or explicit range check) before create

- [ ] **Step 1: Write failing API / job tests**

Append to `tests/web/test_api.py` (reuse existing `_client` / login helpers already in that file):

```python
def test_create_job_accepts_pitch_and_speed(tmp_path, monkeypatch):
    # same setup pattern as existing create-job success test:
    # ensure a source file exists, login, POST with pitch/speed
    ...
    r = c.post(
        "/api/jobs",
        json={
            "source_name": "clip.mp4",
            "story": "Hi.\n",
            "voice": "en-US-EmmaNeural",
            "pitch": 15,
            "speed": 130,
        },
    )
    assert r.status_code == 200


def test_create_job_rejects_bad_pitch(tmp_path, monkeypatch):
    ...
    r = c.post(
        "/api/jobs",
        json={
            "source_name": "clip.mp4",
            "story": "Hi.\n",
            "voice": "en-US-EmmaNeural",
            "pitch": 99,
            "speed": 130,
        },
    )
    assert r.status_code == 400
```

Mirror the fixture/setup from `test_create_job_starts` (or whichever existing success test) in the same file — copy its media/login/monkeypatch preamble exactly.

In `tests/web/test_jobs.py`, add:

```python
def test_run_job_passes_pitch_and_speed_to_tts(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.sources_dir / "clip.mp4").write_bytes(b"x")
    mgr = JobManager()
    constructed = {}

    class FakeProvider:
        def __init__(self, voice, *, rate="+0%", pitch="+0Hz"):
            constructed["voice"] = voice
            constructed["rate"] = rate
            constructed["pitch"] = pitch

        def synthesize(self, text, output_path):
            Path(output_path).write_bytes(b"mp3")
            return [WordTiming("One", 0, 100)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_video(**kwargs):
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    monkeypatch.setattr("roblox_viral.web.jobs.EdgeTTSProvider", FakeProvider)
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)

    job = mgr.create(
        s, "clip.mp4", "One line only here.\n", "en-US-EmmaNeural",
        pitch=15, speed=130,
    )
    mgr.run_job(s, job.id)
    assert constructed["rate"] == "+30%"
    assert constructed["pitch"] == "+15Hz"
    assert mgr.get(job.id, s).status == "done"
```

Adapt `_settings` / patterns to match existing helpers in that file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/web/test_api.py tests/web/test_jobs.py -k "pitch or speed" -v`

Expected: FAIL (missing params / fields)

- [ ] **Step 3: Implement jobs + API**

`JobRecord` — add fields with defaults:

```python
from roblox_viral.voice import (
    DEFAULT_PITCH,
    DEFAULT_SPEED,
    EdgeTTSProvider,
    format_edge_pitch,
    format_edge_rate,
)

@dataclass
class JobRecord:
    ...
    pitch: int = DEFAULT_PITCH
    speed: int = DEFAULT_SPEED
```

`create` signature:

```python
def create(
    self,
    settings: Settings,
    source_name: str,
    story: str,
    voice: str,
    pitch: int = DEFAULT_PITCH,
    speed: int = DEFAULT_SPEED,
) -> JobRecord:
    format_edge_pitch(pitch)  # validate
    format_edge_rate(speed)
    ...
    record = JobRecord(..., pitch=pitch, speed=speed, ...)
```

In `get()` when loading `status.json`, read:

```python
pitch=int(data["pitch"]) if "pitch" in data else DEFAULT_PITCH,
speed=int(data["speed"]) if "speed" in data else DEFAULT_SPEED,
```

(wrap in try already present; bad types fall through to None return)

In `run_job` synthesize call:

```python
words = EdgeTTSProvider(
    record.voice,
    rate=format_edge_rate(record.speed),
    pitch=format_edge_pitch(record.pitch),
).synthesize(join_for_tts(sentences), narration_path)
```

`CreateJobBody`:

```python
class CreateJobBody(BaseModel):
    source_name: str = ""
    story: str = ""
    voice: str | None = None
    pitch: int | None = None
    speed: int | None = None
```

In `create_job` handler:

```python
from roblox_viral.voice import DEFAULT_PITCH, DEFAULT_SPEED, format_edge_pitch, format_edge_rate

pitch = DEFAULT_PITCH if body.pitch is None else body.pitch
speed = DEFAULT_SPEED if body.speed is None else body.speed
try:
    format_edge_pitch(pitch)
    format_edge_rate(speed)
except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
record = mgr.create(settings, source_name, story, voice, pitch=pitch, speed=speed)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/web/test_api.py tests/web/test_jobs.py tests/test_voice.py -q`

Expected: PASS (fix any call sites that need `pitch=`/`speed=` defaults — dataclass defaults should keep old `create(...)` calls working)

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/jobs.py src/roblox_viral/web/app.py tests/web/test_jobs.py tests/web/test_api.py
git commit -m "feat(web): pass pitch and speed through jobs API"
```

---

