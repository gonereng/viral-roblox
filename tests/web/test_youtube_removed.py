from fastapi.testclient import TestClient

from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings


def test_youtube_endpoint_gone(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    client = TestClient(create_app(Settings.from_env()))
    login = client.post(
        "/login",
        data={"password": "s3cret"},
        follow_redirects=False,
    )
    assert login.status_code in (302, 303)

    response = client.post(
        "/api/library/youtube",
        json={"url": "https://youtu.be/x", "name": "a"},
    )

    assert response.status_code == 404
