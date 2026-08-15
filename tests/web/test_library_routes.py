from fastapi.testclient import TestClient

from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    return TestClient(create_app(Settings.from_env()))


def _login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"password": "s3cret"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)


def test_library_raw_video_upload_keeps_videos_tab(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _login(client)

    response = client.post(
        "/library/videos/upload",
        files={"file": ("clip.mp4", b"data", "video/mp4")},
    )

    assert response.status_code == 200
    assert (client.app.state.settings.videos_dir / "clip.mp4").is_file()
    assert 'id="tab-videos"' in response.text
    assert 'aria-selected="true"' in response.text[
        response.text.index('id="tab-videos"') :
    ][:200]


def test_library_raw_video_delete_keeps_videos_tab(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _login(client)
    video = client.app.state.settings.videos_dir / "clip.mp4"
    video.write_bytes(b"data")

    response = client.post(
        "/library/videos/delete",
        data={"name": "clip.mp4"},
    )

    assert response.status_code == 200
    assert not video.exists()
    assert 'id="tab-videos"' in response.text
    assert 'aria-selected="true"' in response.text[
        response.text.index('id="tab-videos"') :
    ][:200]


def test_library_page_has_three_tabs_and_media_lists(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _login(client)
    settings = client.app.state.settings
    (settings.sources_dir / "slice-1.mp4").write_bytes(b"slice")
    (settings.videos_dir / "video.mp4").write_bytes(b"video")
    (settings.images_dir / "image.jpg").write_bytes(b"image")

    response = client.get("/library")

    assert response.status_code == 200
    assert "YouTube" not in response.text
    assert "1-minute clips" in response.text
    assert "Videos" in response.text
    assert "Images" in response.text
    assert "slice-1.mp4" in response.text
    assert "video.mp4" in response.text
    assert "image.jpg" in response.text
    assert 'src="/static/library.js"' in response.text
