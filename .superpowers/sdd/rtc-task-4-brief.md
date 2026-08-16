### Task 4: Wire Reddit `run_job`

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`

**Interfaces:**
- After TTS + ASS, when `mode == "reddit"`:
  - `T = first_sentence_end_s(sentences, words)`
  - `card_path = job_dir / "reddit_card.png"`; `render_reddit_card(sentences[0], card_path)`
  - After `build_reddit_background`, call `render_video(..., overlay_path=None, title_card_path=card_path, title_card_until_s=T, video_speed=...)`
- For `single` (and ephemeral non-picture): keep `overlay_path=settings.overlay_video_path`, no title card

- [ ] **Step 1: Failing tests**

```python
def test_run_reddit_passes_title_card_and_no_greenscreen(...):
    # monkeypatch TTS, write_ass, plan, build_reddit_background, render_video, render_reddit_card
    # assert render_video kwargs: overlay_path is None
    # title_card_path ends with reddit_card.png, title_card_until_s > 0


def test_run_single_still_uses_greenscreen(...):
    # assert overlay_path equals settings.overlay_video_path
    # title_card_path not passed / None
```

Update existing `test_run_reddit_builds_background_and_renders` expectations.

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat(web): attach Reddit title card and disable subscribe overlay`

---

