# Final review Reddit BREAK
BASE: ea3da85912248c796d6bed278d38ca317980a2d9
HEAD: 2229bfcbac9e63d3a7bd4d0d0c8cd7d96023eb53

## Commits

2229bfc feat(api): download-b and Generate UI for Reddit Part B
f5400ee feat(jobs): Reddit BREAK dual render on one job
3e5b9c6 feat: split Reddit stories on BREAK line

## Diff stat

 README.md                                    |   4 +-
 src/roblox_viral/reddit_break.py             |  27 +++
 src/roblox_viral/web/api_v1.py               |  28 +++
 src/roblox_viral/web/jobs.py                 | 297 ++++++++++++++++-----------
 src/roblox_viral/web/static/app.js           |  21 +-
 src/roblox_viral/web/templates/generate.html |   2 +
 tests/test_reddit_break.py                   |  48 +++++
 tests/web/test_api.py                        |  14 ++
 tests/web/test_api_v1.py                     |  87 ++++++++
 tests/web/test_jobs.py                       | 120 +++++++++++
 10 files changed, 523 insertions(+), 125 deletions(-)

## Full diff

diff --git a/README.md b/README.md
index b25c2b8..15fb1a8 100644
--- a/README.md
+++ b/README.md
@@ -124,15 +124,15 @@ Set `API_KEY` in `.env`. Header: `X-API-Key`.
 
 - `voice`, `story`, `type` (`single`|`reddit`|`leni`; `roblox` is rejected ΓÇö use `single`)
 - optional `pitch` (ΓêÆ100ΓÇª100, default 15), `speed` (50ΓÇª200, default 130), and `video_speed` (50ΓÇô200 for `single`/`leni`, 100ΓÇô500 for `reddit`; default 100)
 - optional `tts_provider` (`edge`|`gemini`, default `edge`). For `gemini`, set `voice` to a Gemini name (e.g. `Kore`); requires `GEMINI_API_KEY`. Gemini karaoke uses stable-ts force-align (default language German). Pitch/speed apply to Edge only.
 - for `single`: optional `media` **or** `source_name` (Library Sources slice). If neither is sent, a random Sources clip is chosen. Do not send both.
 - for `leni`: either file field `media` **or** text field `source_name` (Library image name)
-- for `reddit`: story/voice/type only (background is built from the Library Videos pool; do not send `media` or `source_name`)
+- for `reddit`: story/voice/type only (background is built from the Library Videos pool; do not send `media` or `source_name`). The first story line must be `phrase - phrase`. Optionally add a line `BREAK` on its own, then a second story; Part A gets the title card and cover, Part B is a plain video without card/cover.
 
-Then poll `GET /api/v1/videos/{id}` and download `GET /api/v1/videos/{id}/download`; then download the cover with `GET /api/v1/videos/{id}/cover` (Reddit only; 404 for other types).
+Then poll `GET /api/v1/videos/{id}` and download `GET /api/v1/videos/{id}/download` (Part A); for Reddit jobs with a `BREAK` split, download Part B with `GET /api/v1/videos/{id}/download-b` (404 if no Part B). Download the cover with `GET /api/v1/videos/{id}/cover` (Reddit Part A only; 404 for other types).
 
 PowerShell / Windows (upload via `curl.exe` ΓÇö works on PowerShell 5.1):
 
 ```powershell
 $apiKey = "your-key"
 $base = "http://127.0.0.1:8000"
diff --git a/src/roblox_viral/reddit_break.py b/src/roblox_viral/reddit_break.py
new file mode 100644
index 0000000..7d0de79
--- /dev/null
+++ b/src/roblox_viral/reddit_break.py
@@ -0,0 +1,27 @@
+from __future__ import annotations
+
+BREAK_TOKEN = "BREAK"
+
+
+def split_reddit_story(story: str) -> tuple[str, str | None]:
+    """
+    Split on a line that is exactly 'BREAK' after strip.
+    Returns (part_a, part_b_or_None).
+    If no BREAK line, or text after BREAK is empty/whitespace-only, part_b is None.
+    Part A is always the text before the first BREAK line (may be empty string).
+    """
+    text = story if story is not None else ""
+    lines = text.splitlines(keepends=True)
+    # Also handle string without trailing newline consistently via splitlines
+    idx = None
+    for i, line in enumerate(lines):
+        if line.strip() == BREAK_TOKEN:
+            idx = i
+            break
+    if idx is None:
+        return text, None
+    before = "".join(lines[:idx])
+    after = "".join(lines[idx + 1 :])
+    if not after.strip():
+        return before, None
+    return before, after
diff --git a/src/roblox_viral/web/api_v1.py b/src/roblox_viral/web/api_v1.py
index 18a9220..503be56 100644
--- a/src/roblox_viral/web/api_v1.py
+++ b/src/roblox_viral/web/api_v1.py
@@ -226,12 +226,40 @@ def download_video(
     path = (settings.outputs_dir / safe).resolve()
     if not path.is_relative_to(settings.outputs_dir.resolve()) or not path.is_file():
         raise HTTPException(status_code=404, detail="Output file missing")
     return FileResponse(path, media_type="video/mp4", filename=safe)
 
 
+@router.get("/videos/{video_id}/download-b")
+def download_video_b(
+    video_id: str,
+    request: Request,
+    _: None = Depends(require_api_key),
+) -> FileResponse:
+    settings = request.app.state.settings
+    mgr: JobManager = request.app.state.job_manager
+    record = mgr.get(video_id, settings)
+    if record is None:
+        raise HTTPException(status_code=404, detail="Video not found")
+    if record.status == "error":
+        raise HTTPException(
+            status_code=422, detail=record.error or "Render failed"
+        )
+    if record.status != "done":
+        raise HTTPException(status_code=409, detail="Video not ready")
+    if not record.output_name_b:
+        raise HTTPException(status_code=404, detail="Part B not found")
+    safe = Path(record.output_name_b).name
+    if safe != record.output_name_b:
+        raise HTTPException(status_code=400, detail="Invalid output name")
+    path = (settings.outputs_dir / safe).resolve()
+    if not path.is_relative_to(settings.outputs_dir.resolve()) or not path.is_file():
+        raise HTTPException(status_code=404, detail="Output file missing")
+    return FileResponse(path, media_type="video/mp4", filename=safe)
+
+
 @router.get("/videos/{video_id}/cover")
 def download_cover(
     video_id: str,
     request: Request,
     _: None = Depends(require_api_key),
 ) -> FileResponse:
diff --git a/src/roblox_viral/web/jobs.py b/src/roblox_viral/web/jobs.py
index d779eec..aff3866 100644
--- a/src/roblox_viral/web/jobs.py
+++ b/src/roblox_viral/web/jobs.py
@@ -9,12 +9,13 @@ from datetime import datetime, timezone
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
@@ -93,12 +94,13 @@ class JobRecord:
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
 
@@ -151,17 +153,22 @@ class JobManager:
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
@@ -218,12 +225,13 @@ class JobManager:
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
@@ -256,156 +264,203 @@ class JobManager:
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
diff --git a/src/roblox_viral/web/static/app.js b/src/roblox_viral/web/static/app.js
index 3c33749..ecd2913 100644
--- a/src/roblox_viral/web/static/app.js
+++ b/src/roblox_viral/web/static/app.js
@@ -191,12 +191,13 @@
 
   const statusEl = document.getElementById("status");
   const errorEl = document.getElementById("error");
   const resultEl = document.getElementById("result");
   const player = document.getElementById("player");
   const download = document.getElementById("download");
+  const downloadB = document.getElementById("download-b");
   const downloadCard = document.getElementById("download-card");
 
   let pollTimer = null;
 
   function setStatus(text) {
     statusEl.textContent = text;
@@ -216,18 +217,30 @@
     if (pollTimer !== null) {
       clearInterval(pollTimer);
       pollTimer = null;
     }
   }
 
-  function showResult(outputName, titleCardName) {
+  function showResult(outputName, titleCardName, outputNameB) {
     const url = `/media/outputs/${encodeURIComponent(outputName)}`;
     resultEl.hidden = false;
     player.src = url;
     download.href = url;
     download.download = outputName;
+    if (downloadB) {
+      if (outputNameB) {
+        const bUrl = `/media/outputs/${encodeURIComponent(outputNameB)}`;
+        downloadB.hidden = false;
+        downloadB.href = bUrl;
+        downloadB.download = outputNameB;
+      } else {
+        downloadB.hidden = true;
+        downloadB.removeAttribute("href");
+        downloadB.removeAttribute("download");
+      }
+    }
     if (downloadCard) {
       if (titleCardName) {
         const cardUrl = `/media/outputs/${encodeURIComponent(titleCardName)}`;
         downloadCard.hidden = false;
         downloadCard.href = cardUrl;
         downloadCard.download = titleCardName;
@@ -287,13 +300,17 @@
     const job = await res.json();
     setStatus(job.status);
     if (job.status === "done") {
       stopPolling();
       syncGenerateEnabled();
       if (job.output_name) {
-        showResult(job.output_name, job.title_card_name || null);
+        showResult(
+          job.output_name,
+          job.title_card_name || null,
+          job.output_name_b || null
+        );
       }
       return;
     }
     if (job.status === "error") {
       stopPolling();
       syncGenerateEnabled();
diff --git a/src/roblox_viral/web/templates/generate.html b/src/roblox_viral/web/templates/generate.html
index 1d5fbc2..ab11c44 100644
--- a/src/roblox_viral/web/templates/generate.html
+++ b/src/roblox_viral/web/templates/generate.html
@@ -48,12 +48,13 @@
     <div id="reddit-source-block" role="tabpanel" aria-labelledby="tab-reddit" hidden>
       <p>Uses random clips from Library ΓåÆ Videos</p>
     </div>
 
     <p id="reddit-hook-hint" hidden>
       For Reddit, the first story line must be <code>phrase - phrase</code> (exactly one <code>-</code>).
+      Optionally add a line <code>BREAK</code> on its own, then a second story (no title card or cover on Part B).
     </p>
     <label>
       Story
       <textarea id="story" name="story" rows="10" required aria-describedby="reddit-hook-hint" placeholder="One sentence per line."></textarea>
     </label>
     <div class="story-actions">
@@ -119,12 +120,13 @@
   </section>
 
   <section class="result" id="result" hidden>
     <video id="player" controls playsinline></video>
     <p>
       <a id="download" href="#" download>Download MP4</a>
+      <a id="download-b" href="#" download hidden>Download part B</a>
       <a id="download-card" href="#" download hidden>Download title card</a>
     </p>
   </section>
 
   <section class="recent-outputs">
     <h2>Recent outputs</h2>
diff --git a/tests/test_reddit_break.py b/tests/test_reddit_break.py
new file mode 100644
index 0000000..3dea83f
--- /dev/null
+++ b/tests/test_reddit_break.py
@@ -0,0 +1,48 @@
+from roblox_viral.reddit_break import split_reddit_story
+
+
+def test_no_break_returns_full_story():
+    story = "Hook - line\nSecond sentence.\n"
+    a, b = split_reddit_story(story)
+    assert a == story
+    assert b is None
+
+
+def test_break_splits_parts():
+    story = "Hook - top\nMore A.\nBREAK\nPart B starts.\nMore B.\n"
+    a, b = split_reddit_story(story)
+    assert "BREAK" not in a
+    assert "BREAK" not in (b or "")
+    assert a.strip().startswith("Hook")
+    assert "More A." in a
+    assert b is not None
+    assert "Part B starts." in b
+    assert "More B." in b
+
+
+def test_break_empty_after_means_no_b():
+    story = "Hook - only\n\nBREAK\n\n"
+    a, b = split_reddit_story(story)
+    assert "Hook" in a
+    assert b is None
+
+
+def test_break_must_be_own_line_exact():
+    # Word inside a sentence is NOT a split
+    story = "Do not BREAK mid line\nNext.\n"
+    a, b = split_reddit_story(story)
+    assert b is None
+    assert "Do not BREAK mid line" in a
+
+
+def test_break_case_sensitive():
+    story = "Hook - a\nbreak\nPart B.\n"
+    a, b = split_reddit_story(story)
+    assert b is None  # lowercase 'break' is not the token
+
+
+def test_break_with_surrounding_spaces_on_line():
+    story = "Hook - a\n  BREAK  \nAfter.\n"
+    a, b = split_reddit_story(story)
+    assert b is not None
+    assert "After." in b
diff --git a/tests/web/test_api.py b/tests/web/test_api.py
index 0459076..2bc2118 100644
--- a/tests/web/test_api.py
+++ b/tests/web/test_api.py
@@ -241,12 +241,25 @@ def test_generate_page_has_hidden_title_card_download(tmp_path, monkeypatch):
     r = c.get("/")
     assert r.status_code == 200
     assert 'id="download-card"' in r.text
     assert "Download title card" in r.text
 
 
+def test_generate_page_has_hidden_part_b_download(tmp_path, monkeypatch):
+    async def fake_voices():
+        return [VoiceInfo("en-US-EmmaNeural", "en-US", "Female")]
+
+    monkeypatch.setattr("roblox_viral.web.app.list_english_voices", fake_voices)
+    c = _client(tmp_path, monkeypatch)
+    _login(c)
+    r = c.get("/")
+    assert r.status_code == 200
+    assert 'id="download-b"' in r.text
+    assert "Download part B" in r.text
+
+
 def test_generate_page_has_tts_provider_toggle(tmp_path, monkeypatch):
     async def fake_voices():
         return [VoiceInfo("en-US-EmmaNeural", "en-US", "Female")]
 
     monkeypatch.setattr("roblox_viral.web.app.list_english_voices", fake_voices)
     c = _client(tmp_path, monkeypatch)
@@ -402,12 +415,13 @@ def test_generate_page_has_three_mode_tab_controls(tmp_path, monkeypatch):
     assert 'data-mode="reddit"' in r.text
     assert "Single background video" in r.text
     assert "Uses random clips from Library ΓåÆ Videos" in r.text
     assert 'id="reddit-hook-hint"' in r.text
     assert "first story line must be" in r.text.lower()
     assert "phrase - phrase" in r.text
+    assert "BREAK" in r.text
     assert 'id="tab-roblox"' not in r.text
     assert 'data-mode="roblox"' not in r.text
     assert ">Roblox</button>" not in r.text
     assert 'id="image_name"' in r.text
     assert "still.jpg" in r.text
     assert 'id="ken_burns"' in r.text
diff --git a/tests/web/test_api_v1.py b/tests/web/test_api_v1.py
index 985419c..928ceaa 100644
--- a/tests/web/test_api_v1.py
+++ b/tests/web/test_api_v1.py
@@ -598,12 +598,99 @@ def test_download_unknown_404(tmp_path, monkeypatch):
         "/api/v1/videos/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/download",
         headers=_headers(),
     )
     assert r.status_code == 404
 
 
+def test_download_b_404_when_no_part_b(tmp_path, monkeypatch):
+    c = _client(tmp_path, monkeypatch)
+    settings = c.app.state.settings
+    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")
+    mgr: JobManager = c.app.state.job_manager
+    rec = mgr.create(
+        settings, "clip.mp4", "Hi.\n", "en-US-EmmaNeural", mode="single"
+    )
+    rec.status = "done"
+    rec.output_name = f"{rec.id}.mp4"
+    (settings.outputs_dir / rec.output_name).write_bytes(b"mp4")
+    with mgr._lock:
+        mgr._active_id = None
+    r = c.get(f"/api/v1/videos/{rec.id}/download-b", headers=_headers())
+    assert r.status_code == 404
+    assert r.json()["detail"] == "Part B not found"
+
+
+def test_download_b_returns_part_b_file(tmp_path, monkeypatch):
+    c = _client(tmp_path, monkeypatch)
+    settings = c.app.state.settings
+    settings.videos_dir.mkdir(parents=True, exist_ok=True)
+    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")
+
+    def fake_run(self, settings, job_id):
+        rec = self.get(job_id)
+        rec.status = "done"
+        rec.output_name = f"{job_id}.mp4"
+        rec.output_name_b = f"{job_id}-b.mp4"
+        settings.outputs_dir.mkdir(parents=True, exist_ok=True)
+        (settings.outputs_dir / rec.output_name).write_bytes(b"part-a")
+        (settings.outputs_dir / rec.output_name_b).write_bytes(b"part-b")
+        with self._lock:
+            if self._active_id == job_id:
+                self._active_id = None
+
+    monkeypatch.setattr(JobManager, "run_job", fake_run)
+    job_id = c.post(
+        "/api/v1/videos",
+        headers=_headers(),
+        data={
+            "voice": "en-US-EmmaNeural",
+            "story": "Top - Bottom.\nBREAK\nSecond part.\n",
+            "type": "reddit",
+        },
+    ).json()["id"]
+    r = c.get(f"/api/v1/videos/{job_id}/download-b", headers=_headers())
+    assert r.status_code == 200
+    assert r.content == b"part-b"
+    assert r.headers.get("content-type", "").startswith("video/")
+
+
+def test_get_video_includes_output_name_b(tmp_path, monkeypatch):
+    c = _client(tmp_path, monkeypatch)
+    settings = c.app.state.settings
+    settings.videos_dir.mkdir(parents=True, exist_ok=True)
+    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")
+
+    def fake_run(self, settings, job_id):
+        rec = self.get(job_id)
+        rec.status = "done"
+        rec.output_name = f"{job_id}.mp4"
+        rec.output_name_b = f"{job_id}-b.mp4"
+        settings.outputs_dir.mkdir(parents=True, exist_ok=True)
+        (settings.outputs_dir / rec.output_name).write_bytes(b"part-a")
+        (settings.outputs_dir / rec.output_name_b).write_bytes(b"part-b")
+        with self._lock:
+            if self._active_id == job_id:
+                self._active_id = None
+
+    monkeypatch.setattr(JobManager, "run_job", fake_run)
+    job_id = c.post(
+        "/api/v1/videos",
+        headers=_headers(),
+        data={
+            "voice": "en-US-EmmaNeural",
+            "story": "Top - Bottom.\nBREAK\nSecond part.\n",
+            "type": "reddit",
+        },
+    ).json()["id"]
+    st = c.get(f"/api/v1/videos/{job_id}", headers=_headers())
+    assert st.status_code == 200
+    body = st.json()
+    assert "output_name_b" in body
+    assert body["output_name_b"] == f"{job_id}-b.mp4"
+
+
 def test_create_reddit_rejects_story_without_hook_dash(tmp_path, monkeypatch):
     c = _client(tmp_path, monkeypatch)
     settings = c.app.state.settings
     settings.videos_dir.mkdir(parents=True, exist_ok=True)
     (settings.videos_dir / "bg.mp4").write_bytes(b"vid")
     r = c.post(
diff --git a/tests/web/test_jobs.py b/tests/web/test_jobs.py
index 801f3c4..be1ac8c 100644
--- a/tests/web/test_jobs.py
+++ b/tests/web/test_jobs.py
@@ -1148,12 +1148,132 @@ def test_run_job_edge_still_passes_configured_video_speed(tmp_path, monkeypatch)
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
