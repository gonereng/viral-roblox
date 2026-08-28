import importlib.util
from pathlib import Path

import pytest
from roblox_viral.web.library import SourceVideo

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("slice_local", ROOT / "slice_local.py")
assert _spec is not None and _spec.loader is not None
slice_local = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slice_local)


def test_run_missing_file_exits_1(tmp_path, capsys):
    missing = tmp_path / "nope.mp4"
    assert slice_local.run([str(missing)]) == 1
    err = capsys.readouterr().err
    assert "not found" in err.lower() or "nope.mp4" in err


def test_run_uses_filename_stem_and_sources_dir(tmp_path, monkeypatch, capsys):
    src = tmp_path / "long-game.mp4"
    src.write_bytes(b"vid")
    media = tmp_path / "media"
    monkeypatch.setenv("MEDIA_ROOT", str(media))
    seen = {}

    def fake_slice(settings, uploaded_path, base_stem):
        seen["sources_dir"] = settings.sources_dir
        seen["uploaded_path"] = Path(uploaded_path)
        seen["base_stem"] = base_stem
        dest = settings.sources_dir / f"{base_stem}-1.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"slice")
        return [SourceVideo(dest.name, dest, dest.stat().st_size)]

    monkeypatch.setattr(slice_local, "slice_into_minute_parts", fake_slice)
    assert slice_local.run([str(src)]) == 0
    assert seen["uploaded_path"] == src
    assert seen["base_stem"] == "long-game"
    assert seen["sources_dir"] == media.resolve() / "sources"
    assert src.is_file() and src.read_bytes() == b"vid"
    out = capsys.readouterr().out
    assert "long-game-1.mp4" in out
    assert str(media.resolve() / "sources") in out or "sources" in out


def test_run_under_one_minute_exits_1(tmp_path, monkeypatch, capsys):
    src = tmp_path / "short.mp4"
    src.write_bytes(b"vid")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))

    def boom(settings, uploaded_path, base_stem):
        raise ValueError(
            "Video must be at least 1 minute long "
            "(shorter leftover segments are discarded)"
        )

    monkeypatch.setattr(slice_local, "slice_into_minute_parts", boom)
    assert slice_local.run([str(src)]) == 1
    err = capsys.readouterr().err
    assert "at least 1 minute" in err


def test_media_settings_ignores_app_password(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("APP_SECRET", raising=False)
    s = slice_local.media_settings()
    assert s.media_root == (tmp_path / "media").resolve()
    assert s.require_password is False
