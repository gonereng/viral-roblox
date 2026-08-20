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


DEFAULT_PITCH = 15
DEFAULT_SPEED = 130
PITCH_MIN, PITCH_MAX = -100, 100
SPEED_MIN, SPEED_MAX = 50, 200

DEFAULT_VIDEO_SPEED = 100
SINGLE_VIDEO_SPEED_MIN, SINGLE_VIDEO_SPEED_MAX = 50, 200
REDDIT_VIDEO_SPEED_MIN, REDDIT_VIDEO_SPEED_MAX = 100, 500
VIDEO_SPEED_MIN, VIDEO_SPEED_MAX = SINGLE_VIDEO_SPEED_MIN, SINGLE_VIDEO_SPEED_MAX


def validate_video_speed(percent: int, *, mode: str = "single") -> int:
    if not isinstance(percent, int) or isinstance(percent, bool):
        raise ValueError("video_speed must be an int")
    m = (mode or "single").strip().lower()
    if m == "reddit":
        lo, hi = REDDIT_VIDEO_SPEED_MIN, REDDIT_VIDEO_SPEED_MAX
    else:
        lo, hi = SINGLE_VIDEO_SPEED_MIN, SINGLE_VIDEO_SPEED_MAX
    if percent < lo or percent > hi:
        raise ValueError(f"video_speed must be between {lo} and {hi}")
    return percent


def format_edge_pitch(pitch: int) -> str:
    if not isinstance(pitch, int) or isinstance(pitch, bool):
        raise ValueError("pitch must be an int")
    if pitch < PITCH_MIN or pitch > PITCH_MAX:
        raise ValueError(f"pitch must be between {PITCH_MIN} and {PITCH_MAX}")
    if pitch >= 0:
        return f"+{pitch}Hz"
    return f"{pitch}Hz"


def format_edge_rate(speed_percent: int) -> str:
    if not isinstance(speed_percent, int) or isinstance(speed_percent, bool):
        raise ValueError("speed must be an int")
    if speed_percent < SPEED_MIN or speed_percent > SPEED_MAX:
        raise ValueError(
            f"speed must be between {SPEED_MIN} and {SPEED_MAX}"
        )
    delta = speed_percent - 100
    if delta >= 0:
        return f"+{delta}%"
    return f"{delta}%"


# Edge TTS boundary offset/duration are in 100-nanosecond units.
_TICKS_PER_MS = 10_000


class EdgeTTSProvider:
    """Microsoft Edge TTS via edge-tts, with word-boundary events."""

    def __init__(
        self,
        voice: str = "en-US-EmmaNeural",
        *,
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    def synthesize(self, text: str, output_path: Path | str) -> list[WordTiming]:
        return asyncio.run(self._synthesize_async(text, Path(output_path)))

    async def _synthesize_async(self, text: str, output_path: Path) -> list[WordTiming]:
        import edge_tts

        output_path.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=self.rate,
            pitch=self.pitch,
            boundary="WordBoundary",
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
