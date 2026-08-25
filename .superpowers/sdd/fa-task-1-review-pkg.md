# Review package Task 1
BASE: ccb4983af50d9035955dcb07d0ac3a538084cf2b
HEAD: 21e53d16713621eed622d2e18bfdbce355c6b144

## Commits

21e53d1 feat(gemini): force-align karaoke with stable-ts

## Diff stat

 pyproject.toml                 |   1 +
 src/roblox_viral/gemini_tts.py |  73 +++++++++++++++++++---------
 tests/test_gemini_tts.py       | 105 +++++++++++++++++++++++++++++++++++++++++
 3 files changed, 158 insertions(+), 21 deletions(-)

## Full diff

diff --git a/pyproject.toml b/pyproject.toml
index 1a8ea83..2064a59 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -11,20 +11,21 @@ requires-python = ">=3.10"
 dependencies = [
   "edge-tts>=6.1.9",
   "fastapi>=0.115.0",
   "uvicorn[standard]>=0.30.0",
   "jinja2>=3.1.0",
   "python-multipart>=0.0.9",
   "itsdangerous>=2.2.0",
   "httpx>=0.27.0",
   "Pillow>=10.0.0",
   "faster-whisper>=1.0.0",
+  "stable-ts>=2.13.3",
 ]
 
 [project.scripts]
 roblox-viral = "roblox_viral.cli:main"
 roblox-viral-web = "roblox_viral.web.app:main"
 
 [tool.setuptools.packages.find]
 where = ["src"]
 
 [tool.setuptools.package-data]
diff --git a/src/roblox_viral/gemini_tts.py b/src/roblox_viral/gemini_tts.py
index 3f08d8d..0740e82 100644
--- a/src/roblox_viral/gemini_tts.py
+++ b/src/roblox_viral/gemini_tts.py
@@ -1,27 +1,30 @@
 """Gemini TTS provider with faster-whisper word alignment for karaoke."""
 
 from __future__ import annotations
 
 import base64
 import json
 import subprocess
 from pathlib import Path
 
 import httpx
+import stable_whisper
 
 from roblox_viral.render import require_ffmpeg
 from roblox_viral.voice import WordTiming
 
 GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
 DEFAULT_GEMINI_VOICE = "Kore"
 DEFAULT_TTS_PROVIDER = "edge"
+DEFAULT_ALIGN_LANGUAGE = "de"
+DEFAULT_ALIGN_MODEL = "base"
 
 GEMINI_VOICES: tuple[str, ...] = (
     "Zephyr",
     "Puck",
     "Charon",
     "Kore",
     "Fenrir",
     "Leda",
     "Orus",
     "Aoede",
@@ -105,77 +108,105 @@ def _parse_sample_rate(mime: str) -> int:
     # e.g. audio/L16;codec=pcm;rate=24000
     for part in mime.replace(" ", "").split(";"):
         if part.lower().startswith("rate="):
             try:
                 return int(part.split("=", 1)[1])
             except ValueError:
                 break
     return 24000
 
 
-def align_words_with_whisper(audio_path: Path, text: str) -> list[WordTiming]:
-    """Force-align narration audio to produce WordTiming via faster-whisper."""
-    from faster_whisper import WhisperModel
-
-    model = WhisperModel("tiny", device="cpu", compute_type="int8")
-    segments, _info = model.transcribe(
-        str(audio_path),
-        word_timestamps=True,
-        initial_prompt=text[:400],
-        vad_filter=False,
+def align_words_with_whisper(
+    audio_path: Path,
+    text: str,
+    *,
+    language: str = DEFAULT_ALIGN_LANGUAGE,
+    model_size: str = DEFAULT_ALIGN_MODEL,
+) -> list[WordTiming]:
+    """Force-align known script to audio via stable-ts + faster-whisper."""
+    script = (text or "").strip()
+    if not script:
+        raise ValueError("TTS text is empty")
+    lang = (language or DEFAULT_ALIGN_LANGUAGE).strip() or DEFAULT_ALIGN_LANGUAGE
+    size = (model_size or DEFAULT_ALIGN_MODEL).strip() or DEFAULT_ALIGN_MODEL
+    model = stable_whisper.load_faster_whisper(
+        size, device="cpu", compute_type="int8"
     )
+    result = model.align(str(audio_path), script, language=lang)
     words: list[WordTiming] = []
-    for segment in segments:
-        for word in segment.words or []:
-            token = (word.word or "").strip()
-            if not token:
-                continue
-            start_ms = max(0, int(round(word.start * 1000)))
-            end_ms = max(start_ms + 1, int(round(word.end * 1000)))
-            words.append(WordTiming(text=token, start_ms=start_ms, end_ms=end_ms))
+    # WhisperResult.all_words() if available; else flatten segment.words
+    raw_words = (
+        result.all_words()
+        if hasattr(result, "all_words")
+        else [
+            w
+            for seg in (result.segments or [])
+            for w in (getattr(seg, "words", None) or [])
+        ]
+    )
+    for word in raw_words:
+        token = (getattr(word, "word", None) or getattr(word, "text", None) or "").strip()
+        if not token:
+            continue
+        start = float(word.start)
+        end = float(word.end)
+        start_ms = max(0, int(round(start * 1000)))
+        end_ms = max(start_ms + 1, int(round(end * 1000)))
+        words.append(WordTiming(text=token, start_ms=start_ms, end_ms=end_ms))
     if not words:
-        raise RuntimeError("Whisper alignment returned no words")
+        raise RuntimeError("Whisper align returned no words")
     for i in range(len(words) - 1):
         if words[i].end_ms < words[i + 1].start_ms:
             words[i] = WordTiming(
                 text=words[i].text,
                 start_ms=words[i].start_ms,
                 end_ms=words[i + 1].start_ms,
             )
     return words
 
 
 class GeminiTTSProvider:
     """Gemini TTS ΓåÆ MP3 + whisper word timings."""
 
     def __init__(
         self,
         api_key: str,
         voice: str = DEFAULT_GEMINI_VOICE,
         *,
         align_fn=None,
+        align_language: str = DEFAULT_ALIGN_LANGUAGE,
+        align_model: str = DEFAULT_ALIGN_MODEL,
     ) -> None:
         key = (api_key or "").strip()
         if not key:
             raise ValueError("GEMINI_API_KEY is not configured")
         self.api_key = key
         self.voice = validate_gemini_voice(voice)
-        self._align_fn = align_fn or align_words_with_whisper
+        self._align_fn = align_fn
+        self.align_language = align_language
+        self.align_model = align_model
 
     def synthesize(self, text: str, output_path: Path | str) -> list[WordTiming]:
         script = (text or "").strip()
         if not script:
             raise ValueError("TTS text is empty")
         out = Path(output_path)
         pcm, sample_rate = self._generate_pcm(script)
         _pcm_to_mp3(pcm, sample_rate=sample_rate, output_mp3=out)
-        return self._align_fn(out, script)
+        if self._align_fn is not None:
+            return self._align_fn(out, script)
+        return align_words_with_whisper(
+            out,
+            script,
+            language=self.align_language,
+            model_size=self.align_model,
+        )
 
     def _generate_pcm(self, text: str) -> tuple[bytes, int]:
         url = (
             "https://generativelanguage.googleapis.com/v1beta/models/"
             f"{GEMINI_TTS_MODEL}:generateContent"
         )
         payload = {
             "contents": [{"parts": [{"text": text}]}],
             "generationConfig": {
                 "responseModalities": ["AUDIO"],
diff --git a/tests/test_gemini_tts.py b/tests/test_gemini_tts.py
index 74c68ed..6446194 100644
--- a/tests/test_gemini_tts.py
+++ b/tests/test_gemini_tts.py
@@ -57,10 +57,115 @@ def test_gemini_tts_synthesize_mocked(tmp_path, monkeypatch):
 
     monkeypatch.setattr(GeminiTTSProvider, "_generate_pcm", fake_generate)
     monkeypatch.setattr("roblox_viral.gemini_tts._pcm_to_mp3", fake_pcm_to_mp3)
 
     out = tmp_path / "narration.mp3"
     provider = GeminiTTSProvider("test-key", "Puck", align_fn=fake_align)
     words = provider.synthesize("Hello world.", out)
     assert out.read_bytes().startswith(b"ID3")
     assert [w.text for w in words] == ["Hello", "world"]
     assert words[0].end_ms == 200
+
+
+def test_align_words_force_uses_stable_ts_align(tmp_path, monkeypatch):
+    from roblox_viral.gemini_tts import align_words_with_whisper
+
+    audio = tmp_path / "n.mp3"
+    audio.write_bytes(b"fake")
+    seen = {}
+
+    class FakeWord:
+        def __init__(self, word, start, end):
+            self.word = word
+            self.start = start
+            self.end = end
+
+    class FakeResult:
+        def all_words(self):
+            return [
+                FakeWord("Hallo", 0.0, 0.2),
+                FakeWord("Welt", 0.2, 0.5),
+            ]
+
+    class FakeModel:
+        def align(self, audio_path, text, language=None, **kwargs):
+            seen["audio"] = str(audio_path)
+            seen["text"] = text
+            seen["language"] = language
+            return FakeResult()
+
+    def fake_load(model_size, device="cpu", compute_type="int8", **kwargs):
+        seen["model_size"] = model_size
+        seen["device"] = device
+        seen["compute_type"] = compute_type
+        return FakeModel()
+
+    monkeypatch.setattr(
+        "roblox_viral.gemini_tts.stable_whisper.load_faster_whisper",
+        fake_load,
+    )
+
+    words = align_words_with_whisper(
+        audio, "Hallo Welt", language="de", model_size="base"
+    )
+    assert seen["model_size"] == "base"
+    assert seen["device"] == "cpu"
+    assert seen["compute_type"] == "int8"
+    assert seen["language"] == "de"
+    assert "Hallo Welt" in seen["text"]
+    assert [w.text for w in words] == ["Hallo", "Welt"]
+    assert words[0].start_ms == 0
+    assert words[0].end_ms == 200
+    assert words[1].start_ms == 200
+    assert words[1].end_ms == 500
+
+
+def test_align_words_raises_when_empty(tmp_path, monkeypatch):
+    from roblox_viral.gemini_tts import align_words_with_whisper
+
+    audio = tmp_path / "n.mp3"
+    audio.write_bytes(b"x")
+
+    class FakeResult:
+        def all_words(self):
+            return []
+
+    class FakeModel:
+        def align(self, *a, **k):
+            return FakeResult()
+
+    monkeypatch.setattr(
+        "roblox_viral.gemini_tts.stable_whisper.load_faster_whisper",
+        lambda *a, **k: FakeModel(),
+    )
+    with pytest.raises(RuntimeError, match="align"):
+        align_words_with_whisper(audio, "Hi", language="de")
+
+
+def test_provider_passes_language_model_to_default_align(tmp_path, monkeypatch):
+    pcm = b"\x00\x00" * 2400
+    seen = {}
+
+    monkeypatch.setattr(
+        GeminiTTSProvider,
+        "_generate_pcm",
+        lambda self, text: (pcm, 24000),
+    )
+    monkeypatch.setattr(
+        "roblox_viral.gemini_tts._pcm_to_mp3",
+        lambda data, *, sample_rate, output_mp3: Path(output_mp3).write_bytes(b"mp3"),
+    )
+
+    def fake_align(audio_path, text, *, language, model_size):
+        seen["language"] = language
+        seen["model_size"] = model_size
+        return [WordTiming("Hi", 0, 100)]
+
+    monkeypatch.setattr(
+        "roblox_viral.gemini_tts.align_words_with_whisper", fake_align
+    )
+
+    out = tmp_path / "n.mp3"
+    GeminiTTSProvider(
+        "key", "Kore", align_language="en", align_model="small"
+    ).synthesize("Hi", out)
+    assert seen == {"language": "en", "model_size": "small"}
