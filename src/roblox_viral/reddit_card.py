"""Render a Reddit-style title card and calculate its narration duration."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from roblox_viral.captions import partition_words_by_sentences
from roblox_viral.voice import WordTiming

DEFAULT_REDDIT_USERNAME = "Resident_Vehicle2780"
CARD_WIDTH = 864  # ~80% of 1080
CARD_BG = (26, 26, 27, 255)

# 1× (overlay) base; multiply by `scale` (2.0 = download size)
_PADDING = 24
_AVATAR_SIZE = 40
_HEADER_HEIGHT = 40
_TITLE_GAP = 18
_BOTTOM_PADDING = 28
_TITLE_SPACING = 8
_USERNAME_FONT = 19
_META_FONT = 18
_TITLE_FONT = 34


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


def _load_avatar(path: Path, size: int) -> Image.Image:
    with Image.open(path) as source:
        avatar = source.convert("RGBA").resize(
            (size, size), Image.Resampling.LANCZOS
        )
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    avatar.putalpha(mask)
    return avatar


def _scaled(value: float, scale: float) -> int:
    return max(1, int(round(value * scale)))


def render_reddit_card(
    title: str,
    output_path: Path | str,
    *,
    username: str = DEFAULT_REDDIT_USERNAME,
    avatar_path: Path | str | None = None,
    scale: float = 2.0,
) -> Path:
    """Write a Reddit-style RGBA PNG and return its path.

    scale=1.0 → original overlay size; scale=2.0 → download size.
    """
    if scale <= 0:
        raise ValueError("scale must be positive")

    padding = _scaled(_PADDING, scale)
    avatar_size = _scaled(_AVATAR_SIZE, scale)
    header_height = _scaled(_HEADER_HEIGHT, scale)
    title_gap = _scaled(_TITLE_GAP, scale)
    bottom_padding = _scaled(_BOTTOM_PADDING, scale)
    title_spacing = _scaled(_TITLE_SPACING, scale)
    header_gap = _scaled(12, scale)
    header_y_off = _scaled(9, scale)
    meta_gap = _scaled(10, scale)
    meta_y_off = _scaled(1, scale)
    menu_inset = _scaled(4, scale)
    menu_dot = _scaled(2, scale)
    menu_step = _scaled(7, scale)

    avatar_file = (
        Path(avatar_path)
        if avatar_path is not None
        else Path(__file__).parent / "assets" / "reddit_avatar.png"
    )
    avatar = _load_avatar(avatar_file, avatar_size)

    username_font = _font(_scaled(_USERNAME_FONT, scale), bold=True)
    meta_font = _font(_scaled(_META_FONT, scale))
    title_font = _font(_scaled(_TITLE_FONT, scale), bold=True)
    lines = _wrap_text(title, title_font, CARD_WIDTH - 2 * padding)
    title_bbox = title_font.getbbox("Ag")
    line_height = title_bbox[3] - title_bbox[1]
    title_height = max(
        line_height,
        len(lines) * line_height + (len(lines) - 1) * title_spacing,
    )
    card_height = (
        padding + header_height + title_gap + title_height + bottom_padding
    )

    image = Image.new("RGBA", (CARD_WIDTH, card_height), CARD_BG)
    draw = ImageDraw.Draw(image)
    image.alpha_composite(avatar, (padding, padding))

    header_x = padding + avatar_size + header_gap
    header_y = padding + header_y_off
    draw.text((header_x, header_y), username, font=username_font, fill="white")
    username_width = draw.textlength(username, font=username_font)
    draw.text(
        (header_x + username_width + meta_gap, header_y + meta_y_off),
        "3d",
        font=meta_font,
        fill=(129, 131, 132, 255),
    )

    menu_x = CARD_WIDTH - padding - menu_inset
    menu_y = padding + header_height // 2
    for offset in (-menu_step, 0, menu_step):
        draw.ellipse(
            (
                menu_x - menu_dot,
                menu_y + offset - menu_dot,
                menu_x + menu_dot,
                menu_y + offset + menu_dot,
            ),
            fill=(215, 218, 220, 255),
        )

    title_y = padding + header_height + title_gap
    draw.multiline_text(
        (padding, title_y),
        "\n".join(lines),
        font=title_font,
        fill="white",
        spacing=title_spacing,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="PNG")
    return out
