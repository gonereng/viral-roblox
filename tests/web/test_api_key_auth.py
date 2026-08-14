from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from roblox_viral.web.auth import require_api_key
from roblox_viral.web.config import Settings


def _app(settings: Settings) -> TestClient:
    app = FastAPI()
    app.state.settings = settings

    @app.get("/probe")
    async def probe(_: None = Depends(require_api_key)):
        return {"ok": True}

    return TestClient(app)


def test_require_api_key_503_when_unset(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "x")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("API_KEY", raising=False)
    s = Settings.from_env()
    c = _app(s)
    r = c.get("/probe", headers={"X-API-Key": "anything"})
    assert r.status_code == 503


def test_require_api_key_401_and_200(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "x")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("API_KEY", "good")
    s = Settings.from_env()
    c = _app(s)
    assert c.get("/probe").status_code == 401
    assert c.get("/probe", headers={"X-API-Key": "bad"}).status_code == 401
    assert c.get("/probe", headers={"X-API-Key": "good"}).status_code == 200
