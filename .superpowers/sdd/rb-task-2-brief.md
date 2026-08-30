### Task 2: Jobs dual render + `output_name_b`

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Test: `tests/web/test_jobs.py`

**Consumes:** `split_reddit_story`  
**Produces:** `JobRecord.output_name_b: str | None = None`; create validates Part A only; `run_job` renders B when present

- [ ] **Step 1: Write failing job tests**

```python
def test_create_reddit_validates_hook_on_part_a_only(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    # ensure videos exist for reddit (reuse existing reddit test setup)
    ...
    mgr = JobManager()
    story = "Good Hook - Title\nBody A.\nBREAK\nNo dash needed here.\nMore B.\n"
    job = mgr.create(s, "", story, "en-US-EmmaNeural", mode="reddit")
    assert job.mode == "reddit"


def test_create_reddit_rejects_bad_hook_even_with_break(tmp_path, monkeypatch):
    ...
    with pytest.raises(ValueError, match="hook|-" ):  # match existing HOOK_ERROR
        mgr.create(s, "", "Bad first line\nBREAK\nFine B.\n", "en-US-EmmaNeural", mode="reddit")


def test_run_job_reddit_break_writes_two_outputs(tmp_path, monkeypatch):
    """Part A gets card path into render; Part B render has title_card_path=None."""
    ...
    seen = {"renders": []}

    def fake_synthesize(...): ...
    def fake_write_ass(...): ...
    def fake_render_video(**kwargs):
        seen["renders"].append(dict(kwargs))
        Path(kwargs["output_path"]).write_bytes(b"mp4")
    # mock reddit plan/build/card/cover like existing reddit tests

    story = "Hook - One\nSecond A.\nBREAK\nFirst B sentence.\nSecond B.\n"
    job = mgr.create(s, "", story, "en-US-EmmaNeural", mode="reddit")
    mgr.run_job(s, job.id)
    rec = mgr.get(job.id, s)
    assert rec.status == "done"
    assert rec.output_name and rec.output_name.endswith(".mp4")
    assert rec.output_name_b == f"{Path(rec.output_name).stem}-b.mp4"
    assert len(seen["renders"]) == 2
    assert seen["renders"][0]["title_card_path"] is not None
    assert seen["renders"][1]["title_card_path"] is None
    assert (s.outputs_dir / rec.output_name).is_file()
    assert (s.outputs_dir / rec.output_name_b).is_file()


def test_run_job_reddit_without_break_single_output(tmp_path, monkeypatch):
    ...
    # one render; output_name_b is None
```

Mirror existing `test_run_job_reddit_*` helpers for video pool / card mocks. Hook story first line must include ` - ` per `split_hook`.

- [ ] **Step 2: Run — expect fail**

```bash
pytest tests/web/test_jobs.py::test_run_job_reddit_break_writes_two_outputs -v
```

- [ ] **Step 3: Implement jobs**

1. Add `output_name_b: str | None = None` to `JobRecord`; hydrate in `_load` / persist via `asdict`.

2. In `create`, for `mode == "reddit"`:
```python
from roblox_viral.reddit_break import split_reddit_story

part_a, _part_b = split_reddit_story(story)
sentences = split_sentences(part_a)
if not sentences:
    raise ValueError("Story is empty")
split_hook(sentences[0])
# still store full `story` in _stories[job_id]
```
For non-reddit, keep `split_sentences(story)` as today (no BREAK split).

3. Refactor `run_job` body into a private method that renders one story string, e.g.:

```python
def _render_story_part(
    self,
    settings: Settings,
    record: JobRecord,
    *,
    story: str,
    job_dir: Path,
    output_path: Path,
    work_suffix: str,  # "" or "_b"
    with_reddit_card: bool,
) -> tuple[str | None, str | None]:
    """
    Returns (title_card_download_name, None) for reddit+card; else (None, None).
    work_suffix distinguishes narration_b.mp3, captions_b.ass, reddit_bg_b.mp4, render_1x_b.mp4.
    with_reddit_card False → no reddit/x card (Part B).
    Single/picture paths unchanged when called once with full story.
    """
```

Move existing synthesize → caption → card → render → tempo logic into this helper. For Part B, `with_reddit_card=False` skips reddit card/cover (and does not apply single x_card either — Part B is reddit-only).

4. `run_job` orchestration:
```python
story = self._stories[job_id]
if record.mode == "reddit":
    part_a, part_b = split_reddit_story(story)
else:
    part_a, part_b = story, None

output_name = make_output_name(record.source_name or "reddit")
output_path = settings.outputs_dir / output_name
card_name, _ = self._render_story_part(
    settings, record,
    story=part_a,
    job_dir=job_dir,
    output_path=output_path,
    work_suffix="",
    with_reddit_card=(record.mode == "reddit"),
)
# For mode single, with_reddit_card False but existing x_card logic must still run —
# better flag: with_title_card: bool | use mode checks inside helper identical to today for first call.
```

**Important:** Extract carefully so **Single** still gets X card and **Picture** unchanged. Prefer:

```python
include_title_card: bool  # True for normal single/reddit first pass; False for Part B
```

Inside helper: if `include_title_card` and mode reddit → reddit card; elif `include_title_card` and mode single → x card; else no card.

```python
record.output_name = output_name
if record.mode == "reddit" and card_name:
    record.title_card_name = card_name

if part_b is not None:
    output_name_b = f"{Path(output_name).stem}-b.mp4"
    self._render_story_part(
        ...,
        story=part_b,
        output_path=settings.outputs_dir / output_name_b,
        work_suffix="_b",
        include_title_card=False,
    )
    record.output_name_b = output_name_b
else:
    record.output_name_b = None

self._set_status(..., "done")
```

Stay on `"rendering"` (and synthesizing/captioning as today per part — OK to flip synthesizing→captioning→rendering twice).

- [ ] **Step 4: Run job tests + full suite subset**

```bash
pytest tests/web/test_jobs.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/jobs.py tests/web/test_jobs.py
git commit -m "feat(jobs): Reddit BREAK dual render on one job"
```

---

