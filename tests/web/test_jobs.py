from pathlib import Path

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


def test_get_hydrates_from_disk(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    job = mgr.create(s, "clip.mp4", "Hello world.\n", "en-US-EmmaNeural")
    job_id = job.id
    status_path = s.jobs_dir / job_id / "status.json"
    assert status_path.is_file()

    cold = JobManager()
    assert cold.get(job_id) is None
    loaded = cold.get(job_id, s)
    assert loaded is not None
    assert loaded.id == job_id
    assert loaded.status == "queued"
    assert loaded.source_name == "clip.mp4"
    # Registered in memory after hydrate
    assert cold.get(job_id) is loaded


def test_get_rejects_unsafe_job_id(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    assert mgr.get("../etc/passwd", s) is None
    assert mgr.get("not-a-uuid", s) is None
    assert mgr.get("", s) is None


def test_run_job_passes_pitch_and_speed_to_tts(tmp_path, monkeypatch):
    from pathlib import Path

    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    constructed = {}

    class FakeProvider:
        def __init__(self, voice, *, rate="+0%", pitch="+0Hz"):
            constructed["voice"] = voice
            constructed["rate"] = rate
            constructed["pitch"] = pitch

        def synthesize(self, text, output_path):
            Path(output_path).write_bytes(b"mp3")
            return [WordTiming("One", 0, 100)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_video(**kwargs):
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    monkeypatch.setattr("roblox_viral.web.jobs.EdgeTTSProvider", FakeProvider)
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)

    job = mgr.create(
        s,
        "clip.mp4",
        "One line only here.\n",
        "en-US-EmmaNeural",
        pitch=15,
        speed=130,
    )
    mgr.run_job(s, job.id)
    assert constructed["rate"] == "+30%"
    assert constructed["pitch"] == "+15Hz"
    assert mgr.get(job.id, s).status == "done"


def test_get_missing_status_returns_none(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    missing = "a" * 32
    assert mgr.get(missing, s) is None


def test_create_picture_job_resolves_image(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.images_dir / "still.jpg").write_bytes(b"img")
    mgr = JobManager()
    job = mgr.create(
        s,
        "still.jpg",
        "Hello world.\n",
        "en-US-EmmaNeural",
        mode="picture",
        ken_burns=True,
    )
    assert job.mode == "picture"
    assert job.ken_burns is True
    assert job.kind == "render"
    assert job.source_name == "still.jpg"


def test_create_picture_rejects_video_name(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    with pytest.raises((ValueError, FileNotFoundError)):
        mgr.create(
            s, "clip.mp4", "Hello world.\n", "en-US-EmmaNeural", mode="picture"
        )


def test_create_roblox_ignores_ken_burns(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    job = mgr.create(
        s,
        "clip.mp4",
        "Hello world.\n",
        "en-US-EmmaNeural",
        ken_burns=True,
    )
    assert job.mode == "roblox"
    assert job.ken_burns is False


def test_create_rejects_unknown_mode(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    with pytest.raises(ValueError, match="mode"):
        mgr.create(
            s, "clip.mp4", "Hello world.\n", "en-US-EmmaNeural", mode="gif"
        )


def test_picture_job_blocks_second_of_either_mode(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.images_dir / "still.jpg").write_bytes(b"img")
    mgr = JobManager()
    mgr.create(
        s, "still.jpg", "Hello world.\n", "en-US-EmmaNeural", mode="picture"
    )
    with pytest.raises(BusyError):
        mgr.create(s, "clip.mp4", "Other.\n", "en-US-EmmaNeural")


def test_run_picture_job_calls_render_still(tmp_path, monkeypatch):
    from pathlib import Path

    s = _settings(tmp_path, monkeypatch)
    (s.images_dir / "still.jpg").write_bytes(b"img")
    mgr = JobManager()
    seen = {}

    def fake_synthesize(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [WordTiming("One", 0, 100)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_still(**kwargs):
        seen.update(kwargs)
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    def boom_video(**kwargs):
        raise AssertionError("render_video should not run for picture jobs")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_still", fake_render_still)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", boom_video)

    job = mgr.create(
        s,
        "still.jpg",
        "One line only here.\n",
        "en-US-EmmaNeural",
        mode="picture",
        ken_burns=True,
    )
    mgr.run_job(s, job.id)
    done = mgr.get(job.id, s)
    assert done.status == "done"
    assert done.output_name.endswith(".mp4")
    assert "still" in done.output_name
    assert seen["ken_burns"] is True
    assert "overlay_path" not in seen
    assert Path(seen["image_path"]).name == "still.jpg"


def test_create_ephemeral_skips_library(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    job = mgr.create(
        s,
        "input.mp4",
        "One line only here.\n",
        "en-US-EmmaNeural",
        mode="roblox",
        ephemeral=True,
    )
    assert job.ephemeral is True
    assert job.source_name == "input.mp4"


def test_run_job_ephemeral_uses_job_dir_input(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    seen = {}

    def fake_synthesize(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [WordTiming("One", 0, 100)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_video(**kwargs):
        seen["video_path"] = Path(kwargs["video_path"])
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)

    job = mgr.create(
        s,
        "input.mp4",
        "One line only here.\n",
        "en-US-EmmaNeural",
        mode="roblox",
        ephemeral=True,
    )
    input_path = s.jobs_dir / job.id / "input.mp4"
    input_path.write_bytes(b"vid")
    mgr.run_job(s, job.id)
    assert mgr.get(job.id, s).status == "done"
    assert seen["video_path"] == input_path.resolve()
