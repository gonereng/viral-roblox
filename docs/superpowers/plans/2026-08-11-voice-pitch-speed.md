# Voice Pitch & Speed Sliders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Generate-page pitch (−50…+50, default +15 → `+NHz`) and speed (50…200%, default 130 → Edge `rate`) sliders so TTS and karaoke change without speeding gameplay video.

**Architecture:** Pure mappers in `voice.py`; `EdgeTTSProvider` passes `rate`/`pitch` to `edge_tts.Communicate`; jobs/API carry int `pitch`/`speed`; Generate form range inputs post them. Captions/render unchanged.

**Tech Stack:** Python 3.10+, edge-tts, FastAPI, Jinja2, vanilla JS, pytest

## Global Constraints

- Pitch UI: −50 … +50, step 1, default **15** (label `+15%`); Edge: `+NHz` / `-NHz`
- Speed UI: 50 … 200, step 1, default **130**; Edge rate: `+(S-100)%` / `-(100-S)%` (130 → `+30%`)
- Out of range → HTTP 400 (or `ValueError` from helpers used by API)
- Gameplay video not time-stretched; only TTS (+ word timings)
- CLI unchanged
- No preference persistence
- Spec: `docs/superpowers/specs/2026-08-11-voice-pitch-speed-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/voice.py` | `format_edge_pitch` / `format_edge_rate`; provider kwargs |
| `tests/test_voice.py` | Mapper + Communicate kwargs tests |
| `src/roblox_viral/web/jobs.py` | JobRecord + create/run with pitch/speed |
| `src/roblox_viral/web/app.py` | CreateJobBody + validation |
| `tests/web/test_jobs.py` | Provider constructed with mapped strings |
| `tests/web/test_api.py` | Accept / reject pitch/speed |
| `src/roblox_viral/web/templates/generate.html` | Range inputs |
| `src/roblox_viral/web/static/app.js` | Labels + POST fields |
| `src/roblox_viral/web/static/app.css` | Minimal slider layout |

---

### Task 1: Edge pitch/rate helpers + provider

**Files:**
- Modify: `src/roblox_viral/voice.py`
- Create: `tests/test_voice.py`

**Interfaces:**
- Produces:
  - `DEFAULT_PITCH = 15`
  - `DEFAULT_SPEED = 130`
  - `PITCH_MIN, PITCH_MAX = -50, 50`
  - `SPEED_MIN, SPEED_MAX = 50, 200`
  - `format_edge_pitch(pitch: int) -> str` — raise `ValueError` if out of range; `0` → `"+0Hz"`; positive `"+{n}Hz"`; negative `"{n}Hz"` (already has `-`)
  - `format_edge_rate(speed_percent: int) -> str` — raise `ValueError` if out of range; delta `speed_percent - 100`; `0` → `"+0%"`; else signed percent string
  - `EdgeTTSProvider.__init__(self, voice: str = "en-US-EmmaNeural", *, rate: str = "+0%", pitch: str = "+0Hz")`
  - `Communicate(..., rate=self.rate, pitch=self.pitch, boundary="WordBoundary")`

- [ ] **Step 1: Write failing tests**

Create `tests/test_voice.py`:

```python
from roblox_viral.voice import (
    DEFAULT_PITCH,
    DEFAULT_SPEED,
    EdgeTTSProvider,
    format_edge_pitch,
    format_edge_rate,
)


def test_format_edge_pitch_defaults_and_signs():
    assert DEFAULT_PITCH == 15
    assert format_edge_pitch(15) == "+15Hz"
    assert format_edge_pitch(0) == "+0Hz"
    assert format_edge_pitch(-10) == "-10Hz"


def test_format_edge_pitch_rejects_out_of_range():
    with pytest.raises(ValueError):
        format_edge_pitch(-51)
    with pytest.raises(ValueError):
        format_edge_pitch(51)


def test_format_edge_rate_defaults_and_signs():
    assert DEFAULT_SPEED == 130
    assert format_edge_rate(130) == "+30%"
    assert format_edge_rate(100) == "+0%"
    assert format_edge_rate(50) == "-50%"
    assert format_edge_rate(200) == "+100%"


def test_format_edge_rate_rejects_out_of_range():
    with pytest.raises(ValueError):
        format_edge_rate(49)
    with pytest.raises(ValueError):
        format_edge_rate(201)


def test_edge_tts_provider_passes_rate_and_pitch(tmp_path, monkeypatch):
    seen = {}

    class FakeCommunicate:
        def __init__(self, text, voice, **kwargs):
            seen["text"] = text
            seen["voice"] = voice
            seen.update(kwargs)

        async def stream(self):
            yield {"type": "audio", "data": b"ID3fake"}

    import types
    import sys

    fake_mod = types.ModuleType("edge_tts")
    fake_mod.Communicate = FakeCommunicate
    monkeypatch.setitem(sys.modules, "edge_tts", fake_mod)

    out = tmp_path / "n.mp3"
    EdgeTTSProvider(
        voice="en-US-EmmaNeural",
        rate="+30%",
        pitch="+15Hz",
    ).synthesize("Hello", out)
    assert seen["rate"] == "+30%"
    assert seen["pitch"] == "+15Hz"
    assert seen["boundary"] == "WordBoundary"
    assert out.is_file()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_voice.py -v`

Expected: FAIL (imports / missing helpers)

- [ ] **Step 3: Implement helpers + provider kwargs**

In `src/roblox_viral/voice.py`, add constants and formatters near the top (after imports):

```python
DEFAULT_PITCH = 15
DEFAULT_SPEED = 130
PITCH_MIN, PITCH_MAX = -50, 50
SPEED_MIN, SPEED_MAX = 50, 200


def format_edge_pitch(pitch: int) -> str:
    if not isinstance(pitch, int) or isinstance(pitch, bool):
        raise ValueError("pitch must be an int")
    if pitch < PITCH_MIN or pitch > PITCH_MAX:
        raise ValueError(f"pitch must be between {PITCH_MIN} and {PITCH_MAX}")
    if pitch >= 0:
        return f"+{pitch}Hz"
    return f"{pitch}Hz"


def format_edge_rate(speed_percent: int) -> str:
    if not isinstance(speed_percent, int) or isinstance(speed_percent, bool):
        raise ValueError("speed must be an int")
    if speed_percent < SPEED_MIN or speed_percent > SPEED_MAX:
        raise ValueError(
            f"speed must be between {SPEED_MIN} and {SPEED_MAX}"
        )
    delta = speed_percent - 100
    if delta >= 0:
        return f"+{delta}%"
    return f"{delta}%"
```

Update `EdgeTTSProvider`:

```python
class EdgeTTSProvider:
    def __init__(
        self,
        voice: str = "en-US-EmmaNeural",
        *,
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    async def _synthesize_async(self, text: str, output_path: Path) -> list[WordTiming]:
        import edge_tts

        output_path.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=self.rate,
            pitch=self.pitch,
            boundary="WordBoundary",
        )
        # ... rest unchanged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_voice.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/voice.py tests/test_voice.py
git commit -m "feat: Edge TTS pitch and rate formatting"
```

---

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

### Task 3: Generate page sliders

**Files:**
- Modify: `src/roblox_viral/web/templates/generate.html`
- Modify: `src/roblox_viral/web/static/app.js`
- Modify: `src/roblox_viral/web/static/app.css`

**Interfaces:**
- Consumes: API `pitch` / `speed` ints
- Produces: form controls with ids `pitch`, `speed`, labels `pitch-value`, `speed-value`

- [ ] **Step 1: Add HTML sliders after voice select**

In `generate.html`, after the Voice `</label>` and before the Generate button:

```html
    <label class="slider-field">
      Pitch <span id="pitch-value">+15%</span>
      <input id="pitch" name="pitch" type="range" min="-50" max="50" step="1" value="15" />
    </label>

    <label class="slider-field">
      Speed <span id="speed-value">130%</span>
      <input id="speed" name="speed" type="range" min="50" max="200" step="1" value="130" />
    </label>
```

- [ ] **Step 2: Wire JS labels + payload**

In `app.js`, near the top of the generate form setup (after getting `form`):

```javascript
  const pitchInput = document.getElementById("pitch");
  const speedInput = document.getElementById("speed");
  const pitchValue = document.getElementById("pitch-value");
  const speedValue = document.getElementById("speed-value");

  function formatPitchLabel(n) {
    const v = Number(n);
    return (v > 0 ? "+" : "") + v + "%";
  }
  function formatSpeedLabel(n) {
    return Number(n) + "%";
  }
  function syncVoiceSliders() {
    if (pitchValue) pitchValue.textContent = formatPitchLabel(pitchInput.value);
    if (speedValue) speedValue.textContent = formatSpeedLabel(speedInput.value);
  }
  if (pitchInput && speedInput) {
    pitchInput.addEventListener("input", syncVoiceSliders);
    speedInput.addEventListener("input", syncVoiceSliders);
    syncVoiceSliders();
  }
```

Update payload:

```javascript
    const payload = {
      source_name: document.getElementById("source_name").value,
      story: document.getElementById("story").value,
      voice: document.getElementById("voice").value,
      pitch: Number(document.getElementById("pitch").value),
      speed: Number(document.getElementById("speed").value),
    };
```

- [ ] **Step 3: Minimal CSS**

In `app.css`, add:

```css
.slider-field input[type="range"] {
  width: 100%;
  display: block;
  margin-top: 0.35rem;
}
.slider-field span {
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 4: Smoke-check related tests still pass**

Run: `pytest tests/web/test_api.py tests/web/test_jobs.py tests/test_voice.py -q`

Expected: PASS

Manual: rebuild Docker if used; open Generate; confirm defaults +15% / 130%; generate still works.

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/templates/generate.html src/roblox_viral/web/static/app.js src/roblox_viral/web/static/app.css
git commit -m "feat(web): pitch and speed sliders on Generate"
```

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Sliders + defaults + labels | Task 3 |
| Edge Hz / rate mapping | Task 1 |
| Jobs/API fields + validation | Task 2 |
| Captions follow TTS timings | Implicit (no caption changes) |
| Video not sped up | Implicit (no render changes) |
| CLI unchanged | Honored |
| Tests helpers/provider/API/job | Tasks 1–2 |

No placeholders. Types: `pitch: int`, `speed: int`, Edge strings via formatters.
