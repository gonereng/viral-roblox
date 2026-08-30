# Review package RB Task 1
BASE: ea3da85912248c796d6bed278d38ca317980a2d9
HEAD: 3e5b9c6549877c8d64f4990dfff3ea7818433bfd

## Commits

3e5b9c6 feat: split Reddit stories on BREAK line

## Diff stat

 src/roblox_viral/reddit_break.py | 27 ++++++++++++++++++++++
 tests/test_reddit_break.py       | 48 ++++++++++++++++++++++++++++++++++++++++
 2 files changed, 75 insertions(+)

## Full diff

diff --git a/src/roblox_viral/reddit_break.py b/src/roblox_viral/reddit_break.py
new file mode 100644
index 0000000..7d0de79
--- /dev/null
+++ b/src/roblox_viral/reddit_break.py
@@ -0,0 +1,27 @@
+from __future__ import annotations
+
+BREAK_TOKEN = "BREAK"
+
+
+def split_reddit_story(story: str) -> tuple[str, str | None]:
+    """
+    Split on a line that is exactly 'BREAK' after strip.
+    Returns (part_a, part_b_or_None).
+    If no BREAK line, or text after BREAK is empty/whitespace-only, part_b is None.
+    Part A is always the text before the first BREAK line (may be empty string).
+    """
+    text = story if story is not None else ""
+    lines = text.splitlines(keepends=True)
+    # Also handle string without trailing newline consistently via splitlines
+    idx = None
+    for i, line in enumerate(lines):
+        if line.strip() == BREAK_TOKEN:
+            idx = i
+            break
+    if idx is None:
+        return text, None
+    before = "".join(lines[:idx])
+    after = "".join(lines[idx + 1 :])
+    if not after.strip():
+        return before, None
+    return before, after
diff --git a/tests/test_reddit_break.py b/tests/test_reddit_break.py
new file mode 100644
index 0000000..3dea83f
--- /dev/null
+++ b/tests/test_reddit_break.py
@@ -0,0 +1,48 @@
+from roblox_viral.reddit_break import split_reddit_story
+
+
+def test_no_break_returns_full_story():
+    story = "Hook - line\nSecond sentence.\n"
+    a, b = split_reddit_story(story)
+    assert a == story
+    assert b is None
+
+
+def test_break_splits_parts():
+    story = "Hook - top\nMore A.\nBREAK\nPart B starts.\nMore B.\n"
+    a, b = split_reddit_story(story)
+    assert "BREAK" not in a
+    assert "BREAK" not in (b or "")
+    assert a.strip().startswith("Hook")
+    assert "More A." in a
+    assert b is not None
+    assert "Part B starts." in b
+    assert "More B." in b
+
+
+def test_break_empty_after_means_no_b():
+    story = "Hook - only\n\nBREAK\n\n"
+    a, b = split_reddit_story(story)
+    assert "Hook" in a
+    assert b is None
+
+
+def test_break_must_be_own_line_exact():
+    # Word inside a sentence is NOT a split
+    story = "Do not BREAK mid line\nNext.\n"
+    a, b = split_reddit_story(story)
+    assert b is None
+    assert "Do not BREAK mid line" in a
+
+
+def test_break_case_sensitive():
+    story = "Hook - a\nbreak\nPart B.\n"
+    a, b = split_reddit_story(story)
+    assert b is None  # lowercase 'break' is not the token
+
+
+def test_break_with_surrounding_spaces_on_line():
+    story = "Hook - a\n  BREAK  \nAfter.\n"
+    a, b = split_reddit_story(story)
+    assert b is not None
+    assert "After." in b
