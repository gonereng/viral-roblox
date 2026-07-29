# Roblox Viral Storytime Generator — Design

**Date:** 2026-07-27  
**Status:** Approved

## Goal

A Python CLI that turns a Roblox gameplay clip plus a short story into a TikTok/Shorts-ready vertical video: muted looping gameplay, Edge TTS narration, and karaoke word-highlight captions synced to speech.

## Product decisions

- Storytime over full-screen gameplay (not auto-edited cuts)
- Karaoke word highlight within caption lines
- Loop gameplay until narration ends; mute original game audio
- Force vertical 9:16 at 1080×1920 (center crop/cover)
- Edge TTS first, with a `VoiceProvider` interface for later ElevenLabs
- Out of v1: GUI, batch mode, BGM, LLM story generation, upload

## Architecture

```
video + story
    → story.py (normalize, sentence split)
    → voice.py EdgeTTSProvider (audio + word timestamps)
    → captions.py (ASS karaoke)
    → render.py ffmpeg (mute, loop, crop, burn ASS, mux)
    → 1080×1920 MP4
```

### Modules

| Module | Responsibility |
|--------|----------------|
| `story.py` | Load/normalize text; split on `.?!` into sentences |
| `voice.py` | `VoiceProvider` protocol; `EdgeTTSProvider.synthesize()` → audio path + word timings |
| `captions.py` | Chunk ~4–6 words/line; ASS karaoke; white + black outline; yellow active word |
| `render.py` | ffmpeg orchestration; temp cleanup; `--keep-temp` |
| `cli.py` | `--video`, `--story` / `--story-text`, `--out`, `--voice`, `--keep-temp` |

## Captions

- Position: center, lower-middle
- Font: Arial Black (Impact-like fallback)
- Large size for 1080×1920
- White text, thick black outline; active word yellow/gold
- Long sentences split into chunks of ~4–6 words

## Voice

- Default: `en-US-EmmaNeural`
- Timings from Edge TTS word-boundary events (no Whisper)
- Interface returns `(audio_path, list[{text, start_ms, end_ms}])`

## Render

1. Probe video; get TTS audio duration
2. Mute video; loop/trim to audio length
3. Center-crop/scale cover to 1080×1920
4. Burn ASS via ffmpeg `ass`/`subtitles` filter
5. Mux TTS as sole audio (H.264 + AAC)

## Errors

Missing ffmpeg, bad paths, empty story, or TTS failure → non-zero exit with a clear message. Temp files cleaned unless `--keep-temp`.
