"""Gemini TTS provider with faster-whisper word alignment for karaoke."""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

import httpx

from roblox_viral.render import require_ffmpeg
from roblox_viral.voice import WordTiming

GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
DEFAULT_GEMINI_VOICE = "Kore"
DEFAULT_TTS_PROVIDER = "edge"

GEMINI_VOICES: tuple[str, ...] = (
    "Zephyr",
    "Puck",
    "Charon",
    "Kore",
    "Fenrir",
    "Leda",
    "Orus",
    "Aoede",
    "Callirrhoe",
    "Autonoe",
    "Enceladus",
    "Iapetus",
    "Umbriel",
    "Algieba",
    "Despina",
    "Erinome",
    "Algenib",
    "Rasalgethi",
    "Laomedeia",
    "Achernar",
    "Alnilam",
    "Schedar",
    "Gacrux",
    "Pulcherrima",
    "Achird",
    "Zubenelgenubi",
    "Vindemiatrix",
    "Sadachbia",
    "Sadaltager",
    "Sulafat",
)

_GEMINI_VOICES_LOWER = {v.lower(): v for v in GEMINI_VOICES}


def normalize_tts_provider(raw: str | None) -> str:
    value = (raw or DEFAULT_TTS_PROVIDER).strip().lower()
    if value not in ("edge", "gemini"):
        raise ValueError("tts_provider must be 'edge' or 'gemini'")
    return value


def validate_gemini_voice(name: str) -> str:
    key = (name or "").strip()
    if not key:
        raise ValueError("Gemini voice is required")
    canonical = _GEMINI_VOICES_LOWER.get(key.lower())
    if canonical is None:
        raise ValueError(f"Unknown Gemini voice: {name!r}")
    return canonical


def _pcm_to_mp3(pcm: bytes, *, sample_rate: int, output_mp3: Path) -> None:
    ffmpeg = require_ffmpeg()
    output_mp3.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "s16le",
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        "-i",
        "pipe:0",
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(output_mp3),
    ]
    try:
        subprocess.run(
            cmd,
            input=pcm,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or b"").decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"ffmpeg PCM→MP3 failed: {err}") from exc


def _parse_sample_rate(mime: str) -> int:
    # e.g. audio/L16;codec=pcm;rate=24000
    for part in mime.replace(" ", "").split(";"):
        if part.lower().startswith("rate="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                break
    return 24000


def align_words_with_whisper(audio_path: Path, text: str) -> list[WordTiming]:
    """Force-align narration audio to produce WordTiming via faster-whisper."""
    from faster_whisper import WhisperModel

    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        initial_prompt=text[:400],
        vad_filter=False,
    )
    words: list[WordTiming] = []
    for segment in segments:
        for word in segment.words or []:
            token = (word.word or "").strip()
            if not token:
                continue
            start_ms = max(0, int(round(word.start * 1000)))
            end_ms = max(start_ms + 1, int(round(word.end * 1000)))
            words.append(WordTiming(text=token, start_ms=start_ms, end_ms=end_ms))
    if not words:
        raise RuntimeError("Whisper alignment returned no words")
    for i in range(len(words) - 1):
        if words[i].end_ms < words[i + 1].start_ms:
            words[i] = WordTiming(
                text=words[i].text,
                start_ms=words[i].start_ms,
                end_ms=words[i + 1].start_ms,
            )
    return words


class GeminiTTSProvider:
    """Gemini TTS → MP3 + whisper word timings."""

    def __init__(
        self,
        api_key: str,
        voice: str = DEFAULT_GEMINI_VOICE,
        *,
        align_fn=None,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ValueError("GEMINI_API_KEY is not configured")
        self.api_key = key
        self.voice = validate_gemini_voice(voice)
        self._align_fn = align_fn or align_words_with_whisper

    def synthesize(self, text: str, output_path: Path | str) -> list[WordTiming]:
        script = (text or "").strip()
        if not script:
            raise ValueError("TTS text is empty")
        out = Path(output_path)
        pcm, sample_rate = self._generate_pcm(script)
        _pcm_to_mp3(pcm, sample_rate=sample_rate, output_mp3=out)
        return self._align_fn(out, script)

    def _generate_pcm(self, text: str) -> tuple[bytes, int]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_TTS_MODEL}:generateContent"
        )
        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": self.voice}
                    }
                },
            },
        }
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Gemini TTS request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text[:300]
            try:
                detail = response.json().get("error", {}).get("message", detail)
            except Exception:
                pass
            raise RuntimeError(
                f"Gemini TTS error ({response.status_code}): {detail}"
            )

        data = response.json()
        parts = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if not inline or not inline.get("data"):
                continue
            mime = inline.get("mimeType") or inline.get("mime_type") or ""
            raw = base64.b64decode(inline["data"])
            return raw, _parse_sample_rate(mime)
        raise RuntimeError(
            f"Gemini TTS returned no audio: {json.dumps(data)[:300]}"
        )
