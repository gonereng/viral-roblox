# Reddit Per-Sentence Background Clips — Design

**Date:** 2026-08-20  
**Status:** Approved (conversation)  
**Builds on:** [2026-08-15-generate-single-reddit-design.md](./2026-08-15-generate-single-reddit-design.md), [2026-08-15-library-tabs-video-speed-design.md](./2026-08-15-library-tabs-video-speed-design.md)

## Goal

Change **Reddit** background assembly so each **story sentence** gets a **new** random library video (trimmed to that sentence’s narration length), reusing videos only after the pool is exhausted. Extend **Reddit-only** video speed to **100–500%** while **Single** keeps **50–200%**.

## Product decisions

### Per-sentence clips (Reddit only)

- After TTS, derive **one duration per sentence** from word timings (`partition_words_by_sentences`).
- Sentence wall-clock duration: `(last_word.end_ms - first_word.start_ms) / 1000` for words assigned to that sentence.
- For each sentence in order:
  1. Take the next file from a shuffled bag of `media/videos/` (reshuffle when empty — same “no reuse until exhausted” pattern as today).
  2. Compute **source footage needed**: `source_needed = sentence_duration × (video_speed / 100)`.
  3. Append trim segments from **start 0:00** of the chosen file until `source_needed` is covered.
  4. If the file is **shorter** than remaining `source_needed`, **loop** that same file (multiple concat segments, each from `start_s=0`) until the sentence’s source quota is met.
  5. Next sentence picks a **new** bag entry (not the same pick-until-exhausted file unless the bag reshuffles and it comes up again).

- Concat all segments → `reddit_bg.mp4` via existing `build_reddit_background`.
- Global `setpts` in `render_video` still applies `video_speed` to the full background (unchanged).
- **Title card** timing and overlay unchanged (first sentence only).

### Clip start position

- Always **0:00** of each library file (no random in-file offsets).

### Video speed ranges (mode-specific)

| Mode | Range | Default | UI |
|------|-------|---------|-----|
| **Reddit** | 100–500% | 100 | Slider visible |
| **Single** | 50–200% | 100 | Slider visible |
| **Picture** | n/a (stored default 100) | 100 | Slider hidden |

- Validate on job create (web + n8n) using **mode/type**.
- Generate UI: when switching tabs, set `#video_speed` `min`/`max` and clamp current value into the active mode’s range.

### Unchanged

- Single / Picture background behavior.
- Reddit title card, download PNG, no greenscreen.
- Library Videos pool (`media/videos/`).
- n8n Reddit: no `media` / `source_name`.

## Architecture

### New planner

Add `plan_reddit_sentence_clips` in `reddit_clips.py` (recommended name):

```python
def plan_reddit_sentence_clips(
    paths: list[Path],
    sentence_durations_s: list[float],
    *,
    video_speed: int = 100,
    durations: dict[Path, float] | None = None,
    rng: random.Random | None = None,
) -> list[ClipSegment]:
```

- One **bag pop** per sentence (not per loop segment within a sentence).
- Loop segments within a sentence reuse the **same path** until `source_needed` for that sentence is satisfied.
- `ClipSegment.start_s` remains `0.0` for all segments.
- Raise `ValueError` if `paths` empty, `sentence_durations_s` empty, any duration ≤ 0, or invalid `video_speed` for Reddit range.

Reddit `run_job` replaces `plan_reddit_clips(..., narration_duration × speed/100)` with sentence durations from caption partition + `plan_reddit_sentence_clips`. Old total-target planner may remain for tests or be removed if Reddit-only.

### Validation

- Extend `validate_video_speed(percent, *, mode: str)` (or equivalent) in `voice.py`:
  - `reddit`: 100…500
  - `single` (and ephemeral non-picture video): 50…200
  - `picture`: accept but ignore (default 100 on record)

### Wiring

- `jobs.py`: after TTS + `write_ass`, compute sentence durations from `words` + `sentences`; pass to planner with `record.video_speed`.
- `app.py` / `api_v1.py`: pass mode into validation.
- `generate.html` / `app.js`: mode-dependent slider bounds.

## Error handling

| Condition | Response |
|-----------|----------|
| No videos in pool | Existing Reddit create error |
| Caption/word partition failure | Job error (existing behavior) |
| `video_speed` out of range for mode | 400 on create |
| Zero/negative sentence duration | Planner `ValueError` → job error |

## Testing

- Planner: N sentences → N bag picks when pool ≥ N; reshuffle when sentences > |pool|; short file loops within one sentence; `video_speed=200` doubles source per sentence vs 100.
- Jobs: Reddit uses sentence planner (not total narration target).
- Validation: Reddit 500 OK, 99/501 rejected; Single 50/200 unchanged.
- Optional: Generate HTML/JS Reddit tab sets `max=500`.

## Out of scope

- Random start offset within library files
- Per-sentence backgrounds on Single mode
- Title card / overlay geometry changes
- Reddit video_speed below 100% or above 500%

## Success criteria

- Reddit video background changes at **sentence boundaries** with a **new pool video per sentence** (reuse only after bag exhausted).
- Each sentence’s background source length accounts for **video_speed**; wall-clock matches narration after global `setpts`.
- Reddit slider **100–500%**; Single slider **50–200%**.
