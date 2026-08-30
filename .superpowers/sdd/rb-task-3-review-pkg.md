# Review package RB Task 3
BASE: f5400ee855dedea54fba1551cff54305fb1f441f
HEAD: 2229bfcbac9e63d3a7bd4d0d0c8cd7d96023eb53

## Commits

2229bfc feat(api): download-b and Generate UI for Reddit Part B

## Diff stat

 README.md                                    |  4 +-
 src/roblox_viral/web/api_v1.py               | 28 +++++++++
 src/roblox_viral/web/static/app.js           | 21 ++++++-
 src/roblox_viral/web/templates/generate.html |  2 +
 tests/web/test_api.py                        | 14 +++++
 tests/web/test_api_v1.py                     | 87 ++++++++++++++++++++++++++++
 6 files changed, 152 insertions(+), 4 deletions(-)

## Full diff

diff --git a/README.md b/README.md
index b25c2b8..15fb1a8 100644
--- a/README.md
+++ b/README.md
@@ -122,19 +122,19 @@ Set `API_KEY` in `.env`. Header: `X-API-Key`.
 
 **Create** ΓÇö `POST /api/v1/videos` as `multipart/form-data`:
 
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
 $video = "C:\path\to\clip.mp4"
 
diff --git a/src/roblox_viral/web/api_v1.py b/src/roblox_viral/web/api_v1.py
index 18a9220..503be56 100644
--- a/src/roblox_viral/web/api_v1.py
+++ b/src/roblox_viral/web/api_v1.py
@@ -224,16 +224,44 @@ def download_video(
     if safe != record.output_name:
         raise HTTPException(status_code=400, detail="Invalid output name")
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
     settings = request.app.state.settings
     mgr: JobManager = request.app.state.job_manager
diff --git a/src/roblox_viral/web/static/app.js b/src/roblox_viral/web/static/app.js
index 3c33749..ecd2913 100644
--- a/src/roblox_viral/web/static/app.js
+++ b/src/roblox_viral/web/static/app.js
@@ -189,16 +189,17 @@
   if (imageSelect) imageSelect.addEventListener("change", syncGenerateEnabled);
   syncGenerateEnabled();
 
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
   }
 
@@ -214,22 +215,34 @@
 
   function stopPolling() {
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
       } else {
         downloadCard.hidden = true;
@@ -285,17 +298,21 @@
       throw new Error(`Status request failed (${res.status})`);
     }
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
       showError(job.error || "Render failed");
     }
diff --git a/src/roblox_viral/web/templates/generate.html b/src/roblox_viral/web/templates/generate.html
index 1d5fbc2..ab11c44 100644
--- a/src/roblox_viral/web/templates/generate.html
+++ b/src/roblox_viral/web/templates/generate.html
@@ -46,16 +46,17 @@
     </div>
 
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
       <button id="generate-story-btn" type="button">Generate story</button>
       <p id="story-gen-error" class="error" hidden></p>
@@ -117,16 +118,17 @@
     <p>Status: <span id="status">idle</span></p>
     <p id="error" class="error" hidden></p>
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
     {% if recent_outputs %}
     <ul class="source-list">
diff --git a/tests/web/test_api.py b/tests/web/test_api.py
index 0459076..2bc2118 100644
--- a/tests/web/test_api.py
+++ b/tests/web/test_api.py
@@ -239,16 +239,29 @@ def test_generate_page_has_hidden_title_card_download(tmp_path, monkeypatch):
     c = _client(tmp_path, monkeypatch)
     _login(c)
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
     _login(c)
     r = c.get("/")
@@ -400,16 +413,17 @@ def test_generate_page_has_three_mode_tab_controls(tmp_path, monkeypatch):
     assert 'data-mode="single"' in r.text
     assert 'data-mode="picture"' in r.text
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
     assert 'id="image-file"' not in r.text
     assert 'id="image-upload-btn"' not in r.text
diff --git a/tests/web/test_api_v1.py b/tests/web/test_api_v1.py
index 985419c..928ceaa 100644
--- a/tests/web/test_api_v1.py
+++ b/tests/web/test_api_v1.py
@@ -596,16 +596,103 @@ def test_download_unknown_404(tmp_path, monkeypatch):
     c = _client(tmp_path, monkeypatch)
     r = c.get(
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
         "/api/v1/videos",
         headers=_headers(),
