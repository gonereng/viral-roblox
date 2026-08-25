# Gemini Force-Align (stable-ts) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Gemini karaoke free-transcription with stable-ts force-align of the known script; language/model configurable via Settings (defaults `de` / `base`).

**Architecture:** Rewrite `align_words_with_whisper` to call `stable_whisper.load_faster_whisper(...).align(...)`; thread `whisper_align_language` / `whisper_align_model` from Settings into `GeminiTTSProvider`; persist model cache under `MEDIA_ROOT/.cache` via `HF_HOME` in compose.

**Tech Stack:** stable-ts, faster-whisper, existing GeminiTTSProvider / Settings / Docker

## Global Constraints

- Aligner: stable-ts `align()` + faster-whisper backend
- Default language: `de` (`WHISPER_ALIGN_LANGUAGE`)
- Default model: `base` (`WHISPER_ALIGN_MODEL`)
- Device: CPU, `compute_type=int8`
- Per-job language: out of scope
- Edge path unchanged
- Spec: `docs/superpowers/specs/2026-08-25-gemini-force-align-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | Add `stable-ts` dependency |
| `src/roblox_viral/gemini_tts.py` | Force-align helper + provider language/model |
| `src/roblox_viral/web/config.py` | Settings fields from env |
| `src/roblox_viral/web/jobs.py` | Pass settings into GeminiTTSProvider |
| `docker-compose.yml` | Env passthrough + `HF_HOME` under media |
| `README.md` | Document env vars + force-align note |
| `tests/test_gemini_tts.py` | Align unit tests (mocked stable-ts) |
| `tests/web/test_config.py` | Settings defaults / env overrides |
| `tests/web/test_jobs.py` | Assert provider gets language/model from settings |

---

### Task 1: stable-ts force-align in `gemini_tts`

**Files:**
- Modify: `pyproject.toml`, `src/roblox_viral/gemini_tts.py`
- Test: `tests/test_gemini_tts.py`

**Produces:**
```python
DEFAULT_ALIGN_LANGUAGE = "de"
DEFAULT_ALIGN_MODEL = "base"

def align_words_with_whisper(
    audio_path: Path,
    text: str,
    *,
    language: str = DEFAULT_ALIGN_LANGUAGE,
    model_size: str = DEFAULT_ALIGN_MODEL,
) -> list[WordTiming]:
    """Force-align known script to audio via stable-ts + faster-whisper."""

class GeminiTTSProvider:
    def __init__(
        self,
        api_key: str,
        voice: str = DEFAULT_GEMINI_VOICE,
        *,
        align_fn=None,
        align_language: str = DEFAULT_ALIGN_LANGUAGE,
        align_model: str = DEFAULT_ALIGN_MODEL,
    ) -> None: ...
```

When `align_fn` is None, `synthesize` calls `align_words_with_whisper(out, script, language=self.align_language, model_size=self.align_model)`.
When `align_fn` is provided, keep calling `align_fn(out, script)` (two-arg) so existing mocks still work.

- [ ] **Step 1: Add dependency**

In `pyproject.toml` dependencies, add:

```toml
"stable-ts>=2.13.3",
```

Keep `faster-whisper>=1.0.0`. Run `pip install -e ".[dev]"` (or project equivalent) so imports work locally.

- [ ] **Step 2: Write failing tests for force-align**

Add to `tests/test_gemini_tts.py`:

```python
def test_align_words_force_uses_stable_ts_align(tmp_path, monkeypatch):
    from roblox_viral.gemini_tts import align_words_with_whisper

    audio = tmp_path / "n.mp3"
    audio.write_bytes(b"fake")
    seen = {}

    class FakeWord:
        def __init__(self, word, start, end):
            self.word = word
            self.start = start
            self.end = end

    class FakeResult:
        def all_words(self):
            return [
                FakeWord("Hallo", 0.0, 0.2),
                FakeWord("Welt", 0.2, 0.5),
            ]

    class FakeModel:
        def align(self, audio_path, text, language=None, **kwargs):
            seen["audio"] = str(audio_path)
            seen["text"] = text
            seen["language"] = language
            return FakeResult()

    def fake_load(model_size, device="cpu", compute_type="int8", **kwargs):
        seen["model_size"] = model_size
        seen["device"] = device
        seen["compute_type"] = compute_type
        return FakeModel()

    monkeypatch.setattr(
        "roblox_viral.gemini_tts.stable_whisper.load_faster_whisper",
        fake_load,
    )

    words = align_words_with_whisper(
        audio, "Hallo Welt", language="de", model_size="base"
    )
    assert seen["model_size"] == "base"
    assert seen["device"] == "cpu"
    assert seen["compute_type"] == "int8"
    assert seen["language"] == "de"
    assert "Hallo Welt" in seen["text"]
    assert [w.text for w in words] == ["Hallo", "Welt"]
    assert words[0].start_ms == 0
    assert words[0].end_ms == 200
    assert words[1].start_ms == 200
    assert words[1].end_ms == 500


def test_align_words_raises_when_empty(tmp_path, monkeypatch):
    from roblox_viral.gemini_tts import align_words_with_whisper

    audio = tmp_path / "n.mp3"
    audio.write_bytes(b"x")

    class FakeResult:
        def all_words(self):
            return []

    class FakeModel:
        def align(self, *a, **k):
            return FakeResult()

    monkeypatch.setattr(
        "roblox_viral.gemini_tts.stable_whisper.load_faster_whisper",
        lambda *a, **k: FakeModel(),
    )
    with pytest.raises(RuntimeError, match="align"):
        align_words_with_whisper(audio, "Hi", language="de")


def test_provider_passes_language_model_to_default_align(tmp_path, monkeypatch):
    pcm = b"\x00\x00" * 2400
    seen = {}

    monkeypatch.setattr(
        GeminiTTSProvider,
        "_generate_pcm",
        lambda self, text: (pcm, 24000),
    )
    monkeypatch.setattr(
        "roblox_viral.gemini_tts._pcm_to_mp3",
        lambda data, *, sample_rate, output_mp3: Path(output_mp3).write_bytes(b"mp3"),
    )

    def fake_align(audio_path, text, *, language, model_size):
        seen["language"] = language
        seen["model_size"] = model_size
        return [WordTiming("Hi", 0, 100)]

    monkeypatch.setattr(
        "roblox_viral.gemini_tts.align_words_with_whisper", fake_align
    )

    out = tmp_path / "n.mp3"
    GeminiTTSProvider(
        "key", "Kore", align_language="en", align_model="small"
    ).synthesize("Hi", out)
    assert seen == {"language": "en", "model_size": "small"}
```

If stable-ts word iteration is via `result.segments` / nested `.words` rather than `all_words()`, adjust the implementation to match the library API and update the FakeResult accordingly — prefer `all_words()` if present (stable-ts WhisperResult), else iterate segments’ words. Document the chosen accessor in a one-line comment.

- [ ] **Step 3: Run tests — expect fail**

```bash
pytest tests/test_gemini_tts.py::test_align_words_force_uses_stable_ts_align tests/test_gemini_tts.py::test_provider_passes_language_model_to_default_align -v
```

Expected: FAIL (no `stable_whisper` import / wrong signature)

- [ ] **Step 4: Implement force-align**

In `gemini_tts.py`:

1. Add:

```python
import stable_whisper

DEFAULT_ALIGN_LANGUAGE = "de"
DEFAULT_ALIGN_MODEL = "base"
```

2. Replace `align_words_with_whisper` body:

```python
def align_words_with_whisper(
    audio_path: Path,
    text: str,
    *,
    language: str = DEFAULT_ALIGN_LANGUAGE,
    model_size: str = DEFAULT_ALIGN_MODEL,
) -> list[WordTiming]:
    """Force-align known script to audio via stable-ts + faster-whisper."""
    script = (text or "").strip()
    if not script:
        raise ValueError("TTS text is empty")
    lang = (language or DEFAULT_ALIGN_LANGUAGE).strip() or DEFAULT_ALIGN_LANGUAGE
    size = (model_size or DEFAULT_ALIGN_MODEL).strip() or DEFAULT_ALIGN_MODEL
    model = stable_whisper.load_faster_whisper(
        size, device="cpu", compute_type="int8"
    )
    result = model.align(str(audio_path), script, language=lang)
    words: list[WordTiming] = []
    # WhisperResult.all_words() if available; else flatten segment.words
    raw_words = (
        result.all_words()
        if hasattr(result, "all_words")
        else [
            w
            for seg in (result.segments or [])
            for w in (getattr(seg, "words", None) or [])
        ]
    )
    for word in raw_words:
        token = (getattr(word, "word", None) or getattr(word, "text", None) or "").strip()
        if not token:
            continue
        start = float(word.start)
        end = float(word.end)
        start_ms = max(0, int(round(start * 1000)))
        end_ms = max(start_ms + 1, int(round(end * 1000)))
        words.append(WordTiming(text=token, start_ms=start_ms, end_ms=end_ms))
    if not words:
        raise RuntimeError("Whisper align returned no words")
    for i in range(len(words) - 1):
        if words[i].end_ms < words[i + 1].start_ms:
            words[i] = WordTiming(
                text=words[i].text,
                start_ms=words[i].start_ms,
                end_ms=words[i + 1].start_ms,
            )
    return words
```

3. Update `GeminiTTSProvider.__init__` to store `align_language` / `align_model`.

4. Update `synthesize` default align call:

```python
if self._align_fn is not None:
    return self._align_fn(out, script)
return align_words_with_whisper(
    out,
    script,
    language=self.align_language,
    model_size=self.align_model,
)
```

- [ ] **Step 5: Run gemini_tts tests — expect PASS**

```bash
pytest tests/test_gemini_tts.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/roblox_viral/gemini_tts.py tests/test_gemini_tts.py
git commit -m "feat(gemini): force-align karaoke with stable-ts"
```

---

### Task 2: Settings, jobs, Docker, README

**Files:**
- Modify: `src/roblox_viral/web/config.py`, `src/roblox_viral/web/jobs.py`, `docker-compose.yml`, `README.md`
- Test: `tests/web/test_config.py`, `tests/web/test_jobs.py`

**Consumes:** Task 1 provider kwargs `align_language`, `align_model`

- [ ] **Step 1: Write failing Settings + jobs tests**

Add to `tests/web/test_config.py`:

```python
def test_whisper_align_defaults(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("WHISPER_ALIGN_LANGUAGE", raising=False)
    monkeypatch.delenv("WHISPER_ALIGN_MODEL", raising=False)
    settings = Settings.from_env()
    assert settings.whisper_align_language == "de"
    assert settings.whisper_align_model == "base"


def test_whisper_align_from_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("WHISPER_ALIGN_LANGUAGE", "en")
    monkeypatch.setenv("WHISPER_ALIGN_MODEL", "small")
    settings = Settings.from_env()
    assert settings.whisper_align_language == "en"
    assert settings.whisper_align_model == "small"
```

Add to `tests/web/test_jobs.py` (mirror existing gemini job test pattern; set env language/model on settings via monkeypatch before `_settings`):

```python
def test_run_job_gemini_passes_align_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("WHISPER_ALIGN_LANGUAGE", "en")
    monkeypatch.setenv("WHISPER_ALIGN_MODEL", "small")
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    seen = {}

    def fake_gemini_init(self, api_key, voice, *, align_fn=None, align_language="de", align_model="base"):
        seen["align_language"] = align_language
        seen["align_model"] = align_model
        self.api_key = api_key
        self.voice = voice
        self._align_fn = align_fn

    def fake_gemini_synth(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [WordTiming("One", 0, 100)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_video(**kwargs):
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.GeminiTTSProvider.__init__", fake_gemini_init
    )
    monkeypatch.setattr(
        "roblox_viral.web.jobs.GeminiTTSProvider.synthesize", fake_gemini_synth
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)

    job = mgr.create(
        s, "clip.mp4", "One line only here.\n", "Kore", tts_provider="gemini"
    )
    mgr.run_job(s, job.id)
    assert seen["align_language"] == "en"
    assert seen["align_model"] == "small"
    assert mgr.get(job.id, s).status == "done"
```

Note: `_settings` must pick up env via `Settings.from_env()` — if it caches `get_settings`, clear cache or construct Settings the same way other tests do after setenv.

- [ ] **Step 2: Run new tests — expect fail**

```bash
pytest tests/web/test_config.py::test_whisper_align_defaults tests/web/test_jobs.py::test_run_job_gemini_passes_align_settings -v
```

Expected: FAIL (missing Settings fields / kwargs)

- [ ] **Step 3: Implement Settings + jobs**

`config.py` — add fields with defaults so existing `Settings(...)` call sites keep working:

```python
whisper_align_language: str = "de"
whisper_align_model: str = "base"
```

In `from_env`:

```python
whisper_align_language=(
    os.environ.get("WHISPER_ALIGN_LANGUAGE", "de").strip() or "de"
),
whisper_align_model=(
    os.environ.get("WHISPER_ALIGN_MODEL", "base").strip() or "base"
),
```

`jobs.py`:

```python
words = GeminiTTSProvider(
    settings.gemini_api_key,
    record.voice,
    align_language=settings.whisper_align_language,
    align_model=settings.whisper_align_model,
).synthesize(tts_text, narration_path)
```

Update any existing `fake_gemini_init` in `test_jobs.py` that must accept the new kwargs (add `**kwargs` or explicit defaults) so older tests don’t break.

- [ ] **Step 4: Docker + README**

`docker-compose.yml` environment:

```yaml
GEMINI_API_KEY: ${GEMINI_API_KEY:-}
WHISPER_ALIGN_LANGUAGE: ${WHISPER_ALIGN_LANGUAGE:-de}
WHISPER_ALIGN_MODEL: ${WHISPER_ALIGN_MODEL:-base}
HF_HOME: /app/media/.cache/huggingface
```

(`./media` volume already persists `/app/media/.cache/...`.)

README optional env table — add rows for `WHISPER_ALIGN_LANGUAGE`, `WHISPER_ALIGN_MODEL`; note Gemini karaoke uses stable-ts force-align (default language German). Mention first Gemini job may download the Whisper model into `media/.cache/`.

- [ ] **Step 5: Run covering + full suite**

```bash
pytest tests/test_gemini_tts.py tests/web/test_config.py tests/web/test_jobs.py -q
pytest -q
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/roblox_viral/web/config.py src/roblox_viral/web/jobs.py docker-compose.yml README.md tests/web/test_config.py tests/web/test_jobs.py
git commit -m "feat(web): wire whisper align language/model settings"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| stable-ts force-align | 1 |
| Defaults de / base | 1 + 2 |
| Settings env vars | 2 |
| jobs pass settings | 2 |
| Docker HF cache + env | 2 |
| README | 2 |
| Mocked tests | 1 + 2 |

## Self-review

- No TBD steps; `align_fn` two-arg contract preserved for mocks
- Word accessor fallback documented if `all_words` missing
- Existing `Settings(...)` constructors remain valid via field defaults
