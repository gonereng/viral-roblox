from datetime import datetime

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


def test_plan_full_minute_count_discards_short_tail():
    assert library.plan_full_minute_count(59.9) == 0
    assert library.plan_full_minute_count(60) == 1
    assert library.plan_full_minute_count(150) == 2
    assert library.plan_full_minute_count(180) == 3


def test_slice_part_and_output_names():
    assert library.slice_part_name("gameplay", 2) == "gameplay-2.mp4"
    when = datetime(2026, 7, 30, 19, 45, 12)
    assert (
        library.make_output_name("gameplay-1.mp4", when=when)
        == "gameplay-1-2026-07-30_194512.mp4"
    )


def test_save_upload_rejects_oversize(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    monkeypatch.setattr(library, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(ValueError, match="maximum size"):
        library.save_upload(s, "clip.mp4", b"x" * 11)


def test_rejects_path_traversal(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        library.resolve_source(s, "../evil.mp4")


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


def test_save_upload_slices_and_discards_short_tail(tmp_path, monkeypatch):
    """150s source → two 60s slices; 30s remainder discarded."""
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not on PATH")

    s = _settings(tmp_path, monkeypatch)
    raw = tmp_path / "raw_150s.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:d=150",
            "-f",
            "lavfi",
            "-i",
            "sine=f=440:d=150",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(raw),
        ],
        check=True,
        capture_output=True,
    )
    slices = library.save_upload(s, "gameplay.mp4", raw.read_bytes())
    assert [x.name for x in slices] == ["gameplay-1.mp4", "gameplay-2.mp4"]
    assert library.list_sources(s) == slices
    # Original full upload must not remain as gameplay.mp4
    assert not (s.sources_dir / "gameplay.mp4").exists()


def test_save_upload_rejects_under_one_minute(tmp_path, monkeypatch):
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not on PATH")

    s = _settings(tmp_path, monkeypatch)
    raw = tmp_path / "raw_30s.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=320x240:d=30",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(raw),
        ],
        check=True,
        capture_output=True,
    )
    with pytest.raises(ValueError, match="at least 1 minute"):
        library.save_upload(s, "short.mp4", raw.read_bytes())


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


def test_save_image_does_not_require_hard_links(tmp_path, monkeypatch):
    import os

    s = _settings(tmp_path, monkeypatch)

    def unavailable_link(*_args, **_kwargs):
        raise OSError("hard links unavailable")

    monkeypatch.setattr(os, "link", unavailable_link)
    saved = library.save_image(s, "photo.jpg", b"jpeg-bytes")
    assert saved.path.read_bytes() == b"jpeg-bytes"


def test_save_image_concurrent_same_name(tmp_path, monkeypatch):
    import concurrent.futures

    s = _settings(tmp_path, monkeypatch)
    payloads = [f"payload-{i}".encode() for i in range(8)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda data: library.save_image(s, "photo.jpg", data), payloads))

    names = {r.name for r in results}
    assert len(names) == len(payloads)
    assert sum(1 for n in names if n == "photo.jpg") == 1
    for payload, saved in zip(payloads, results):
        assert saved.path.read_bytes() == payload
    assert len(library.list_images(s)) == len(payloads)


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


def test_save_video_stores_as_is_no_slice(tmp_path, monkeypatch):
    from roblox_viral.web.config import Settings
    from roblox_viral.web import library as lib

    media = tmp_path / "media"
    s = Settings(
        media_root=media,
        app_password="x",
        app_secret="dev-secret-key-at-least-32-chars!!",
        require_password=False,
        youtube_cookies="",
    )
    s.ensure_media_dirs()
    called = {"slice": False}

    def boom(*a, **k):
        called["slice"] = True
        raise AssertionError("slice must not run")

    monkeypatch.setattr(lib, "slice_into_minute_parts", boom)
    item = lib.save_video(s, "full.mp4", b"rawbytes")
    assert item.name == "full.mp4"
    assert (s.videos_dir / "full.mp4").read_bytes() == b"rawbytes"
    assert called["slice"] is False
    assert lib.list_videos(s)[0].name == "full.mp4"


def test_resolve_roblox_media_sources_win(tmp_path):
    from roblox_viral.web.config import Settings
    from roblox_viral.web import library as lib

    media = tmp_path / "media"
    s = Settings(
        media_root=media,
        app_password="x",
        app_secret="dev-secret-key-at-least-32-chars!!",
        require_password=False,
        youtube_cookies="",
    )
    s.ensure_media_dirs()
    (s.sources_dir / "same.mp4").write_bytes(b"slice")
    (s.videos_dir / "same.mp4").write_bytes(b"raw")
    path = lib.resolve_roblox_media(s, "same.mp4")
    assert path == (s.sources_dir / "same.mp4").resolve()


def test_resolve_roblox_media_falls_back_to_videos(tmp_path):
    from roblox_viral.web.config import Settings
    from roblox_viral.web import library as lib

    media = tmp_path / "media"
    s = Settings(
        media_root=media,
        app_password="x",
        app_secret="dev-secret-key-at-least-32-chars!!",
        require_password=False,
        youtube_cookies="",
    )
    s.ensure_media_dirs()
    (s.videos_dir / "only.mp4").write_bytes(b"raw")
    path = lib.resolve_roblox_media(s, "only.mp4")
    assert path == (s.videos_dir / "only.mp4").resolve()


def test_list_roblox_sources_labels_kinds(tmp_path):
    from roblox_viral.web.config import Settings
    from roblox_viral.web import library as lib

    media = tmp_path / "media"
    s = Settings(
        media_root=media,
        app_password="x",
        app_secret="dev-secret-key-at-least-32-chars!!",
        require_password=False,
        youtube_cookies="",
    )
    s.ensure_media_dirs()
    (s.sources_dir / "a-1.mp4").write_bytes(b"1")
    (s.videos_dir / "b.mp4").write_bytes(b"2")
    items = lib.list_roblox_sources(s)
    kinds = {i.name: i.kind for i in items}
    assert kinds["a-1.mp4"] == "slice"
    assert kinds["b.mp4"] == "video"
