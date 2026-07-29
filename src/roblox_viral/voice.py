"""Text-to-speech providers with word-level timings."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class WordTiming:
    text: str
    start_ms: int
    end_ms: int


class VoiceProvider(Protocol):
    """Interface for TTS backends (Edge TTS now, ElevenLabs later)."""

    def synthesize(self, text: str, output_path: Path | str) -> list[WordTiming]:
        """Synthesize speech to output_path; return word timings."""
        ...


# Edge TTS boundary offset/duration are in 100-nanosecond units.
_TICKS_PER_MS = 10_000


class EdgeTTSProvider:
    """Microsoft Edge TTS via edge-tts, with word-boundary events."""

    def __init__(self, voice: str = "en-US-EmmaNeural") -> None:
        self.voice = voice

    def synthesize(self, text: str, output_path: Path | str) -> list[WordTiming]:
        return asyncio.run(self._synthesize_async(text, Path(output_path)))

    async def _synthesize_async(self, text: str, output_path: Path) -> list[WordTiming]:
        import edge_tts

        output_path.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(
            text, self.voice, boundary="WordBoundary"
        )
        words: list[WordTiming] = []
        audio_chunks: list[bytes] = []

        async for chunk in communicate.stream():
            kind = chunk.get("type")
            if kind == "audio":
                audio_chunks.append(chunk["data"])
            elif kind == "WordBoundary":
                offset_ms = int(chunk["offset"] / _TICKS_PER_MS)
                duration_ms = int(chunk["duration"] / _TICKS_PER_MS)
                words.append(
                    WordTiming(
                        text=str(chunk["text"]).strip(),
                        start_ms=offset_ms,
                        end_ms=offset_ms + max(duration_ms, 1),
                    )
                )

        if not audio_chunks:
            raise RuntimeError("Edge TTS returned no audio")

        output_path.write_bytes(b"".join(audio_chunks))

        # Fill gaps so karaoke covers continuous speech without blank flashes
        for i in range(len(words) - 1):
            if words[i].end_ms < words[i + 1].start_ms:
                words[i] = WordTiming(
                    text=words[i].text,
                    start_ms=words[i].start_ms,
                    end_ms=words[i + 1].start_ms,
                )

        return words
