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


def test_youtube_cookies_path_default_and_env(tmp_path: Path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("MEDIA_ROOT", str(media))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("YOUTUBE_COOKIES", raising=False)
    settings = Settings.from_env()
    assert settings.youtube_cookies_path is None

    cookies = media / "youtube_cookies.txt"
    cookies.write_text("# Netscape\n", encoding="utf-8")
    assert settings.youtube_cookies_path == cookies

    other = tmp_path / "other_cookies.txt"
    other.write_text("# Netscape\n", encoding="utf-8")
    monkeypatch.setenv("YOUTUBE_COOKIES", str(other))
    settings2 = Settings.from_env()
    assert settings2.youtube_cookies_path == other


def test_overlay_video_path_default_and_env(tmp_path: Path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("MEDIA_ROOT", str(media))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("OVERLAY_VIDEO", raising=False)
    settings = Settings.from_env()
    assert settings.overlay_video_path is None

    overlay = media / "overlay.mp4"
    overlay.write_bytes(b"fake")
    assert settings.overlay_video_path == overlay

    other = tmp_path / "other_overlay.mp4"
    other.write_bytes(b"fake")
    monkeypatch.setenv("OVERLAY_VIDEO", str(other))
    settings2 = Settings.from_env()
    assert settings2.overlay_video_path == other
