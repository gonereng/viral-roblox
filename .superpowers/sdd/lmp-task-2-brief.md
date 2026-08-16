### Task 2: Inline previews in Library UI + CSS + HTML smoke

**Files:**
- Modify: `src/roblox_viral/web/templates/library.html`
- Modify: `src/roblox_viral/web/static/app.css`
- Modify: `tests/web/test_library_routes.py`
- Modify: `README.md` (brief Library bullet)

**Interfaces:**
- Consumes: `/media/sources/{name}`, `/media/videos/{name}`, `/media/images/{name}` from Task 1
- Produces: each listed asset renders an inline preview element with those URLs

- [ ] **Step 1: Write failing HTML smoke test** in `tests/web/test_library_routes.py`:

```python
def test_library_page_embeds_inline_previews(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _login(client)
    settings = client.app.state.settings
    settings.sources_dir.mkdir(parents=True, exist_ok=True)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    (settings.sources_dir / "slice.mp4").write_bytes(b"s")
    (settings.videos_dir / "raw.mp4").write_bytes(b"v")
    (settings.images_dir / "pic.png").write_bytes(b"i")

    page = client.get("/library")
    assert page.status_code == 200
    assert 'preload="none"' in page.text
    assert 'src="/media/sources/slice.mp4"' in page.text
    assert 'src="/media/videos/raw.mp4"' in page.text

    images = client.get("/library?tab=images")
    assert 'src="/media/images/pic.png"' in images.text
    assert 'loading="lazy"' in images.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_library_routes.py::test_library_page_embeds_inline_previews -v`

Expected: FAIL (missing `preload="none"` / media URLs in HTML)

- [ ] **Step 3: Update `library.html` list items**

For slices (`{% for source in sources %}`), inside `<li>` after meta (before delete form):

```html
        <div class="source-preview">
          <video controls playsinline preload="none"
                 src="/media/sources/{{ source.name }}"></video>
        </div>
```

For videos:

```html
        <div class="source-preview">
          <video controls playsinline preload="none"
                 src="/media/videos/{{ video.name }}"></video>
        </div>
```

For images:

```html
        <div class="source-preview">
          <img src="/media/images/{{ image.name }}"
               alt="{{ image.name }}" loading="lazy">
        </div>
```

Keep name, size, and delete controls unchanged. Preview should sit full-width under the text row (flex-wrap already on `.source-list li`).

- [ ] **Step 4: Add CSS** to `app.css`:

```css
.source-preview {
  flex: 1 1 100%;
  max-width: 100%;
}

.source-preview video,
.source-preview img {
  display: block;
  max-width: 100%;
  max-height: 240px;
  width: auto;
  height: auto;
  object-fit: contain;
  background: var(--bg-elevated, #111);
}
```

If `--bg-elevated` is undefined in this stylesheet, use an existing token (e.g. `var(--panel)` / `var(--surface)`) or a simple `transparent` / `var(--line)` — match current theme variables in `app.css`.

- [ ] **Step 5: Run smoke test**

Run: `pytest tests/web/test_library_routes.py::test_library_page_embeds_inline_previews -v`

Expected: PASS

- [ ] **Step 6: README** — under Library / Web app, add one bullet: Library lists include inline preview (video controls with no preload; lazy images).

- [ ] **Step 7: Run full library route suite**

Run: `pytest tests/web/test_library_routes.py -v`

Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add src/roblox_viral/web/templates/library.html src/roblox_viral/web/static/app.css tests/web/test_library_routes.py README.md
git commit -m "feat(web): inline library video and image previews"
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| `/media/sources|videos|images/{name}` + login | 1 |
| resolve helpers + 400/404 | 1 |
| MIME by suffix | 1 |
| Inline `<video preload="none">` on clips + Videos | 2 |
| Inline lazy `<img>` on Images | 2 |
| CSS max-height ~240px | 2 |
| No StaticFiles mount | (constraint; not done) |
| No poster / Generate preview | (out of scope) |
| Tests: auth, 200, 404, 400, HTML smoke | 1–2 |
