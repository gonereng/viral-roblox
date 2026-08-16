### Task 4: JobManager `single` / `reddit`

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `tests/web/test_jobs.py`

**Interfaces:**
- Consumes: `plan_reddit_clips`, `build_reddit_background`, `list_videos`, `probe_duration_seconds`, `resolve_source`
- Produces:
  - `normalize_mode(mode: str) -> str` — `roblox`→`single`; validate ∈ {single,picture,reddit}
  - `create(..., mode="single")`:
    - `single`: `resolve_source` (not `resolve_roblox_media`); require non-empty source_name
    - `picture`: unchanged
    - `reddit`: `source_name` may be `""`; require `list_videos(settings)` non-empty; store `source_name=""` or `"reddit"`
  - `run_job`:
    - `single` / ephemeral roblox-like: existing render_video + overlay
    - `reddit`: probe TTS duration after synth (or probe narration file); plan clips with durations; `build_reddit_background` → `job_dir/reddit_bg.mp4`; `render_video` that path + overlay + video_speed
  - Disk hydrate: `normalize_mode(data.get("mode") or "single")`

Update all tests that use `mode="roblox"` → `"single"`.

- [ ] **Step 1: Failing tests**

```python
def test_create_single_rejects_missing_source(...): ...
def test_create_reddit_requires_videos_pool(...): ...
def test_create_reddit_ok_with_videos(...): ...
def test_hydrate_roblox_mode_as_single(...): ...
def test_run_reddit_builds_background_and_renders(...):
    # monkeypatch plan, build_reddit_background, render_video, TTS
    # assert build called; render_video video_path == reddit_bg
```

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat(web): job modes single and reddit with concat background`

---

