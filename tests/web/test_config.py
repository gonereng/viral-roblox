from pathlib import Path

from roblox_viral.web.config import Settings


def test_ensure_media_dirs(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    settings = Settings.from_env()
    settings.ensure_media_dirs()
    assert settings.sources_dir.is_dir()
    assert settings.outputs_dir.is_dir()
    assert settings.jobs_dir.is_dir()


def test_gemini_settings_and_prompt_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    settings = Settings.from_env()
    assert settings.gemini_api_key == "test-gemini-key"
    assert settings.prompt_path == settings.media_root / "prompt.txt"
