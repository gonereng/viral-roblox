"""Tests for Reddit title-card rendering and timing."""

from PIL import Image

from roblox_viral import reddit_card as rc
from roblox_viral.reddit_card import first_sentence_end_s, render_reddit_card
from roblox_viral.voice import WordTiming


def test_reddit_card_layout_constants_are_scaled():
    assert rc.CARD_WIDTH == 972
    assert rc._AVATAR_SIZE == 80
    assert rc._PADDING == 48
    assert rc._HEADER_HEIGHT == 80
    assert rc._TITLE_GAP == 36
    assert rc._BOTTOM_PADDING == 56
    assert rc._TITLE_SPACING == 16


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
        assert image.size[1] > 160  # taller than old ~80+ header
        assert image.mode in ("RGBA", "RGB")
