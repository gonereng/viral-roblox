from pathlib import Path

import pytest

from roblox_viral.gemini_tts import (
    DEFAULT_GEMINI_VOICE,
    GEMINI_VOICES,
    GeminiTTSProvider,
    normalize_tts_provider,
    validate_gemini_voice,
)
from roblox_viral.voice import WordTiming


def test_normalize_tts_provider():
    assert normalize_tts_provider(None) == "edge"
    assert normalize_tts_provider("") == "edge"
    assert normalize_tts_provider("Gemini") == "gemini"
    with pytest.raises(ValueError, match="tts_provider"):
        normalize_tts_provider("eleven")


def test_validate_gemini_voice_allowlist():
    assert validate_gemini_voice("kore") == "Kore"
    assert validate_gemini_voice(DEFAULT_GEMINI_VOICE) == "Kore"
    assert "Zephyr" in GEMINI_VOICES
    with pytest.raises(ValueError, match="Unknown Gemini voice"):
        validate_gemini_voice("en-US-EmmaNeural")


def test_gemini_tts_provider_requires_api_key():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiTTSProvider("")


def test_gemini_tts_synthesize_mocked(tmp_path, monkeypatch):
    # 0.1s of silence at 24kHz mono s16le
    pcm = b"\x00\x00" * 2400
    sample_rate = 24000

    def fake_generate(self, text: str):
        assert "Hello" in text
        return pcm, sample_rate

    def fake_pcm_to_mp3(data, *, sample_rate, output_mp3):
        assert data == pcm
        assert sample_rate == 24000
        Path(output_mp3).write_bytes(b"ID3fake-mp3")

    def fake_align(audio_path: Path, text: str):
        assert audio_path.is_file()
        assert "Hello" in text
        return [
            WordTiming("Hello", 0, 200),
            WordTiming("world", 200, 500),
        ]

    monkeypatch.setattr(GeminiTTSProvider, "_generate_pcm", fake_generate)
    monkeypatch.setattr("roblox_viral.gemini_tts._pcm_to_mp3", fake_pcm_to_mp3)

    out = tmp_path / "narration.mp3"
    provider = GeminiTTSProvider("test-key", "Puck", align_fn=fake_align)
    words = provider.synthesize("Hello world.", out)
    assert out.read_bytes().startswith(b"ID3")
    assert [w.text for w in words] == ["Hello", "world"]
    assert words[0].end_ms == 200


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
