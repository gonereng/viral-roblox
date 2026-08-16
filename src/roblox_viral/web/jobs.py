from __future__ import annotations

import json
import re
import shutil
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

from pathlib import Path

from roblox_viral.captions import write_ass
from roblox_viral.reddit_card import first_sentence_end_s, render_reddit_card
from roblox_viral.reddit_clips import plan_reddit_clips
from roblox_viral.render import (
    build_reddit_background,
    probe_duration_seconds,
    render_still,
    render_video,
)
from roblox_viral.story import join_for_tts, split_sentences
from roblox_viral.voice import (
    DEFAULT_PITCH,
    DEFAULT_SPEED,
    DEFAULT_VIDEO_SPEED,
    EdgeTTSProvider,
    format_edge_pitch,
    format_edge_rate,
    validate_video_speed,
)
from roblox_viral.web.config import Settings
from roblox_viral.web.library import (
    list_videos,
    make_output_name,
    resolve_image,
    resolve_source,
    validate_image_filename,
    validate_video_filename,
)

JobStatus = Literal[
    "queued",
    "synthesizing",
    "captioning",
    "rendering",
    "done",
    "error",
]

# uuid4().hex — reject path traversal / odd filenames
_SAFE_JOB_ID = re.compile(r"^[0-9a-f]{32}$")


def normalize_mode(mode: str) -> str:
    normalized = "single" if mode == "roblox" else mode
    if normalized not in ("single", "picture", "reddit"):
        raise ValueError(f"Invalid mode: {mode!r}")
    return normalized


class BusyError(Exception):
    """Raised when a job is already active (single-flight)."""


@dataclass
class JobRecord:
    id: str
    status: JobStatus
    error: str | None
    source_name: str
    voice: str
    output_name: str | None
    created_at: str
    kind: str = "render"
    pitch: int = DEFAULT_PITCH
    speed: int = DEFAULT_SPEED
    video_speed: int = DEFAULT_VIDEO_SPEED
    mode: str = "single"  # "single" | "picture" | "reddit"
    ken_burns: bool = False
    url: str | None = None
    stem: str | None = None
    created_slices: list[str] | None = None
    ephemeral: bool = False
    title_card_name: str | None = None


class JobManager:
    """In-memory job store with single-flight pipeline execution."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_id: str | None = None
        self._jobs: dict[str, JobRecord] = {}
        self._stories: dict[str, str] = {}

    def create(
        self,
        settings: Settings,
        source_name: str,
        story: str,
        voice: str,
        pitch: int = DEFAULT_PITCH,
        speed: int = DEFAULT_SPEED,
        video_speed: int = DEFAULT_VIDEO_SPEED,
        mode: str = "single",
        ken_burns: bool = False,
        ephemeral: bool = False,
    ) -> JobRecord:
        format_edge_pitch(pitch)
        format_edge_rate(speed)
        validate_video_speed(video_speed)
        mode = normalize_mode(mode)
        if mode == "reddit":
            if not list_videos(settings):
                raise ValueError("Reddit mode requires at least one video")
            source_name = source_name or "reddit"
            ken_burns = False
            ephemeral = False
        elif ephemeral:
            safe = Path(source_name).name
            if safe != source_name or not safe:
                raise ValueError("Invalid source_name")
            if mode == "picture":
                source_name = validate_image_filename(safe)
            else:
                source_name = validate_video_filename(safe)
                ken_burns = False
        elif mode == "picture":
            resolve_image(settings, source_name)
        else:
            resolve_source(settings, source_name)
            ken_burns = False
        sentences = split_sentences(story)
        if not sentences:
            raise ValueError("Story is empty")

        with self._lock:
            if self._active_id is not None:
                raise BusyError("A job is already in progress")
            job_id = uuid.uuid4().hex
            record = JobRecord(
                id=job_id,
                status="queued",
                error=None,
                source_name=source_name,
                voice=voice,
                output_name=None,
                created_at=datetime.now(timezone.utc).isoformat(),
                kind="render",
                pitch=pitch,
                speed=speed,
                video_speed=video_speed,
                mode=mode,
                ken_burns=ken_burns,
                ephemeral=ephemeral,
            )
            self._jobs[job_id] = record
            self._stories[job_id] = story
            self._active_id = job_id

        try:
            job_dir = settings.jobs_dir / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            self._persist(settings, record)
        except Exception:
            with self._lock:
                if self._active_id == job_id:
                    self._active_id = None
                self._jobs.pop(job_id, None)
                self._stories.pop(job_id, None)
            raise
        return record

    def get(self, job_id: str, settings: Settings | None = None) -> JobRecord | None:
        with self._lock:
            cached = self._jobs.get(job_id)
            if cached is not None:
                return cached

        if settings is None or not _SAFE_JOB_ID.fullmatch(job_id):
            return None

        jobs_root = settings.jobs_dir.resolve()
        status_path = (settings.jobs_dir / job_id / "status.json").resolve()
        if not status_path.is_relative_to(jobs_root) or not status_path.is_file():
            return None

        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
            record = JobRecord(
                id=str(data["id"]),
                status=data["status"],
                error=data.get("error"),
                source_name=str(data.get("source_name") or ""),
                voice=str(data.get("voice") or ""),
                output_name=data.get("output_name"),
                created_at=str(data["created_at"]),
                kind=str(data.get("kind") or "render"),
                pitch=int(data["pitch"]) if "pitch" in data else DEFAULT_PITCH,
                speed=int(data["speed"]) if "speed" in data else DEFAULT_SPEED,
                video_speed=int(data["video_speed"])
                if "video_speed" in data
                else DEFAULT_VIDEO_SPEED,
                mode=normalize_mode(str(data.get("mode") or "single")),
                ken_burns=bool(data.get("ken_burns", False)),
                url=data.get("url"),
                stem=data.get("stem"),
                created_slices=data.get("created_slices"),
                ephemeral=bool(data.get("ephemeral", False)),
                title_card_name=data.get("title_card_name"),
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

        if record.id != job_id or not _SAFE_JOB_ID.fullmatch(record.id):
            return None

        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is not None:
                return existing
            self._jobs[job_id] = record
            return record

    def run_job(self, settings: Settings, job_id: str) -> None:
        record = self._jobs.get(job_id)
        if record is None:
            raise KeyError(f"Unknown job: {job_id}")

        try:
            story = self._stories[job_id]
            sentences = split_sentences(story)
            if not sentences:
                raise ValueError("Story is empty")

            job_dir = settings.jobs_dir / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            narration_path = job_dir / "narration.mp3"
            ass_path = job_dir / "captions.ass"
            output_name = make_output_name(record.source_name or "reddit")
            output_path = settings.outputs_dir / output_name

            self._set_status(settings, record, "synthesizing")
            words = EdgeTTSProvider(
                record.voice,
                rate=format_edge_rate(record.speed),
                pitch=format_edge_pitch(record.pitch),
            ).synthesize(join_for_tts(sentences), narration_path)

            self._set_status(settings, record, "captioning")
            write_ass(words, ass_path, sentences=sentences)

            title_card_path: Path | None = None
            title_card_until_s: float | None = None
            if record.mode == "reddit":
                title_card_until_s = first_sentence_end_s(sentences, words)
                title_card_path = job_dir / "reddit_card.png"
                render_reddit_card(sentences[0], title_card_path)

            self._set_status(settings, record, "rendering")
            if record.ephemeral:
                media_path = (job_dir / record.source_name).resolve()
                if (
                    not media_path.is_relative_to(job_dir.resolve())
                    or not media_path.is_file()
                ):
                    raise FileNotFoundError(record.source_name)
            elif record.mode == "picture":
                media_path = resolve_image(settings, record.source_name)
            elif record.mode == "reddit":
                videos = [video.path for video in list_videos(settings)]
                durations = {
                    video_path: probe_duration_seconds(video_path)
                    for video_path in videos
                }
                narration_duration = probe_duration_seconds(narration_path)
                # setpts shortens wall-clock playback; plan enough source to cover audio
                plan_target = narration_duration * (record.video_speed / 100.0)
                segments = plan_reddit_clips(
                    videos,
                    plan_target,
                    durations=durations,
                )
                media_path = job_dir / "reddit_bg.mp4"
                build_reddit_background(
                    segments,
                    media_path,
                    work_dir=job_dir,
                )
            else:
                media_path = resolve_source(settings, record.source_name)

            if record.mode == "picture":
                render_still(
                    image_path=media_path,
                    audio_path=narration_path,
                    ass_path=ass_path,
                    output_path=output_path,
                    ken_burns=record.ken_burns,
                    work_dir=job_dir,
                )
            else:
                overlay_path = (
                    None if record.mode == "reddit" else settings.overlay_video_path
                )
                render_video(
                    video_path=media_path,
                    audio_path=narration_path,
                    ass_path=ass_path,
                    output_path=output_path,
                    work_dir=job_dir,
                    overlay_path=overlay_path,
                    title_card_path=title_card_path,
                    title_card_until_s=title_card_until_s,
                    video_speed=record.video_speed,
                )

            record.output_name = output_name
            if record.mode == "reddit" and title_card_path is not None:
                card_out_name = f"{Path(output_name).stem}-card.png"
                settings.outputs_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(title_card_path, settings.outputs_dir / card_out_name)
                record.title_card_name = card_out_name
            self._set_status(settings, record, "done")
        except Exception as exc:
            record.error = str(exc)
            self._set_status(settings, record, "error")
        finally:
            with self._lock:
                if self._active_id == job_id:
                    self._active_id = None

    def _set_status(
        self, settings: Settings, record: JobRecord, status: JobStatus
    ) -> None:
        record.status = status
        self._persist(settings, record)

    def _persist(self, settings: Settings, record: JobRecord) -> None:
        path = settings.jobs_dir / record.id / "status.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(record), indent=2), encoding="utf-8")
