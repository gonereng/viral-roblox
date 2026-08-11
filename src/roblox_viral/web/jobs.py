from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

from roblox_viral.captions import write_ass
from roblox_viral.render import render_video
from roblox_viral.story import join_for_tts, split_sentences
from roblox_viral.voice import (
    DEFAULT_PITCH,
    DEFAULT_SPEED,
    EdgeTTSProvider,
    format_edge_pitch,
    format_edge_rate,
)
from roblox_viral.web.config import Settings
from roblox_viral.web.library import (
    make_output_name,
    resolve_source,
    slice_into_minute_parts,
)
from roblox_viral.web.youtube import (
    download_youtube,
    validate_stem,
    validate_youtube_url,
)

JobStatus = Literal[
    "queued",
    "synthesizing",
    "captioning",
    "rendering",
    "downloading",
    "slicing",
    "done",
    "error",
]

# uuid4().hex — reject path traversal / odd filenames
_SAFE_JOB_ID = re.compile(r"^[0-9a-f]{32}$")


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
    kind: str = "render"  # "render" | "youtube"
    pitch: int = DEFAULT_PITCH
    speed: int = DEFAULT_SPEED
    url: str | None = None
    stem: str | None = None
    created_slices: list[str] | None = None


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
    ) -> JobRecord:
        format_edge_pitch(pitch)
        format_edge_rate(speed)
        resolve_source(settings, source_name)
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

    def create_youtube(self, settings: Settings, url: str, stem: str) -> JobRecord:
        safe_url = validate_youtube_url(url)
        safe_stem = validate_stem(stem)

        with self._lock:
            if self._active_id is not None:
                raise BusyError("A job is already in progress")
            job_id = uuid.uuid4().hex
            record = JobRecord(
                id=job_id,
                status="queued",
                error=None,
                source_name="",
                voice="",
                output_name=None,
                created_at=datetime.now(timezone.utc).isoformat(),
                kind="youtube",
                url=safe_url,
                stem=safe_stem,
                created_slices=None,
            )
            self._jobs[job_id] = record
            self._active_id = job_id

        try:
            (settings.jobs_dir / job_id).mkdir(parents=True, exist_ok=True)
            self._persist(settings, record)
        except Exception:
            with self._lock:
                if self._active_id == job_id:
                    self._active_id = None
                self._jobs.pop(job_id, None)
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
                url=data.get("url"),
                stem=data.get("stem"),
                created_slices=data.get("created_slices"),
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

            video_path = resolve_source(settings, record.source_name)
            job_dir = settings.jobs_dir / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            narration_path = job_dir / "narration.mp3"
            ass_path = job_dir / "captions.ass"
            output_name = make_output_name(record.source_name)
            output_path = settings.outputs_dir / output_name

            self._set_status(settings, record, "synthesizing")
            words = EdgeTTSProvider(
                record.voice,
                rate=format_edge_rate(record.speed),
                pitch=format_edge_pitch(record.pitch),
            ).synthesize(join_for_tts(sentences), narration_path)

            self._set_status(settings, record, "captioning")
            write_ass(words, ass_path, sentences=sentences)

            self._set_status(settings, record, "rendering")
            render_video(
                video_path=video_path,
                audio_path=narration_path,
                ass_path=ass_path,
                output_path=output_path,
                work_dir=job_dir,
                overlay_path=settings.overlay_video_path,
            )

            record.output_name = output_name
            self._set_status(settings, record, "done")
        except Exception as exc:
            record.error = str(exc)
            self._set_status(settings, record, "error")
        finally:
            with self._lock:
                if self._active_id == job_id:
                    self._active_id = None

    def run_youtube_job(self, settings: Settings, job_id: str) -> None:
        record = self._jobs.get(job_id)
        if record is None:
            raise KeyError(f"Unknown job: {job_id}")
        job_dir = settings.jobs_dir / job_id
        download_path = job_dir / "download.mp4"
        try:
            self._set_status(settings, record, "downloading")
            download_youtube(
                record.url or "",
                download_path,
                cookies_path=settings.youtube_cookies_path,
            )

            self._set_status(settings, record, "slicing")
            slices = slice_into_minute_parts(
                settings, download_path, record.stem or "video"
            )
            record.created_slices = [s.name for s in slices]
            self._set_status(settings, record, "done")
        except Exception as exc:
            record.error = str(exc)
            self._set_status(settings, record, "error")
        finally:
            download_path.unlink(missing_ok=True)
            download_path.with_suffix("").unlink(missing_ok=True)
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
