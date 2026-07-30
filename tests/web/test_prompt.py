from pathlib import Path

from roblox_viral.web.config import Settings
from roblox_viral.web.prompt import DEFAULT_PROMPT, load_prompt, save_prompt


def _settings(tmp_path: Path, monkeypatch) -> Settings:
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_PASSWORD", "secret")
    monkeypatch.setenv("APP_SECRET", "dev-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    s = Settings.from_env()
    s.ensure_media_dirs()
    return s


def test_load_prompt_seeds_default(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    assert not s.prompt_path.exists()
    text = load_prompt(s)
    assert text == DEFAULT_PROMPT
    assert s.prompt_path.read_text(encoding="utf-8") == DEFAULT_PROMPT


def test_save_and_load_prompt(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    save_prompt(s, "Custom prompt.\nWrite one sentence per line.")
    assert load_prompt(s) == "Custom prompt.\nWrite one sentence per line."


def test_save_prompt_rejects_empty(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch)
    try:
        save_prompt(s, "   \n  ")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "empty" in str(exc).lower()
