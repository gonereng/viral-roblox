from fastapi.testclient import TestClient

from roblox_viral.web.app import create_app
from roblox_viral.web.config import Settings
from roblox_viral.web.prompt import save_prompt


def _client(tmp_path, monkeypatch, gemini_key: str = "fake-key"):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    if gemini_key is None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    else:
        monkeypatch.setenv("GEMINI_API_KEY", gemini_key)
    return TestClient(create_app(Settings.from_env()))


def _login(c: TestClient) -> None:
    r = c.post("/login", data={"password": "s3cret"}, follow_redirects=False)
    assert r.status_code in (302, 303)


def test_generate_story_requires_auth(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.post("/api/generate-story").status_code == 401


def test_generate_story_missing_key(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch, gemini_key=None)
    _login(c)
    r = c.post("/api/generate-story")
    assert r.status_code == 503
    assert "GEMINI_API_KEY" in r.json()["detail"]


def test_generate_story_success(tmp_path, monkeypatch):
    async def fake_generate(api_key: str, prompt: str) -> str:
        assert api_key == "fake-key"
        assert "Custom" in prompt
        return "I joined a scary game.\nThen the lights went out."

    monkeypatch.setattr(
        "roblox_viral.web.app.generate_story",
        fake_generate,
    )
    c = _client(tmp_path, monkeypatch)
    _login(c)
    save_prompt(c.app.state.settings, "Custom prompt for tests.")
    r = c.post("/api/generate-story")
    assert r.status_code == 200
    assert r.json()["story"] == "I joined a scary game.\nThen the lights went out."


def test_generate_story_empty_prompt(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _login(c)
    # Write empty file bypassing save_prompt validation
    path = c.app.state.settings.prompt_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("   \n", encoding="utf-8")
    r = c.post("/api/generate-story")
    assert r.status_code == 400
