"""Plan reddit background clips by shuffling source videos."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from roblox_viral.captions import partition_words_by_sentences
from roblox_viral.render import probe_duration_seconds
from roblox_viral.voice import WordTiming

_EPSILON = 1e-6


@dataclass(frozen=True)
class ClipSegment:
    path: Path
    start_s: float  # always 0 for v1
    duration_s: float


def _duration_for(path: Path, durations: dict[Path, float] | None) -> float:
    if durations is not None:
        return durations[path]
    return probe_duration_seconds(path)


def plan_reddit_clips(
    paths: list[Path],
    target_seconds: float,
    *,
    durations: dict[Path, float] | None = None,
    rng: random.Random | None = None,
) -> list[ClipSegment]:
    """
    Shuffle without replacement; reshuffle when exhausted; trim last segment.

    durations: optional map path→seconds (tests inject; production uses probe).
    Raise ValueError if paths empty or target_seconds <= 0.
    """
    if not paths or target_seconds <= 0:
        raise ValueError("paths must be non-empty and target_seconds must be positive")

    rng = rng or random.Random()
    remaining = target_seconds
    out: list[ClipSegment] = []
    bag: list[Path] = []

    while remaining > _EPSILON:
        if not bag:
            bag = list(paths)
            rng.shuffle(bag)

        path = bag.pop()
        duration = _duration_for(path, durations)
        if duration <= 0:
            raise ValueError(f"duration must be positive for {path}")

        use = min(duration, remaining)
        out.append(ClipSegment(path=path, start_s=0.0, duration_s=use))
        remaining -= use

    return out


def sentence_durations_s(
    sentences: list[str], words: list[WordTiming]
) -> list[float]:
    groups = partition_words_by_sentences(sentences, words)
    if len(groups) != len(sentences):
        raise ValueError("sentence count mismatch")
    out: list[float] = []
    for group in groups:
        if not group:
            raise ValueError("sentence has no words")
        duration = (group[-1].end_ms - group[0].start_ms) / 1000.0
        if duration <= 0:
            raise ValueError("sentence duration must be positive")
        out.append(duration)
    return out


def plan_reddit_sentence_clips(
    paths: list[Path],
    sentence_durations_s: list[float],
    *,
    video_speed: int = 100,
    durations: dict[Path, float] | None = None,
    rng: random.Random | None = None,
) -> list[ClipSegment]:
    if not paths or not sentence_durations_s:
        raise ValueError("paths and sentence_durations_s must be non-empty")
    if video_speed <= 0:
        raise ValueError("video_speed must be positive")

    rng = rng or random.Random()
    out: list[ClipSegment] = []
    bag: list[Path] = []

    for sent_dur in sentence_durations_s:
        if sent_dur <= 0:
            raise ValueError("sentence duration must be positive")
        source_needed = sent_dur * (video_speed / 100.0)
        if not bag:
            bag = list(paths)
            rng.shuffle(bag)
        path = bag.pop()
        file_duration = _duration_for(path, durations)
        if file_duration <= 0:
            raise ValueError(f"duration must be positive for {path}")

        remaining = source_needed
        while remaining > _EPSILON:
            use = min(file_duration, remaining)
            out.append(ClipSegment(path=path, start_s=0.0, duration_s=use))
            remaining -= use

    return out
