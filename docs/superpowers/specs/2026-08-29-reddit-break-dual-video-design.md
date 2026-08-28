# Reddit BREAK Dual Video — Design

**Date:** 2026-08-29  
**Status:** Approved (conversation)  

## Goal

For **Reddit** jobs only: an optional story line that is exactly `BREAK` splits one submission into **two** finished videos on the **same job**. Part A keeps today’s hook card + cover behavior; Part B is the same pipeline without the screenshot and without the first-sentence hook format rule. No `BREAK` (or empty after) → one video as today.

## Product decisions

| Decision | Choice |
|----------|--------|
| Modes | Reddit only |
| Split token | Own line, exact `BREAK` after trim |
| Optional | No `BREAK` or empty Part B → single Part A |
| Job model | One job, two sequential render passes |
| Part A | Hook `Top - Bottom` required; Reddit card + cover download |
| Part B | No title card / cover; no `split_hook`; free first sentence |
| Shared settings | Same voice, pitch/speed (Edge), video_speed, tts_provider |
| `BREAK` spoken? | No — stripped before TTS |
| Non-Reddit + `BREAK` | Leave text unchanged (no split) |
| Part B failure after A OK | Job `error` (v1; no partial done) |

## Architecture

```
create(reddit, story):
  parts = split_reddit_story(story)  # (part_a, part_b|None)
  validate part_a non-empty + split_hook(sentences[0])
  store full story (or both parts) on job; hydrate as today

run_job:
  render_part(part_a, with_card=True)  → output_name, title_card_name
  if part_b:
    render_part(part_b, with_card=False) → output_name_b
  status done
```

Each `render_part` is the existing pipeline slice: synthesize → ASS → (optional card/cover) → Reddit clips → render → optional Gemini tempo. Parts use separate job-dir work files (`narration.mp3` / `narration_b.mp3`, etc.) so they don’t clobber each other.

### Outputs

- Part A: `reddit-YYYY-…mp4` (existing naming)
- Part B: same stem + `-b.mp4` (e.g. `reddit-2026-08-29_120000-b.mp4`)
- Cover: Part A only (`{stem}-card.png`)

### Job / status fields

- `output_name` — Part A (required when done)
- `output_name_b` — Part B or `null`
- `title_card_name` — Part A cover or `null`

### API (n8n)

| Asset | Method | Notes |
|-------|--------|--------|
| Status | `GET /api/v1/videos/{id}` | Includes `output_name`, `output_name_b` |
| Part A video | `GET /api/v1/videos/{id}/download` | Unchanged |
| Part B video | `GET /api/v1/videos/{id}/download-b` | **404** if no Part B |
| Cover | `GET /api/v1/videos/{id}/cover` | Part A only (unchanged) |

GUI Generate result: second download link when `output_name_b` is set. Reddit hint text mentions optional `BREAK` line.

## Testing

- Split helper: no BREAK; BREAK with empty after → one part; BREAK with both parts; line must be exact `BREAK`
- Create Reddit: hook still required on Part A; Part B first line need not be hook
- Jobs: dual run writes two MP4s + status fields; single path unchanged
- API: `download-b` 200 with B / 404 without; status JSON shape
- UI: markup/hint or payload field for second download (lightweight)

## Non-goals (v1)

- Per-part voice/speed
- Part B title card or cover
- Parallel Part A/B renders
- Recoverable “A done, B failed” success status
- Splitting Single / Picture on `BREAK`
