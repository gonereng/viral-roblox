"""Render a Reddit-style title card and calculate its narration duration."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from roblox_viral.captions import partition_words_by_sentences
from roblox_viral.voice import WordTiming

DEFAULT_REDDIT_USERNAME = "Resident_Vehicle2780"
CARD_WIDTH = 972
CARD_BG = (26, 26, 27, 255)

_PADDING = 48
_AVATAR_SIZE = 80
_HEADER_HEIGHT = 80
_TITLE_GAP = 36
_BOTTOM_PADDING = 56
_TITLE_SPACING = 16


def first_sentence_end_s(
    sentences: list[str],
    words: list[WordTiming],
    *,
    fallback_s: float = 2.0,
) -> float:
    """Return the first sentence's end time in seconds."""
    groups = partition_words_by_sentences(sentences, words)
    if not groups or not groups[0]:
        return fallback_s
    return groups[0][-1].end_ms / 1000.0


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


def _load_avatar(path: Path) -> Image.Image:
    with Image.open(path) as source:
        avatar = source.convert("RGBA").resize(
            (_AVATAR_SIZE, _AVATAR_SIZE), Image.Resampling.LANCZOS
        )
    mask = Image.new("L", (_AVATAR_SIZE, _AVATAR_SIZE), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, _AVATAR_SIZE - 1, _AVATAR_SIZE - 1), fill=255)
    avatar.putalpha(mask)
    return avatar


def render_reddit_card(
    title: str,
    output_path: Path | str,
    *,
    username: str = DEFAULT_REDDIT_USERNAME,
    avatar_path: Path | str | None = None,
) -> Path:
    """Write a Reddit-style RGBA PNG and return its path."""
    avatar_file = (
        Path(avatar_path)
        if avatar_path is not None
        else Path(__file__).parent / "assets" / "reddit_avatar.png"
    )
    avatar = _load_avatar(avatar_file)

    username_font = _font(38, bold=True)
    meta_font = _font(36)
    title_font = _font(68, bold=True)
    lines = _wrap_text(title, title_font, CARD_WIDTH - 2 * _PADDING)
    title_bbox = title_font.getbbox("Ag")
    line_height = title_bbox[3] - title_bbox[1]
    title_height = max(line_height, len(lines) * line_height + (len(lines) - 1) * _TITLE_SPACING)
    card_height = (
        _PADDING + _HEADER_HEIGHT + _TITLE_GAP + title_height + _BOTTOM_PADDING
    )

    image = Image.new("RGBA", (CARD_WIDTH, card_height), CARD_BG)
    draw = ImageDraw.Draw(image)
    image.alpha_composite(avatar, (_PADDING, _PADDING))

    header_x = _PADDING + _AVATAR_SIZE + 24
    header_y = _PADDING + 18
    draw.text((header_x, header_y), username, font=username_font, fill="white")
    username_width = draw.textlength(username, font=username_font)
    draw.text(
        (header_x + username_width + 20, header_y + 2),
        "3d",
        font=meta_font,
        fill=(129, 131, 132, 255),
    )

    menu_x = CARD_WIDTH - _PADDING - 8
    menu_y = _PADDING + _HEADER_HEIGHT // 2
    for offset in (-14, 0, 14):
        draw.ellipse(
            (menu_x - 4, menu_y + offset - 4, menu_x + 4, menu_y + offset + 4),
            fill=(215, 218, 220, 255),
        )

    title_y = _PADDING + _HEADER_HEIGHT + _TITLE_GAP
    draw.multiline_text(
        (_PADDING, title_y),
        "\n".join(lines),
        font=title_font,
        fill="white",
        spacing=_TITLE_SPACING,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="PNG")
    return out
