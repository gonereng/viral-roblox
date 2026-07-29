"""Story loading and sentence splitting (one sentence per line)."""

from __future__ import annotations

import re
from pathlib import Path


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_line(text: str) -> str:
    """Collapse whitespace within a single line and strip."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_text(text: str) -> str:
    """Normalize a block of text to a single spaced string (TTS join helper)."""
    return normalize_line(text)


def split_sentences(text: str) -> list[str]:
    """Split story into sentences: one non-empty line per sentence."""
    if not text or not text.strip():
        return []
    return [normalize_line(line) for line in text.splitlines() if normalize_line(line)]


def load_story_lines(path: Path | str) -> list[str]:
    """Load story file as one sentence per line."""
    content = Path(path).read_text(encoding="utf-8")
    return split_sentences(content)


def resolve_story_sentences(
    *, story_path: Path | str | None = None, story_text: str | None = None
) -> list[str]:
    """Resolve story into sentences. Raises ValueError if empty/missing."""
    if story_path is not None and story_text is not None:
        raise ValueError("Provide only one of --story or --story-text")
    if story_path is None and story_text is None:
        raise ValueError("Provide --story or --story-text")

    if story_path is not None:
        sentences = load_story_lines(story_path)
    else:
        sentences = split_sentences(story_text or "")

    if not sentences:
        raise ValueError("Story is empty")
    return sentences


def join_for_tts(sentences: list[str]) -> str:
    """Join sentences for a single TTS pass (space-separated)."""
    return " ".join(sentences)


# Back-compat alias used by older tests/callers
def resolve_story(*, story_path: Path | str | None = None, story_text: str | None = None) -> str:
    return join_for_tts(resolve_story_sentences(story_path=story_path, story_text=story_text))
