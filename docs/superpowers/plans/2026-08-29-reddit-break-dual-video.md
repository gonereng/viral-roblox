# Reddit BREAK Dual Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reddit jobs optionally split on a `BREAK` line into two sequential videos on one job (Part A with card/cover; Part B without); expose `download-b` and UI second download.

**Architecture:** `split_reddit_story` parses optional `BREAK`; create validates hook on Part A only; `run_job` runs the existing pipeline twice when Part B exists (separate work files, `-b` output name); status/API/UI surface `output_name_b`.

**Tech Stack:** Existing FastAPI job runner, TTS/render stack, pytest

## Global Constraints

- Reddit mode only
- Split: own line exact `BREAK` (trim)
- No BREAK or empty Part B → single Part A
- One job, sequential passes; `download` = A, `download-b` = B (404 if absent), `cover` = A only
- Part B: no card/cover, no `split_hook`
- Spec: `docs/superpowers/specs/2026-08-29-reddit-break-dual-video-design.md`

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/reddit_break.py` | `split_reddit_story` helper |
| `src/roblox_viral/web/jobs.py` | Validate Part A; dual `run_job`; `output_name_b` |
| `src/roblox_viral/web/api_v1.py` | `GET .../download-b` |
| `src/roblox_viral/web/app.py` | Job status already `asdict` — ensure field present |
| `src/roblox_viral/web/templates/generate.html` | Hint + second download link markup |
| `src/roblox_viral/web/static/app.js` | Show Part B download when present |
| `README.md` | Document BREAK + download-b |
| `tests/test_reddit_break.py` | Split helper unit tests |
| `tests/web/test_jobs.py` | Dual / single Reddit job tests |
| `tests/web/test_api_v1.py` | download-b + status field |

---

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

### Task 3: API `download-b` + Generate UI + README

**Files:**
- Modify: `src/roblox_viral/web/api_v1.py`, `generate.html`, `app.js`, `README.md`
- Test: `tests/web/test_api_v1.py`, optionally `tests/web/test_api.py` for hint text

**Consumes:** `output_name_b` on JobRecord

- [ ] **Step 1: Failing API tests**

```python
def test_download_b_404_when_no_part_b(tmp_path, monkeypatch):
    # create+fake done job without output_name_b
    ...
    r = client.get(f"/api/v1/videos/{job_id}/download-b", headers=...)
    assert r.status_code == 404


def test_download_b_returns_part_b_file(tmp_path, monkeypatch):
    # persist record status=done, output_name=..., output_name_b=...-b.mp4
    # write both files under outputs
    r = client.get(f"/api/v1/videos/{job_id}/download-b", headers=...)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("video/")


def test_get_video_includes_output_name_b(tmp_path, monkeypatch):
    ...
    assert "output_name_b" in st.json()
```

- [ ] **Step 2: Implement `download-b`**

Clone `download_video` but use `record.output_name_b`; if missing → 404 `"Part B not found"`. Same 422/409 rules as primary download when error/not ready.

`get_video` already returns `asdict(record)` — field appears automatically.

- [ ] **Step 3: UI**

`generate.html`:
- Update `#reddit-hook-hint` to mention optional line `BREAK` then a second story without screenshot.
- Add `<a id="download-b" hidden>Download part B</a>` near existing download.

`app.js` `showResult(outputName, titleCardName, outputNameB)`:
- If `outputNameB`, show `#download-b` with `/media/outputs/...`; else hide.
- Call site: `showResult(job.output_name, job.title_card_name || null, job.output_name_b || null)`.

- [ ] **Step 4: README**

Document Reddit `BREAK` line; n8n: `GET /api/v1/videos/{id}/download-b`.

- [ ] **Step 5: Tests + full suite**

```bash
pytest tests/web/test_api_v1.py tests/web/test_api.py -q
pytest -q
```

- [ ] **Step 6: Commit**

```bash
git add src/roblox_viral/web/api_v1.py src/roblox_viral/web/templates/generate.html src/roblox_viral/web/static/app.js README.md tests/web/test_api_v1.py tests/web/test_api.py
git commit -m "feat(api): download-b and Generate UI for Reddit Part B"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| `split_reddit_story` / exact BREAK | 1 |
| Optional empty B | 1 |
| Create hook on A only | 2 |
| Dual sequential render | 2 |
| `output_name_b` / `-b.mp4` | 2 |
| `download` / `download-b` / `cover` | 3 |
| Generate UI + hint | 3 |
| README | 3 |

## Self-review

- Helper extraction must preserve Single X-card and Picture paths on the single-pass call
- Part B never calls `split_hook` / cover
- Non-Reddit stories are not split
