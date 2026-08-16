### Task 2: `first_sentence_end_s` + `render_reddit_card`

**Files:**
- Create: `src/roblox_viral/reddit_card.py`
- Create: `tests/test_reddit_card.py`

**Interfaces:**
- Produces:

```python
DEFAULT_REDDIT_USERNAME = "Resident_Vehicle2780"
CARD_WIDTH = 972  # ~90% of 1080
CARD_BG = (26, 26, 27, 255)  # #1A1A1B

def first_sentence_end_s(
    sentences: list[str],
    words: list[WordTiming],
    *,
    fallback_s: float = 2.0,
) -> float:
    """Return end time (seconds) of first sentence; fallback if no words."""

def render_reddit_card(
    title: str,
    output_path: Path | str,
    *,
    username: str = DEFAULT_REDDIT_USERNAME,
    avatar_path: Path | str | None = None,
) -> Path:
    """Write RGBA PNG; return path. Width CARD_WIDTH; height from content."""
```

`first_sentence_end_s` implementation:

```python
groups = partition_words_by_sentences(sentences, words)
if not groups or not groups[0]:
    return fallback_s
return groups[0][-1].end_ms / 1000.0
```

Card layout (Pillow):
- Load avatar (default packaged); resize to ~40px circle (mask)
- Header row: avatar | username (white) | "3d" (gray) | kebab menu right-aligned
- Title: bold white, wrap to card inner width, line spacing
- Padding ~24px; dark fill rectangle

- [ ] **Step 1: Failing tests**

```python
from roblox_viral.voice import WordTiming
from roblox_viral.reddit_card import first_sentence_end_s, render_reddit_card


def test_first_sentence_end_s():
    sentences = ["Hello world.", "Second line."]
    words = [
        WordTiming("Hello", 0, 200),
        WordTiming("world.", 200, 500),
        WordTiming("Second", 500, 800),
        WordTiming("line.", 800, 1000),
    ]
    assert abs(first_sentence_end_s(sentences, words) - 0.5) < 1e-6


def test_first_sentence_end_s_fallback_empty_words():
    assert first_sentence_end_s(["Hi."], []) == 2.0


def test_render_reddit_card_writes_png(tmp_path):
    out = tmp_path / "card.png"
    path = render_reddit_card("Company copied my code after refusing to pay.", out)
    assert path.is_file()
    from PIL import Image
    im = Image.open(path)
    assert im.size[0] == 972
    assert im.size[1] > 80
    assert im.mode in ("RGBA", "RGB")
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_reddit_card.py -v`

- [ ] **Step 3: Implement `reddit_card.py`**

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit** `feat: generate Reddit title card PNG with Pillow`

---

