### Task 2: Reddit jobs use hook cover instead of 2× screenshot

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`

**Interfaces:**
- Consumes: `split_hook`, `render_hook_cover` from Task 1
- Produces: Reddit `create` calls `split_hook(sentences[0])`; `run_job` writes cover via `render_hook_cover` to `outputs/{stem}-card.png`; overlay still `render_reddit_card(..., scale=1.0)` only (no second call at scale 2.0)

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_jobs.py`:

```python
def test_create_reddit_rejects_hook_without_dash(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.videos_dir / "one.mp4").write_bytes(b"vid")
    mgr = JobManager()
    with pytest.raises(ValueError, match="phrase - phrase"):
        mgr.create(s, "", "Hello world.\nSecond.\n", "en-US-EmmaNeural", mode="reddit")
```

In `test_run_reddit_passes_title_card_and_no_greenscreen`:

- Change `story` to `"First sentence here - Second hook.\nSecond line.\n"`
- After fakes, add:

```python
    def fake_render_hook_cover(top, bottom, output_path, *, template_path=None):
        seen.setdefault("covers", []).append((top, bottom, Path(output_path)))
        Path(output_path).write_bytes(b"hook-png")

    monkeypatch.setattr(
        jobs_module, "render_hook_cover", fake_render_hook_cover, raising=False
    )
```

- Change assertions: `seen["cards"]` has **length 1**, scale `1.0`, title `"First sentence here - Second hook."`
- Assert `seen["covers"][0][0] == "First sentence here"`
- Assert `seen["covers"][0][1] == "Second hook."`
- Assert `str(seen["covers"][0][2]).endswith("-card.png")`
- Remove `assert seen["cards"][1][2] == 2.0`

In `test_run_reddit_copies_title_card_to_outputs`:

- Story: `"One line only here - Bottom phrase.\n"`
- Replace reliance on `fake_render_reddit_card` writing the **outputs** file. Keep overlay fake; add:

```python
    def fake_render_hook_cover(top, bottom, output_path, *, template_path=None):
        Path(output_path).write_bytes(b"hook-png")

    monkeypatch.setattr(
        jobs_module, "render_hook_cover", fake_render_hook_cover, raising=False
    )
```

- Assert `card_path.read_bytes() == b"hook-png"` (not `b"png-card"`)

Update **every** `mgr.create(..., mode="reddit")` story in this file so the first line has exactly one `-` (existing tests will 400 otherwise), e.g. `"Hello - world.\n"`, `"One line only - here.\n"`. Search `mode="reddit"` and fix each story.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/web/test_jobs.py -k reddit -v`

Expected: new reject test FAIL (create succeeds) and/or 2× card assertions still expecting two `render_reddit_card` calls.

- [ ] **Step 3: Wire jobs**

In `src/roblox_viral/web/jobs.py`:

1. Import:

```python
from roblox_viral.hook_cover import render_hook_cover, split_hook
```

2. In `create`, after `if not sentences: raise ValueError("Story is empty")`:

```python
        if mode == "reddit":
            split_hook(sentences[0])
```

3. Replace the block that calls `render_reddit_card` twice. Keep 1× overlay; write cover with `render_hook_cover`:

```python
            if record.mode == "reddit":
                title_card_until_s = first_sentence_end_s(sentences, words)
                title_card_path = job_dir / "reddit_card.png"
                render_reddit_card(sentences[0], title_card_path, scale=1.0)
                top, bottom = split_hook(sentences[0])
                title_card_download_name = f"{Path(output_name).stem}-card.png"
                settings.outputs_dir.mkdir(parents=True, exist_ok=True)
                render_hook_cover(
                    top,
                    bottom,
                    settings.outputs_dir / title_card_download_name,
                )
```

Do not call `render_reddit_card(..., scale=2.0)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/web/test_jobs.py tests/test_hook_cover.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/jobs.py tests/web/test_jobs.py
git commit -m "feat(web): Reddit jobs write hook cover instead of 2x screenshot"
```

---

