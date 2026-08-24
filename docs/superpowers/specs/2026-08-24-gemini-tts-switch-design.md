# Edge vs Gemini TTS Provider Switch — Design

**Date:** 2026-08-24  
**Status:** Approved (conversation)  

## Goal

Add a Generate-page (and n8n) switch to synthesize narration with either **Edge TTS** (current default) or **Gemini TTS** (`gemini-3.1-flash-tts-preview`, verified working with the project API key). Karaoke captions continue to work under Gemini via **faster-whisper** force-alignment against the known script.

## Probe result (2026-08-24)

| Model | Result |
|-------|--------|
| `gemini-3.1-flash-tts-preview` | OK — PCM `audio/L16;rate=24000` |
| `gemini-2.5-flash-preview-tts` | 400 (prompt / TTS-only constraint) |
| `gemini-2.5-pro-preview-tts` | 429 quota |

## Product decisions

| Decision | Choice |
|----------|--------|
| UI toggle | Above Voice dropdown: **Edge TTS** \| **Gemini** |
| Default | Edge |
| Edge voices | Existing English Edge list |
| Gemini voices | Fixed 30 prebuilt names (Zephyr, Kore, Puck, …) |
| Pitch / speed sliders | Edge only; hidden when Gemini selected |
| Job field | `tts_provider: "edge" \| "gemini"` (+ existing `voice`) |
| n8n | Optional `tts_provider` form field; default `edge` |
| Gemini model | `gemini-3.1-flash-tts-preview` only |
| Alignment | faster-whisper `tiny` word timestamps vs known text |
| Missing `GEMINI_API_KEY` + gemini | 503 (API) / job error with clear message |
| Invalid Gemini voice | 400 |

## Architecture

```
UI: tts_provider toggle → voice list swap → hide pitch/speed if gemini
POST /api/jobs | /api/v1/videos { tts_provider, voice, ... }

run_job synthesizing:
  if edge → EdgeTTSProvider(voice, rate, pitch).synthesize → WordTiming
  if gemini → GeminiTTSProvider(api_key, voice).synthesize:
       generateContent AUDIO + speechConfig.voiceName
       decode L16 PCM → wav/mp3 via ffmpeg
       faster-whisper tiny align → WordTiming
  write_ass(words, ...) → render as today
```

### GeminiTTSProvider

- Input: full TTS script string (same as Edge), output path for `narration.mp3`
- Call Gemini with `responseModalities: ["AUDIO"]` and `prebuiltVoiceConfig.voiceName`
- Convert returned PCM to MP3 with existing ffmpeg helper path
- Run faster-whisper on the audio with the known transcript to produce `list[WordTiming]`
- Raise clear errors on API / align failure

### Jobs / persistence

- Add `tts_provider` to `JobRecord` (default `"edge"`), hydrate from `status.json`
- `create` validates provider + voice set for that provider
- Pitch/speed still stored but ignored for Gemini synthesis

## Testing

- Unit: Gemini voice allowlist validation
- Unit/mocked: GeminiTTSProvider converts mock PCM + mocked whisper → WordTiming
- Jobs: `tts_provider=gemini` selects Gemini path; edge path unchanged
- API: optional `tts_provider`; missing key → 503 for gemini
- UI: Generate HTML has toggle; pitch/speed field hidden for Gemini (test markup / data attrs)

## Non-goals (v1)

- Gemini style prompts / audio tags UI
- Multi-speaker Gemini
- Pitch/speed mapping for Gemini
- Baking whisper weights into the Docker image (download on first use OK)
- Replacing Edge as default
