# Gemini Story Generation — Design

**Date:** 2026-07-30  
**Status:** Approved (conversation)  
**Builds on:** [2026-07-29-roblox-viral-webapp-design.md](./2026-07-29-roblox-viral-webapp-design.md)

## Goal

Add a “Generate story” button on the Generate page that calls the Gemini API and fills the existing story textarea. The Gemini prompt is editable and persistent on a new Prompt page linked from the header. The API key comes from an environment variable.

## Product decisions

- Approach: file-backed prompt + `httpx` Gemini REST (no official Google SDK)
- Prompt storage: `MEDIA_ROOT/prompt.txt` (survives restarts; works with Docker volume)
- Prompt page: editable and persistent
- Story format: default prompt asks for one sentence per line; **not** server-enforced — only part of the editable prompt text
- Generate story only fills the textarea; it does not start a video render job
- Auth: Prompt page and generate-story API require the same login as Generate/Library
- Out of scope: streaming tokens, prompt history, multiple prompts, model picker in UI

## Architecture

```
Browser
  → Prompt page (edit / save prompt.txt)
  → Generate page “Generate story” button
  → POST /api/generate-story
  → Read MEDIA_ROOT/prompt.txt
  → Gemini REST (GEMINI_API_KEY via httpx)
  → Fill #story textarea
  → Existing Generate video flow unchanged
```

### Config

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Gemini API key; required for story generation |
| `MEDIA_ROOT` | Existing; prompt file lives at `{MEDIA_ROOT}/prompt.txt` |

- `Settings.gemini_api_key` loaded from `GEMINI_API_KEY` (empty string if unset)
- Document in README; pass through `docker-compose` (placeholder/empty ok; real key via env override)
- Model: `gemini-2.5-flash` via Gemini generateContent REST (`gemini-2.0-flash` is shut down)

### Storage layout (addition)

```
media/
  sources/
  outputs/
  jobs/{id}/
  prompt.txt    # editable Gemini prompt
```

If `prompt.txt` is missing on first Prompt page visit or generate-story call, seed a default Roblox storytime prompt that asks for one sentence per line, then persist it.

## Pages & UI

### Header

Add **Prompt** link next to Generate / Library in `base.html`.

### Prompt page (`/prompt`)

- Auth required
- Textarea with current prompt text
- Save button → `POST /prompt` writes `MEDIA_ROOT/prompt.txt`
- Success / error message on the page
- Seed default prompt if file missing

### Generate page

- “Generate story” button near the Story textarea
- On click: disable button, `POST /api/generate-story`, put returned text into `#story`
- Show inline error on failure
- Does not submit the generate-video form

## API

| Route | Behavior |
|-------|----------|
| `GET /prompt` | Prompt editor page |
| `POST /prompt` | Save prompt text to `prompt.txt` (form post) |
| `POST /api/generate-story` | Read prompt → call Gemini → `{ "story": "..." }` |

All require login.

### Generate-story request

No body required. Server always uses the saved prompt file (or seeds default).

### Generate-story success response

```json
{ "story": "Line one.\nLine two.\n" }
```

## Error handling

| Case | Response |
|------|----------|
| Not logged in | 401 |
| Empty prompt after trim | 400 |
| `GEMINI_API_KEY` unset | 503 with clear message |
| Gemini HTTP/API failure | 502 with short error detail |
| Empty model response | 502 |

## Data flow

1. Edit/save prompt on `/prompt` → `MEDIA_ROOT/prompt.txt`
2. Click “Generate story” → `POST /api/generate-story`
3. Server reads prompt, calls Gemini with `GEMINI_API_KEY`
4. Response text → JSON → client fills `#story`
5. User may edit the story, then run the existing Generate video flow

## Implementation sketch

- `Settings`: add `gemini_api_key`; property or helper for `prompt_path`
- New module e.g. `roblox_viral/web/prompt.py`: load/save/default prompt
- New module e.g. `roblox_viral/web/gemini.py`: `httpx` call to Gemini generateContent
- Routes in `app.py`; template `prompt.html`; small JS on Generate page for the button
- CSS: reuse existing form styles; minimal additions

## Testing

Mock Gemini (`httpx` mock / monkeypatch) — no real API calls in CI.

- Prompt GET/POST require auth
- Save + reload persists prompt text
- Generate-story requires auth
- Success path returns story and uses saved prompt
- Missing API key → 503
- Empty prompt → 400

## Default prompt (seed)

A short Roblox horror/storytime style instruction that ends with: write the story with exactly one sentence per line, no blank lines, no preamble.
