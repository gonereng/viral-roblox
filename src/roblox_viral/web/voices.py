from __future__ import annotations

import time
from dataclasses import dataclass

import edge_tts

DEFAULT_VOICE = "en-US-EmmaNeural"
_CACHE_TTL_SECONDS = 3600

_cache: list[VoiceInfo] | None = None
_cache_time: float = 0.0


@dataclass(frozen=True)
class VoiceInfo:
    short_name: str
    locale: str
    gender: str


def clear_cache() -> None:
    global _cache, _cache_time
    _cache = None
    _cache_time = 0.0


async def _fetch_voices() -> list[dict]:
    return await edge_tts.list_voices()


async def list_english_voices() -> list[VoiceInfo]:
    global _cache, _cache_time
    now = time.monotonic()
    if _cache is not None and (now - _cache_time) < _CACHE_TTL_SECONDS:
        return _cache

    raw = await _fetch_voices()
    english = [
        VoiceInfo(
            short_name=v["ShortName"],
            locale=v["Locale"],
            gender=v["Gender"],
        )
        for v in raw
        if v["Locale"].startswith("en")
    ]
    english.sort(key=lambda v: v.short_name)
    _cache = english
    _cache_time = now
    return _cache
