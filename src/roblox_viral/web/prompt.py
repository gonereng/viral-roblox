from __future__ import annotations

from roblox_viral.web.config import Settings

DEFAULT_PROMPT = """Write a short Roblox horror storytime script for a vertical TikTok-style video.

Requirements:
- First-person narrator discovering something scary in a Roblox game
- 8 to 14 sentences
- Exactly one sentence per line
- No blank lines
- No title, preamble, or markdown — only the story lines
"""


def load_prompt(settings: Settings) -> str:
    path = settings.prompt_path
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_PROMPT, encoding="utf-8")
        return DEFAULT_PROMPT
    return path.read_text(encoding="utf-8").rstrip("\n")


def save_prompt(settings: Settings, text: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Prompt cannot be empty")
    path = settings.prompt_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cleaned + "\n", encoding="utf-8")
