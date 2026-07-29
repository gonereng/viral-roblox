"""Tests for story loading/splitting."""

from roblox_viral.story import (
    join_for_tts,
    normalize_text,
    resolve_story,
    resolve_story_sentences,
    split_sentences,
)


def test_split_one_sentence_per_line():
    text = "Hello world.\nHow are you?\n\nFine!\n"
    assert split_sentences(text) == ["Hello world.", "How are you?", "Fine!"]


def test_normalize_collapses_spaces():
    assert normalize_text("  Hello   world.  ") == "Hello world."


def test_resolve_story_sentences_and_join():
    sentences = resolve_story_sentences(
        story_text="I love Roblox.\nThen everything went wrong."
    )
    assert sentences == ["I love Roblox.", "Then everything went wrong."]
    assert join_for_tts(sentences) == "I love Roblox. Then everything went wrong."
    assert "Roblox" in resolve_story(story_text="I love Roblox.")


def test_resolve_story_empty_raises():
    try:
        resolve_story_sentences(story_text="   \n  \n")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "empty" in str(exc).lower()
