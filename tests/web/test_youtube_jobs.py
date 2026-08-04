from pathlib import Path

import pytest

from roblox_viral.web.config import Settings
from roblox_viral.web.jobs import BusyError, JobManager
from roblox_viral.web.library import SourceVideo


def _settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "x")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    s = Settings.from_env()
    s.ensure_media_dirs()
    return s


def test_youtube_job_busy_blocks_render(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    mgr._active_id = "busy"
    (s.sources_dir / "clip.mp4").write_bytes(b"x")
    with pytest.raises(BusyError, match="already in progress"):
        mgr.create(s, "clip.mp4", "Hi.\n", "en-US-EmmaNeural")


def test_run_youtube_job_success(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()

    def fake_download(url: str, dest: Path) -> Path:
        dest.write_bytes(b"video")
        return dest

    def fake_slice(settings, uploaded_path, base_stem):
        name = f"{base_stem}-1.mp4"
        path = settings.sources_dir / name
        path.write_bytes(b"slice")
        return [SourceVideo(name, path, path.stat().st_size)]

    monkeypatch.setattr("roblox_viral.web.jobs.download_youtube", fake_download)
    monkeypatch.setattr(
        "roblox_viral.web.jobs.slice_into_minute_parts", fake_slice
    )

    record = mgr.create_youtube(
        s, "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "gameplay"
    )
    assert record.kind == "youtube"
    assert record.status == "queued"
    mgr.run_youtube_job(s, record.id)
    done = mgr.get(record.id, s)
    assert done is not None
    assert done.status == "done"
    assert done.created_slices == ["gameplay-1.mp4"]
    assert (s.sources_dir / "gameplay-1.mp4").is_file()
    assert mgr._active_id is None
