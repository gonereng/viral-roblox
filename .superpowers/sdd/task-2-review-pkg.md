# Review package Task 2
BASE: 7d3137f420b40a9bb253b2140f154d2ffa6c0e42
HEAD: 7fc360f2df4607b54f247d53936d77d6ca3488d1

## Commits

7fc360f feat(jobs): Gemini video_speed via post-render tempo

## Diff stat

 src/roblox_viral/web/jobs.py |  28 +++++-
 tests/web/test_jobs.py       | 202 +++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 227 insertions(+), 3 deletions(-)

## Full diff

diff --git a/src/roblox_viral/web/jobs.py b/src/roblox_viral/web/jobs.py
index 87ce00a..7386ac7 100644
--- a/src/roblox_viral/web/jobs.py
+++ b/src/roblox_viral/web/jobs.py
@@ -16,20 +16,21 @@ from roblox_viral.reddit_card import first_sentence_end_s, render_reddit_card
 from roblox_viral.x_card import render_x_card
 from roblox_viral.reddit_clips import (
     plan_reddit_sentence_clips,
     sentence_durations_s,
 )
 from roblox_viral.render import (
     build_reddit_background,
     probe_duration_seconds,
     render_still,
     render_video,
+    tempo_finished_video,
 )
 from roblox_viral.story import join_for_tts, split_sentences
 from roblox_viral.gemini_tts import (
     DEFAULT_GEMINI_VOICE,
     DEFAULT_TTS_PROVIDER,
     GeminiTTSProvider,
     normalize_tts_provider,
     validate_gemini_voice,
 )
 from roblox_viral.voice import (
@@ -297,78 +298,99 @@ class JobManager:
                     top,
                     bottom,
                     settings.outputs_dir / title_card_download_name,
                 )
             elif record.mode == "single":
                 title_card_until_s = first_sentence_end_s(sentences, words)
                 title_card_path = job_dir / "x_card.png"
                 render_x_card(sentences[0], title_card_path)
 
             self._set_status(settings, record, "rendering")
+            render_video_speed = (
+                100 if record.tts_provider == "gemini" else record.video_speed
+            )
+            needs_tempo = (
+                record.tts_provider == "gemini" and record.video_speed != 100
+            )
+            pass1_path = (
+                job_dir / "render_1x.mp4" if needs_tempo else output_path
+            )
             if record.ephemeral:
                 media_path = (job_dir / record.source_name).resolve()
                 if (
                     not media_path.is_relative_to(job_dir.resolve())
                     or not media_path.is_file()
                 ):
                     raise FileNotFoundError(record.source_name)
             elif record.mode == "picture":
                 media_path = resolve_image(settings, record.source_name)
             elif record.mode == "reddit":
                 videos = [video.path for video in list_videos(settings)]
                 durations = {
                     video_path: probe_duration_seconds(video_path)
                     for video_path in videos
                 }
                 sent_durations = sentence_durations_s(sentences, words)
                 segments = plan_reddit_sentence_clips(
                     videos,
                     sent_durations,
-                    video_speed=record.video_speed,
+                    video_speed=render_video_speed,
                     durations=durations,
                 )
                 media_path = job_dir / "reddit_bg.mp4"
                 build_reddit_background(
                     segments,
                     media_path,
                     work_dir=job_dir,
                 )
             else:
                 media_path = resolve_source(settings, record.source_name)
 
             if record.mode == "picture":
                 render_still(
                     image_path=media_path,
                     audio_path=narration_path,
                     ass_path=ass_path,
-                    output_path=output_path,
+                    output_path=pass1_path,
                     ken_burns=record.ken_burns,
                     work_dir=job_dir,
                 )
             else:
                 overlay_path = (
                     None
                     if record.mode in ("reddit", "single")
                     else settings.overlay_video_path
                 )
                 render_video(
                     video_path=media_path,
                     audio_path=narration_path,
                     ass_path=ass_path,
-                    output_path=output_path,
+                    output_path=pass1_path,
                     work_dir=job_dir,
                     overlay_path=overlay_path,
                     title_card_path=title_card_path,
                     title_card_until_s=title_card_until_s,
+                    video_speed=render_video_speed,
+                    mode=record.mode,
+                )
+
+            if needs_tempo:
+                tempo_finished_video(
+                    input_path=pass1_path,
+                    output_path=output_path,
                     video_speed=record.video_speed,
                     mode=record.mode,
                 )
+                try:
+                    pass1_path.unlink(missing_ok=True)
+                except OSError:
+                    pass
 
             record.output_name = output_name
             if record.mode == "reddit" and title_card_download_name is not None:
                 record.title_card_name = title_card_download_name
             self._set_status(settings, record, "done")
         except Exception as exc:
             record.error = str(exc)
             self._set_status(settings, record, "error")
         finally:
             with self._lock:
diff --git a/tests/web/test_jobs.py b/tests/web/test_jobs.py
index 263c966..bfbe6d3 100644
--- a/tests/web/test_jobs.py
+++ b/tests/web/test_jobs.py
@@ -882,10 +882,212 @@ def test_run_single_passes_x_card_and_no_greenscreen(tmp_path, monkeypatch):
     )
 
     job = mgr.create(s, "clip.mp4", "One line only here.\n", "en-US-EmmaNeural")
     mgr.run_job(s, job.id)
 
     assert seen["render"]["overlay_path"] is None
     assert str(seen["render"]["title_card_path"]).endswith("x_card.png")
     assert seen["render"]["title_card_until_s"] == 0.5
     assert mgr.get(job.id, s).status == "done"
     assert mgr.get(job.id, s).title_card_name is None
+
+
+def test_run_job_gemini_forces_render_video_speed_100(tmp_path, monkeypatch):
+    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
+    s = _settings(tmp_path, monkeypatch)
+    mgr = JobManager()
+    seen = {}
+
+    def fake_gemini_synth(self, text, output_path):
+        Path(output_path).write_bytes(b"mp3")
+        return [WordTiming("One", 0, 100)]
+
+    def fake_write_ass(words, ass_path, sentences=None):
+        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")
+
+    def fake_render_video(**kwargs):
+        seen["render"] = kwargs
+        Path(kwargs["output_path"]).write_bytes(b"mp4-1x")
+
+    def boom_tempo(**kwargs):
+        raise AssertionError("tempo must not run at video_speed 100")
+
+    monkeypatch.setattr(
+        "roblox_viral.web.jobs.GeminiTTSProvider.synthesize", fake_gemini_synth
+    )
+    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
+    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)
+    monkeypatch.setattr("roblox_viral.web.jobs.tempo_finished_video", boom_tempo)
+
+    job = mgr.create(
+        s,
+        "clip.mp4",
+        "One line only here.\n",
+        "Kore",
+        tts_provider="gemini",
+        video_speed=100,
+    )
+    mgr.run_job(s, job.id)
+    assert seen["render"]["video_speed"] == 100
+    assert mgr.get(job.id, s).status == "done"
+    assert (s.outputs_dir / mgr.get(job.id, s).output_name).is_file()
+
+
+def test_run_job_gemini_tempos_when_video_speed_not_100(tmp_path, monkeypatch):
+    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
+    s = _settings(tmp_path, monkeypatch)
+    mgr = JobManager()
+    seen = {}
+
+    def fake_gemini_synth(self, text, output_path):
+        Path(output_path).write_bytes(b"mp3")
+        return [WordTiming("One", 0, 100)]
+
+    def fake_write_ass(words, ass_path, sentences=None):
+        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")
+
+    def fake_render_video(**kwargs):
+        seen["render"] = dict(kwargs)
+        Path(kwargs["output_path"]).write_bytes(b"mp4-1x")
+
+    def fake_tempo(**kwargs):
+        seen["tempo"] = dict(kwargs)
+        Path(kwargs["output_path"]).write_bytes(b"mp4-sped")
+
+    monkeypatch.setattr(
+        "roblox_viral.web.jobs.GeminiTTSProvider.synthesize", fake_gemini_synth
+    )
+    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
+    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)
+    monkeypatch.setattr("roblox_viral.web.jobs.tempo_finished_video", fake_tempo)
+
+    job = mgr.create(
+        s,
+        "clip.mp4",
+        "One line only here.\n",
+        "Kore",
+        tts_provider="gemini",
+        video_speed=160,
+    )
+    mgr.run_job(s, job.id)
+    assert seen["render"]["video_speed"] == 100
+    render_out = Path(seen["render"]["output_path"])
+    assert render_out.name == "render_1x.mp4"
+    assert seen["tempo"]["video_speed"] == 160
+    assert seen["tempo"]["mode"] == "single"
+    assert Path(seen["tempo"]["input_path"]) == render_out
+    final = s.outputs_dir / mgr.get(job.id, s).output_name
+    assert Path(seen["tempo"]["output_path"]) == final
+    assert final.read_bytes() == b"mp4-sped"
+    assert not render_out.is_file()
+    assert mgr.get(job.id, s).status == "done"
+
+
+def test_run_job_edge_still_passes_configured_video_speed(tmp_path, monkeypatch):
+    """Regression: Edge must not force 100 or call tempo_finished_video."""
+    s = _settings(tmp_path, monkeypatch)
+    mgr = JobManager()
+    seen = {}
+
+    def fake_synthesize(self, text, output_path):
+        Path(output_path).write_bytes(b"mp3")
+        return [WordTiming("One", 0, 100)]
+
+    def fake_write_ass(words, ass_path, sentences=None):
+        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")
+
+    def fake_render_video(**kwargs):
+        seen["render"] = kwargs
+        Path(kwargs["output_path"]).write_bytes(b"mp4")
+
+    def boom_tempo(**kwargs):
+        raise AssertionError("tempo must not run for edge")
+
+    monkeypatch.setattr(
+        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
+    )
+    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
+    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)
+    monkeypatch.setattr("roblox_viral.web.jobs.tempo_finished_video", boom_tempo)
+
+    job = mgr.create(
+        s,
+        "clip.mp4",
+        "One line only here.\n",
+        "en-US-EmmaNeural",
+        video_speed=175,
+    )
+    mgr.run_job(s, job.id)
+    assert seen["render"]["video_speed"] == 175
+    assert mgr.get(job.id, s).status == "done"
+
+
+def test_run_job_gemini_reddit_plans_at_100_then_tempos(tmp_path, monkeypatch):
+    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
+    s = _settings(tmp_path, monkeypatch)
+    videos_dir = s.videos_dir
+    videos_dir.mkdir(parents=True, exist_ok=True)
+    (videos_dir / "a.mp4").write_bytes(b"vid")
+
+    mgr = JobManager()
+    seen = {}
+
+    def fake_gemini_synth(self, text, output_path):
+        Path(output_path).write_bytes(b"mp3")
+        return [WordTiming("One", 0, 500), WordTiming("line", 500, 1000)]
+
+    def fake_write_ass(words, ass_path, sentences=None):
+        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")
+
+    def fake_plan(paths, sentence_durations_s, *, video_speed, durations):
+        seen["plan_speed"] = video_speed
+        from roblox_viral.reddit_clips import ClipSegment
+
+        return [
+            ClipSegment(path=paths[0], start_s=0.0, duration_s=1.0)
+            for _ in sentence_durations_s
+        ]
+
+    def fake_build(segments, output_path, *, work_dir=None):
+        Path(output_path).write_bytes(b"bg")
+
+    def fake_render_video(**kwargs):
+        seen["render"] = dict(kwargs)
+        Path(kwargs["output_path"]).write_bytes(b"mp4-1x")
+
+    def fake_card(*a, **k):
+        if a and hasattr(a[-1], "write_bytes"):
+            Path(a[-1]).write_bytes(b"png")
+        elif "output_path" in k:
+            Path(k["output_path"]).write_bytes(b"png")
+
+    def fake_tempo(**kwargs):
+        seen["tempo"] = dict(kwargs)
+        Path(kwargs["output_path"]).write_bytes(b"sped")
+
+    monkeypatch.setattr(
+        "roblox_viral.web.jobs.GeminiTTSProvider.synthesize", fake_gemini_synth
+    )
+    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
+    monkeypatch.setattr("roblox_viral.web.jobs.plan_reddit_sentence_clips", fake_plan)
+    monkeypatch.setattr("roblox_viral.web.jobs.build_reddit_background", fake_build)
+    monkeypatch.setattr("roblox_viral.web.jobs.render_reddit_card", fake_card)
+    monkeypatch.setattr("roblox_viral.web.jobs.render_hook_cover", fake_card)
+    monkeypatch.setattr("roblox_viral.web.jobs.probe_duration_seconds", lambda p: 10.0)
+    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)
+    monkeypatch.setattr("roblox_viral.web.jobs.tempo_finished_video", fake_tempo)
+
+    job = mgr.create(
+        s,
+        "",
+        "One line only - here.\n",
+        "Kore",
+        mode="reddit",
+        tts_provider="gemini",
+        video_speed=200,
+    )
+    mgr.run_job(s, job.id)
+    assert seen["plan_speed"] == 100
+    assert seen["render"]["video_speed"] == 100
+    assert seen["tempo"]["video_speed"] == 200
+    assert seen["tempo"]["mode"] == "reddit"
+    assert mgr.get(job.id, s).status == "done"
