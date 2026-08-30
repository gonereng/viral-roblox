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
