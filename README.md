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

Optional env vars:

| Variable | Description |
|----------|-------------|
| `MEDIA_ROOT` | Upload/output directory (default: `./media`) |
| `APP_PASSWORD` | Login password (required unless `APP_REQUIRE_PASSWORD=0`) |
| `APP_SECRET` | Session signing key (random ephemeral value if unset) |
| `GEMINI_API_KEY` | Google Gemini API key used by **Generate story** |

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
