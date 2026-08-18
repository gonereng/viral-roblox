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


def _trim_lines_to_height(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    spacing: int,
    inner_h: int,
) -> tuple[list[str], list[int]]:
    fitted = list(lines)
    while fitted:
        heights = _line_heights(draw, fitted, font)
        if _block_height_from_heights(heights, spacing) <= inner_h:
            return fitted, heights
        fitted = fitted[:-1]
    return [], []


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
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
) -> None:
    x1, y1, x2, y2 = box
    inner_w = (x2 - x1) - 2 * BOX_INSET
    inner_h = (y2 - y1) - 2 * BOX_INSET
    font = _font(_MIN_FONT, bold=True)
    lines = _wrap_text(text, font, inner_w)
    spacing = max(4, _MIN_FONT // 8)
    line_heights = _line_heights(draw, lines, font)
    for size in range(_MAX_FONT, _MIN_FONT - 1, -2):
        candidate = _font(size, bold=True)
        wrapped = _wrap_text(text, candidate, inner_w)
        sp = max(4, size // 8)
        heights = _line_heights(draw, wrapped, candidate)
        if _block_height_from_heights(heights, sp) <= inner_h:
            font = candidate
            lines = wrapped
            spacing = sp
            line_heights = heights
            break
    lines, line_heights = _trim_lines_to_height(draw, lines, font, spacing, inner_h)
    if not lines:
        return
    inner_y1 = y1 + BOX_INSET
    inner_y2 = inner_y1 + inner_h
    block_h = _block_height_from_heights(line_heights, spacing)
    y = inner_y1 + max(0, (inner_h - block_h) / 2)
    for line, lh in zip(lines, line_heights, strict=True):
        w = draw.textlength(line, font=font)
        x = x1 + BOX_INSET + max(0, (inner_w - w) / 2)
        bbox = draw.textbbox((x, y), line, font=font)
        if bbox[1] < inner_y1 or bbox[3] > inner_y2:
            break
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += lh + spacing


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
    draw = ImageDraw.Draw(image)
    _draw_box(draw, top, BOX_TOP)
    _draw_box(draw, bottom, BOX_BOTTOM)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="PNG")
    return out
