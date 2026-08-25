# Gemini Video Speed via Post-Render — Design

**Date:** 2026-08-25  
**Status:** Approved (conversation)  

## Goal

For **Gemini TTS jobs only**, apply the configured **Video speed** by re-timing the finished vertical MP4 after a normal 1× render (voice + burned karaoke). Edge jobs keep today’s in-render `video_speed` behavior.

## Product decisions

| Decision | Choice |
|----------|--------|
| Trigger | `tts_provider == "gemini"` only |
| Control | Existing **Video speed** slider / `video_speed` field (already visible for Gemini) |
| Pass 1 | Always render as if `video_speed=100` (Reddit clip math, `setpts`, still path) |
| Pass 2 | If configured `video_speed != 100`, tempo the finished MP4 (A+V) to that % |
| Skip Pass 2 | When `video_speed == 100` — Pass 1 output is final |
| Pitch | Preserve with `atempo` (not chipmunk `asetrate`) |
| Edge | Unchanged — `video_speed` still applied during render |
| Voice Speed / Pitch | Stay hidden for Gemini; unused for this feature |
| Job status | Stay on `"rendering"` through both passes (no new status) |
| UI | No Generate-page change |

## Why post-render

Gemini does not use Edge rate. Speeding the finished file keeps burned karaoke, title-card overlays, gameplay, and voice locked together. Retiming ASS + audio before a single render is more fragile.

## Architecture

```
run_job (gemini):
  synthesize + write_ass  (natural pace)
  effective_vs = 100 for Pass 1
  plan clips / render_* → temp or final
    if video_speed == 100:
      write straight to outputs/{name}.mp4
    else:
      write job_dir/render_1x.mp4
      tempo_finished_video(1x → outputs/{name}.mp4, video_speed)
      delete render_1x.mp4 on success

run_job (edge):
  unchanged (pass record.video_speed into plan/render)
```

### Pass 2 ffmpeg helper

- New helper (e.g. `tempo_finished_video` in `render.py`):
  - Video: `setpts=100/{video_speed}*PTS`
  - Audio: chain `atempo` factors in `[0.5, 2.0]` so Single 50–200% and Reddit 100–500% are covered
  - Re-encode to the same vertical H.264/AAC profile used for finals today
- Validate `video_speed` with existing `validate_video_speed(..., mode=...)`

### Jobs wiring

- In `run_job`, when `tts_provider == "gemini"`:
  - Pass `video_speed=100` into `plan_reddit_sentence_clips` / `render_video` / still path as applicable
  - After successful Pass 1, if `record.video_speed != 100`, run helper then replace final output
- Persist `record.video_speed` as the user-configured value (API/status unchanged)

### Failure

- Pass 2 failure → job `"error"` as today; do not mark `"done"` with an unsped or partial final
- On Pass 2 success, remove `render_1x.mp4`

## Testing

- Unit: `atempo` chain builder for 50%, 100%, 200%, 500%
- Unit/integration: helper no-ops or skip path at 100%; applies filters when ≠100% (mock ffmpeg if needed)
- Jobs: Gemini + `video_speed=100` never calls tempo helper; Gemini + ≠100 calls it with configured %; Edge still passes configured `video_speed` into render

## Non-goals (v1)

- New job status / progress string for Pass 2
- Keeping the 1× artifact as a downloadable output
- Mapping Edge **Voice Speed** into Gemini
- Changing Video speed min/max ranges
- Gemini prompt-based speaking rate
