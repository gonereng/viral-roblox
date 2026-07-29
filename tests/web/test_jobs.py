import pytest
from roblox_viral.voice import WordTiming
from roblox_viral.web.config import Settings
from roblox_viral.web.jobs import BusyError, JobManager


def _settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "x")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    s = Settings.from_env()
    s.ensure_media_dirs()
    (s.sources_dir / "clip.mp4").write_bytes(b"abc")
    return s


def test_single_flight_rejects_second_job(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    j1 = mgr.create(s, "clip.mp4", "Hello world.\n", "en-US-EmmaNeural")
    assert j1.status == "queued"
    with pytest.raises(BusyError):
        mgr.create(s, "clip.mp4", "Other.\n", "en-US-EmmaNeural")


def test_run_job_updates_statuses(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()

    def fake_synthesize(self, text, output_path):
        from pathlib import Path

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"fake-audio")
        return [WordTiming(text="One", start_ms=0, end_ms=100)]

    def fake_write_ass(words, path, *, sentences=None, **kwargs):
        from pathlib import Path

        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("[Script Info]\n", encoding="utf-8")
        return out

    def fake_render_video(*, video_path, audio_path, ass_path, output_path, work_dir=None, **kwargs):
        from pathlib import Path

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"")
        return out

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)

    job = mgr.create(s, "clip.mp4", "One line only here.\n", "en-US-EmmaNeural")
    mgr.run_job(s, job.id)
    done = mgr.get(job.id)
    assert done.status == "done"
    assert done.output_name.endswith(".mp4")
    assert (s.jobs_dir / job.id / "status.json").is_file()


def test_create_succeeds_after_done(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()

    def fake_synthesize(self, text, output_path):
        from pathlib import Path

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"fake-audio")
        return [WordTiming(text="One", start_ms=0, end_ms=100)]

    def fake_write_ass(words, path, *, sentences=None, **kwargs):
        from pathlib import Path

        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("[Script Info]\n", encoding="utf-8")
        return out

    def fake_render_video(*, video_path, audio_path, ass_path, output_path, work_dir=None, **kwargs):
        from pathlib import Path

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"")
        return out

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)

    job = mgr.create(s, "clip.mp4", "One line only here.\n", "en-US-EmmaNeural")
    mgr.run_job(s, job.id)
    assert mgr.get(job.id).status == "done"

    j2 = mgr.create(s, "clip.mp4", "Another story line.\n", "en-US-EmmaNeural")
    assert j2.status == "queued"
    assert j2.id != job.id


def test_create_succeeds_after_error(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()

    def boom(self, text, output_path):
        raise RuntimeError("tts failed")

    monkeypatch.setattr("roblox_viral.web.jobs.EdgeTTSProvider.synthesize", boom)

    job = mgr.create(s, "clip.mp4", "One line only here.\n", "en-US-EmmaNeural")
    mgr.run_job(s, job.id)
    failed = mgr.get(job.id)
    assert failed.status == "error"
    assert "tts failed" in (failed.error or "")

    j2 = mgr.create(s, "clip.mp4", "Retry after error.\n", "en-US-EmmaNeural")
    assert j2.status == "queued"
    assert j2.id != job.id
