# Task 1 Report: Edge pitch/rate helpers + provider

## Status: DONE

## Summary

Implemented Edge TTS pitch and rate formatting helpers plus provider kwargs per the task brief. Followed TDD: failing tests → implementation → all tests passing → commit.

## Changes

### `src/roblox_viral/voice.py`

- Added constants: `DEFAULT_PITCH = 15`, `DEFAULT_SPEED = 130`, `PITCH_MIN/PITCH_MAX = -50/50`, `SPEED_MIN/SPEED_MAX = 50/200`
- Added `format_edge_pitch(pitch: int) -> str` — validates int range, formats signed Hz strings (`0` → `"+0Hz"`, positive `"+{n}Hz"`, negative `"{n}Hz"`)
- Added `format_edge_rate(speed_percent: int) -> str` — validates int range, converts percent to delta from 100, formats signed percent strings
- Updated `EdgeTTSProvider.__init__` with keyword-only `rate` and `pitch` parameters (defaults `"+0%"`, `"+0Hz"`)
- Updated `edge_tts.Communicate(...)` call to pass `rate=self.rate`, `pitch=self.pitch`, `boundary="WordBoundary"`

### `tests/test_voice.py` (new)

- `test_format_edge_pitch_defaults_and_signs`
- `test_format_edge_pitch_rejects_out_of_range`
- `test_format_edge_rate_defaults_and_signs`
- `test_format_edge_rate_rejects_out_of_range`
- `test_edge_tts_provider_passes_rate_and_pitch`

## Test Results

```
pytest tests/test_voice.py -v
5 passed in 0.12s
```

### TDD verification

- Step 2 (pre-implementation): ImportError — `cannot import name 'DEFAULT_PITCH'` — confirmed failing state
- Step 4 (post-implementation): 5/5 PASSED

## Commit

```
feat: Edge TTS pitch and rate formatting
```

Files committed: `src/roblox_viral/voice.py`, `tests/test_voice.py`

## Concerns

None.

## Out of Scope (later tasks)

- Wiring pitch/speed into jobs, API, and UI
- Using `DEFAULT_PITCH` / `DEFAULT_SPEED` at call sites (helpers exported for downstream tasks)
