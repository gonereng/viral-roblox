from pathlib import Path

from fastapi.testclient import TestClient

from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings
from roblox_viral.web.library import SourceVideo


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    return TestClient(create_app(Settings.from_env()))


def _login(c: TestClient) -> None:
    r = c.post("/login", data={"password": "s3cret"}, follow_redirects=False)
    assert r.status_code in (302, 303)


def test_youtube_import_requires_auth(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert (
        c.post(
            "/api/library/youtube",
            json={"url": "https://youtu.be/dQw4w9WgXcQ", "name": "clip"},
        ).status_code
        == 401
    )


def test_youtube_import_rejects_bad_name(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    r = c.post(
        "/api/library/youtube",
        json={"url": "https://youtu.be/dQw4w9WgXcQ", "name": "bad.mp4"},
    )
    assert r.status_code == 400


def test_youtube_import_success(tmp_path, monkeypatch):
    def fake_download(url: str, dest: Path) -> Path:
        dest.write_bytes(b"vid")
        return dest

    def fake_slice(settings, uploaded_path, base_stem):
        name = f"{base_stem}-1.mp4"
        path = settings.sources_dir / name
        path.write_bytes(b"slice")
        return [SourceVideo(name, path, 5)]

    monkeypatch.setattr("roblox_viral.web.jobs.download_youtube", fake_download)
    monkeypatch.setattr(
        "roblox_viral.web.jobs.slice_into_minute_parts", fake_slice
    )

    c = _client(tmp_path, monkeypatch)
    _login(c)
    r = c.post(
        "/api/library/youtube",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "name": "gameplay",
        },
    )
    assert r.status_code == 200
    job_id = r.json()["id"]
    status = c.get(f"/api/jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "done"
    assert body["created_slices"] == ["gameplay-1.mp4"]
