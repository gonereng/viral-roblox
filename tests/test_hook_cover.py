from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

import roblox_viral.hook_cover as hook_cover
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


def _changed_bbox(
    before: Image.Image,
    after: Image.Image,
    region: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    x1, y1, _, _ = region
    before_crop = before.crop(region).convert("RGB")
    after_crop = after.crop(region).convert("RGB")
    bbox = ImageChops.difference(before_crop, after_crop).getbbox()
    if bbox is None:
        return None
    bx1, by1, bx2, by2 = bbox
    return (x1 + bx1, y1 + by1, x1 + bx2, y1 + by2)


def test_render_hook_cover_paints_both_boxes(tmp_path):
    template = _blank_template(tmp_path / "tpl.png")
    out = tmp_path / "cover.png"
    render_hook_cover("Hello world", "Second phrase", out, template_path=template)
    assert out.is_file()
    with Image.open(template) as blank, Image.open(out) as painted:
        assert painted.size == (1080, 1920)
        assert _box_pixels(painted, BOX_TOP) != _box_pixels(blank, BOX_TOP)
        assert _box_pixels(painted, BOX_BOTTOM) != _box_pixels(blank, BOX_BOTTOM)


def test_packaged_template_boxes_are_inside_and_receive_text(tmp_path):
    template = hook_cover.default_template_path()
    assert template.is_file()

    out = tmp_path / "cover.png"
    long_top = " ".join(["something was hiding behind the locked door"] * 12)
    long_bottom = " ".join(["then every light in the hallway went dark"] * 12)
    interiors = ((77, 126, 500, 237), (75, 786, 502, 913))
    with Image.open(template) as untouched:
        boxes = hook_cover.boxes_for(untouched.size)
        width, height = untouched.size
        for x1, y1, x2, y2 in boxes:
            assert x1 >= 0
            assert y1 >= 0
            assert x2 <= width
            assert y2 <= height

        scaled_inset = round(BOX_INSET * min(width / 1080, height / 1920))
        min_font = _font(_MIN_FONT, bold=True)
        for text, box in zip((long_top, long_bottom), boxes, strict=True):
            inner_width = (box[2] - box[0]) - 2 * scaled_inset
            assert len(_wrap_text(text, min_font, inner_width)) >= 3

        render_hook_cover(long_top, long_bottom, out, template_path=template)
        with Image.open(out) as painted:
            search_regions = (
                (0, 0, width, height // 2),
                (0, height // 2, width, height),
            )
            for box, interior, search_region in zip(
                boxes, interiors, search_regions, strict=True
            ):
                assert _box_pixels(painted, box) != _box_pixels(untouched, box)
                changed = _changed_bbox(untouched, painted, search_region)
                assert changed is not None
                cx1, cy1, cx2, cy2 = changed
                ix1, iy1, ix2, iy2 = interior
                assert cx1 >= ix1
                assert cy1 >= iy1
                assert cx2 <= ix2
                assert cy2 <= iy2


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


def _text_span_y(
    image: Image.Image,
    region: tuple[int, int, int, int],
) -> int:
    crop = image.crop(region)
    rows = [
        y
        for y in range(crop.height)
        if any(pixel[0] > 200 for pixel in crop.crop((0, y, crop.width, y + 1)).getdata())
    ]
    return max(rows) - min(rows) if rows else 0


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
            inset = _inset_region(box)
            for region in _outside_inset_margin_regions(box):
                assert not _non_background_pixels(painted, region)
            assert _non_background_pixels(painted, inset)
            assert _text_span_y(painted, inset) > 20


def test_render_hook_cover_missing_template_raises(tmp_path):
    with pytest.raises((FileNotFoundError, RuntimeError), match="[Tt]emplate"):
        render_hook_cover(
            "A",
            "B",
            tmp_path / "out.png",
            template_path=tmp_path / "missing.png",
        )
