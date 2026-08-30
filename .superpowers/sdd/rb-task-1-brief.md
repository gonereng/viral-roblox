### Task 1: `split_reddit_story` helper

**Files:**
- Create: `src/roblox_viral/reddit_break.py`
- Test: `tests/test_reddit_break.py`

**Produces:**
```python
def split_reddit_story(story: str) -> tuple[str, str | None]:
    """
    Split on a line that is exactly 'BREAK' after strip.
    Returns (part_a, part_b_or_None).
    If no BREAK line, or text after BREAK is empty/whitespace-only, part_b is None.
    Part A is always the text before the first BREAK line (may be empty string).
    """
```

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run — expect fail**

```bash
pytest tests/test_reddit_break.py -v
```

Expected: FAIL import

- [ ] **Step 3: Implement**

```python
# src/roblox_viral/reddit_break.py
from __future__ import annotations

BREAK_TOKEN = "BREAK"


def split_reddit_story(story: str) -> tuple[str, str | None]:
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
```

Note: if `story` has no newlines and is exactly content without BREAK, return as-is. Preserve original newlines in parts so `split_sentences` still works.

- [ ] **Step 4: Run tests — PASS**

```bash
pytest tests/test_reddit_break.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/reddit_break.py tests/test_reddit_break.py
git commit -m "feat: split Reddit stories on BREAK line"
```

---

