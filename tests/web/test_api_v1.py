from fastapi.testclient import TestClient

from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings
from roblox_viral.web.jobs import JobManager
from roblox_viral.web.voices import clear_cache

API_KEY = "test-key"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("API_KEY", API_KEY)
    clear_cache()
    return TestClient(create_app(Settings.from_env()))


def _headers():
    return {"X-API-Key": API_KEY}


def test_create_single_video_returns_id(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        rec.status = "done"
        rec.output_name = f"{job_id}.mp4"
        out = settings.outputs_dir / rec.output_name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"mp4")
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hello world.\n",
            "type": "single",
            "source_name": "clip.mp4",
        },
    )
    assert r.status_code == 200
    job_id = r.json()["id"]
    assert job_id
    st = c.get(f"/api/v1/videos/{job_id}", headers=_headers())
    assert st.status_code == 200
    assert st.json()["status"] == "done"
    assert st.json()["mode"] == "single"


def test_create_leni_maps_to_picture(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    (settings.images_dir / "still.jpg").write_bytes(b"img")

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        rec.status = "done"
        rec.output_name = f"{job_id}.mp4"
        (settings.outputs_dir / rec.output_name).write_bytes(b"mp4")
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "leni",
            "source_name": "still.jpg",
        },
    )
    assert r.status_code == 200
    st = c.get(f"/api/v1/videos/{r.json()['id']}", headers=_headers())
    assert st.json()["mode"] == "picture"


def test_create_accepts_optional_pitch_and_speed(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")
    monkeypatch.setattr(JobManager, "run_job", lambda *a, **k: None)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
            "source_name": "clip.mp4",
            "pitch": "-20",
            "speed": "150",
        },
    )
    assert r.status_code == 200
    st = c.get(f"/api/v1/videos/{r.json()['id']}", headers=_headers())
    assert st.json()["pitch"] == -20
    assert st.json()["speed"] == 150


def test_create_defaults_pitch_and_speed(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")
    monkeypatch.setattr(JobManager, "run_job", lambda *a, **k: None)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
            "source_name": "clip.mp4",
        },
    )
    assert r.status_code == 200
    st = c.get(f"/api/v1/videos/{r.json()['id']}", headers=_headers())
    assert st.json()["pitch"] == 15
    assert st.json()["speed"] == 130
    assert st.json()["video_speed"] == 100


def test_create_accepts_video_speed(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")
    monkeypatch.setattr(JobManager, "run_job", lambda *a, **k: None)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
            "source_name": "clip.mp4",
            "video_speed": "160",
        },
    )
    assert r.status_code == 200
    st = c.get(f"/api/v1/videos/{r.json()['id']}", headers=_headers())
    assert st.json()["video_speed"] == 160


def test_create_resolves_source_video(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "raw.mp4").write_bytes(b"vid")
    monkeypatch.setattr(JobManager, "run_job", lambda *a, **k: None)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
            "source_name": "raw.mp4",
        },
    )
    assert r.status_code == 200


def test_create_invalid_video_speed_400(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
            "source_name": "clip.mp4",
            "video_speed": "9",
        },
    )
    assert r.status_code == 400


def test_create_invalid_pitch_400(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
            "source_name": "clip.mp4",
            "pitch": "999",
        },
    )
    assert r.status_code == 400


def test_create_bad_type_400(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "other",
            "source_name": "clip.mp4",
        },
    )
    assert r.status_code == 400


def test_create_roblox_type_400(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    (c.app.state.settings.sources_dir / "clip.mp4").write_bytes(b"vid")
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "roblox",
            "source_name": "clip.mp4",
        },
    )
    assert r.status_code == 400
    assert "single" in r.json()["detail"].lower()


def test_create_reddit_with_story_voice_type(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")
    monkeypatch.setattr(JobManager, "run_job", lambda *a, **k: None)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi - there.\n",
            "type": "reddit",
        },
    )
    assert r.status_code == 200
    st = c.get(f"/api/v1/videos/{r.json()['id']}", headers=_headers())
    assert st.json()["mode"] == "reddit"


def test_create_reddit_rejects_media(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi - there.\n",
            "type": "reddit",
        },
        files={"media": ("clip.mp4", b"x", "video/mp4")},
    )
    assert r.status_code == 400


def test_create_reddit_rejects_source_name(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    (settings.videos_dir / "bg.mp4").write_bytes(b"vid")
    monkeypatch.setattr(JobManager, "run_job", lambda *a, **k: None)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi - there.\n",
            "type": "reddit",
            "source_name": "clip.mp4",
        },
    )
    assert r.status_code == 400


def test_create_busy_409(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")
    mgr: JobManager = c.app.state.job_manager
    mgr._active_id = "busy"
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
            "source_name": "clip.mp4",
        },
    )
    assert r.status_code == 409


def test_create_with_media_upload_single(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        assert rec.ephemeral is True
        inp = settings.jobs_dir / job_id / rec.source_name
        assert inp.is_file()
        rec.status = "done"
        rec.output_name = f"{job_id}.mp4"
        (settings.outputs_dir / rec.output_name).write_bytes(b"mp4")
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
        },
        files={"media": ("clip.mp4", b"fake-video", "video/mp4")},
    )
    assert r.status_code == 200
    assert r.json()["id"]


def test_create_with_media_upload_leni(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        assert rec.mode == "picture"
        assert rec.ephemeral is True
        rec.status = "done"
        rec.output_name = f"{job_id}.mp4"
        (settings.outputs_dir / rec.output_name).write_bytes(b"mp4")
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "leni",
        },
        files={"media": ("still.jpg", b"fake-img", "image/jpeg")},
    )
    assert r.status_code == 200
    st = c.get(f"/api/v1/videos/{r.json()['id']}", headers=_headers())
    assert st.json()["mode"] == "picture"


def test_create_rejects_both_media_and_source_name(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    (c.app.state.settings.sources_dir / "clip.mp4").write_bytes(b"vid")
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
            "source_name": "clip.mp4",
        },
        files={"media": ("clip.mp4", b"x", "video/mp4")},
    )
    assert r.status_code == 400


def test_create_rejects_neither_media_nor_source(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
        },
    )
    assert r.status_code == 400


def test_create_rejects_image_for_single(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
        },
        files={"media": ("still.jpg", b"x", "image/jpeg")},
    )
    assert r.status_code == 400


def test_download_done_returns_mp4(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")

    def fake_run(self, settings, job_id):
        rec = self.get(job_id)
        rec.status = "done"
        rec.output_name = f"{job_id}.mp4"
        (settings.outputs_dir / rec.output_name).write_bytes(b"fake-mp4-bytes")
        with self._lock:
            if self._active_id == job_id:
                self._active_id = None

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    job_id = c.post(
        "/api/v1/videos",
        headers=_headers(),
        data={
            "voice": "en-US-EmmaNeural",
            "story": "Hi.\n",
            "type": "single",
            "source_name": "clip.mp4",
        },
    ).json()["id"]
    r = c.get(f"/api/v1/videos/{job_id}/download", headers=_headers())
    assert r.status_code == 200
    assert r.content == b"fake-mp4-bytes"
    assert "video/mp4" in r.headers.get("content-type", "")


def test_download_not_ready_409(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")

    def fake_run(self, settings, job_id):
        pass

    monkeypatch.setattr(JobManager, "run_job", fake_run)
    mgr: JobManager = c.app.state.job_manager
    rec = mgr.create(
        settings, "clip.mp4", "Hi.\n", "en-US-EmmaNeural", mode="single"
    )
    with mgr._lock:
        mgr._active_id = None
    r = c.get(f"/api/v1/videos/{rec.id}/download", headers=_headers())
    assert r.status_code == 409


def test_download_error_422(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    settings = c.app.state.settings
    (settings.sources_dir / "clip.mp4").write_bytes(b"vid")
    mgr: JobManager = c.app.state.job_manager
    rec = mgr.create(
        settings, "clip.mp4", "Hi.\n", "en-US-EmmaNeural", mode="single"
    )
    rec.status = "error"
    rec.error = "boom"
    with mgr._lock:
        mgr._active_id = None
    r = c.get(f"/api/v1/videos/{rec.id}/download", headers=_headers())
    assert r.status_code == 422


def test_download_unknown_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get(
        "/api/v1/videos/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/download",
        headers=_headers(),
    )
    assert r.status_code == 404
