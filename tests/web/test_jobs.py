import json
from pathlib import Path

import pytest
from roblox_viral.voice import WordTiming
from roblox_viral.web import jobs as jobs_module
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


def test_create_single_ignores_ken_burns(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    job = mgr.create(
        s,
        "clip.mp4",
        "Hello world.\n",
        "en-US-EmmaNeural",
        ken_burns=True,
    )
    assert job.mode == "single"
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
        mode="single",
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
        mode="single",
        ephemeral=True,
    )
    input_path = s.jobs_dir / job.id / "input.mp4"
    input_path.write_bytes(b"vid")
    mgr.run_job(s, job.id)
    assert mgr.get(job.id, s).status == "done"
    assert seen["video_path"] == input_path.resolve()


def test_create_job_persists_video_speed(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.sources_dir / "raw-only.mp4").write_bytes(b"vid")
    mgr = JobManager()
    record = mgr.create(
        s,
        "raw-only.mp4",
        "Hello world.\n",
        "en-US-EmmaNeural",
        video_speed=150,
    )
    assert record.video_speed == 150
    job_id = record.id
    status_path = s.jobs_dir / job_id / "status.json"
    assert status_path.is_file()

    cold = JobManager()
    assert cold.get(job_id) is None
    loaded = cold.get(job_id, s)
    assert loaded is not None
    assert loaded.video_speed == 150


def test_create_job_rejects_bad_video_speed(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    with pytest.raises(ValueError):
        mgr.create(
            s,
            "clip.mp4",
            "Hello world.\n",
            "en-US-EmmaNeural",
            video_speed=999,
        )


def test_run_job_passes_video_speed_to_render(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    seen = {}

    def fake_synthesize(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [WordTiming("One", 0, 100)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_video(**kwargs):
        seen.update(kwargs)
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)

    job = mgr.create(
        s,
        "clip.mp4",
        "One line only here.\n",
        "en-US-EmmaNeural",
        video_speed=175,
    )
    mgr.run_job(s, job.id)
    assert seen["video_speed"] == 175
    assert mgr.get(job.id, s).status == "done"


def test_normalize_mode_maps_roblox_to_single():
    assert hasattr(jobs_module, "normalize_mode")
    assert jobs_module.normalize_mode("roblox") == "single"
    assert jobs_module.normalize_mode("single") == "single"
    assert jobs_module.normalize_mode("picture") == "picture"
    assert jobs_module.normalize_mode("reddit") == "reddit"
    with pytest.raises(ValueError, match="mode"):
        jobs_module.normalize_mode("gif")


def test_create_single_rejects_missing_source(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    with pytest.raises((ValueError, FileNotFoundError)):
        mgr.create(s, "", "Hello world.\n", "en-US-EmmaNeural", mode="single")


def test_create_reddit_requires_videos_pool(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    with pytest.raises(ValueError, match="video"):
        mgr.create(s, "", "Hello - world.\n", "en-US-EmmaNeural", mode="reddit")


def test_create_reddit_ok_with_videos(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.videos_dir / "background.mp4").write_bytes(b"vid")
    mgr = JobManager()
    job = mgr.create(s, "", "Hello - world.\n", "en-US-EmmaNeural", mode="reddit")
    assert job.mode == "reddit"
    assert job.source_name in ("", "reddit")
    assert job.ken_burns is False


def test_create_reddit_rejects_hook_without_dash(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.videos_dir / "one.mp4").write_bytes(b"vid")
    mgr = JobManager()
    with pytest.raises(ValueError, match="phrase - phrase"):
        mgr.create(s, "", "Hello world.\nSecond.\n", "en-US-EmmaNeural", mode="reddit")


def test_hydrate_roblox_mode_as_single(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    job = mgr.create(
        s, "clip.mp4", "Hello world.\n", "en-US-EmmaNeural", mode="single"
    )
    status_path = s.jobs_dir / job.id / "status.json"
    data = json.loads(status_path.read_text(encoding="utf-8"))
    data["mode"] = "roblox"
    status_path.write_text(json.dumps(data), encoding="utf-8")

    hydrated = JobManager().get(job.id, s)
    assert hydrated is not None
    assert hydrated.mode == "single"


def test_run_reddit_builds_background_and_renders(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    videos = [s.videos_dir / "one.mp4", s.videos_dir / "two.mp4"]
    for video in videos:
        video.write_bytes(b"vid")
    mgr = JobManager()
    seen = {}

    def fake_synthesize(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [WordTiming("One", 0, 100)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_probe(path):
        path = Path(path)
        return 12.0 if path.name == "narration.mp3" else 8.0

    def fake_plan(paths, sentence_durations_s, *, video_speed, durations):
        seen["plan"] = (paths, sentence_durations_s, video_speed, durations)
        return ["planned-segment"]

    def fake_build(segments, output_path, *, work_dir=None):
        seen["build"] = (segments, Path(output_path), Path(work_dir))
        Path(output_path).write_bytes(b"background")

    def fake_render_video(**kwargs):
        seen["render"] = kwargs
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr(
        jobs_module, "probe_duration_seconds", fake_probe, raising=False
    )
    monkeypatch.setattr(
        jobs_module, "plan_reddit_sentence_clips", fake_plan, raising=False
    )
    monkeypatch.setattr(
        jobs_module, "build_reddit_background", fake_build, raising=False
    )
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)

    job = mgr.create(s, "", "One line only - here.\n", "en-US-EmmaNeural", mode="reddit")
    mgr.run_job(s, job.id)

    reddit_bg = s.jobs_dir / job.id / "reddit_bg.mp4"
    paths, sent_durs, speed, durations = seen["plan"]
    assert paths == videos
    assert len(sent_durs) == 1
    assert sent_durs[0] == 0.1
    assert speed == job.video_speed
    assert durations == {videos[0]: 8.0, videos[1]: 8.0}
    assert seen["build"] == (["planned-segment"], reddit_bg, s.jobs_dir / job.id)
    assert seen["render"]["video_path"] == reddit_bg
    assert seen["render"]["overlay_path"] is None
    assert str(seen["render"]["title_card_path"]).endswith("reddit_card.png")
    assert seen["render"]["title_card_until_s"] > 0
    assert seen["render"]["video_speed"] == job.video_speed
    assert mgr.get(job.id, s).status == "done"


def test_run_reddit_plans_by_sentence_durations(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.videos_dir / "one.mp4").write_bytes(b"vid")
    mgr = JobManager()
    seen = {}

    def fake_synthesize(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [
            WordTiming("First", 0, 500),
            WordTiming("sentence", 500, 1000),
            WordTiming("here", 1000, 1500),
            WordTiming("Second", 1500, 2000),
            WordTiming("line", 2000, 2500),
        ]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_probe(path):
        return 12.0 if Path(path).name == "narration.mp3" else 8.0

    def fake_plan(paths, sentence_durations_s, *, video_speed, durations):
        seen["plan"] = (paths, sentence_durations_s, video_speed, durations)
        return ["planned-segment"]

    def fake_build(segments, output_path, *, work_dir=None):
        Path(output_path).write_bytes(b"background")

    def fake_render_video(**kwargs):
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr(
        jobs_module, "probe_duration_seconds", fake_probe, raising=False
    )
    monkeypatch.setattr(
        jobs_module, "plan_reddit_sentence_clips", fake_plan, raising=False
    )
    monkeypatch.setattr(
        jobs_module, "build_reddit_background", fake_build, raising=False
    )
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)

    story = "First sentence - here.\nSecond line.\n"
    job = mgr.create(
        s,
        "",
        story,
        "en-US-EmmaNeural",
        mode="reddit",
        video_speed=200,
    )
    mgr.run_job(s, job.id)

    _, sent_durs, speed, _ = seen["plan"]
    assert len(sent_durs) == 2
    assert speed == 200
    assert mgr.get(job.id, s).status == "done"


def test_run_reddit_passes_title_card_and_no_greenscreen(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.videos_dir / "one.mp4").write_bytes(b"vid")
    mgr = JobManager()
    seen = {}

    def fake_synthesize(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [
            WordTiming("First", 0, 500),
            WordTiming("sentence", 500, 1000),
            WordTiming("here", 1000, 1500),
            WordTiming("Second", 1500, 2000),
            WordTiming("line", 2000, 2500),
        ]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_probe(path):
        return 12.0 if Path(path).name == "narration.mp3" else 8.0

    def fake_plan(paths, sentence_durations_s, *, video_speed, durations):
        return ["planned-segment"]

    def fake_build(segments, output_path, *, work_dir=None):
        Path(output_path).write_bytes(b"background")

    def fake_render_reddit_card(title, output_path, *, scale=2.0):
        seen.setdefault("cards", []).append(
            (title, Path(output_path), scale)
        )
        Path(output_path).write_bytes(b"png")

    def fake_render_hook_cover(top, bottom, output_path, *, template_path=None):
        seen.setdefault("covers", []).append((top, bottom, Path(output_path)))
        Path(output_path).write_bytes(b"hook-png")

    def fake_first_sentence_end_s(sentences, words):
        seen["timing"] = (sentences, words)
        return 0.5

    def fake_render_video(**kwargs):
        seen["render"] = kwargs
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr(jobs_module, "probe_duration_seconds", fake_probe, raising=False)
    monkeypatch.setattr(
        jobs_module, "plan_reddit_sentence_clips", fake_plan, raising=False
    )
    monkeypatch.setattr(
        jobs_module, "build_reddit_background", fake_build, raising=False
    )
    monkeypatch.setattr(
        jobs_module, "render_reddit_card", fake_render_reddit_card, raising=False
    )
    monkeypatch.setattr(
        jobs_module, "render_hook_cover", fake_render_hook_cover, raising=False
    )
    monkeypatch.setattr(
        jobs_module, "first_sentence_end_s", fake_first_sentence_end_s, raising=False
    )
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)

    story = "First sentence here - Second hook.\nSecond line.\n"
    job = mgr.create(s, "", story, "en-US-EmmaNeural", mode="reddit")
    mgr.run_job(s, job.id)

    assert len(seen["cards"]) == 1
    assert seen["cards"][0][0] == "First sentence here - Second hook."
    assert seen["cards"][0][1] == s.jobs_dir / job.id / "reddit_card.png"
    assert seen["cards"][0][2] == 1.0
    assert seen["covers"][0][0] == "First sentence here"
    assert seen["covers"][0][1] == "Second hook."
    assert str(seen["covers"][0][2]).endswith("-card.png")
    assert seen["render"]["overlay_path"] is None
    assert str(seen["render"]["title_card_path"]).endswith("reddit_card.png")
    assert seen["render"]["title_card_until_s"] == 0.5
    assert mgr.get(job.id, s).status == "done"


def test_run_reddit_copies_title_card_to_outputs(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    (s.videos_dir / "one.mp4").write_bytes(b"vid")
    mgr = JobManager()

    def fake_synthesize(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [WordTiming("One", 0, 500)]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_probe(path):
        return 12.0 if Path(path).name == "narration.mp3" else 8.0

    def fake_plan(paths, sentence_durations_s, *, video_speed, durations):
        return ["planned-segment"]

    def fake_build(segments, output_path, *, work_dir=None):
        Path(output_path).write_bytes(b"background")

    def fake_render_reddit_card(title, output_path, *, scale=2.0):
        Path(output_path).write_bytes(b"png-card")

    def fake_render_hook_cover(top, bottom, output_path, *, template_path=None):
        Path(output_path).write_bytes(b"hook-png")

    def fake_render_video(**kwargs):
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr(
        jobs_module, "probe_duration_seconds", fake_probe, raising=False
    )
    monkeypatch.setattr(
        jobs_module, "plan_reddit_sentence_clips", fake_plan, raising=False
    )
    monkeypatch.setattr(
        jobs_module, "build_reddit_background", fake_build, raising=False
    )
    monkeypatch.setattr(
        jobs_module, "render_reddit_card", fake_render_reddit_card, raising=False
    )
    monkeypatch.setattr(
        jobs_module, "render_hook_cover", fake_render_hook_cover, raising=False
    )
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)

    job = mgr.create(
        s,
        "",
        "One line only here - Bottom phrase.\n",
        "en-US-EmmaNeural",
        mode="reddit",
    )
    mgr.run_job(s, job.id)

    job = mgr.get(job.id, s)
    assert job is not None
    assert job.title_card_name is not None
    assert job.title_card_name.endswith("-card.png")
    card_path = s.outputs_dir / job.title_card_name
    assert card_path.is_file()
    assert card_path.read_bytes() == b"hook-png"

    loaded = JobManager().get(job.id, s)
    assert loaded is not None
    assert loaded.title_card_name == job.title_card_name


def test_run_single_passes_x_card_and_no_greenscreen(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    mgr = JobManager()
    seen = {}

    def fake_synthesize(self, text, output_path):
        Path(output_path).write_bytes(b"mp3")
        return [
            WordTiming("One", 0, 200),
            WordTiming("line", 200, 500),
        ]

    def fake_write_ass(words, ass_path, sentences=None):
        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")

    def fake_render_x_card(body, output_path, **kwargs):
        Path(output_path).write_bytes(b"png")
        return Path(output_path)

    def fake_render_video(**kwargs):
        seen["render"] = kwargs
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    def boom_reddit(*args, **kwargs):
        raise AssertionError("render_reddit_card should not run for single jobs")

    monkeypatch.setattr(
        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
    )
    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)
    monkeypatch.setattr("roblox_viral.web.jobs.render_x_card", fake_render_x_card)
    monkeypatch.setattr(
        "roblox_viral.web.jobs.render_reddit_card", boom_reddit, raising=False
    )

    job = mgr.create(s, "clip.mp4", "One line only here.\n", "en-US-EmmaNeural")
    mgr.run_job(s, job.id)

    assert seen["render"]["overlay_path"] is None
    assert str(seen["render"]["title_card_path"]).endswith("x_card.png")
    assert seen["render"]["title_card_until_s"] == 0.5
    assert mgr.get(job.id, s).status == "done"
    assert mgr.get(job.id, s).title_card_name is None
