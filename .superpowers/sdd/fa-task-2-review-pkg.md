# Review package Task 2
BASE: 21e53d16713621eed622d2e18bfdbce355c6b144
HEAD: 45371505f5f1ca266d73fa6b74324c7f6c3dae9d

## Commits

4537150 feat(web): wire whisper align language/model settings

## Diff stat

 README.md                      | 10 +++++++--
 docker-compose.yml             |  3 +++
 src/roblox_viral/web/config.py |  8 ++++++++
 src/roblox_viral/web/jobs.py   |  2 ++
 tests/web/test_config.py       | 22 ++++++++++++++++++++
 tests/web/test_jobs.py         | 46 +++++++++++++++++++++++++++++++++++++++++-
 6 files changed, 88 insertions(+), 3 deletions(-)

## Full diff

diff --git a/README.md b/README.md
index 98f521a..2aab00b 100644
--- a/README.md
+++ b/README.md
@@ -95,33 +95,35 @@ uvicorn roblox_viral.web.app:create_app --factory --reload
 
 Open http://127.0.0.1:8000, log in with `APP_PASSWORD`, upload media in **Library**, then use **Generate**.
 
 Optional env vars:
 
 | Variable | Description |
 |----------|-------------|
 | `MEDIA_ROOT` | Upload/output directory (default: `./media`) |
 | `APP_PASSWORD` | Login password (required unless `APP_REQUIRE_PASSWORD=0`) |
 | `APP_SECRET` | Session signing key (random ephemeral value if unset) |
-| `GEMINI_API_KEY` | Google Gemini API key used by **Generate story** |
+| `GEMINI_API_KEY` | Google Gemini API key used by **Generate story** and Gemini TTS |
+| `WHISPER_ALIGN_LANGUAGE` | Language code for stable-ts force-align on Gemini karaoke captions (default: `de`) |
+| `WHISPER_ALIGN_MODEL` | Whisper model size for Gemini force-align (default: `base`; e.g. `small`, `medium`) |
 | `API_KEY` | Shared secret for `/api/v1/videos*` (`X-API-Key`). Required for n8n integration. |
 | `OVERLAY_VIDEO` | Optional path to a greenscreen MP4. If unset, uses `MEDIA_ROOT/overlay.mp4` when present, otherwise the packaged `assets/overlay.mp4` shipped in the image. First 3.5s are chromakeyed, scaled to fit inside the full 1080├ù1920 frame, centered, and composited at the start of **Single** videos (audio ignored). |
 
 ### n8n API
 
 Set `API_KEY` in `.env`. Header: `X-API-Key`.
 
 **Create** ΓÇö `POST /api/v1/videos` as `multipart/form-data`:
 
 - `voice`, `story`, `type` (`single`|`reddit`|`leni`; `roblox` is rejected ΓÇö use `single`)
 - optional `pitch` (ΓêÆ100ΓÇª100, default 15), `speed` (50ΓÇª200, default 130), and `video_speed` (50ΓÇô200 for `single`/`leni`, 100ΓÇô500 for `reddit`; default 100)
-- optional `tts_provider` (`edge`|`gemini`, default `edge`). For `gemini`, set `voice` to a Gemini name (e.g. `Kore`); requires `GEMINI_API_KEY`. Pitch/speed apply to Edge only.
+- optional `tts_provider` (`edge`|`gemini`, default `edge`). For `gemini`, set `voice` to a Gemini name (e.g. `Kore`); requires `GEMINI_API_KEY`. Gemini karaoke uses stable-ts force-align (default language German). Pitch/speed apply to Edge only.
 - for `single`: optional `media` **or** `source_name` (Library Sources slice). If neither is sent, a random Sources clip is chosen. Do not send both.
 - for `leni`: either file field `media` **or** text field `source_name` (Library image name)
 - for `reddit`: story/voice/type only (background is built from the Library Videos pool; do not send `media` or `source_name`)
 
 Then poll `GET /api/v1/videos/{id}` and download `GET /api/v1/videos/{id}/download`; then download the cover with `GET /api/v1/videos/{id}/cover` (Reddit only; 404 for other types).
 
 PowerShell / Windows (upload via `curl.exe` ΓÇö works on PowerShell 5.1):
 
 ```powershell
 $apiKey = "your-key"
@@ -164,22 +166,26 @@ curl.exe -s -X POST "http://127.0.0.1:8000/api/v1/videos" `
 ```
 
 ### Docker
 
 Create a `.env` file (or export vars in your shell):
 
 ```bash
 APP_PASSWORD=your-password
 APP_SECRET=your-long-random-secret
 GEMINI_API_KEY=
+WHISPER_ALIGN_LANGUAGE=de
+WHISPER_ALIGN_MODEL=base
 ```
 
+The first Gemini TTS job may download the Whisper model into `media/.cache/huggingface` (persisted via the `./media` volume in Docker).
+
 Build and run:
 
 ```bash
 docker compose up --build
 ```
 
 The app listens on http://localhost:8000. Source videos, outputs, and job state persist in `./media` via a bind mount.
 
 ## Design
 
diff --git a/docker-compose.yml b/docker-compose.yml
index 48d3897..483ad7c 100644
--- a/docker-compose.yml
+++ b/docker-compose.yml
@@ -2,13 +2,16 @@ services:
   web:
     build: .
     ports:
       - "8000:8000"
     environment:
       APP_PASSWORD: ${APP_PASSWORD:?set APP_PASSWORD}
       APP_SECRET: ${APP_SECRET:?set APP_SECRET}
       MEDIA_ROOT: /app/media
       API_KEY: ${API_KEY:-}
       GEMINI_API_KEY: ${GEMINI_API_KEY:-}
+      WHISPER_ALIGN_LANGUAGE: ${WHISPER_ALIGN_LANGUAGE:-de}
+      WHISPER_ALIGN_MODEL: ${WHISPER_ALIGN_MODEL:-base}
+      HF_HOME: /app/media/.cache/huggingface
       YOUTUBE_COOKIES: ${YOUTUBE_COOKIES:-/app/media/youtube_cookies.txt}
     volumes:
       - ./media:/app/media
diff --git a/src/roblox_viral/web/config.py b/src/roblox_viral/web/config.py
index 1796746..b169a03 100644
--- a/src/roblox_viral/web/config.py
+++ b/src/roblox_viral/web/config.py
@@ -31,20 +31,22 @@ def resolve_overlay_video_path(
 
 @dataclass(frozen=True)
 class Settings:
     media_root: Path
     app_password: str
     app_secret: str
     require_password: bool = True
     gemini_api_key: str = ""
     overlay_video: str = ""
     api_key: str = ""
+    whisper_align_language: str = "de"
+    whisper_align_model: str = "base"
 
     @property
     def sources_dir(self) -> Path:
         return self.media_root / "sources"
 
     @property
     def videos_dir(self) -> Path:
         return self.media_root / "videos"
 
     @property
@@ -93,16 +95,22 @@ class Settings:
         overlay_video = os.environ.get("OVERLAY_VIDEO", "")
         api_key = os.environ.get("API_KEY", "")
         return cls(
             media_root=media,
             app_password=password,
             app_secret=secret,
             require_password=require,
             gemini_api_key=gemini_api_key,
             overlay_video=overlay_video,
             api_key=api_key,
+            whisper_align_language=(
+                os.environ.get("WHISPER_ALIGN_LANGUAGE", "de").strip() or "de"
+            ),
+            whisper_align_model=(
+                os.environ.get("WHISPER_ALIGN_MODEL", "base").strip() or "base"
+            ),
         )
 
 
 @lru_cache
 def get_settings() -> Settings:
     return Settings.from_env()
diff --git a/src/roblox_viral/web/jobs.py b/src/roblox_viral/web/jobs.py
index 9a32387..d779eec 100644
--- a/src/roblox_viral/web/jobs.py
+++ b/src/roblox_viral/web/jobs.py
@@ -269,20 +269,22 @@ class JobManager:
             ass_path = job_dir / "captions.ass"
             output_name = make_output_name(record.source_name or "reddit")
             output_path = settings.outputs_dir / output_name
 
             self._set_status(settings, record, "synthesizing")
             tts_text = join_for_tts(sentences)
             if record.tts_provider == "gemini":
                 words = GeminiTTSProvider(
                     settings.gemini_api_key,
                     record.voice,
+                    align_language=settings.whisper_align_language,
+                    align_model=settings.whisper_align_model,
                 ).synthesize(tts_text, narration_path)
             else:
                 words = EdgeTTSProvider(
                     record.voice,
                     rate=format_edge_rate(record.speed),
                     pitch=format_edge_pitch(record.pitch),
                 ).synthesize(tts_text, narration_path)
 
             self._set_status(settings, record, "captioning")
             write_ass(words, ass_path, sentences=sentences)
diff --git a/tests/web/test_config.py b/tests/web/test_config.py
index fc4bef2..738f235 100644
--- a/tests/web/test_config.py
+++ b/tests/web/test_config.py
@@ -50,20 +50,42 @@ def test_overlay_video_path_default_and_env(tmp_path: Path, monkeypatch):
 
 def test_api_key_from_env(tmp_path: Path, monkeypatch):
     monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
     monkeypatch.setenv("APP_PASSWORD", "secret")
     monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
     monkeypatch.setenv("API_KEY", "n8n-secret")
     settings = Settings.from_env()
     assert settings.api_key == "n8n-secret"
 
 
+def test_whisper_align_defaults(tmp_path: Path, monkeypatch):
+    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
+    monkeypatch.setenv("APP_PASSWORD", "secret")
+    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
+    monkeypatch.delenv("WHISPER_ALIGN_LANGUAGE", raising=False)
+    monkeypatch.delenv("WHISPER_ALIGN_MODEL", raising=False)
+    settings = Settings.from_env()
+    assert settings.whisper_align_language == "de"
+    assert settings.whisper_align_model == "base"
+
+
+def test_whisper_align_from_env(tmp_path: Path, monkeypatch):
+    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
+    monkeypatch.setenv("APP_PASSWORD", "secret")
+    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
+    monkeypatch.setenv("WHISPER_ALIGN_LANGUAGE", "en")
+    monkeypatch.setenv("WHISPER_ALIGN_MODEL", "small")
+    settings = Settings.from_env()
+    assert settings.whisper_align_language == "en"
+    assert settings.whisper_align_model == "small"
+
+
 def test_resolve_overlay_falls_back_to_packaged(tmp_path: Path, monkeypatch):
     from roblox_viral.web.config import resolve_overlay_video_path
 
     monkeypatch.delenv("OVERLAY_VIDEO", raising=False)
     media = tmp_path / "empty-media"
     media.mkdir()
     path = resolve_overlay_video_path(media_root=media, overlay_video="")
     assert path is not None
     assert path.is_file()
     assert path.name == "overlay.mp4"
diff --git a/tests/web/test_jobs.py b/tests/web/test_jobs.py
index 52286e9..801f3c4 100644
--- a/tests/web/test_jobs.py
+++ b/tests/web/test_jobs.py
@@ -514,31 +514,75 @@ def test_run_job_passes_video_speed_to_render(tmp_path, monkeypatch):
         "clip.mp4",
         "One line only here.\n",
         "en-US-EmmaNeural",
         video_speed=175,
     )
     mgr.run_job(s, job.id)
     assert seen["video_speed"] == 175
     assert mgr.get(job.id, s).status == "done"
 
 
+def test_run_job_gemini_passes_align_settings(tmp_path, monkeypatch):
+    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
+    monkeypatch.setenv("WHISPER_ALIGN_LANGUAGE", "en")
+    monkeypatch.setenv("WHISPER_ALIGN_MODEL", "small")
+    s = _settings(tmp_path, monkeypatch)
+    mgr = JobManager()
+    seen = {}
+
+    def fake_gemini_init(self, api_key, voice, *, align_fn=None, align_language="de", align_model="base"):
+        seen["align_language"] = align_language
+        seen["align_model"] = align_model
+        self.api_key = api_key
+        self.voice = voice
+        self._align_fn = align_fn
+
+    def fake_gemini_synth(self, text, output_path):
+        Path(output_path).write_bytes(b"mp3")
+        return [WordTiming("One", 0, 100)]
+
+    def fake_write_ass(words, ass_path, sentences=None):
+        Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")
+
+    def fake_render_video(**kwargs):
+        Path(kwargs["output_path"]).write_bytes(b"mp4")
+
+    monkeypatch.setattr(
+        "roblox_viral.web.jobs.GeminiTTSProvider.__init__", fake_gemini_init
+    )
+    monkeypatch.setattr(
+        "roblox_viral.web.jobs.GeminiTTSProvider.synthesize", fake_gemini_synth
+    )
+    monkeypatch.setattr("roblox_viral.web.jobs.write_ass", fake_write_ass)
+    monkeypatch.setattr("roblox_viral.web.jobs.render_video", fake_render_video)
+
+    job = mgr.create(
+        s, "clip.mp4", "One line only here.\n", "Kore", tts_provider="gemini"
+    )
+    mgr.run_job(s, job.id)
+    assert seen["align_language"] == "en"
+    assert seen["align_model"] == "small"
+    assert mgr.get(job.id, s).status == "done"
+
+
 def test_run_job_gemini_uses_gemini_provider(tmp_path, monkeypatch):
     monkeypatch.setenv("GEMINI_API_KEY", "test-key")
     s = _settings(tmp_path, monkeypatch)
     mgr = JobManager()
     seen = {}
 
-    def fake_gemini_init(self, api_key, voice, *, align_fn=None):
+    def fake_gemini_init(self, api_key, voice, *, align_fn=None, align_language="de", align_model="base"):
         seen["api_key"] = api_key
         seen["voice"] = voice
         self.api_key = api_key
         self.voice = voice
+        self._align_fn = align_fn
 
     def fake_gemini_synth(self, text, output_path):
         Path(output_path).write_bytes(b"mp3")
         return [WordTiming("One", 0, 100)]
 
     def boom_edge(*a, **k):
         raise AssertionError("EdgeTTS should not run for gemini jobs")
 
     def fake_write_ass(words, ass_path, sentences=None):
         Path(ass_path).write_text("[Script Info]\n", encoding="utf-8")
