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
        files=[("files", ("clip.mp4", b"data", "video/mp4"))],
    )

    assert response.status_code == 200
    assert (client.app.state.settings.videos_dir / "clip.mp4").is_file()
    assert 'id="tab-videos"' in response.text
    assert 'aria-selected="true"' in response.text[
        response.text.index('id="tab-videos"') :
    ][:200]


def test_library_raw_video_multi_upload(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _login(client)

    response = client.post(
        "/library/videos/upload",
        files=[
            ("files", ("a (1).mp4", b"one", "video/mp4")),
            ("files", ("b.mp4", b"two", "video/mp4")),
        ],
    )

    assert response.status_code == 200
    settings = client.app.state.settings
    assert (settings.videos_dir / "a (1).mp4").read_bytes() == b"one"
    assert (settings.videos_dir / "b.mp4").read_bytes() == b"two"
    assert "Uploaded 2 video" in response.text


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


def test_media_library_routes_require_auth_and_serve(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    settings = client.app.state.settings
    settings.sources_dir.mkdir(parents=True, exist_ok=True)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    (settings.sources_dir / "slice.mp4").write_bytes(b"slice-bytes")
    (settings.videos_dir / "raw.mp4").write_bytes(b"raw-bytes")
    (settings.images_dir / "pic.png").write_bytes(b"png-bytes")

    for url in (
        "/media/sources/slice.mp4",
        "/media/videos/raw.mp4",
        "/media/images/pic.png",
    ):
        unauth = client.get(url, follow_redirects=False)
        assert unauth.status_code in (302, 303, 401)

    _login(client)
    assert client.get("/media/sources/slice.mp4").content == b"slice-bytes"
    assert client.get("/media/videos/raw.mp4").content == b"raw-bytes"
    img = client.get("/media/images/pic.png")
    assert img.status_code == 200
    assert img.content == b"png-bytes"
    assert "image/png" in img.headers.get("content-type", "")


def test_media_library_routes_404_and_400(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _login(client)
    assert client.get("/media/videos/missing.mp4").status_code == 404
    assert client.get("/media/sources/not!!valid.mp4").status_code == 400
    assert client.get("/media/images/not-a-path.jpg").status_code == 404


def test_library_page_embeds_inline_previews(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _login(client)
    settings = client.app.state.settings
    settings.sources_dir.mkdir(parents=True, exist_ok=True)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    (settings.sources_dir / "slice.mp4").write_bytes(b"s")
    (settings.videos_dir / "raw.mp4").write_bytes(b"v")
    (settings.images_dir / "pic.png").write_bytes(b"i")

    page = client.get("/library")
    assert page.status_code == 200
    assert 'preload="none"' in page.text
    assert 'src="/media/sources/slice.mp4"' in page.text
    assert 'src="/media/videos/raw.mp4"' in page.text

    images = client.get("/library?tab=images")
    assert 'src="/media/images/pic.png"' in images.text
    assert 'loading="lazy"' in images.text
