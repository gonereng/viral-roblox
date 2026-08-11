from fastapi.testclient import TestClient

from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings
from roblox_viral.web.jobs import JobManager
from roblox_viral.web.voices import VoiceInfo, clear_cache


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    clear_cache()
    app = create_app(Settings.from_env())
    return TestClient(app)


def _login(c: TestClient) -> None:
    r = c.post("/login", data={"password": "s3cret"}, follow_redirects=False)
    assert r.status_code in (302, 303)


def _seed_source(c: TestClient, name: str = "clip.mp4", data: bytes = b"abc") -> None:
    settings = c.app.state.settings
    settings.sources_dir.mkdir(parents=True, exist_ok=True)
    (settings.sources_dir / name).write_bytes(data)


def test_api_jobs_require_auth(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post(
        "/api/jobs",
        json={"source_name": "clip.mp4", "story": "Hi.\n", "voice": "en-US-EmmaNeural"},
    )
    assert r.status_code == 401


def test_create_job_and_poll(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    _seed_source(c)

    def fake_run_job(self: JobManager, settings: Settings, job_id: str) -> None:
        record = self.get(job_id)
        assert record is not None
        record.output_name = f"{job_id}.mp4"
        out = settings.outputs_dir / record.output_name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake-mp4")
        record.status = "done"
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run_job)

    r = c.post(
        "/api/jobs",
        json={
            "source_name": "clip.mp4",
            "story": "Hi there.\n",
            "voice": "en-US-EmmaNeural",
        },
    )
    assert r.status_code == 200
    body = r.json()
    job_id = body["id"]
    assert body["status"] == "queued"

    # TestClient runs BackgroundTasks before returning; GET should be done.
    polled = c.get(f"/api/jobs/{job_id}")
    assert polled.status_code == 200
    data = polled.json()
    assert data["id"] == job_id
    assert data["status"] == "done"
    assert data["output_name"] == f"{job_id}.mp4"
    assert data["error"] is None


def test_create_job_busy_returns_409(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    _seed_source(c)
    settings = c.app.state.settings
    mgr: JobManager = c.app.state.job_manager
    mgr.create(settings, "clip.mp4", "First story.\n", "en-US-EmmaNeural")

    r = c.post(
        "/api/jobs",
        json={
            "source_name": "clip.mp4",
            "story": "Second story.\n",
            "voice": "en-US-EmmaNeural",
        },
    )
    assert r.status_code == 409


def test_get_job_not_found(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    r = c.get("/api/jobs/does-not-exist")
    assert r.status_code == 404


def test_create_job_invalid_json_returns_400(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    r = c.post(
        "/api/jobs",
        content=b"{not-json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400
    assert "Invalid JSON" in r.json()["detail"]


def test_get_job_hydrates_from_disk(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    _seed_source(c)
    settings = c.app.state.settings
    mgr: JobManager = c.app.state.job_manager
    job = mgr.create(settings, "clip.mp4", "Persist me.\n", "en-US-EmmaNeural")
    # Simulate process restart: empty memory, status.json still on disk
    c.app.state.job_manager = JobManager()

    r = c.get(f"/api/jobs/{job.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == job.id
    assert data["status"] == "queued"
    assert data["source_name"] == "clip.mp4"


def test_library_upload_rejects_oversize(tmp_path, monkeypatch):
    from roblox_viral.web import library

    monkeypatch.setattr(library, "MAX_UPLOAD_BYTES", 100)

    c = _client(tmp_path, monkeypatch)
    _login(c)
    upload = c.post(
        "/library/upload",
        files={"file": ("clip.mp4", b"x" * 150, "video/mp4")},
        follow_redirects=False,
    )
    assert upload.status_code == 400
    assert "maximum size" in upload.text.lower() or "exceeds" in upload.text.lower()


def test_library_upload_list_delete(tmp_path, monkeypatch):
    from roblox_viral.web.library import SourceVideo

    def fake_save(settings, filename, data):
        name = "clip-1.mp4"
        path = settings.sources_dir / name
        path.write_bytes(data)
        return [SourceVideo(name, path, path.stat().st_size)]

    monkeypatch.setattr(
        "roblox_viral.web.app.save_upload",
        fake_save,
    )

    c = _client(tmp_path, monkeypatch)
    _login(c)

    upload = c.post(
        "/library/upload",
        files={"file": ("clip.mp4", b"fake-bytes", "video/mp4")},
        follow_redirects=False,
    )
    assert upload.status_code == 200
    assert "clip-1.mp4" in upload.text

    page = c.get("/library")
    assert page.status_code == 200
    assert "clip-1.mp4" in page.text

    deleted = c.post(
        "/library/delete",
        data={"name": "clip-1.mp4"},
        follow_redirects=False,
    )
    assert deleted.status_code in (302, 303)
    assert "clip-1.mp4" not in c.get("/library").text


def test_media_output_requires_auth_and_serves_file(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    (settings.outputs_dir / "out.mp4").write_bytes(b"video-bytes")

    unauth = c.get("/media/outputs/out.mp4", follow_redirects=False)
    assert unauth.status_code in (302, 303, 401)

    _login(c)
    r = c.get("/media/outputs/out.mp4")
    assert r.status_code == 200
    assert r.content == b"video-bytes"


def test_generate_page_lists_recent_outputs(tmp_path, monkeypatch):
    async def fake_voices():
        return [VoiceInfo("en-US-EmmaNeural", "en-US", "Female")]

    monkeypatch.setattr(
        "roblox_viral.web.app.list_english_voices", fake_voices
    )
    c = _client(tmp_path, monkeypatch)
    _login(c)
    settings = c.app.state.settings
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    (settings.outputs_dir / "older.mp4").write_bytes(b"old")
    (settings.outputs_dir / "newer.mp4").write_bytes(b"new")

    r = c.get("/")
    assert r.status_code == 200
    assert "Recent outputs" in r.text
    assert "older.mp4" in r.text
    assert "newer.mp4" in r.text
    assert "/media/outputs/newer.mp4" in r.text


def test_create_job_accepts_pitch_and_speed(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    _seed_source(c)

    def fake_run_job(self: JobManager, settings: Settings, job_id: str) -> None:
        record = self.get(job_id)
        assert record is not None
        record.output_name = f"{job_id}.mp4"
        out = settings.outputs_dir / record.output_name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake-mp4")
        record.status = "done"
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run_job)

    r = c.post(
        "/api/jobs",
        json={
            "source_name": "clip.mp4",
            "story": "Hi.\n",
            "voice": "en-US-EmmaNeural",
            "pitch": 15,
            "speed": 130,
        },
    )
    assert r.status_code == 200


def test_create_job_rejects_bad_pitch(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    _seed_source(c)

    r = c.post(
        "/api/jobs",
        json={
            "source_name": "clip.mp4",
            "story": "Hi.\n",
            "voice": "en-US-EmmaNeural",
            "pitch": 101,
            "speed": 130,
        },
    )
    assert r.status_code == 400


def test_generate_page_lists_sources_and_default_voice(tmp_path, monkeypatch):
    async def fake_voices():
        return [
            VoiceInfo("en-US-EmmaNeural", "en-US", "Female"),
            VoiceInfo("en-GB-SoniaNeural", "en-GB", "Female"),
        ]

    monkeypatch.setattr(
        "roblox_viral.web.app.list_english_voices", fake_voices
    )
    c = _client(tmp_path, monkeypatch)
    _login(c)
    _seed_source(c)

    r = c.get("/")
    assert r.status_code == 200
    assert "clip.mp4" in r.text
    assert "en-US-EmmaNeural" in r.text
    assert 'selected' in r.text.lower() or "Emma" in r.text
