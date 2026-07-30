from __future__ import annotations

import httpx

GEMINI_MODEL = "gemini-2.5-flash"
_GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


async def generate_story(api_key: str, prompt: str) -> str:
    key = (api_key or "").strip()
    text = (prompt or "").strip()
    if not key:
        raise ValueError("GEMINI_API_KEY is not configured")
    if not text:
        raise ValueError("Prompt cannot be empty")

    payload = {"contents": [{"parts": [{"text": text}]}]}
    headers = {
        "x-goog-api-key": key,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(_GEMINI_URL, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text[:300]
        try:
            body = response.json()
            detail = body.get("error", {}).get("message", detail)
        except Exception:
            pass
        raise RuntimeError(f"Gemini API error ({response.status_code}): {detail}")

    data = response.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        story = "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Gemini returned an unexpected response") from exc
    if not story:
        raise RuntimeError("Gemini returned an empty story")
    return story
