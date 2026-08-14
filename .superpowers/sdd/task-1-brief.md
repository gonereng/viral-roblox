### Task 1: Image library helpers

**Files:**
- Modify: `src/roblox_viral/web/config.py`
- Modify: `src/roblox_viral/web/library.py`
- Modify: `tests/web/test_config.py`
- Modify: `tests/web/test_library.py`

**Interfaces:**
- Consumes: `Settings.media_root`
- Produces:
  - `Settings.images_dir` → `self.media_root / "images"`
  - `MAX_IMAGE_UPLOAD_BYTES = 20_000_000`
  - `SourceImage(name: str, path: Path, size_bytes: int)`
  - `list_images(settings: Settings) -> list[SourceImage]`
  - `resolve_image(settings: Settings, name: str) -> Path`
  - `save_image(settings: Settings, filename: str, data: bytes) -> SourceImage`
  - `delete_image(settings: Settings, name: str) -> None`
  - Collision: if dest exists, `{stem}-{uuid.uuid4().hex[:8]}{suffix}`
  - Temp write then rename; unlink temp on failure

- [ ] **Step 1: Write failing tests**

Add to `tests/web/test_config.py` inside `test_ensure_media_dirs`:

```python
    assert settings.images_dir.is_dir()
```

Append to `tests/web/test_library.py`:

```python
def test_save_list_delete_image(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    saved = library.save_image(s, "photo.jpg", b"jpeg-bytes")
    assert saved.name == "photo.jpg"
    assert saved.path == s.images_dir / "photo.jpg"
    assert saved.path.read_bytes() == b"jpeg-bytes"
    listed = library.list_images(s)
    assert [i.name for i in listed] == ["photo.jpg"]
    assert library.resolve_image(s, "photo.jpg") == saved.path
    library.delete_image(s, "photo.jpg")
    assert library.list_images(s) == []


def test_save_image_unique_on_collision(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    first = library.save_image(s, "photo.jpg", b"a")
    second = library.save_image(s, "photo.jpg", b"b")
    assert first.name == "photo.jpg"
    assert second.name != "photo.jpg"
    assert second.name.startswith("photo-")
    assert second.name.endswith(".jpg")
    assert {first.name, second.name} == {i.name for i in library.list_images(s)}


def test_save_image_rejects_oversize_and_unsafe(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    monkeypatch.setattr(library, "MAX_IMAGE_UPLOAD_BYTES", 10)
    with pytest.raises(ValueError, match="maximum size"):
        library.save_image(s, "photo.jpg", b"x" * 11)
    assert list(s.images_dir.iterdir()) == []
    with pytest.raises(ValueError):
        library.save_image(s, "evil.exe", b"xx")
    with pytest.raises(ValueError):
        library.resolve_image(s, "../evil.jpg")
    with pytest.raises(ValueError):
        library.resolve_image(s, "clip.mp4")


def test_images_not_listed_as_video_sources(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    library.save_image(s, "still.png", b"png")
    (s.sources_dir / "clip.mp4").write_bytes(b"vid")
    assert [x.name for x in library.list_sources(s)] == ["clip.mp4"]
    assert [x.name for x in library.list_images(s)] == ["still.png"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/web/test_config.py::test_ensure_media_dirs tests/web/test_library.py -v`

Expected: `images_dir` assertion fails and image helper tests fail with `ImportError` / `AttributeError`.

- [ ] **Step 3: Implement helpers**

In `src/roblox_viral/web/config.py`, add property and include it in `ensure_media_dirs`:

```python
    @property
    def images_dir(self) -> Path:
        return self.media_root / "images"

    def ensure_media_dirs(self) -> None:
        for d in (self.sources_dir, self.images_dir, self.outputs_dir, self.jobs_dir):
            d.mkdir(parents=True, exist_ok=True)
```

In `src/roblox_viral/web/library.py`, add next to the video helpers:

```python
_SAFE_IMAGE_NAME = re.compile(r"^[A-Za-z0-9._ -]+\.(jpg|jpeg|png|webp)$", re.I)
MAX_IMAGE_UPLOAD_BYTES = 20_000_000


@dataclass(frozen=True)
class SourceImage:
    name: str
    path: Path
    size_bytes: int


def _safe_image_name(name: str) -> str:
    base = Path(name).name
    if base != name or not _SAFE_IMAGE_NAME.match(base):
        raise ValueError(f"Invalid image filename: {name!r}")
    return base


def list_images(settings: Settings) -> list[SourceImage]:
    items: list[SourceImage] = []
    if not settings.images_dir.is_dir():
        return items
    for path in sorted(settings.images_dir.iterdir()):
        if path.is_file() and _SAFE_IMAGE_NAME.match(path.name) and not path.name.startswith("."):
            items.append(SourceImage(path.name, path, path.stat().st_size))
    return items


def resolve_image(settings: Settings, name: str) -> Path:
    safe = _safe_image_name(name)
    path = (settings.images_dir / safe).resolve()
    if not path.is_relative_to(settings.images_dir.resolve()):
        raise ValueError("Invalid path")
    if not path.is_file():
        raise FileNotFoundError(safe)
    return path


def save_image(settings: Settings, filename: str, data: bytes) -> SourceImage:
    if len(data) > MAX_IMAGE_UPLOAD_BYTES:
        raise ValueError(
            f"Upload exceeds maximum size of {MAX_IMAGE_UPLOAD_BYTES} bytes"
        )
    safe = _safe_image_name(filename)
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.images_dir / safe
    if dest.exists():
        dest = settings.images_dir / f"{Path(safe).stem}-{uuid.uuid4().hex[:8]}{Path(safe).suffix.lower()}"
    temp = settings.images_dir / f".upload-{uuid.uuid4().hex}{Path(safe).suffix.lower()}"
    try:
        temp.write_bytes(data)
        temp.replace(dest)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return SourceImage(dest.name, dest, dest.stat().st_size)


def delete_image(settings: Settings, name: str) -> None:
    resolve_image(settings, name).unlink()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/web/test_config.py::test_ensure_media_dirs tests/web/test_library.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/roblox_viral/web/config.py src/roblox_viral/web/library.py tests/web/test_config.py tests/web/test_library.py
git commit -m "feat(web): image library helpers under media/images"
```

---

