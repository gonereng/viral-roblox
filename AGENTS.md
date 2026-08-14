# AGENTS.md

## Cursor Cloud specific instructions

### What this is
`roblox-viral` is a Python 3.10+ package with two entry points that share the same pipeline (Edge TTS narration → ASS karaoke captions → `ffmpeg` render to vertical 1080×1920 MP4):
- CLI: `roblox-viral` (`src/roblox_viral/cli.py`)
- Web app: FastAPI + Jinja templates, `roblox-viral-web` / `roblox_viral.web.app:create_app` (`src/roblox_viral/web/`)

### Environment already provided
- Python 3.12 and `ffmpeg`/`ffprobe` are installed system-wide. `ffmpeg` is a hard runtime dependency for both the CLI and web app.
- The update script creates `.venv/` and installs the package editable with dev extras. Activate with `.venv/bin/...` (there is no global `roblox-viral` on PATH).

### Running things (use the venv)
- Tests: `.venv/bin/python -m pytest` (config lives in `pyproject.toml`; `pythonpath=["src"]`, `asyncio_mode=auto`). All tests are offline/hermetic.
- CLI smoke test: `.venv/bin/roblox-viral --video examples/sample.mp4 --story-text "..." --out /tmp/out.mp4`
- Web dev server (auto-reload): `APP_PASSWORD=devpass APP_SECRET=dev-secret MEDIA_ROOT=/workspace/media .venv/bin/uvicorn roblox_viral.web.app:create_app --factory --reload --host 127.0.0.1 --port 8000`
- There is **no configured linter/formatter** (no ruff/flake8/black/pre-commit and no active git hooks). "Lint" for this repo is just the test suite plus `.venv/bin/python -m compileall src`.

### Non-obvious gotchas
- The web app requires `APP_PASSWORD` at startup (raises `RuntimeError` otherwise) unless `APP_REQUIRE_PASSWORD=0`. Log in at `/login` with that password before any page/API works; API calls need the session cookie.
- **Edge TTS makes an outbound network call** to Microsoft's TTS service for every render (both CLI and web). Renders fail offline; there is no local TTS fallback.
- Library upload (`POST /library/upload`) rejects clips shorter than 60s — it slices into whole 1-minute parts and discards the remainder. `examples/sample.mp4` is only 3s, so to exercise upload, make a ≥60s clip (e.g. `ffmpeg -stream_loop -1 -i examples/sample.mp4 -t 65 -an /tmp/clip.mp4`). Generation itself loops any-length source to the narration length, so a short source is fine once it is in `media/sources/`.
- `GEMINI_API_KEY` is optional and only used by the "Generate story" button (`/api/generate-story`, returns 503 when unset). YouTube import needs network and may need `media/youtube_cookies.txt`. Neither is required to render a video from a typed/pasted story.
- Media state (sources, outputs, jobs, `prompt.txt`) lives under `MEDIA_ROOT` (default `./media`) and is gitignored.
