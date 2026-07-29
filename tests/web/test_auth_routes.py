from fastapi.testclient import TestClient
from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings


def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    app = create_app(Settings.from_env())
    return TestClient(app)


def test_generate_requires_login(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "/login" in r.headers["location"]


def test_login_success(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.post("/login", data={"password": "s3cret"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert c.get("/").status_code == 200
