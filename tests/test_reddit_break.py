from roblox_viral.reddit_break import split_reddit_story


def test_no_break_returns_full_story():
    story = "Hook - line\nSecond sentence.\n"
    a, b = split_reddit_story(story)
    assert a == story
    assert b is None


def test_break_splits_parts():
    story = "Hook - top\nMore A.\nBREAK\nPart B starts.\nMore B.\n"
    a, b = split_reddit_story(story)
    assert "BREAK" not in a
    assert "BREAK" not in (b or "")
    assert a.strip().startswith("Hook")
    assert "More A." in a
    assert b is not None
    assert "Part B starts." in b
    assert "More B." in b


def test_break_empty_after_means_no_b():
    story = "Hook - only\n\nBREAK\n\n"
    a, b = split_reddit_story(story)
    assert "Hook" in a
    assert b is None


def test_break_must_be_own_line_exact():
    # Word inside a sentence is NOT a split
    story = "Do not BREAK mid line\nNext.\n"
    a, b = split_reddit_story(story)
    assert b is None
    assert "Do not BREAK mid line" in a


def test_break_case_sensitive():
    story = "Hook - a\nbreak\nPart B.\n"
    a, b = split_reddit_story(story)
    assert b is None  # lowercase 'break' is not the token


def test_break_with_surrounding_spaces_on_line():
    story = "Hook - a\n  BREAK  \nAfter.\n"
    a, b = split_reddit_story(story)
    assert b is not None
    assert "After." in b
