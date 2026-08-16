"""Tests for Reddit title-card rendering and timing."""

from PIL import Image
import pytest

from roblox_viral import reddit_card as rc
from roblox_viral.reddit_card import first_sentence_end_s, render_reddit_card
from roblox_viral.voice import WordTiming


def test_reddit_card_layout_constants_are_1x_base():
    assert rc.CARD_WIDTH == 864
    assert rc._AVATAR_SIZE == 40
    assert rc._PADDING == 24
    assert rc._HEADER_HEIGHT == 40
    assert rc._TITLE_GAP == 18
    assert rc._BOTTOM_PADDING == 28
    assert rc._TITLE_SPACING == 8
    assert rc._TITLE_FONT == 34
    assert rc._USERNAME_FONT == 19
    assert rc._META_FONT == 18


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


def test_render_reddit_card_scale_2_is_taller_than_scale_1(tmp_path):
    title = "Company copied my code after refusing to pay."
    out1 = tmp_path / "card1.png"
    out2 = tmp_path / "card2.png"

    render_reddit_card(title, out1, scale=1.0)
    render_reddit_card(title, out2, scale=2.0)

    with Image.open(out1) as a, Image.open(out2) as b:
        assert a.size[0] == 864
        assert b.size[0] == 864
        assert a.size[1] > 80
        assert b.size[1] > a.size[1]
        assert a.mode in ("RGBA", "RGB")
        assert b.mode in ("RGBA", "RGB")


def test_render_reddit_card_rejects_non_positive_scale(tmp_path):
    with pytest.raises(ValueError, match="scale"):
        render_reddit_card("Hi.", tmp_path / "x.png", scale=0)
