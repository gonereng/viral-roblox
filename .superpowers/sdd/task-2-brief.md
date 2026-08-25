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
