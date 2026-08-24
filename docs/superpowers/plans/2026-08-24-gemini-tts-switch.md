# Gemini TTS Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Generate UI / n8n choose Edge TTS or Gemini TTS (`gemini-3.1-flash-tts-preview`); Gemini path force-aligns with faster-whisper for karaoke.

**Architecture:** `tts_provider` on jobs; `GeminiTTSProvider` synthesizes PCM→MP3 and aligns with whisper tiny; UI toggle swaps voice lists and hides pitch/speed for Gemini.

**Tech Stack:** httpx, ffmpeg, faster-whisper, existing FastAPI/Edge stack

## Global Constraints

- Model: `gemini-3.1-flash-tts-preview` only
- Default provider: `edge`
- Gemini voices: fixed 30 prebuilt names
- Pitch/speed: Edge only (UI hidden for Gemini)
- Align: faster-whisper `tiny`
- Missing `GEMINI_API_KEY` + gemini → 503 / clear job error
- Spec: `docs/superpowers/specs/2026-08-24-gemini-tts-switch-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | Add `faster-whisper` |
| `src/roblox_viral/gemini_tts.py` | Voices, provider, PCM→MP3, whisper align |
| `src/roblox_viral/web/jobs.py` | `tts_provider` field + synthesize branch |
| `src/roblox_viral/web/app.py` | CreateJobBody + generate page gemini voices |
| `src/roblox_viral/web/api_v1.py` | Optional `tts_provider` form |
| `src/roblox_viral/web/templates/generate.html` | Toggle + dual voice data |
| `src/roblox_viral/web/static/app.js` | Toggle behavior + payload |
| `tests/test_gemini_tts.py` | Unit tests (mocked HTTP/whisper) |
| `tests/web/test_jobs.py` / `test_api*.py` | Wiring |
| `README.md` | Short note |

---

### Task 1: `gemini_tts` module + dependency

**Files:** Create `src/roblox_viral/gemini_tts.py`, `tests/test_gemini_tts.py`; modify `pyproject.toml`

**Produces:**
```python
GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
GEMINI_VOICES: list[str]  # 30 names
DEFAULT_GEMINI_VOICE = "Kore"
def validate_gemini_voice(name: str) -> str: ...
def normalize_tts_provider(raw: str | None) -> str:  # "edge"|"gemini"
class GeminiTTSProvider:
    def __init__(self, api_key: str, voice: str = DEFAULT_GEMINI_VOICE): ...
    def synthesize(self, text: str, output_path: Path | str) -> list[WordTiming]: ...
```

- [ ] Add `faster-whisper>=1.0.0` to `pyproject.toml`
- [ ] TDD: allowlist + normalize_tts_provider tests
- [ ] TDD: synthesize with mocked httpx response (fake L16 bytes) + mocked WhisperModel returning fixed words; assert MP3 written and WordTiming list non-empty
- [ ] Implement: POST generateContent with AUDIO + voiceName; decode base64; ffmpeg s16le 24kHz mono → mp3; whisper tiny word_timestamps
- [ ] Commit: `feat: add GeminiTTSProvider with whisper alignment`

### Task 2: Job + API wiring

**Files:** `jobs.py`, `app.py`, `api_v1.py`, tests

- [ ] `JobRecord.tts_provider: str = "edge"`; hydrate; `create(..., tts_provider=...)`
- [ ] Validate: gemini requires api_key + validate_gemini_voice; edge keeps Edge voice string as today
- [ ] `run_job`: branch synthesize on provider
- [ ] `CreateJobBody.tts_provider`; `/api/jobs` + `/api/v1/videos` accept it
- [ ] Tests: gemini path calls GeminiTTSProvider (mocked); edge unchanged; API 503 without key
- [ ] Commit: `feat(web): wire tts_provider through jobs and API`

### Task 3: Generate UI toggle

**Files:** `generate.html`, `app.js`, `app.py` page context, CSS if needed, tests

- [ ] Toggle Edge/Gemini above voice select
- [ ] Pass `gemini_voices` JSON/list from server; keep Edge options in DOM or rebuild
- [ ] On Gemini: swap options, hide pitch+speed fields; on Edge: restore
- [ ] Payload includes `tts_provider`
- [ ] Test: page contains toggle + gemini voice names
- [ ] README note
- [ ] Commit: `feat(web): Edge/Gemini TTS toggle on Generate`

---

## Spec coverage

| Spec | Task |
|------|------|
| GeminiTTSProvider + whisper | 1 |
| Job/API tts_provider | 2 |
| UI toggle + voice swap | 3 |
| Pitch/speed Edge-only | 3 |
| 503 without key | 2 |
