from pathlib import Path

import pytest

from roblox_viral.web.youtube import (
    download_youtube,
    validate_stem,
    validate_youtube_url,
)


def test_validate_youtube_url_accepts_watch_and_short():
    assert "youtube.com" in validate_youtube_url(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    assert "youtu.be" in validate_youtube_url("https://youtu.be/dQw4w9WgXcQ")


def test_validate_youtube_url_rejects_non_youtube():
    with pytest.raises(ValueError, match="YouTube"):
        validate_youtube_url("https://example.com/watch?v=abc")


def test_validate_stem_ok():
    assert validate_stem("  gameplay clip ") == "gameplay clip"


def test_validate_stem_rejects_extension_and_empty():
    with pytest.raises(ValueError):
        validate_stem("clip.mp4")
    with pytest.raises(ValueError):
        validate_stem("   ")
    with pytest.raises(ValueError):
        validate_stem("../evil")


def test_download_youtube_writes_dest(tmp_path, monkeypatch):
    dest = tmp_path / "download.mp4"

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def download(self, urls):
            dest.write_bytes(b"fake-mp4")

    monkeypatch.setattr(
        "roblox_viral.web.youtube.yt_dlp.YoutubeDL",
        FakeYDL,
    )
    out = download_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ", dest)
    assert out == dest
    assert dest.read_bytes() == b"fake-mp4"
