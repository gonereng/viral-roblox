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

Browser UI to upload gameplay clips or import a YouTube URL on **Library** (background job; best MP4 ≤1080p; split into 1-minute slices), edit the Gemini prompt on the **Prompt** page, generate a story into the textarea, pick a voice, and render storytime videos. Requires the same **ffmpeg** dependency as the CLI (and `yt-dlp`, installed with the package).

On **Generate**, switch **Roblox** (gameplay clip from Library) or **Picture** (upload a still on that tab: jpg/png/webp). Picture videos use the same story, voice, pitch, and speed; optional **Ken Burns** slowly zooms in. The greenscreen overlay applies to Roblox videos only.

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

Open http://127.0.0.1:8000, log in with `APP_PASSWORD`, upload or YouTube-import a source in **Library**, then use **Generate**.

If YouTube shows a bot check (“Sign in to confirm you’re not a bot”), export cookies from a logged-in browser session to `media/youtube_cookies.txt` (Netscape format). Extensions such as “Get cookies.txt LOCALLY” work; or set `YOUTUBE_COOKIES` to that file path. Keep the file private — it authenticates as your account.

Optional env vars:

| Variable | Description |
|----------|-------------|
| `MEDIA_ROOT` | Upload/output directory (default: `./media`) |
| `APP_PASSWORD` | Login password (required unless `APP_REQUIRE_PASSWORD=0`) |
| `APP_SECRET` | Session signing key (random ephemeral value if unset) |
| `GEMINI_API_KEY` | Google Gemini API key used by **Generate story** |
| `YOUTUBE_COOKIES` | Optional path to a Netscape `cookies.txt` for YouTube imports (bot checks). If unset, `MEDIA_ROOT/youtube_cookies.txt` is used when present. |
| `API_KEY` | Shared secret for `/api/v1/videos*` (`X-API-Key`). Required for n8n integration. |
| `OVERLAY_VIDEO` | Optional path to a greenscreen MP4. If unset, uses `MEDIA_ROOT/overlay.mp4` when present, otherwise the packaged `assets/overlay.mp4` shipped in the image. First 3.5s are keyed and centered at half height at the start of each generated video (audio ignored). |

### n8n API

Set `API_KEY` in `.env`. Header: `X-API-Key`.

**Create** — `POST /api/v1/videos` as `multipart/form-data`:

- `voice`, `story`, `type` (`roblox`|`leni`)
- either file field `media` **or** text field `source_name` (Library name)

Then poll `GET /api/v1/videos/{id}` and download `GET /api/v1/videos/{id}/download`.

PowerShell / Windows (upload via `curl.exe` — works on PowerShell 5.1):

```powershell
$apiKey = "your-key"
$base = "http://127.0.0.1:8000"
$video = "C:\path\to\clip.mp4"

$create = curl.exe -s -X POST "$base/api/v1/videos" `
  -H "X-API-Key: $apiKey" `
  -F "voice=en-US-EmmaNeural" `
  -F "story=Hello from n8n.`nThis is a test." `
  -F "type=roblox" `
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
  -F "type=roblox" `
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
