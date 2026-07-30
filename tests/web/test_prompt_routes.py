from fastapi.testclient import TestClient

from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings
from roblox_viral.web.prompt import DEFAULT_PROMPT, load_prompt


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return TestClient(create_app(Settings.from_env()))


def _login(c: TestClient) -> None:
    r = c.post("/login", data={"password": "s3cret"}, follow_redirects=False)
    assert r.status_code in (302, 303)


def test_prompt_requires_auth(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/prompt", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "/login" in r.headers["location"]


def test_prompt_get_shows_default(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    r = c.get("/prompt")
    assert r.status_code == 200
    assert "Prompt" in r.text
    assert "Write a short Roblox" in r.text or DEFAULT_PROMPT.split("\n")[0] in r.text


def test_prompt_save_persists(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    r = c.post(
        "/prompt",
        data={"prompt": "Only this prompt.\nOne sentence per line."},
    )
    assert r.status_code == 200
    assert "saved" in r.text.lower()
    settings = c.app.state.settings
    assert load_prompt(settings) == "Only this prompt.\nOne sentence per line."
