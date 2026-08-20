"""Tests for reddit clip planning."""

import random
from pathlib import Path

import pytest

from roblox_viral.reddit_clips import (
    plan_reddit_clips,
    plan_reddit_sentence_clips,
    sentence_durations_s,
)
from roblox_viral.voice import WordTiming


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


def test_sentence_durations_s_from_word_groups():
    sentences = ["Hello world.", "Second line."]
    words = [
        WordTiming("Hello", 0, 200),
        WordTiming("world.", 200, 500),
        WordTiming("Second", 500, 800),
        WordTiming("line.", 800, 1000),
    ]
    durs = sentence_durations_s(sentences, words)
    assert len(durs) == 2
    assert abs(durs[0] - 0.5) < 1e-6
    assert abs(durs[1] - 0.5) < 1e-6


def test_plan_one_video_per_sentence():
    paths = [Path("a.mp4"), Path("b.mp4"), Path("c.mp4")]
    durs_map = {p: 30.0 for p in paths}
    rng = random.Random(0)
    segs = plan_reddit_sentence_clips(
        paths,
        [2.0, 3.0, 1.5],
        video_speed=100,
        durations=durs_map,
        rng=rng,
    )
    # 3 sentences -> 3 picks -> 3 segments (each file long enough)
    assert len(segs) == 3
    assert segs[0].path != segs[1].path != segs[2].path
    assert abs(segs[0].duration_s - 2.0) < 1e-6
    assert abs(segs[1].duration_s - 3.0) < 1e-6
    assert abs(segs[2].duration_s - 1.5) < 1e-6


def test_plan_loops_short_file_within_sentence():
    p = Path("short.mp4")
    segs = plan_reddit_sentence_clips(
        [p],
        [5.0],
        video_speed=100,
        durations={p: 2.0},
        rng=random.Random(1),
    )
    assert len(segs) == 3  # 2+2+1
    assert all(s.path == p and s.start_s == 0.0 for s in segs)
    assert abs(sum(s.duration_s for s in segs) - 5.0) < 1e-6


def test_plan_video_speed_doubles_source():
    p = Path("a.mp4")
    segs = plan_reddit_sentence_clips(
        [p],
        [2.0],
        video_speed=200,
        durations={p: 10.0},
        rng=random.Random(2),
    )
    assert abs(sum(s.duration_s for s in segs) - 4.0) < 1e-6


def test_plan_reshuffles_when_more_sentences_than_pool():
    paths = [Path("a.mp4"), Path("b.mp4")]
    durs_map = {p: 10.0 for p in paths}
    rng = random.Random(3)
    segs = plan_reddit_sentence_clips(
        paths,
        [1.0, 1.0, 1.0],
        durations=durs_map,
        rng=rng,
    )
    assert len(segs) == 3
    assert len({s.path for s in segs}) >= 2  # used both before repeat
