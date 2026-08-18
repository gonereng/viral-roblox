"""Stamp hook phrases onto the packaged Reddit cover template."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from roblox_viral.reddit_card import _font, _wrap_text

HOOK_ERROR = 'First line must be "phrase - phrase"'
BOX_TOP = (200, 335, 880, 520)
BOX_BOTTOM = (200, 1400, 880, 1600)
BOX_INSET = 16
_MAX_FONT = 56
_MIN_FONT = 16


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
    lines = [text]
    spacing = 4
    line_h = _MIN_FONT
    for size in range(_MAX_FONT, _MIN_FONT - 1, -2):
        candidate = _font(size, bold=True)
        wrapped = _wrap_text(text, candidate, inner_w)
        bbox = candidate.getbbox("Ag")
        lh = bbox[3] - bbox[1]
        sp = max(4, size // 8)
        block_h = len(wrapped) * lh + max(0, len(wrapped) - 1) * sp
        if block_h <= inner_h:
            font = candidate
            lines = wrapped
            spacing = sp
            line_h = lh
            break
    block_h = len(lines) * line_h + max(0, len(lines) - 1) * spacing
    y = y1 + BOX_INSET + max(0, (inner_h - block_h) / 2)
    for line in lines:
        w = draw.textlength(line, font=font)
        x = x1 + BOX_INSET + max(0, (inner_w - w) / 2)
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h + spacing


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
