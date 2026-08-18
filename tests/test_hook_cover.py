from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from roblox_viral.hook_cover import (
    BOX_BOTTOM,
    BOX_INSET,
    BOX_TOP,
    HOOK_ERROR,
    _MIN_FONT,
    render_hook_cover,
    split_hook,
)
from roblox_viral.reddit_card import _font, _wrap_text


def test_split_hook_valid():
    assert split_hook("I found a door - Then it slammed") == (
        "I found a door",
        "Then it slammed",
    )
    assert split_hook("  A  -  B  ") == ("A", "B")


@pytest.mark.parametrize(
    "line",
    [
        "No dash here",
        "too - many - dashes",
        " - only bottom",
        "only top - ",
        "-",
        "",
    ],
)
def test_split_hook_rejects_bad_lines(line):
    with pytest.raises(ValueError, match="phrase - phrase"):
        split_hook(line)


def _blank_template(path: Path) -> Path:
    img = Image.new("RGBA", (1080, 1920), (10, 10, 10, 255))
    draw = ImageDraw.Draw(img)
    for box in (BOX_TOP, BOX_BOTTOM):
        draw.rectangle(box, fill=(40, 40, 40, 255))
    img.save(path)
    return path


def _box_pixels(image: Image.Image, box: tuple[int, int, int, int]) -> list:
    x1, y1, x2, y2 = box
    crop = image.crop((x1, y1, x2, y2))
    return list(crop.getdata())


def test_render_hook_cover_paints_both_boxes(tmp_path):
    template = _blank_template(tmp_path / "tpl.png")
    out = tmp_path / "cover.png"
    render_hook_cover("Hello world", "Second phrase", out, template_path=template)
    assert out.is_file()
    with Image.open(template) as blank, Image.open(out) as painted:
        assert painted.size == (1080, 1920)
        assert _box_pixels(painted, BOX_TOP) != _box_pixels(blank, BOX_TOP)
        assert _box_pixels(painted, BOX_BOTTOM) != _box_pixels(blank, BOX_BOTTOM)


def _inset_region(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    return (x1 + BOX_INSET, y1 + BOX_INSET, x2 - BOX_INSET, y2 - BOX_INSET)


def _outside_inset_margin_regions(
    box: tuple[int, int, int, int],
) -> list[tuple[int, int, int, int]]:
    x1, y1, x2, y2 = box
    ix1, iy1, ix2, iy2 = _inset_region(box)
    return [
        (x1, y1, x2, iy1),
        (x1, iy2, x2, y2),
        (x1, iy1, ix1, iy2),
        (ix2, iy1, x2, iy2),
    ]


def _non_background_pixels(
    image: Image.Image,
    region: tuple[int, int, int, int],
    *,
    background: tuple[int, int, int, int] = (40, 40, 40, 255),
) -> list[tuple[int, ...]]:
    crop = image.crop(region)
    return [pixel for pixel in crop.getdata() if pixel != background]


def test_render_hook_cover_long_text_stays_inside_inset(tmp_path):
    template = _blank_template(tmp_path / "tpl.png")
    out = tmp_path / "cover.png"
    long_top = " ".join(["word"] * 50)
    long_bottom = " ".join(["phrase"] * 50)
    inner_w = (BOX_TOP[2] - BOX_TOP[0]) - 2 * BOX_INSET
    min_font = _font(_MIN_FONT, bold=True)
    assert len(_wrap_text(long_top, min_font, inner_w)) > 1
    render_hook_cover(long_top, long_bottom, out, template_path=template)
    with Image.open(out) as painted:
        for box in (BOX_TOP, BOX_BOTTOM):
            for region in _outside_inset_margin_regions(box):
                assert not _non_background_pixels(painted, region)
            assert _non_background_pixels(painted, _inset_region(box))


def test_render_hook_cover_missing_template_raises(tmp_path):
    with pytest.raises((FileNotFoundError, RuntimeError), match="[Tt]emplate"):
        render_hook_cover(
            "A",
            "B",
            tmp_path / "out.png",
            template_path=tmp_path / "missing.png",
        )
