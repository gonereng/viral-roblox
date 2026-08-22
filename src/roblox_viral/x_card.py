"""Render an X / Twitter-style hook card PNG for Single-mode videos."""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEFAULT_X_DISPLAY_NAME = "jacques.guddebuer"
DEFAULT_X_HANDLE = "@jacques.guddebuer"
CARD_WIDTH = 972  # ~90% of 1080
CARD_BG = (0, 0, 0, 255)

_PADDING = 20
_AVATAR_SIZE = 48
_HEADER_GAP = 12
_CHECK_SIZE = 18
_BODY_FONT_SIZE = 28
_DISPLAY_NAME_FONT_SIZE = 20
_HANDLE_FONT_SIZE = 16
_BODY_SPACING = 6
_MAX_BODY_LINES = 6
_FOOTER_GAP = 16
_FOOTER_ICON_SIZE = 18
_FOOTER_FONT_SIZE = 14
_FOOTER_ITEM_GAP = 28
_VERIFIED_BLUE = (29, 155, 240, 255)
_HANDLE_GRAY = (113, 118, 123, 255)
_SHOW_MORE_BLUE = (29, 155, 240, 255)
_KEBAB_GRAY = (113, 118, 123, 255)


def format_engagement_count(n: int) -> str:
    """Format an integer count as plain, K, or M suffix string."""
    if n < 1000:
        return str(n)
    if n >= 1_000_000:
        value = n / 1_000_000
        formatted = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{formatted}M"
    value = n / 1000
    formatted = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{formatted}K"


def random_engagement(*, rng: random.Random | None = None) -> dict[str, int]:
    """Return random high engagement counts for replies, reposts, likes, views."""
    r = rng or random.Random()
    return {
        "replies": r.randint(1_000, 20_000),
        "reposts": r.randint(5_000, 80_000),
        "likes": r.randint(20_000, 500_000),
        "views": r.randint(100_000, 2_000_000),
    }


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        ("DejaVuSans-Bold.ttf", "arialbd.ttf")
        if bold
        else ("DejaVuSans.ttf", "arial.ttf")
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    draw = ImageDraw.Draw(Image.new("L", (1, 1)))
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if draw.textlength(candidate, font=font) <= max_width:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def _load_avatar(path: Path, size: int) -> Image.Image:
    if not path.is_file():
        raise FileNotFoundError(f"Avatar not found: {path}")
    with Image.open(path) as source:
        avatar = source.convert("RGBA").resize(
            (size, size), Image.Resampling.LANCZOS
        )
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    avatar.putalpha(mask)
    return avatar


def _draw_verified_badge(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    size: int,
) -> None:
    draw.ellipse((x, y, x + size - 1, y + size - 1), fill=_VERIFIED_BLUE)
    check_font = _font(max(8, size - 6), bold=True)
    check = "✓"
    bbox = check_font.getbbox(check)
    check_w = bbox[2] - bbox[0]
    check_h = bbox[3] - bbox[1]
    draw.text(
        (x + (size - check_w) // 2, y + (size - check_h) // 2 - 1),
        check,
        font=check_font,
        fill="white",
    )


def _draw_kebab_menu(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    dot = 3
    step = 7
    for offset in (-step, 0, step):
        draw.ellipse(
            (x - dot, y + offset - dot, x + dot, y + offset + dot),
            fill=_KEBAB_GRAY,
        )


def _draw_footer_icon(
    draw: ImageDraw.ImageDraw,
    kind: str,
    x: int,
    y: int,
    size: int,
) -> None:
    color = _HANDLE_GRAY
    if kind == "reply":
        draw.arc((x, y + 2, x + size, y + size), 200, 340, fill=color, width=2)
        draw.line((x + 4, y + size - 2, x + 2, y + size + 4), fill=color, width=2)
    elif kind == "repost":
        mid = x + size // 2
        draw.arc((x + 2, y + 4, x + size - 2, y + size - 2), 30, 210, fill=color, width=2)
        draw.polygon(
            [(mid - 4, y + 6), (mid + 4, y + 6), (mid, y)],
            fill=color,
        )
        draw.polygon(
            [(mid - 4, y + size - 6), (mid + 4, y + size - 6), (mid, y + size)],
            fill=color,
        )
    elif kind == "like":
        cx = x + size // 2
        cy = y + size // 2 + 2
        draw.ellipse((cx - 5, cy - 5, cx - 1, cy - 1), fill=color)
        draw.ellipse((cx + 1, cy - 5, cx + 5, cy - 1), fill=color)
        draw.polygon(
            [(cx - 5, cy - 1), (cx + 5, cy - 1), (cx, cy + 6)],
            fill=color,
        )
    elif kind == "views":
        base = y + size - 4
        draw.rectangle((x + 2, base - 4, x + 5, base), fill=color)
        draw.rectangle((x + 7, base - 8, x + 10, base), fill=color)
        draw.rectangle((x + 12, base - 2, x + 15, base), fill=color)


def render_x_card(
    body: str,
    output_path: Path | str,
    *,
    display_name: str = DEFAULT_X_DISPLAY_NAME,
    handle: str = DEFAULT_X_HANDLE,
    avatar_path: Path | str | None = None,
    engagement: dict[str, int] | None = None,
    rng: random.Random | None = None,
) -> Path:
    """Write an X-style dark-mode RGBA PNG and return its path."""
    counts = engagement or random_engagement(rng=rng)

    avatar_file = (
        Path(avatar_path)
        if avatar_path is not None
        else Path(__file__).parent / "assets" / "x_avatar.png"
    )
    avatar = _load_avatar(avatar_file, _AVATAR_SIZE)

    display_font = _font(_DISPLAY_NAME_FONT_SIZE, bold=True)
    handle_font = _font(_HANDLE_FONT_SIZE)
    body_font = _font(_BODY_FONT_SIZE)
    footer_font = _font(_FOOTER_FONT_SIZE)
    show_more_font = _font(_BODY_FONT_SIZE)

    text_width = CARD_WIDTH - 2 * _PADDING
    all_body_lines = _wrap_text(body, body_font, text_width)
    truncated = len(all_body_lines) > _MAX_BODY_LINES
    visible_lines = all_body_lines[:_MAX_BODY_LINES]

    body_bbox = body_font.getbbox("Ag")
    body_line_height = body_bbox[3] - body_bbox[1]
    body_height = len(visible_lines) * body_line_height + max(
        0, len(visible_lines) - 1
    ) * _BODY_SPACING
    if truncated:
        show_more_bbox = show_more_font.getbbox("Show more")
        body_height += (
            _BODY_SPACING + show_more_bbox[3] - show_more_bbox[1]
        )

    header_height = max(_AVATAR_SIZE, _DISPLAY_NAME_FONT_SIZE + _HANDLE_FONT_SIZE + 4)
    footer_height = _FOOTER_ICON_SIZE + 4
    card_height = (
        _PADDING
        + header_height
        + _FOOTER_GAP
        + body_height
        + _FOOTER_GAP
        + footer_height
        + _PADDING
    )

    image = Image.new("RGBA", (CARD_WIDTH, card_height), CARD_BG)
    draw = ImageDraw.Draw(image)
    image.alpha_composite(avatar, (_PADDING, _PADDING))

    header_x = _PADDING + _AVATAR_SIZE + _HEADER_GAP
    header_y = _PADDING
    draw.text((header_x, header_y), display_name, font=display_font, fill="white")
    name_width = draw.textlength(display_name, font=display_font)
    check_x = int(header_x + name_width + 6)
    check_y = header_y + 1
    _draw_verified_badge(draw, check_x, check_y, _CHECK_SIZE)

    handle_y = header_y + _DISPLAY_NAME_FONT_SIZE + 4
    meta_text = f"{handle} · 22h"
    draw.text((header_x, handle_y), meta_text, font=handle_font, fill=_HANDLE_GRAY)

    menu_x = CARD_WIDTH - _PADDING - 4
    menu_y = _PADDING + header_height // 2
    _draw_kebab_menu(draw, menu_x, menu_y)

    body_y = _PADDING + header_height + _FOOTER_GAP
    draw.multiline_text(
        (_PADDING, body_y),
        "\n".join(visible_lines),
        font=body_font,
        fill="white",
        spacing=_BODY_SPACING,
    )

    if truncated:
        show_more_y = body_y + len(visible_lines) * (
            body_line_height + _BODY_SPACING
        )
        draw.text(
            (_PADDING, show_more_y),
            "Show more",
            font=show_more_font,
            fill=_SHOW_MORE_BLUE,
        )

    footer_y = card_height - _PADDING - footer_height
    footer_items = [
        ("reply", format_engagement_count(counts["replies"])),
        ("repost", format_engagement_count(counts["reposts"])),
        ("like", format_engagement_count(counts["likes"])),
        ("views", format_engagement_count(counts["views"])),
    ]
    footer_x = _PADDING
    for kind, label in footer_items:
        _draw_footer_icon(draw, kind, footer_x, footer_y, _FOOTER_ICON_SIZE)
        label_x = footer_x + _FOOTER_ICON_SIZE + 6
        label_y = footer_y + (_FOOTER_ICON_SIZE - _FOOTER_FONT_SIZE) // 2
        draw.text((label_x, label_y), label, font=footer_font, fill=_HANDLE_GRAY)
        label_width = draw.textlength(label, font=footer_font)
        footer_x += _FOOTER_ICON_SIZE + 6 + label_width + _FOOTER_ITEM_GAP

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="PNG")
    return out
