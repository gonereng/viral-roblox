# Review package RB Task 2
BASE: 3e5b9c6549877c8d64f4990dfff3ea7818433bfd
HEAD: f5400ee855dedea54fba1551cff54305fb1f441f

## Commits

f5400ee feat(jobs): Reddit BREAK dual render on one job

## Diff stat

 src/roblox_viral/web/jobs.py | 297 +++++++++++++++++++++++++------------------
 tests/web/test_jobs.py       | 120 +++++++++++++++++
 2 files changed, 296 insertions(+), 121 deletions(-)

## Full diff

diff --git a/src/roblox_viral/web/jobs.py b/src/roblox_viral/web/jobs.py
index d779eec..aff3866 100644
--- a/src/roblox_viral/web/jobs.py
+++ b/src/roblox_viral/web/jobs.py
@@ -7,16 +7,17 @@ import uuid
 from dataclasses import asdict, dataclass
 from datetime import datetime, timezone
 from typing import Literal
 
 from pathlib import Path
 
 from roblox_viral.captions import write_ass
 from roblox_viral.hook_cover import render_hook_cover, split_hook
+from roblox_viral.reddit_break import split_reddit_story
 from roblox_viral.reddit_card import first_sentence_end_s, render_reddit_card
 from roblox_viral.x_card import render_x_card
 from roblox_viral.reddit_clips import (
     plan_reddit_sentence_clips,
     sentence_durations_s,
 )
 from roblox_viral.render import (
     build_reddit_background,
@@ -91,16 +92,17 @@ class JobRecord:
     video_speed: int = DEFAULT_VIDEO_SPEED
     mode: str = "single"  # "single" | "picture" | "reddit"
     ken_burns: bool = False
     url: str | None = None
     stem: str | None = None
     created_slices: list[str] | None = None
     ephemeral: bool = False
     title_card_name: str | None = None
+    output_name_b: str | None = None
     tts_provider: str = DEFAULT_TTS_PROVIDER
 
 
 class JobManager:
     """In-memory job store with single-flight pipeline execution."""
 
     def __init__(self) -> None:
         self._lock = threading.Lock()
@@ -149,21 +151,26 @@ class JobManager:
             else:
                 source_name = validate_video_filename(safe)
                 ken_burns = False
         elif mode == "picture":
             resolve_image(settings, source_name)
         else:
             resolve_source(settings, source_name)
             ken_burns = False
-        sentences = split_sentences(story)
-        if not sentences:
-            raise ValueError("Story is empty")
         if mode == "reddit":
+            part_a, _part_b = split_reddit_story(story)
+            sentences = split_sentences(part_a)
+            if not sentences:
+                raise ValueError("Story is empty")
             split_hook(sentences[0])
+        else:
+            sentences = split_sentences(story)
+            if not sentences:
+                raise ValueError("Story is empty")
 
         with self._lock:
             if self._active_id is not None:
                 raise BusyError("A job is already in progress")
             job_id = uuid.uuid4().hex
             record = JobRecord(
                 id=job_id,
                 status="queued",
@@ -216,16 +223,17 @@ class JobManager:
             data = json.loads(status_path.read_text(encoding="utf-8"))
             record = JobRecord(
                 id=str(data["id"]),
                 status=data["status"],
                 error=data.get("error"),
                 source_name=str(data.get("source_name") or ""),
                 voice=str(data.get("voice") or ""),
                 output_name=data.get("output_name"),
+                output_name_b=data.get("output_name_b"),
                 created_at=str(data["created_at"]),
                 kind=str(data.get("kind") or "render"),
                 pitch=int(data["pitch"]) if "pitch" in data else DEFAULT_PITCH,
                 speed=int(data["speed"]) if "speed" in data else DEFAULT_SPEED,
                 video_speed=int(data["video_speed"])
                 if "video_speed" in data
                 else DEFAULT_VIDEO_SPEED,
                 mode=normalize_mode(str(data.get("mode") or "single")),
@@ -254,160 +262,207 @@ class JobManager:
 
     def run_job(self, settings: Settings, job_id: str) -> None:
         record = self._jobs.get(job_id)
         if record is None:
             raise KeyError(f"Unknown job: {job_id}")
 
         try:
             story = self._stories[job_id]
-            sentences = split_sentences(story)
-            if not sentences:
-                raise ValueError("Story is empty")
+            if record.mode == "reddit":
+                part_a, part_b = split_reddit_story(story)
+            else:
+                part_a, part_b = story, None
 
             job_dir = settings.jobs_dir / job_id
             job_dir.mkdir(parents=True, exist_ok=True)
-            narration_path = job_dir / "narration.mp3"
-            ass_path = job_dir / "captions.ass"
+
             output_name = make_output_name(record.source_name or "reddit")
             output_path = settings.outputs_dir / output_name
 
-            self._set_status(settings, record, "synthesizing")
-            tts_text = join_for_tts(sentences)
-            if record.tts_provider == "gemini":
-                words = GeminiTTSProvider(
-                    settings.gemini_api_key,
-                    record.voice,
-                    align_language=settings.whisper_align_language,
-                    align_model=settings.whisper_align_model,
-                ).synthesize(tts_text, narration_path)
+            card_name = self._render_story_part(
+                settings,
+                record,
+                story=part_a,
+                job_dir=job_dir,
+                output_path=output_path,
+                work_suffix="",
+                include_title_card=True,
+            )
+
+            record.output_name = output_name
+            if record.mode == "reddit" and card_name:
+                record.title_card_name = card_name
+
+            if part_b is not None:
+                output_name_b = f"{Path(output_name).stem}-b.mp4"
+                self._render_story_part(
+                    settings,
+                    record,
+                    story=part_b,
+                    job_dir=job_dir,
+                    output_path=settings.outputs_dir / output_name_b,
+                    work_suffix="_b",
+                    include_title_card=False,
+                )
+                record.output_name_b = output_name_b
             else:
-                words = EdgeTTSProvider(
-                    record.voice,
-                    rate=format_edge_rate(record.speed),
-                    pitch=format_edge_pitch(record.pitch),
-                ).synthesize(tts_text, narration_path)
-
-            self._set_status(settings, record, "captioning")
-            write_ass(words, ass_path, sentences=sentences)
-
-            title_card_path: Path | None = None
-            title_card_until_s: float | None = None
-            title_card_download_name: str | None = None
+                record.output_name_b = None
+
+            self._set_status(settings, record, "done")
+        except Exception as exc:
+            record.error = str(exc)
+            self._set_status(settings, record, "error")
+        finally:
+            with self._lock:
+                if self._active_id == job_id:
+                    self._active_id = None
+
+    def _render_story_part(
+        self,
+        settings: Settings,
+        record: JobRecord,
+        *,
+        story: str,
+        job_dir: Path,
+        output_path: Path,
+        work_suffix: str,
+        include_title_card: bool,
+    ) -> str | None:
+        sentences = split_sentences(story)
+        if not sentences:
+            raise ValueError("Story is empty")
+
+        narration_path = job_dir / f"narration{work_suffix}.mp3"
+        ass_path = job_dir / f"captions{work_suffix}.ass"
+
+        self._set_status(settings, record, "synthesizing")
+        tts_text = join_for_tts(sentences)
+        if record.tts_provider == "gemini":
+            words = GeminiTTSProvider(
+                settings.gemini_api_key,
+                record.voice,
+                align_language=settings.whisper_align_language,
+                align_model=settings.whisper_align_model,
+            ).synthesize(tts_text, narration_path)
+        else:
+            words = EdgeTTSProvider(
+                record.voice,
+                rate=format_edge_rate(record.speed),
+                pitch=format_edge_pitch(record.pitch),
+            ).synthesize(tts_text, narration_path)
+
+        self._set_status(settings, record, "captioning")
+        write_ass(words, ass_path, sentences=sentences)
+
+        title_card_path: Path | None = None
+        title_card_until_s: float | None = None
+        title_card_download_name: str | None = None
+        if include_title_card:
             if record.mode == "reddit":
                 title_card_until_s = first_sentence_end_s(sentences, words)
-                title_card_path = job_dir / "reddit_card.png"
+                title_card_path = job_dir / f"reddit_card{work_suffix}.png"
                 render_reddit_card(sentences[0], title_card_path, scale=1.0)
                 top, bottom = split_hook(sentences[0])
-                title_card_download_name = f"{Path(output_name).stem}-card.png"
+                title_card_download_name = f"{output_path.stem}-card.png"
                 settings.outputs_dir.mkdir(parents=True, exist_ok=True)
                 render_hook_cover(
                     top,
                     bottom,
                     settings.outputs_dir / title_card_download_name,
                 )
             elif record.mode == "single":
                 title_card_until_s = first_sentence_end_s(sentences, words)
-                title_card_path = job_dir / "x_card.png"
+                title_card_path = job_dir / f"x_card{work_suffix}.png"
                 render_x_card(sentences[0], title_card_path)
 
-            self._set_status(settings, record, "rendering")
-            render_video_speed = (
-                100 if record.tts_provider == "gemini" else record.video_speed
+        self._set_status(settings, record, "rendering")
+        render_video_speed = (
+            100 if record.tts_provider == "gemini" else record.video_speed
+        )
+        needs_tempo = (
+            record.tts_provider == "gemini"
+            and record.mode != "picture"
+            and record.video_speed != 100
+        )
+        pass1_path = (
+            job_dir / f"render_1x{work_suffix}.mp4" if needs_tempo else output_path
+        )
+        if record.ephemeral:
+            media_path = (job_dir / record.source_name).resolve()
+            if (
+                not media_path.is_relative_to(job_dir.resolve())
+                or not media_path.is_file()
+            ):
+                raise FileNotFoundError(record.source_name)
+        elif record.mode == "picture":
+            media_path = resolve_image(settings, record.source_name)
+        elif record.mode == "reddit":
+            videos = [video.path for video in list_videos(settings)]
+            durations = {
+                video_path: probe_duration_seconds(video_path)
+                for video_path in videos
+            }
+            sent_durations = sentence_durations_s(sentences, words)
+            segments = plan_reddit_sentence_clips(
+                videos,
+                sent_durations,
+                video_speed=render_video_speed,
+                durations=durations,
             )
-            needs_tempo = (
-                record.tts_provider == "gemini"
-                and record.mode != "picture"
-                and record.video_speed != 100
+            media_path = job_dir / f"reddit_bg{work_suffix}.mp4"
+            build_reddit_background(
+                segments,
+                media_path,
+                work_dir=job_dir,
             )
-            pass1_path = (
-                job_dir / "render_1x.mp4" if needs_tempo else output_path
+        else:
+            media_path = resolve_source(settings, record.source_name)
+
+        if record.mode == "picture":
+            render_still(
+                image_path=media_path,
+                audio_path=narration_path,
+                ass_path=ass_path,
+                output_path=pass1_path,
+                ken_burns=record.ken_burns,
+                work_dir=job_dir,
+            )
+        else:
+            overlay_path = (
+                None
+                if record.mode in ("reddit", "single")
+                else settings.overlay_video_path
+            )
+            render_video(
+                video_path=media_path,
+                audio_path=narration_path,
+                ass_path=ass_path,
+                output_path=pass1_path,
+                work_dir=job_dir,
+                overlay_path=overlay_path,
+                title_card_path=title_card_path,
+                title_card_until_s=title_card_until_s,
+                video_speed=render_video_speed,
+                mode=record.mode,
             )
-            if record.ephemeral:
-                media_path = (job_dir / record.source_name).resolve()
-                if (
-                    not media_path.is_relative_to(job_dir.resolve())
-                    or not media_path.is_file()
-                ):
-                    raise FileNotFoundError(record.source_name)
-            elif record.mode == "picture":
-                media_path = resolve_image(settings, record.source_name)
-            elif record.mode == "reddit":
-                videos = [video.path for video in list_videos(settings)]
-                durations = {
-                    video_path: probe_duration_seconds(video_path)
-                    for video_path in videos
-                }
-                sent_durations = sentence_durations_s(sentences, words)
-                segments = plan_reddit_sentence_clips(
-                    videos,
-                    sent_durations,
-                    video_speed=render_video_speed,
-                    durations=durations,
-                )
-                media_path = job_dir / "reddit_bg.mp4"
-                build_reddit_background(
-                    segments,
-                    media_path,
-                    work_dir=job_dir,
-                )
-            else:
-                media_path = resolve_source(settings, record.source_name)
-
-            if record.mode == "picture":
-                render_still(
-                    image_path=media_path,
-                    audio_path=narration_path,
-                    ass_path=ass_path,
-                    output_path=pass1_path,
-                    ken_burns=record.ken_burns,
-                    work_dir=job_dir,
-                )
-            else:
-                overlay_path = (
-                    None
-                    if record.mode in ("reddit", "single")
-                    else settings.overlay_video_path
-                )
-                render_video(
-                    video_path=media_path,
-                    audio_path=narration_path,
-                    ass_path=ass_path,
-                    output_path=pass1_path,
-                    work_dir=job_dir,
-                    overlay_path=overlay_path,
-                    title_card_path=title_card_path,
-                    title_card_until_s=title_card_until_s,
-                    video_speed=render_video_speed,
-                    mode=record.mode,
-                )
 
-            if needs_tempo:
-                tempo_finished_video(
-                    input_path=pass1_path,
-                    output_path=output_path,
-                    video_speed=record.video_speed,
-                    mode=record.mode,
-                )
-                try:
-                    pass1_path.unlink(missing_ok=True)
-                except OSError:
-                    pass
+        if needs_tempo:
+            tempo_finished_video(
+                input_path=pass1_path,
+                output_path=output_path,
+                video_speed=record.video_speed,
+                mode=record.mode,
+            )
+            try:
+                pass1_path.unlink(missing_ok=True)
+            except OSError:
+                pass
 
-            record.output_name = output_name
-            if record.mode == "reddit" and title_card_download_name is not None:
-                record.title_card_name = title_card_download_name
-            self._set_status(settings, record, "done")
-        except Exception as exc:
-            record.error = str(exc)
-            self._set_status(settings, record, "error")
-        finally:
-            with self._lock:
-                if self._active_id == job_id:
-                    self._active_id = None
+        return title_card_download_name
 
     def _set_status(
         self, settings: Settings, record: JobRecord, status: JobStatus
     ) -> None:
         record.status = status
         self._persist(settings, record)
 
     def _persist(self, settings: Settings, record: JobRecord) -> None:
diff --git a/tests/web/test_jobs.py b/tests/web/test_jobs.py
index 801f3c4..be1ac8c 100644
--- a/tests/web/test_jobs.py
+++ b/tests/web/test_jobs.py
@@ -1146,16 +1146,136 @@ def test_run_job_edge_still_passes_configured_video_speed(tmp_path, monkeypatch)
         "en-US-EmmaNeural",
         video_speed=175,
     )
     mgr.run_job(s, job.id)
     assert seen["render"]["video_speed"] == 175
     assert mgr.get(job.id, s).status == "done"
 
 
+def test_create_reddit_validates_hook_on_part_a_only(tmp_path, monkeypatch):
+    s = _settings(tmp_path, monkeypatch)
+    (s.videos_dir / "one.mp4").write_bytes(b"vid")
+    mgr = JobManager()
+    story = "Good Hook - Title\nBody A.\nBREAK\nNo dash needed here.\nMore B.\n"
+    job = mgr.create(s, "", story, "en-US-EmmaNeural", mode="reddit")
+    assert job.mode == "reddit"
+
+
+def test_create_reddit_rejects_bad_hook_even_with_break(tmp_path, monkeypatch):
+    s = _settings(tmp_path, monkeypatch)
+    (s.videos_dir / "one.mp4").write_bytes(b"vid")
+    mgr = JobManager()
+    with pytest.raises(ValueError, match="phrase - phrase"):
+        mgr.create(
+            s,
+            "",
+            "Bad first line\nBREAK\nFine B.\n",
+            "en-US-EmmaNeural",
+            mode="reddit",
+        )
+
+
+def _reddit_break_mocks(monkeypatch, seen):
+    def fake_synthesize(self, text, output_path):
+        Path(output_path).write_bytes(b"mp3")
+        return [
+            WordTiming("Hook", 0, 200),
+            WordTiming("One", 200, 500),
+            WordTiming("Second", 500, 800),
+            WordTiming("A", 800, 1000),
+            WordTiming("First", 1000, 1300),
+            WordTiming("B", 1300, 1600),
+            WordTiming("sentence", 1600, 1900),
+            WordTiming("Second", 1900, 2200),
+            WordTiming("B", 2200, 2500),
+        ]
+
+    def fake_write_ass(words, ass_path, sentences=None):
+        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")
+
+    def fake_probe(path):
+        return 12.0 if Path(path).name.startswith("narration") else 8.0
+
+    def fake_plan(paths, sentence_durations_s, *, video_speed, durations):
+        return ["planned-segment"]
+
+    def fake_build(segments, output_path, *, work_dir=None):
+        Path(output_path).write_bytes(b"background")
+
+    def fake_render_reddit_card(title, output_path, *, scale=2.0):
+        Path(output_path).write_bytes(b"png")
+
+    def fake_render_hook_cover(top, bottom, output_path, *, template_path=None):
+        Path(output_path).write_bytes(b"hook-png")
+
+    def fake_render_video(**kwargs):
+        seen["renders"].append(dict(kwargs))
+        Path(kwargs["output_path"]).write_bytes(b"mp4")
+
+    monkeypatch.setattr(
+        "roblox_viral.web.jobs.EdgeTTSProvider.synthesize", fake_synthesize
+    )
+    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
+    monkeypatch.setattr(jobs_module, "probe_duration_seconds", fake_probe, raising=False)
+    monkeypatch.setattr(
+        jobs_module, "plan_reddit_sentence_clips", fake_plan, raising=False
+    )
+    monkeypatch.setattr(
+        jobs_module, "build_reddit_background", fake_build, raising=False
+    )
+    monkeypatch.setattr(
+        jobs_module, "render_reddit_card", fake_render_reddit_card, raising=False
+    )
+    monkeypatch.setattr(
+        jobs_module, "render_hook_cover", fake_render_hook_cover, raising=False
+    )
+    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)
+
+
+def test_run_job_reddit_break_writes_two_outputs(tmp_path, monkeypatch):
+    s = _settings(tmp_path, monkeypatch)
+    (s.videos_dir / "one.mp4").write_bytes(b"vid")
+    mgr = JobManager()
+    seen = {"renders": []}
+    _reddit_break_mocks(monkeypatch, seen)
+
+    story = "Hook - One\nSecond A.\nBREAK\nFirst B sentence.\nSecond B.\n"
+    job = mgr.create(s, "", story, "en-US-EmmaNeural", mode="reddit")
+    mgr.run_job(s, job.id)
+    rec = mgr.get(job.id, s)
+    assert rec.status == "done"
+    assert rec.output_name and rec.output_name.endswith(".mp4")
+    assert rec.output_name_b == f"{Path(rec.output_name).stem}-b.mp4"
+    assert len(seen["renders"]) == 2
+    assert seen["renders"][0]["title_card_path"] is not None
+    assert seen["renders"][1]["title_card_path"] is None
+    assert (s.outputs_dir / rec.output_name).is_file()
+    assert (s.outputs_dir / rec.output_name_b).is_file()
+
+
+def test_run_job_reddit_without_break_single_output(tmp_path, monkeypatch):
+    s = _settings(tmp_path, monkeypatch)
+    (s.videos_dir / "one.mp4").write_bytes(b"vid")
+    mgr = JobManager()
+    seen = {"renders": []}
+    _reddit_break_mocks(monkeypatch, seen)
+
+    story = "Hook - One\nSecond A.\n"
+    job = mgr.create(s, "", story, "en-US-EmmaNeural", mode="reddit")
+    mgr.run_job(s, job.id)
+    rec = mgr.get(job.id, s)
+    assert rec.status == "done"
+    assert rec.output_name and rec.output_name.endswith(".mp4")
+    assert rec.output_name_b is None
+    assert len(seen["renders"]) == 1
+    assert seen["renders"][0]["title_card_path"] is not None
+    assert (s.outputs_dir / rec.output_name).is_file()
+
+
 def test_run_job_gemini_reddit_plans_at_100_then_tempos(tmp_path, monkeypatch):
     monkeypatch.setenv("GEMINI_API_KEY", "test-key")
     s = _settings(tmp_path, monkeypatch)
     videos_dir = s.videos_dir
     videos_dir.mkdir(parents=True, exist_ok=True)
     (videos_dir / "a.mp4").write_bytes(b"vid")
 
     mgr = JobManager()
