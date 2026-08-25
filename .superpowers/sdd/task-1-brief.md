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

