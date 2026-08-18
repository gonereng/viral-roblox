"""Stamp hook phrases onto the packaged Reddit cover template."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from roblox_viral.reddit_card import _font, _wrap_text

HOOK_ERROR = 'First line must be "phrase - phrase"'
BOX_TOP = (200, 335, 880, 520)
BOX_BOTTOM = (200, 1400, 880, 1600)
BOX_INSET = 16
_MAX_FONT = 56
_MIN_FONT = 8


def _line_heights(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> list[int]:
    heights: list[int] = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        heights.append(bbox[3] - bbox[1])
    return heights


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
    heights = _line_heights(measure, lines, font)
    block_w = max(int(measure.textlength(line, font=font)) for line in lines)
    block_h = int(_block_height_from_heights(heights, spacing))
    layer = Image.new("RGBA", (block_w, block_h), (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    y = 0
    for line, lh in zip(lines, heights, strict=True):
        w = layer_draw.textlength(line, font=font)
        x = (block_w - w) / 2
        layer_draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
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
) -> None:
    x1, y1, x2, y2 = box
    inner_w = (x2 - x1) - 2 * BOX_INSET
    inner_h = (y2 - y1) - 2 * BOX_INSET
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

    paste_x = x1 + BOX_INSET + (inner_w - layer.width) // 2
    paste_y = y1 + BOX_INSET + (inner_h - layer.height) // 2
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
    _draw_box(image, top, BOX_TOP)
    _draw_box(image, bottom, BOX_BOTTOM)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="PNG")
    return out
