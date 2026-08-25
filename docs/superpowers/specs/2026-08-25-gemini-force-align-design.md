# Gemini Karaoke Force-Align (stable-ts) — Design

**Date:** 2026-08-25  
**Status:** Approved (conversation)  

## Goal

Fix Gemini TTS karaoke desync by replacing faster-whisper **free transcription** with **stable-ts force-alignment** of the known script to the narration audio. Language is configurable (default German).

## Problem (evidence)

Recent Gemini jobs (including `video_speed=100`, so post-render tempo is irrelevant) showed:

- Speech from t=0 in `narration.mp3`, but first ASS word ~6.6s late
- Many words collapsed onto identical timestamps (50ms flash pile-ups)
- Root cause: `align_words_with_whisper` called `model.transcribe(..., initial_prompt=...)` — not true force-align against the script

## Product decisions

| Decision | Choice |
|----------|--------|
| Aligner | **stable-ts** `align()` over faster-whisper backend |
| Script | Full TTS text already used for Gemini synthesize |
| Language | Env/setting `WHISPER_ALIGN_LANGUAGE`, default **`de`** |
| Per-job language | Out of scope v1 |
| Model | Env/setting `WHISPER_ALIGN_MODEL`, default **`base`** |
| Device | CPU, `int8` (Docker slim, no GPU assumed) |
| Failure | Clear RuntimeError / job error if align returns no words |
| Edge path | Unchanged |
| Post-render tempo | Unchanged (orthogonal) |

## Architecture

```
GeminiTTSProvider.synthesize(text, out.mp3):
  PCM → MP3 (unchanged)
  align_words_force(out.mp3, text, language, model_size)
    → stable_whisper.load_faster_whisper(model_size, device=cpu, compute_type=int8)
    → model.align(audio, text, language=language)
    → list[WordTiming] from result words (start/end seconds → ms)
  write_ass(words, ...)  # existing
```

### Settings

Add to `Settings` / `load_settings`:

- `whisper_align_language: str` ← `WHISPER_ALIGN_LANGUAGE` or `"de"`
- `whisper_align_model: str` ← `WHISPER_ALIGN_MODEL` or `"base"`

Pass into `GeminiTTSProvider` (or the align helper) from `run_job` via settings.

### Cache / Docker

- `docker-compose.yml`: forward optional env vars; mount a host cache dir for Whisper/HF weights (exact path confirmed during implementation against faster-whisper/stable-ts defaults, e.g. under `media/.cache/...`)
- First align after cold cache downloads weights; subsequent jobs reuse

### README

Short note: Gemini karaoke uses stable-ts force-align; default language `de`; override with `WHISPER_ALIGN_LANGUAGE` / `WHISPER_ALIGN_MODEL`.

## Testing

- Mock stable-ts align → assert `WordTiming` list and language/model passed through
- Settings defaults `de` / `base`
- Existing Gemini synthesize tests keep using injectable `align_fn`
- No mandatory real-model CI smoke in v1

## Non-goals (v1)

- Per-job / UI language control
- WhisperX, MFA, or heuristic redistribute-only fix
- Baking model weights into the Docker image
- Changing ASS karaoke styling or Edge alignment
