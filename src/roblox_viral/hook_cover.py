"""Stamp hook phrases onto the packaged Reddit cover template."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from roblox_viral.reddit_card import _font, _wrap_text

HOOK_ERROR = 'First line must be "phrase - phrase"'
DESIGN_SIZE = (1080, 1920)
BOX_TOP = (117, 210, 962, 468)
BOX_BOTTOM = (117, 1447, 962, 1726)
BOX_INSET = 16
_MAX_FONT = 56
_MIN_FONT = 8


def boxes_for(
    size: tuple[int, int],
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    width, height = size
    sx = width / DESIGN_SIZE[0]
    sy = height / DESIGN_SIZE[1]

    def scale(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        return (int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy))

    return scale(BOX_TOP), scale(BOX_BOTTOM)


def _block_height_from_heights(heights: list[int], spacing: int) -> float:
    if not heights:
        return 0
    return sum(heights) + max(0, len(heights) - 1) * spacing


def _render_text_block(
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    spacing: int,
) -> Image.Image:
    if not lines:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    line_bboxes = [measure.textbbox((0, 0), line, font=font) for line in lines]
    heights = [bbox[3] - bbox[1] for bbox in line_bboxes]
    block_w = max(int(measure.textlength(line, font=font)) for line in lines)
    content_h = int(_block_height_from_heights(heights, spacing))
    top_pad = max(bbox[1] for bbox in line_bboxes)
    layer = Image.new("RGBA", (block_w, content_h + top_pad), (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    y = top_pad
    for line, bbox, lh in zip(lines, line_bboxes, heights, strict=True):
        w = layer_draw.textlength(line, font=font)
        x = (block_w - w) / 2
        layer_draw.text((x, y - bbox[1]), line, font=font, fill=(255, 255, 255, 255))
        y += lh + spacing
    alpha_bbox = layer.split()[3].getbbox()
    if alpha_bbox:
        layer = layer.crop(alpha_bbox)
    return layer


def _scale_to_fit(layer: Image.Image, inner_w: int, inner_h: int) -> Image.Image:
    if layer.width <= inner_w and layer.height <= inner_h:
        return layer
    scale = min(inner_w / layer.width, inner_h / layer.height)
    new_w = max(1, int(layer.width * scale))
    new_h = max(1, int(layer.height * scale))
    return layer.resize((new_w, new_h), Image.Resampling.LANCZOS)


def default_template_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "hook_card.png"


def split_hook(line: str) -> tuple[str, str]:
    text = line or ""
    if text.count("-") != 1:
        raise ValueError(HOOK_ERROR)
    left, right = text.split("-", 1)
    top, bottom = left.strip(), right.strip()
    if not top or not bottom:
        raise ValueError(HOOK_ERROR)
    return top, bottom


def _draw_box(
    image: Image.Image,
    text: str,
    box: tuple[int, int, int, int],
    inset: int,
) -> None:
    x1, y1, x2, y2 = box
    inner_w = (x2 - x1) - 2 * inset
    inner_h = (y2 - y1) - 2 * inset
    if not text:
        return

    layer: Image.Image | None = None
    for size in range(_MAX_FONT, _MIN_FONT - 1, -2):
        font = _font(size, bold=True)
        lines = _wrap_text(text, font, inner_w)
        spacing = max(4, size // 8)
        candidate = _render_text_block(lines, font, spacing)
        if candidate.width <= inner_w and candidate.height <= inner_h:
            layer = candidate
            break

    if layer is None:
        font = _font(_MIN_FONT, bold=True)
        lines = _wrap_text(text, font, inner_w)
        spacing = max(4, _MIN_FONT // 8)
        layer = _scale_to_fit(_render_text_block(lines, font, spacing), inner_w, inner_h)

    paste_x = x1 + inset + (inner_w - layer.width) // 2
    paste_y = y1 + inset + (inner_h - layer.height) // 2
    image.paste(layer, (paste_x, paste_y), layer)


def render_hook_cover(
    top: str,
    bottom: str,
    output_path: Path | str,
    *,
    template_path: Path | str | None = None,
) -> Path:
    template = Path(template_path) if template_path is not None else default_template_path()
    if not template.is_file():
        raise FileNotFoundError(f"Cover template not found: {template}")
    with Image.open(template) as src:
        image = src.convert("RGBA")
    sx = image.width / DESIGN_SIZE[0]
    sy = image.height / DESIGN_SIZE[1]
    inset = max(1, round(BOX_INSET * min(sx, sy)))
    top_box, bottom_box = boxes_for(image.size)
    _draw_box(image, top, top_box, inset)
    _draw_box(image, bottom, bottom_box, inset)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="PNG")
    return out
