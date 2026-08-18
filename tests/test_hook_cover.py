from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from roblox_viral.hook_cover import (
    BOX_BOTTOM,
    BOX_TOP,
    HOOK_ERROR,
    render_hook_cover,
    split_hook,
)


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


def test_render_hook_cover_missing_template_raises(tmp_path):
    with pytest.raises((FileNotFoundError, RuntimeError), match="[Tt]emplate"):
        render_hook_cover(
            "A",
            "B",
            tmp_path / "out.png",
            template_path=tmp_path / "missing.png",
        )
