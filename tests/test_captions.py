"""Tests for ASS one-word-at-a-time caption builder."""

from __future__ import annotations

from roblox_viral.captions import (
    build_ass,
    partition_words_by_sentences,
    _ass_time,
)
from roblox_viral.voice import WordTiming


def _words() -> list[WordTiming]:
    texts = ["I", "was", "playing", "Roblox", "when", "everything", "went", "wrong"]
    words: list[WordTiming] = []
    t = 0
    for text in texts:
        words.append(WordTiming(text=text, start_ms=t, end_ms=t + 200))
        t += 220
    return words


def test_ass_time_format():
    assert _ass_time(0) == "0:00:00.00"
    assert _ass_time(1500) == "0:00:01.50"
    assert _ass_time(61_070) == "0:01:01.07"


def test_build_ass_contains_events_and_styles():
    ass = build_ass(_words())
    assert "[Script Info]" in ass
    assert "PlayResX: 1080" in ass
    assert "PlayResY: 1920" in ass
    assert "Arial Black" in ass
    assert "Dialogue:" in ass
    assert r"\c&H00FFFF&" in ass
    assert "0:00:00.00" in ass
    assert ass.count("Dialogue:") == len(_words())


def test_build_ass_escapes_braces():
    words = [WordTiming(text="{hi}", start_ms=0, end_ms=100)]
    ass = build_ass(words)
    assert r"\{hi\}" in ass


def test_partition_by_sentences():
    words = _words()
    sentences = ["I was playing Roblox", "when everything went wrong"]
    groups = partition_words_by_sentences(sentences, words)
    assert [w.text for w in groups[0]] == ["I", "was", "playing", "Roblox"]
    assert [w.text for w in groups[1]] == ["when", "everything", "went", "wrong"]


def test_sentence_words_do_not_appear_before_sentence_starts():
    words = _words()
    sentences = ["I was playing Roblox", "when everything went wrong"]
    ass = build_ass(words, sentences=sentences)

    dialogue_lines = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    for line in dialogue_lines:
        parts = line.split(",", 9)
        start_s = parts[1]
        text = parts[9]
        if start_s < "0:00:00.88":
            assert "when" not in text
            assert "everything" not in text
            assert "went" not in text
            assert "wrong" not in text


def test_one_word_at_a_time():
    words = [
        WordTiming("Hello", 0, 100),
        WordTiming("world", 100, 200),
        WordTiming("today", 200, 300),
    ]
    ass = build_ass(words, sentences=["Hello world today"])
    lines = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    assert len(lines) == 3

    first_text = lines[0].split(",", 9)[9]
    assert "Hello" in first_text
    assert "world" not in first_text
    assert "today" not in first_text

    second_text = lines[1].split(",", 9)[9]
    assert "world" in second_text
    assert "Hello" not in second_text
    assert "today" not in second_text

    third_text = lines[2].split(",", 9)[9]
    assert "today" in third_text
    assert "Hello" not in third_text
    assert "world" not in third_text
