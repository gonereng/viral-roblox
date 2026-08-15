"""Plan reddit background clips by shuffling source videos."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from roblox_viral.render import probe_duration_seconds

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
