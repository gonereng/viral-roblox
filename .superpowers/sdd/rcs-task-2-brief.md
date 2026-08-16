### Task 2: Persist `title_card_name` + serve PNG from `/media/outputs`

**Files:**
- Modify: `src/roblox_viral/web/jobs.py`
- Modify: `src/roblox_viral/web/app.py`
- Modify: `tests/web/test_jobs.py`
- Modify: `tests/web/test_api.py`

**Interfaces:**
- Consumes: `render_reddit_card`, `make_output_name`, `media_type_for_name` (already in `library.py`)
- Produces:

```python
# JobRecord field
title_card_name: str | None = None

# On Reddit success, after output_name is known:
# title_card_name = f"{Path(output_name).stem}-card.png"
# shutil.copy2(job_dir / "reddit_card.png", settings.outputs_dir / title_card_name)
# OR render_reddit_card(..., outputs_path) then copy to job_dir — prefer:
#   render once to job_dir for overlay; copy bytes/file to outputs
```

`GET /api/jobs/{id}` already returns `asdict(record)` — new field appears automatically once on the dataclass + hydrate path.

- [ ] **Step 1: Write failing tests**

In `tests/web/test_jobs.py`, extend Reddit run test(s) (prefer updating `test_run_reddit_builds_background_and_renders` or add focused test):

```python
def test_run_reddit_copies_title_card_to_outputs(tmp_path, monkeypatch):
    # same fakes as existing reddit run test; ensure fake render_reddit_card writes PNG
    # after mgr.run_job:
    assert job.title_card_name is not None
    assert job.title_card_name.endswith("-card.png")
    card_path = s.outputs_dir / job.title_card_name
    assert card_path.is_file()
    # cold hydrate
    loaded = JobManager().get(job.id, s)
    assert loaded is not None
    assert loaded.title_card_name == job.title_card_name
```

Ensure `fake_render_reddit_card` (or the real one if already patched elsewhere) writes a file when the job path calls `render_reddit_card`. Existing title-card test already patches `render_reddit_card` — reuse that pattern and also assert copy to outputs happens in `run_job` (implementation copies after render).

In `tests/web/test_api.py`:

```python
def test_media_output_serves_png(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    settings = c.app.state.settings
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    (settings.outputs_dir / "story-card.png").write_bytes(b"png-bytes")
    r = c.get("/media/outputs/story-card.png")
    assert r.status_code == 200
    assert r.content == b"png-bytes"
    assert "image/png" in r.headers.get("content-type", "")
```

- [ ] **Step 2: Run RED**

Run:

```bash
pytest tests/web/test_jobs.py::test_run_reddit_copies_title_card_to_outputs \
       tests/web/test_api.py::test_media_output_serves_png -v
```

Expected: FAIL (`title_card_name` missing / Content-Type still video/mp4)

- [ ] **Step 3: Implement**

`JobRecord` — add `title_card_name: str | None = None`.

`create(...)` — leave default `None`.

`get` hydrate — add:

```python
title_card_name=data.get("title_card_name"),
```

In `run_job` Reddit block, after `render_reddit_card(...)` and once `output_name` is known (same place `record.output_name = output_name` is set is fine; do copy before or with that assignment):

```python
import shutil
# ...
card_out_name = f"{Path(output_name).stem}-card.png"
settings.outputs_dir.mkdir(parents=True, exist_ok=True)
shutil.copy2(title_card_path, settings.outputs_dir / card_out_name)
record.title_card_name = card_out_name
```

Only when `record.mode == "reddit"` and `title_card_path` was written. Non-Reddit: leave `None`.

`app.py` `media_output`:

```python
from roblox_viral.web.library import media_type_for_name  # if not already

return FileResponse(
    path,
    media_type=media_type_for_name(safe),
    filename=safe,
)
```

- [ ] **Step 4: Run GREEN**

Run same pytest command + `pytest tests/web/test_api.py::test_media_output_requires_auth_and_serves_file -v`

Expected: PASS (MP4 still works)

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/jobs.py src/roblox_viral/web/app.py tests/web/test_jobs.py tests/web/test_api.py
git commit -m "feat(web): persist and serve Reddit title card PNG downloads"
```

---

