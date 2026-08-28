from __future__ import annotations

BREAK_TOKEN = "BREAK"


def split_reddit_story(story: str) -> tuple[str, str | None]:
    """
    Split on a line that is exactly 'BREAK' after strip.
    Returns (part_a, part_b_or_None).
    If no BREAK line, or text after BREAK is empty/whitespace-only, part_b is None.
    Part A is always the text before the first BREAK line (may be empty string).
    """
    text = story if story is not None else ""
    lines = text.splitlines(keepends=True)
    # Also handle string without trailing newline consistently via splitlines
    idx = None
    for i, line in enumerate(lines):
        if line.strip() == BREAK_TOKEN:
            idx = i
            break
    if idx is None:
        return text, None
    before = "".join(lines[:idx])
    after = "".join(lines[idx + 1 :])
    if not after.strip():
        return before, None
    return before, after
