import httpx
import pytest

from roblox_viral.web.gemini import GEMINI_MODEL, generate_story


@pytest.mark.asyncio
async def test_generate_story_success(monkeypatch):
    async def fake_post(self, url, **kwargs):
        assert GEMINI_MODEL in url
        assert kwargs["headers"]["x-goog-api-key"] == "k"
        assert kwargs["json"]["contents"][0]["parts"][0]["text"] == "Do the thing"
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "I joined a game.\nIt was dark.\n"}]}}
                ]
            },
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    story = await generate_story("k", "Do the thing")
    assert story == "I joined a game.\nIt was dark."


@pytest.mark.asyncio
async def test_generate_story_requires_api_key():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        await generate_story("", "prompt")


@pytest.mark.asyncio
async def test_generate_story_http_error(monkeypatch):
    async def fake_post(self, url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(403, json={"error": {"message": "nope"}}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(RuntimeError, match="Gemini"):
        await generate_story("k", "prompt")
