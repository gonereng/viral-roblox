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

