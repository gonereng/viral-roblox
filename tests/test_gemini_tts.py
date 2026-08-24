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
