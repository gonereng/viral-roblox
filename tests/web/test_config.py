from pathlib import Path

from roblox_viral.web.config import Settings


def test_ensure_media_dirs(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    settings = Settings.from_env()
    settings.ensure_media_dirs()
    assert settings.sources_dir.is_dir()
    assert settings.images_dir.is_dir()
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


def test_overlay_video_path_default_and_env(tmp_path: Path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setenv("MEDIA_ROOT", str(media))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("OVERLAY_VIDEO", raising=False)
    settings = Settings.from_env()
    # Packaged asset may exist in the checkout; media override is tested below.
    packaged = settings.overlay_video_path
    assert packaged is None or packaged.name == "overlay.mp4"

    overlay = media / "overlay.mp4"
    overlay.write_bytes(b"fake")
    assert settings.overlay_video_path == overlay

    other = tmp_path / "other_overlay.mp4"
    other.write_bytes(b"fake")
    monkeypatch.setenv("OVERLAY_VIDEO", str(other))
    settings2 = Settings.from_env()
    assert settings2.overlay_video_path == other


def test_api_key_from_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("API_KEY", "n8n-secret")
    settings = Settings.from_env()
    assert settings.api_key == "n8n-secret"


def test_whisper_align_defaults(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("WHISPER_ALIGN_LANGUAGE", raising=False)
    monkeypatch.delenv("WHISPER_ALIGN_MODEL", raising=False)
    settings = Settings.from_env()
    assert settings.whisper_align_language == "de"
    assert settings.whisper_align_model == "base"


def test_whisper_align_from_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("WHISPER_ALIGN_LANGUAGE", "en")
    monkeypatch.setenv("WHISPER_ALIGN_MODEL", "small")
    settings = Settings.from_env()
    assert settings.whisper_align_language == "en"
    assert settings.whisper_align_model == "small"


def test_resolve_overlay_falls_back_to_packaged(tmp_path: Path, monkeypatch):
    from roblox_viral.web.config import resolve_overlay_video_path

    monkeypatch.delenv("OVERLAY_VIDEO", raising=False)
    media = tmp_path / "empty-media"
    media.mkdir()
    path = resolve_overlay_video_path(media_root=media, overlay_video="")
    assert path is not None
    assert path.is_file()
    assert path.name == "overlay.mp4"
