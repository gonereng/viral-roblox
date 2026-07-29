"""ASS karaoke caption generation from word timings."""

from __future__ import annotations

from pathlib import Path

from roblox_viral.voice import WordTiming

# ASS colors are &HAABBGGRR
YELLOW = "00FFFF"  # gold/yellow in BGR


def expected_word_count(sentence: str) -> int:
    """How many TTS words a sentence should consume."""
    return len(sentence.split())


def partition_words_by_sentences(
    sentences: list[str], words: list[WordTiming]
) -> list[list[WordTiming]]:
    """
    Assign flat TTS word timings to story sentences (one sentence per line).

    Consumes words in order using each sentence's whitespace token count.
    """
    groups: list[list[WordTiming]] = []
    cursor = 0
    for sentence in sentences:
        n = expected_word_count(sentence)
        if n == 0:
            groups.append([])
            continue
        if cursor + n > len(words):
            raise ValueError(
                f"TTS word count mismatch: need {n} words for sentence "
                f"{sentence!r}, but only {len(words) - cursor} remain "
                f"({len(words)} total words for {len(sentences)} sentences)"
            )
        groups.append(words[cursor : cursor + n])
        cursor += n

    if cursor < len(words):
        if groups:
            groups[-1] = groups[-1] + words[cursor:]
        else:
            groups.append(words[cursor:])
    return groups


def _ass_time(ms: int) -> str:
    """Format milliseconds as ASS H:MM:SS.cs."""
    if ms < 0:
        ms = 0
    total_cs = ms // 10
    hours = total_cs // 360_000
    minutes = (total_cs % 360_000) // 6_000
    seconds = (total_cs % 6_000) // 100
    centiseconds = total_cs % 100
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _escape_ass(text: str) -> str:
    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", r"\N")
    )


def _styled_word(word: WordTiming) -> str:
    """Single on-screen word, highlighted yellow."""
    return rf"{{\c&H{YELLOW}&}}{_escape_ass(word.text)}"


def build_ass(
    words: list[WordTiming],
    *,
    sentences: list[str] | None = None,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    font_name: str = "Arial Black",
    font_size: int = 96,
) -> str:
    """
    Build ASS captions: one word on screen at a time.

    When `sentences` is provided (one sentence per line), each word only appears
    during its sentence window — never before that sentence starts, and the
    last word clears when the next sentence starts.
    """
    header = f"""[Script Info]
Title: Roblox Viral Captions
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00{YELLOW},&H00{YELLOW},&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    if sentences is not None:
        sentence_groups = partition_words_by_sentences(sentences, words)
    else:
        sentence_groups = [words]

    events: list[str] = []
    for si, sentence_words in enumerate(sentence_groups):
        if not sentence_words:
            continue

        if si + 1 < len(sentence_groups) and sentence_groups[si + 1]:
            sentence_end = sentence_groups[si + 1][0].start_ms
        else:
            sentence_end = sentence_words[-1].end_ms

        for i, word in enumerate(sentence_words):
            start = word.start_ms
            if i + 1 < len(sentence_words):
                end = sentence_words[i + 1].start_ms
            else:
                end = sentence_end

            end = min(end, sentence_end)
            if end <= start:
                end = start + 50

            text = _styled_word(word)
            events.append(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}"
            )

    return header + "\n".join(events) + "\n"


def write_ass(
    words: list[WordTiming],
    path: Path | str,
    *,
    sentences: list[str] | None = None,
    **kwargs,
) -> Path:
    """Write ASS captions to path; return the path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_ass(words, sentences=sentences, **kwargs), encoding="utf-8")
    return out
