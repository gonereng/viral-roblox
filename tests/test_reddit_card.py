"""Tests for Reddit title-card rendering and timing."""

from PIL import Image

from roblox_viral.reddit_card import first_sentence_end_s, render_reddit_card
from roblox_viral.voice import WordTiming


def test_first_sentence_end_s():
    sentences = ["Hello world.", "Second line."]
    words = [
        WordTiming("Hello", 0, 200),
        WordTiming("world.", 200, 500),
        WordTiming("Second", 500, 800),
        WordTiming("line.", 800, 1000),
    ]

    assert abs(first_sentence_end_s(sentences, words) - 0.5) < 1e-6


def test_first_sentence_end_s_fallback_empty_words():
    assert first_sentence_end_s(["Hi."], []) == 2.0


def test_render_reddit_card_writes_png(tmp_path):
    out = tmp_path / "card.png"

    path = render_reddit_card("Company copied my code after refusing to pay.", out)

    assert path.is_file()
    with Image.open(path) as image:
        assert image.size[0] == 972
        assert image.size[1] > 80
        assert image.mode in ("RGBA", "RGB")
