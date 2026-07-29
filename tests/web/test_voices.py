import pytest
from roblox_viral.web import voices

@pytest.mark.asyncio
async def test_list_english_voices_filters(monkeypatch):
    async def fake_list():
        return [
            {"ShortName": "en-US-EmmaNeural", "Locale": "en-US", "Gender": "Female"},
            {"ShortName": "de-DE-ConradNeural", "Locale": "de-DE", "Gender": "Male"},
            {"ShortName": "en-GB-RyanNeural", "Locale": "en-GB", "Gender": "Male"},
        ]
    monkeypatch.setattr(voices, "_fetch_voices", fake_list)
    voices.clear_cache()
    result = await voices.list_english_voices()
    names = [v.short_name for v in result]
    assert names == ["en-GB-RyanNeural", "en-US-EmmaNeural"]
    assert voices.DEFAULT_VOICE == "en-US-EmmaNeural"
