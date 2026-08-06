"""CLI for Roblox viral storytime video generation."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from roblox_viral.captions import write_ass
from roblox_viral.render import RenderError, render_video, require_ffmpeg
from roblox_viral.story import join_for_tts, resolve_story_sentences
from roblox_viral.voice import EdgeTTSProvider
from roblox_viral.web.config import resolve_overlay_video_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="roblox-viral",
        description="Generate a vertical Roblox storytime video with TTS and karaoke captions.",
    )
    parser.add_argument("--video", required=True, type=Path, help="Path to Roblox gameplay video")
    story = parser.add_mutually_exclusive_group(required=True)
    story.add_argument(
        "--story",
        type=Path,
        help="Path to story text file (one sentence per line)",
    )
    story.add_argument(
        "--story-text",
        type=str,
        help="Story text inline (use newlines for one sentence per line)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("output.mp4"),
        help="Output MP4 path (default: output.mp4)",
    )
    parser.add_argument(
        "--voice",
        default="en-US-EmmaNeural",
        help="Edge TTS voice name (default: en-US-EmmaNeural)",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary narration/caption files for debugging",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        require_ffmpeg()
        if not args.video.is_file():
            raise FileNotFoundError(f"Video not found: {args.video}")

        sentences = resolve_story_sentences(
            story_path=args.story, story_text=args.story_text
        )
        text = join_for_tts(sentences)

        temp_dir = Path(tempfile.mkdtemp(prefix="roblox_viral_"))
        audio_path = temp_dir / "narration.mp3"
        ass_path = temp_dir / "captions.ass"

        try:
            print(f"Synthesizing voice ({args.voice})...")
            provider = EdgeTTSProvider(voice=args.voice)
            words = provider.synthesize(text, audio_path)
            if not words:
                raise RuntimeError("TTS produced no word timings; cannot build captions")

            print(
                f"Building karaoke captions ({len(words)} words, {len(sentences)} sentences)..."
            )
            write_ass(words, ass_path, sentences=sentences)

            print("Rendering 1080x1920 video with ffmpeg...")
            render_video(
                video_path=args.video,
                audio_path=audio_path,
                ass_path=ass_path,
                output_path=args.out,
                keep_temp=args.keep_temp,
                work_dir=temp_dir,
                overlay_path=resolve_overlay_video_path(),
            )
            print(f"Done: {args.out.resolve()}")
            return 0
        finally:
            if args.keep_temp:
                print(f"Temp files kept at: {temp_dir}")
            else:
                shutil.rmtree(temp_dir, ignore_errors=True)

    except (ValueError, FileNotFoundError, RenderError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
