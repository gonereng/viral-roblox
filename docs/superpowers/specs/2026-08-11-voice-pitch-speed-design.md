# Voice Pitch & Speed Sliders — Design

**Date:** 2026-08-11  
**Status:** Approved (conversation)  
**Builds on:** [2026-07-29-roblox-viral-webapp-design.md](./2026-07-29-roblox-viral-webapp-design.md)

## Goal

On the Generate page, let the user set TTS pitch and speaking rate via sliders (defaults +15% pitch / 130% speed). Karaoke captions follow the resulting word timings. Gameplay video is **not** time-stretched — only voice and text timing change.

## Product decisions

- **UI:** Two range inputs on Generate, under the voice select
- **Pitch:** −50 … +50, step 1, default **+15**; label shows `+15%` (etc.)
- **Speed:** 50% … 200%, step 1, default **130%**; label shows current percent
- **Edge mapping:** Pitch UI value `N` → Edge `pitch` `+NHz` / `-NHz` (treat “%” label as Hz for Edge). Speed `S` → Edge `rate` `+(S-100)%` or `-(100-S)%` (130 → `+30%`)
- **Persistence:** Form defaults only; refresh resets; not stored in settings/DB
- **CLI:** unchanged (out of scope)
- **Video:** `render_video` unchanged; duration still follows TTS audio length; no `setpts` / playback-rate on gameplay
- **Captions:** unchanged logic — consume Edge word boundaries from the pitched/rated synth

## Architecture

```
Generate form (pitch, speed sliders)
  → POST /api/jobs { source_name, story, voice, pitch, speed }
  → JobManager.create(..., pitch, speed)
  → EdgeTTSProvider(voice, rate=..., pitch=...).synthesize(...)
  → write_ass(words) + render_video(...)  # existing
```

### Mapping helpers

Place small pure functions (e.g. in `voice.py`):

- `format_edge_pitch(pitch: int) -> str` — clamp/validate −50…+50; `0` → `+0Hz`
- `format_edge_rate(speed_percent: int) -> str` — clamp/validate 50…200; `100` → `+0%`

### EdgeTTSProvider

Extend constructor:

```python
EdgeTTSProvider(voice=..., rate="+0%", pitch="+0Hz")
```

Pass `rate=` and `pitch=` into `edge_tts.Communicate(...)`.

### Job / API

- `JobRecord` fields: `pitch: int`, `speed: int` (store UI values)
- `GenerateJobBody` (or equivalent): optional `pitch` / `speed` with server defaults **15** / **130** if omitted
- Validate ranges; invalid → HTTP 400
- `run_job` builds provider with `format_edge_rate(record.speed)` and `format_edge_pitch(record.pitch)`

### Frontend

- `generate.html`: two `<input type="range">` + `<output>`/span for live labels
- `app.js`: read values into job POST JSON; update labels on `input`
- Light CSS consistent with existing Generate form

## Testing

- Helper unit tests: defaults, signs, bounds
- Provider: monkeypatch Communicate; assert rate/pitch kwargs
- API create: accepts values; out-of-range → 400
- Job run: mocked provider receives mapped strings
- Existing caption/render tests remain valid

## Non-goals

- CLI `--pitch` / `--rate`
- Saving user preferences
- Preview/listen before generate
- Changing gameplay playback speed
- ElevenLabs or other TTS backends
