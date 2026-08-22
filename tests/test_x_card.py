from pathlib import Path
import random

from roblox_viral.x_card import (
    DEFAULT_X_DISPLAY_NAME,
    DEFAULT_X_HANDLE,
    format_engagement_count,
    random_engagement,
    render_x_card,
)


def test_format_engagement_count():
    assert format_engagement_count(37) == "37"
    assert format_engagement_count(866) == "866"
    assert format_engagement_count(3200) == "3.2K"
    assert format_engagement_count(95000) == "95K"
    assert format_engagement_count(1_100_000) == "1.1M"


def test_random_engagement_ranges():
    rng = random.Random(0)
    for _ in range(20):
        e = random_engagement(rng=rng)
        assert 1_000 <= e["replies"] <= 20_000
        assert 5_000 <= e["reposts"] <= 80_000
        assert 20_000 <= e["likes"] <= 500_000
        assert 100_000 <= e["views"] <= 2_000_000


def test_render_x_card_writes_png(tmp_path):
    out = tmp_path / "x_card.png"
    path = render_x_card(
        "Hook line that should appear on the card.",
        out,
        engagement={
            "replies": 1200,
            "reposts": 8600,
            "likes": 32000,
            "views": 950000,
        },
    )
    assert path == out
    assert out.is_file()
    assert out.stat().st_size > 1000
    from PIL import Image

    with Image.open(out) as im:
        assert im.size[0] >= 800
        assert im.size[1] > 100
