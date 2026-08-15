"""Tests for reddit clip planning."""

import random
from pathlib import Path

import pytest

from roblox_viral.reddit_clips import plan_reddit_clips


def test_plan_trims_last_clip():
    paths = [Path("a.mp4"), Path("b.mp4")]
    durs = {paths[0]: 10.0, paths[1]: 10.0}
    rng = random.Random(0)
    segs = plan_reddit_clips(paths, 15.0, durations=durs, rng=rng)
    assert abs(sum(s.duration_s for s in segs) - 15.0) < 1e-6
    assert segs[-1].duration_s < 10.0 or len(segs) == 2


def test_plan_reshuffles_when_exhausted():
    p = Path("only.mp4")
    segs = plan_reddit_clips([p], 25.0, durations={p: 10.0}, rng=random.Random(1))
    assert len(segs) == 3
    assert abs(sum(s.duration_s for s in segs) - 25.0) < 1e-6


def test_plan_empty_pool_errors():
    with pytest.raises(ValueError):
        plan_reddit_clips([], 10.0, durations={})
