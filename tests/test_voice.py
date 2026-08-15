import pytest

from roblox_viral.voice import (
    DEFAULT_PITCH,
    DEFAULT_SPEED,
    DEFAULT_VIDEO_SPEED,
    EdgeTTSProvider,
    VIDEO_SPEED_MAX,
    VIDEO_SPEED_MIN,
    format_edge_pitch,
    format_edge_rate,
    validate_video_speed,
)


def test_format_edge_pitch_defaults_and_signs():
    assert DEFAULT_PITCH == 15
    assert format_edge_pitch(15) == "+15Hz"
    assert format_edge_pitch(0) == "+0Hz"
    assert format_edge_pitch(-10) == "-10Hz"


def test_format_edge_pitch_rejects_out_of_range():
    with pytest.raises(ValueError):
        format_edge_pitch(-101)
    with pytest.raises(ValueError):
        format_edge_pitch(101)


def test_format_edge_rate_defaults_and_signs():
    assert DEFAULT_SPEED == 130
    assert format_edge_rate(130) == "+30%"
    assert format_edge_rate(100) == "+0%"
    assert format_edge_rate(50) == "-50%"
    assert format_edge_rate(200) == "+100%"


def test_format_edge_rate_rejects_out_of_range():
    with pytest.raises(ValueError):
        format_edge_rate(49)
    with pytest.raises(ValueError):
        format_edge_rate(201)


def test_edge_tts_provider_passes_rate_and_pitch(tmp_path, monkeypatch):
    seen = {}

    class FakeCommunicate:
        def __init__(self, text, voice, **kwargs):
            seen["text"] = text
            seen["voice"] = voice
            seen.update(kwargs)

        async def stream(self):
            yield {"type": "audio", "data": b"ID3fake"}

    import types
    import sys

    fake_mod = types.ModuleType("edge_tts")
    fake_mod.Communicate = FakeCommunicate
    monkeypatch.setitem(sys.modules, "edge_tts", fake_mod)

    out = tmp_path / "n.mp3"
    EdgeTTSProvider(
        voice="en-US-EmmaNeural",
        rate="+30%",
        pitch="+15Hz",
    ).synthesize("Hello", out)
    assert seen["rate"] == "+30%"
    assert seen["pitch"] == "+15Hz"
    assert seen["boundary"] == "WordBoundary"
    assert out.is_file()


def test_validate_video_speed_ok():
    assert DEFAULT_VIDEO_SPEED == 100
    assert validate_video_speed(100) == 100
    assert validate_video_speed(50) == 50
    assert validate_video_speed(200) == 200


def test_validate_video_speed_rejects():
    with pytest.raises(ValueError):
        validate_video_speed(49)
    with pytest.raises(ValueError):
        validate_video_speed(201)
    with pytest.raises(ValueError):
        validate_video_speed(True)  # type: ignore[arg-type]
