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
import pytest

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

