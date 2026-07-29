import pytest
from roblox_viral.web.config import Settings
from roblox_viral.web import library


def _settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "x")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    s = Settings.from_env()
    s.ensure_media_dirs()
    return s


def test_save_list_delete_source(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    vid = library.save_upload(s, "clip.mp4", b"fake-bytes")
    assert vid.name == "clip.mp4"
    assert library.list_sources(s)[0].name == "clip.mp4"
    assert library.resolve_source(s, "clip.mp4").is_file()
    library.delete_source(s, "clip.mp4")
    assert library.list_sources(s) == []


def test_list_outputs_newest_first(tmp_path, monkeypatch):
    import os
    import time

    s = _settings(tmp_path, monkeypatch)
    older = s.outputs_dir / "older.mp4"
    newer = s.outputs_dir / "newer.mp4"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    now = time.time()
    os.utime(older, (now - 60, now - 60))
    os.utime(newer, (now, now))

    listed = library.list_outputs(s)
    assert [o.name for o in listed] == ["newer.mp4", "older.mp4"]


def test_rejects_path_traversal(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        library.resolve_source(s, "../evil.mp4")
