# Library Media Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve authenticated Library media files and embed inline video/image previews on all three Library tabs.

**Architecture:** Three login-gated `GET /media/{sources|videos|images}/{name}` routes resolve files via existing `resolve_source` / `resolve_video` / `resolve_image` helpers and return `FileResponse`. `library.html` embeds `<video preload="none">` / `<img loading="lazy">` pointing at those URLs; light CSS caps preview height.

**Tech Stack:** FastAPI, Starlette `FileResponse`, Jinja2 templates, existing pytest `TestClient` patterns

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-16-library-media-preview-design.md`
- Auth: same `Depends(require_login)` as `/media/outputs/{name}`
- Videos: `controls playsinline preload="none"` — no autoplay, no poster pipeline
- Images: `loading="lazy"`; no lightbox
- Do not mount `StaticFiles` on media dirs
- No Generate-page preview; no upload/delete behavior changes

## File map

| File | Responsibility |
|------|----------------|
| `src/roblox_viral/web/library.py` | `media_type_for_name(name: str) -> str` suffix → MIME |
| `src/roblox_viral/web/app.py` | Three media GET routes (+ optional thin wrapper) |
| `src/roblox_viral/web/templates/library.html` | Inline `<video>` / `<img>` previews |
| `src/roblox_viral/web/static/app.css` | `.source-preview` sizing |
| `tests/web/test_library_routes.py` | Route auth / 200 / 404 / 400 + HTML smoke |
| `README.md` | One-line Library preview note (optional, fold into Task 2) |

---

### Task 1: Media MIME helper + `/media/{sources,videos,images}/{name}` routes

**Files:**
- Modify: `src/roblox_viral/web/library.py`
- Modify: `src/roblox_viral/web/app.py`
- Modify: `tests/web/test_library_routes.py`

**Interfaces:**
- Consumes: `resolve_source`, `resolve_video`, `resolve_image` from `library.py` (existing)
- Produces:

```python
def media_type_for_name(name: str) -> str:
    """Return Content-Type from file suffix; default application/octet-stream."""
```

```text
GET /media/sources/{name}  -> FileResponse  (login required)
GET /media/videos/{name}   -> FileResponse
GET /media/images/{name}   -> FileResponse
```

Map ValueError → 400, FileNotFoundError → 404.

- [ ] **Step 1: Write the failing tests** in `tests/web/test_library_routes.py` (reuse `_client` / `_login` already in that file):

```python
def test_media_library_routes_require_auth_and_serve(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    settings = client.app.state.settings
    settings.sources_dir.mkdir(parents=True, exist_ok=True)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    (settings.sources_dir / "slice.mp4").write_bytes(b"slice-bytes")
    (settings.videos_dir / "raw.mp4").write_bytes(b"raw-bytes")
    (settings.images_dir / "pic.png").write_bytes(b"png-bytes")

    for url in (
        "/media/sources/slice.mp4",
        "/media/videos/raw.mp4",
        "/media/images/pic.png",
    ):
        unauth = client.get(url, follow_redirects=False)
        assert unauth.status_code in (302, 303, 401)

    _login(client)
    assert client.get("/media/sources/slice.mp4").content == b"slice-bytes"
    assert client.get("/media/videos/raw.mp4").content == b"raw-bytes"
    img = client.get("/media/images/pic.png")
    assert img.status_code == 200
    assert img.content == b"png-bytes"
    assert "image/png" in img.headers.get("content-type", "")


def test_media_library_routes_404_and_400(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _login(client)
    assert client.get("/media/videos/missing.mp4").status_code == 404
    assert client.get("/media/sources/../secrets.mp4").status_code == 400
    assert client.get("/media/images/not-a-path.jpg").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/web/test_library_routes.py::test_media_library_routes_require_auth_and_serve tests/web/test_library_routes.py::test_media_library_routes_404_and_400 -v`

Expected: FAIL (404 on routes that do not exist yet, or import/route missing)

- [ ] **Step 3: Add `media_type_for_name` to `library.py`**

```python
_MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def media_type_for_name(name: str) -> str:
    return _MEDIA_TYPES.get(Path(name).suffix.lower(), "application/octet-stream")
```

- [ ] **Step 4: Add routes in `app.py`** (import `media_type_for_name`, `resolve_source`, `resolve_video`, `resolve_image` — latter may already be imported via `library_mod` or named imports; use existing import style)

Place next to `media_output`. Prefer one shared handler pattern:

```python
def _library_media_response(resolve, settings: Settings, name: str) -> FileResponse:
    try:
        path = resolve(settings, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(
        path,
        media_type=media_type_for_name(path.name),
        filename=path.name,
    )


@app.get("/media/sources/{name}")
def media_source(
    name: str,
    request: Request,
    _: None = Depends(require_login),
) -> FileResponse:
    return _library_media_response(
        resolve_source, request.app.state.settings, name
    )


@app.get("/media/videos/{name}")
def media_video(
    name: str,
    request: Request,
    _: None = Depends(require_login),
) -> FileResponse:
    return _library_media_response(
        resolve_video, request.app.state.settings, name
    )


@app.get("/media/images/{name}")
def media_image(
    name: str,
    request: Request,
    _: None = Depends(require_login),
) -> FileResponse:
    return _library_media_response(
        resolve_image, request.app.state.settings, name
    )
```

Ensure `resolve_source` / `resolve_video` / `resolve_image` / `media_type_for_name` are imported at module top (extend existing `from roblox_viral.web.library import (...)` block).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/web/test_library_routes.py::test_media_library_routes_require_auth_and_serve tests/web/test_library_routes.py::test_media_library_routes_404_and_400 -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/roblox_viral/web/library.py src/roblox_viral/web/app.py tests/web/test_library_routes.py
git commit -m "feat(web): serve authenticated library media for preview"
```

---

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
