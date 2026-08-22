# Roblox Viral Storytime Generator

Turn a Roblox gameplay clip + a short story into a vertical **1080×1920** storytime video with Edge TTS narration and karaoke word-highlight captions.

Story files use **one sentence per line**. Captions show **one word at a time** while that sentence is spoken (they clear when the next sentence starts).

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) on your PATH (includes `ffprobe`)

## Install

```bash
cd roblox-viral
python -m pip install -e .
```

## Usage

```bash
roblox-viral --video path/to/gameplay.mp4 --story examples/story.txt --out output.mp4
```

Inline story:

```bash
roblox-viral --video clip.mp4 --story-text "I joined a scary Roblox game. Then everything went wrong." --out out.mp4
```

Options:

| Flag | Description |
|------|-------------|
| `--video` | Roblox gameplay video (required) |
| `--story` | Story text file |
| `--story-text` | Inline story (mutually exclusive with `--story`) |
| `--out` | Output MP4 (default: `output.mp4`) |
| `--voice` | Edge TTS voice (default: `en-US-EmmaNeural`) |
| `--keep-temp` | Keep temp narration/ASS files for debugging |

## Pipeline

1. Normalize story text
2. Synthesize narration with **Edge TTS** (word-boundary timings)
3. Build **ASS** karaoke captions (yellow active word)
4. **ffmpeg**: mute + loop video to audio length, center-crop to 9:16, burn captions, mux TTS

## Web app

Browser UI with a **Library** page (three tabs), **Prompt** page (Gemini story prompt), and **Generate** page to pick sources, write a story, choose voice settings, and render storytime videos. Requires the same **ffmpeg** dependency as the CLI.

**Library** has three tabs:

| Tab | Behavior |
|-----|----------|
| **1-minute clips** | Upload gameplay; split into complete one-minute slices (`media/sources/`) |
| **Videos** | Upload full clips as-is, no slicing (`media/videos/`) |
| **Images** | Upload stills for Picture mode (jpg/png/webp; `media/images/`) |

Library lists include inline preview (video controls with no preload; lazy images).

On **Generate**, pick a background mode via three tabs:

| Tab | Behavior |
|-----|----------|
| **Single background video** | Pick a one-minute clip from Library → 1-minute clips (`media/sources/`). Loops that clip to TTS length. **Video speed** slider (50–200%, default 100%) independent of voice pitch/speed. Shows an X-style hook card with the first story line until that sentence ends; the greenscreen subscribe overlay is not used on Single while this card is active. |
| **Picture** | Pick an image from Library → Images. Optional **Ken Burns** slow zoom. No overlay; no video speed. |
| **Reddit** | No source picker — one library video per sentence (bag pop, reshuffle when empty). **Video speed** slider (100–500%, default 100%). Requires at least one video in the Videos pool. |

**Reddit** shows a title card with the first story line, centered until that sentence finishes in the narration. The in-video card is unchanged. After generate, **Download title card** is a cover PNG: the packaged Snoo template with the first story line split on a single `-` (`phrase - phrase`) drawn in the two boxes. n8n: `GET /api/v1/videos/{id}/cover`.

The optional greenscreen overlay (first 3.5s) is scaled to **fit inside the full 1080×1920 frame** (2× the former half-height target), chromakeyed, and centered. Not used for **Single** or **Reddit** (both use title cards instead).

### Local run

```bash
# Windows
set APP_PASSWORD=your-password
set APP_SECRET=your-long-random-secret

# macOS / Linux
export APP_PASSWORD=your-password
export APP_SECRET=your-long-random-secret

pip install -e .
roblox-viral-web
```

Or with auto-reload:

```bash
uvicorn roblox_viral.web.app:create_app --factory --reload
```

Open http://127.0.0.1:8000, log in with `APP_PASSWORD`, upload media in **Library**, then use **Generate**.

Optional env vars:

| Variable | Description |
|----------|-------------|
| `MEDIA_ROOT` | Upload/output directory (default: `./media`) |
| `APP_PASSWORD` | Login password (required unless `APP_REQUIRE_PASSWORD=0`) |
| `APP_SECRET` | Session signing key (random ephemeral value if unset) |
| `GEMINI_API_KEY` | Google Gemini API key used by **Generate story** |
| `API_KEY` | Shared secret for `/api/v1/videos*` (`X-API-Key`). Required for n8n integration. |
| `OVERLAY_VIDEO` | Optional path to a greenscreen MP4. If unset, uses `MEDIA_ROOT/overlay.mp4` when present, otherwise the packaged `assets/overlay.mp4` shipped in the image. First 3.5s are chromakeyed, scaled to fit inside the full 1080×1920 frame, centered, and composited at the start of **Single** videos (audio ignored). |

### n8n API

Set `API_KEY` in `.env`. Header: `X-API-Key`.

**Create** — `POST /api/v1/videos` as `multipart/form-data`:

- `voice`, `story`, `type` (`single`|`reddit`|`leni`; `roblox` is rejected — use `single`)
- optional `pitch` (−100…100, default 15), `speed` (50…200, default 130), and `video_speed` (50–200 for `single`/`leni`, 100–500 for `reddit`; default 100)
- for `single` or `leni`: either file field `media` **or** text field `source_name` (Library clip or raw video/image name)
- for `reddit`: story/voice/type only (background is built from the Library Videos pool; do not send `media` or `source_name`)

Then poll `GET /api/v1/videos/{id}` and download `GET /api/v1/videos/{id}/download`; then download the cover with `GET /api/v1/videos/{id}/cover` (Reddit only; 404 for other types).

PowerShell / Windows (upload via `curl.exe` — works on PowerShell 5.1):

```powershell
$apiKey = "your-key"
$base = "http://127.0.0.1:8000"
$video = "C:\path\to\clip.mp4"

$create = curl.exe -s -X POST "$base/api/v1/videos" `
  -H "X-API-Key: $apiKey" `
  -F "voice=en-US-EmmaNeural" `
  -F "story=Hello from n8n.`nThis is a test." `
  -F "type=single" `
  -F "pitch=15" `
  -F "speed=130" `
  -F "video_speed=100" `
  -F "media=@$video"
$create
$id = ($create | ConvertFrom-Json).id

do {
  Start-Sleep -Seconds 2
  $status = curl.exe -s "$base/api/v1/videos/$id" -H "X-API-Key: $apiKey" | ConvertFrom-Json
  Write-Host "status=$($status.status)"
} while ($status.status -notin @("done", "error"))

if ($status.status -eq "error") { throw $status.error }

curl.exe -s -L "$base/api/v1/videos/$id/download" -H "X-API-Key: $apiKey" -o ".\out-$id.mp4"
Write-Host "saved out-$id.mp4"
```

Library name instead of upload (no `media` file):

```powershell
curl.exe -s -X POST "http://127.0.0.1:8000/api/v1/videos" `
  -H "X-API-Key: your-key" `
  -F "voice=en-US-EmmaNeural" `
  -F "story=Hello.`nWorld." `
  -F "type=single" `
  -F "source_name=gameplay-1.mp4"
```

### Docker

Create a `.env` file (or export vars in your shell):

```bash
APP_PASSWORD=your-password
APP_SECRET=your-long-random-secret
GEMINI_API_KEY=
```

Build and run:

```bash
docker compose up --build
```

The app listens on http://localhost:8000. Source videos, outputs, and job state persist in `./media` via a bind mount.

## Design

See [docs/superpowers/specs/2026-07-27-roblox-viral-storytime-design.md](docs/superpowers/specs/2026-07-27-roblox-viral-storytime-design.md).

Web app design: [docs/superpowers/specs/2026-07-29-roblox-viral-webapp-design.md](docs/superpowers/specs/2026-07-29-roblox-viral-webapp-design.md).

Gemini story generation: [docs/superpowers/specs/2026-07-30-gemini-story-generation-design.md](docs/superpowers/specs/2026-07-30-gemini-story-generation-design.md).
