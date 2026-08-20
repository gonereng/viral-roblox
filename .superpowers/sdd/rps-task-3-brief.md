### Task 3: Wire Reddit `run_job` to sentence planner

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`

**Interfaces:**
- Consumes: `sentence_durations_s`, `plan_reddit_sentence_clips` from Task 1

- [ ] **Step 1: Update failing job test**

Replace `test_run_reddit_scales_plan_target_by_video_speed` with sentence-based assertion:

```python
def test_run_reddit_plans_by_sentence_durations(tmp_path, monkeypatch):
    # ... fakes like existing reddit run tests ...
    seen = {}

    def fake_plan(paths, sentence_durations_s, *, video_speed, durations):
        seen["plan"] = (paths, sentence_durations_s, video_speed, durations)
        return ["planned-segment"]

    monkeypatch.setattr(
        jobs_module, "plan_reddit_sentence_clips", fake_plan, raising=False
    )
    # fake synthesize returns words spanning 2 sentences with known timings
    # ...
    job = mgr.create(..., mode="reddit", video_speed=200)
    mgr.run_job(s, job.id)
    _, sent_durs, speed, _ = seen["plan"]
    assert len(sent_durs) == 2  # match story lines
    assert speed == 200
```

Remove or update any test still patching `plan_reddit_clips` for Reddit success path to patch `plan_reddit_sentence_clips` instead.

- [ ] **Step 2: Run RED**

Run: `pytest tests/web/test_jobs.py::test_run_reddit_plans_by_sentence_durations -v`

Expected: FAIL

- [ ] **Step 3: Implement `jobs.py` reddit block**

Imports:

```python
from roblox_viral.reddit_clips import (
    plan_reddit_clips,
    plan_reddit_sentence_clips,
    sentence_durations_s,
)
```

Replace reddit planning block:

```python
                sent_durations = sentence_durations_s(sentences, words)
                segments = plan_reddit_sentence_clips(
                    videos,
                    sent_durations,
                    video_speed=record.video_speed,
                    durations=durations,
                )
```

Remove `narration_duration` / `plan_target` / `plan_reddit_clips` from Reddit branch.

- [ ] **Step 4: Run GREEN**

Run: `pytest tests/web/test_jobs.py -k reddit -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/jobs.py tests/web/test_jobs.py
git commit -m "feat(web): Reddit background one clip per sentence"
```

---

